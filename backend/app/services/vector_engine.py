"""
vector_engine.py - Motor vectorial CAD con aislamiento de vista (v7, validado).
"""
import fitz
import numpy as np
import cv2
import re
from typing import List, Tuple, Dict, Optional
from app.models.schemas import Wall, Door, Window, Room, Vector3, FloorPlanData


class VectorEngine:
    def __init__(self, min_wall_ft: float = 1.1, tol_merge_ft: float = 0.45,
                 bridge_gap_ft: float = 1.4, drop_note_boxes: bool = True,
                 table_fill_max: float = 0.12):
        self.min_wall_ft = min_wall_ft
        self.tol_merge_ft = tol_merge_ft
        self.bridge_gap_ft = bridge_gap_ft
        self.drop_note_boxes = drop_note_boxes
        self.table_fill_max = table_fill_max
        self.FT2M = 0.3048

    def process_pdf(self, pdf_path: str, config: Optional[dict] = None) -> FloorPlanData:
        doc = fitz.open(pdf_path)
        page = doc[0]
        H, V, labels = self._extract(page)
        cal = config or self._auto_calibrate(page, H, V, labels)
        H, V, labels = self._isolate_view(page, H, V, labels)
        H, V = self._drop_text_lines(H, V, labels)
        walls_ft = self._merge(H, cal, True) + self._merge(V, cal, False)
        walls_ft = self._envelope_filter(walls_ft)
        walls_ft = self._drop_fixture_walls(walls_ft)
        walls_ft = self._drop_cabinet_walls(walls_ft)
        walls, cx, cy = self._to_schema_walls(walls_ft, cal)
        rooms = self._detect_rooms(page, walls_ft, labels, cal, walls)
        return FloorPlanData(
            walls=walls, doors=[], windows=[], rooms=rooms,
            dimensions={
                "px_per_ft_x": cal["pxft_x"],
                "px_per_ft_y": cal["pxft_y"],
                "estimated_width_m": (cal["x1_ft"] - cal["x0_ft"]) * self.FT2M,
                "estimated_height_m": (cal["y1_ft"] - cal["y0_ft"]) * self.FT2M,
            },
        )

    def _extract(self, page) -> Tuple[list, list, list]:
        segs, labels = [], []
        for d in page.get_drawings():
            for it in d["items"]:
                if it[0] == "l":
                    segs.append((it[1].x, it[1].y, it[2].x, it[2].y))
                elif it[0] in ("re", "qu"):
                    q = it[1]
                    pts = [(q.x0, q.y0), (q.x1, q.y0), (q.x1, q.y1), (q.x0, q.y1)] \
                        if it[0] == "re" else \
                        [(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y)]
                    for i in range(4):
                        a, b = pts[i], pts[(i + 1) % 4]
                        segs.append((a[0], a[1], b[0], b[1]))
        for x0, y0, x1, y1, w, *_ in page.get_text("words"):
            labels.append((x0, y0, x1, y1, w))
        H, V = [], []
        pw, ph = page.rect.width, page.rect.height
        for sx1, sy1, sx2, sy2 in segs:
            mx, my = (sx1 + sx2) / 2, (sy1 + sy2) / 2
            if not (pw * 0.03 < mx < pw * 0.97 and ph * 0.03 < my < ph * 0.97):
                continue
            if abs(sy2 - sy1) < 0.6 and abs(sx2 - sx1) > 6:
                H.append(((sy1 + sy2) / 2, min(sx1, sx2), max(sx1, sx2), abs(sx2 - sx1)))
            elif abs(sx2 - sx1) < 0.6 and abs(sy2 - sy1) > 6:
                V.append(((sx1 + sx2) / 2, min(sy1, sy2), max(sy1, sy2), abs(sy2 - sy1)))
        return H, V, labels

    ROOM_WORDS = ["SUITE", "GREAT", "KITCHEN", "DINING", "FOYER", "ENTRY", "LANAI",
                  "BEDROOM", "BATH", "GARAGE", "LAUNDRY", "PANTRY", "W.I.C", "SHOWER", "CLOSET"]

    def _room_seeds(self, labels):
        seeds = []
        for x0, y0, x1, y1, w in labels:
            up = w.upper()
            if any(k in up for k in self.ROOM_WORDS) and 2 < len(w) < 18:
                seeds.append(((x0 + x1) / 2, (y0 + y1) / 2, up))
        return seeds

    def _isolate_view(self, page, H, V, labels):
        pw, ph = int(page.rect.width), int(page.rect.height)
        mask = np.zeros((ph, pw), np.uint8)
        for c, a0, a1, L in H:
            cv2.line(mask, (int(a0), int(c)), (int(a1), int(c)), 255, 1)
        for c, a0, a1, L in V:
            cv2.line(mask, (int(c), int(a0)), (int(c), int(a1)), 255, 1)
        dil = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (17, 17)))
        n, lbl = cv2.connectedComponents(dil)
        seeds = self._room_seeds(labels)
        if len(seeds) < 2:
            raise ValueError("No se encontro una vista de plano arquitectonico "
                             "(faltan etiquetas de cuartos). Sube la hoja del "
                             "FLOOR PLAN (A-2), no elevaciones ni estructural.")
        info = {}
        for cid in range(1, n):
            ys, xs = np.where(lbl == cid)
            if len(xs) == 0:
                continue
            x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
            area = (x1 - x0 + 1) * (y1 - y0 + 1)
            fill = float(np.count_nonzero(mask[ys, xs])) / max(area, 1)
            info[cid] = (x0, y0, x1, y1, fill)
        page_area = pw * ph
        votes = {}
        for sx, sy, _ in seeds:
            best_cid, best_area = None, -1
            for cid, (x0, y0, x1, y1, fill) in info.items():
                bx_area = (x1 - x0 + 1) * (y1 - y0 + 1)
                if bx_area > 0.7 * page_area:
                    continue
                if fill >= self.table_fill_max:
                    continue
                if x0 - 2 <= sx <= x1 + 2 and y0 - 2 <= sy <= y1 + 2 \
                        and bx_area > best_area:
                    best_cid, best_area = cid, bx_area
            if best_cid is not None:
                votes[best_cid] = votes.get(best_cid, 0) + 1
        if not votes:
            raise ValueError("Las etiquetas de cuarto caen solo en tablas/leyendas, "
                             "no en una vista de plano.")
        winner = max(votes, key=votes.get)
        if votes[winner] < 2:
            raise ValueError("Vista ambigua: menos de 2 etiquetas de cuarto asociadas.")
        x0, y0, x1, y1, _ = info[winner]
        if (x1 - x0) < 250 or (y1 - y0) < 250:
            raise ValueError("La vista detectada es demasiado pequena para ser un plano.")
        m = 30
        x0, y0, x1, y1 = x0 - m, y0 - m, x1 + m, y1 + m
        H2 = [h for h in H if x0 <= (h[1] + h[2]) / 2 <= x1 and y0 <= h[0] <= y1]
        V2 = [v for v in V if x0 <= v[0] <= x1 and y0 <= (v[1] + v[2]) / 2 <= y1]
        labels2 = [w for w in labels
                   if x0 <= (w[0] + w[2]) / 2 <= x1 and y0 <= (w[1] + w[3]) / 2 <= y1]
        if len(H2) + len(V2) < 30:
            raise ValueError("La vista aislada tiene muy pocos segmentos.")
        return H2, V2, labels2

    def _drop_text_lines(self, H, V, labels):
        boxes = [(x0 - 2, y0 - 2, x1 + 2, y1 + 2) for x0, y0, x1, y1, w in labels]

        def under_word_h(xa, y, xb):
            L = abs(xb - xa)
            for x0, y0, x1, y1 in boxes:
                wl = x1 - x0
                if abs(y - y1) < 2 and 0.75 * wl < L < 1.3 * wl \
                        and min(xb, x1) - max(xa, x0) > 0.6 * wl:
                    return True
            return False

        def under_word_v(x, ya, yb):
            L = abs(yb - ya)
            for x0, y0, x1, y1 in boxes:
                wl = y1 - y0
                if abs(x - x1) < 2 and 0.75 * wl < L < 1.3 * wl \
                        and min(yb, y1) - max(ya, y0) > 0.6 * wl:
                    return True
            return False

        H2 = [h for h in H if not under_word_h(h[1], h[0], h[2])]
        V2 = [v for v in V if not under_word_v(v[0], v[1], v[2])]
        return H2, V2

    DIM_RE = re.compile(r"(\d+)'[-\u2013]?(\d+)?\"?")

    def _auto_calibrate(self, page, H, V, labels=None) -> dict:
        if labels is None:
            labels = [(x0, y0, x1, y1, w) for x0, y0, x1, y1, w, *_ in page.get_text("words")]
        ests = []
        for x0, y0, x1, y1, w in labels:
            m = self.DIM_RE.search(w)
            if not m:
                continue
            ft = int(m.group(1)) + (int(m.group(2)) / 12 if m.group(2) else 0)
            if ft < 8:
                continue
            cx = (x0 + x1) / 2
            cy = (y0 + y1) / 2
            cands = [h for h in H
                     if h[1] - 6 <= cx <= h[2] + 6 and abs(h[0] - y1) < 14
                     and 4 < h[3] / ft < 60]
            if cands:
                line = max(cands, key=lambda h: h[3])
                ests.append(line[3] / ft)
            cands_v = [v for v in V
                       if v[1] - 6 <= cy <= v[2] + 6 and 0 < v[0] - x1 < 30
                       and 4 < v[3] / ft < 60]
            if cands_v:
                line = max(cands_v, key=lambda v: v[3])
                ests.append(line[3] / ft)
        if not ests:
            raise ValueError("No se pudo auto-calibrar: pasa config={pxft_x, pxft_y, x0, y0}")
        pxft_x = float(np.median(ests))
        pxft_y = pxft_x / 0.734
        xs = [v[0] for v in V] + [h[1] for h in H] + [h[2] for h in H]
        ys = [h[0] for h in H] + [v[1] for v in V] + [v[2] for v in V]
        x0_px, y1_px = min(xs), min(ys)
        return {"pxft_x": pxft_x, "pxft_y": pxft_y,
                "x0_px": x0_px, "y0_px": max(ys),
                "x0_ft": 0.0, "y0_ft": 0.0,
                "x1_ft": (max(xs) - x0_px) / pxft_x,
                "y1_ft": (max(ys) - y1_px) / pxft_y}

    def _merge(self, lines, cal, is_h):
        X0, Y0, SX, SY = cal["x0_px"], cal["y0_px"], cal["pxft_x"], cal["pxft_y"]
        items = []
        for c, a0, a1, L in lines:
            if is_h:
                cf, a, b = (Y0 - c) / SY, (a0 - X0) / SX, (a1 - X0) / SX
            else:
                cf, a, b = (c - X0) / SX, (Y0 - a1) / SY, (Y0 - a0) / SY
            a, b = min(a, b), max(a, b)
            if b - a >= self.min_wall_ft:
                items.append((cf, a, b))
        items.sort()
        merged, used = [], [False] * len(items)
        for i, (c, a, b) in enumerate(items):
            if used[i]:
                continue
            ca, cb, grp = a, b, [i]
            used[i] = True
            changed = True
            while changed:
                changed = False
                for j, (c2, a2, b2) in enumerate(items):
                    if used[j]:
                        continue
                    gap = max(a2 - cb, ca - b2, 0)
                    if abs(c2 - c) <= self.tol_merge_ft and gap <= self.bridge_gap_ft:
                        grp.append(j)
                        used[j] = True
                        ca, cb = min(ca, a2), max(cb, b2)
                        c = float(np.mean([items[g][0] for g in grp]))
                        changed = True
            merged.append({"o": "H" if is_h else "V", "c": c, "a": ca, "b": cb})
        if self.drop_note_boxes and merged:
            cs = [m["c"] for m in merged]
            lo, hi = np.percentile(cs, [2, 98])
            merged = [m for m in merged
                      if lo - 1.5 <= m["c"] <= hi + 1.5 or (m["b"] - m["a"]) > 6.0]
        return merged

    def _to_schema_walls(self, walls_ft, cal):
        allx = []
        ally = []
        for w in walls_ft:
            allx += [w["a"], w["b"]] if w["o"] == "H" else [w["c"], w["c"]]
            ally += [w["c"], w["c"]] if w["o"] == "H" else [w["a"], w["b"]]
        if walls_ft:
            px2, px98 = np.percentile(allx, [2, 98])
            py2, py98 = np.percentile(ally, [2, 98])
            mg = 0.8
            def in_env(w):
                wx = [w["a"], w["b"]] if w["o"] == "H" else [w["c"]]
                wy = [w["c"]] if w["o"] == "H" else [w["a"], w["b"]]
                return (min(wx) > px2 - mg and max(wx) < px98 + mg
                        and min(wy) > py2 - mg and max(wy) < py98 + mg)
            walls_ft = [w for w in walls_ft if in_env(w)]
        cx, cy = (min(allx) + max(allx)) / 2, (min(ally) + max(ally)) / 2
        out = []
        x0f, y0f, x1f, y1f = min(allx), min(ally), max(allx), max(ally)
        cal["x0_ft"], cal["y0_ft"], cal["x1_ft"], cal["y1_ft"] = x0f, y0f, x1f, y1f
        for w in walls_ft:
            ext = (w["o"] == "H" and (w["c"] < y0f + 1.2 or w["c"] > y1f - 1.2
                                      or w["a"] < x0f + 1.2 or w["b"] > x1f - 1.2)) or \
                  (w["o"] == "V" and (w["c"] < x0f + 1.2 or w["c"] > x1f - 1.2
                                      or w["a"] < y0f + 1.2 or w["b"] > y1f - 1.2))
            h = 16.0 if ext else 10.0
            t = 0.66 if ext else 0.45
            if w["o"] == "H":
                p1 = (w["a"], w["c"]); p2 = (w["b"], w["c"])
            else:
                p1 = (w["c"], w["a"]); p2 = (w["c"], w["b"])
            out.append(Wall(
                start=Vector3(x=(p1[0] - cx) * self.FT2M, y=0, z=-(p1[1] - cy) * self.FT2M),
                end=Vector3(x=(p2[0] - cx) * self.FT2M, y=0, z=-(p2[1] - cy) * self.FT2M),
                height=h * self.FT2M,
                thickness=t * self.FT2M,
            ))
        return out, cx, cy

    CLG_RE = re.compile(r"(\d+)'(\d+)?")

    def _detect_rooms(self, page, walls_ft, labels, cal, schema_walls):
        X0, Y0, SX, SY = cal["x0_px"], cal["y0_px"], cal["pxft_x"], cal["pxft_y"]
        xs, ys = [], []
        for w in walls_ft:
            xs += [w["a"], w["b"]] if w["o"] == "H" else [w["c"], w["c"]]
            ys += [w["c"], w["c"]] if w["o"] == "H" else [w["a"], w["b"]]
        x0f, x1f, y0f, y1f = min(xs), max(xs), min(ys), max(ys)
        res = 0.15
        W = int((x1f - x0f) / res) + 40
        Hh = int((y1f - y0f) / res) + 40
        mask = np.zeros((Hh, W), np.uint8)

        def to_px(fx, fy):
            return int((fx - x0f) / res) + 20, int((fy - y0f) / res) + 20

        for w in walls_ft:
            if w["o"] == "H":
                p1, p2 = to_px(w["a"], w["c"]), to_px(w["b"], w["c"])
            else:
                p1, p2 = to_px(w["c"], w["a"]), to_px(w["c"], w["b"])
            cv2.line(mask, p1, p2, 255, 5)
        mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15)))

        seeds = []
        for x0, y0, x1, y1, w in labels:
            up = w.upper()
            if any(k in up for k in self.ROOM_WORDS) and 2 < len(w) < 18:
                fx = ((x0 + x1) / 2 - X0) / SX
                fy = (Y0 - (y0 + y1) / 2) / SY
                seeds.append((w, fx, fy, up))
        seeds.sort(key=lambda s: -s[1])

        rooms, taken = [], np.zeros((Hh, W), np.uint8)
        for name, fx, fy, up in seeds:
            sx, sy = to_px(fx, fy)
            if not (0 <= sx < W and 0 <= sy < Hh):
                continue
            if fx < x0f - 1 or fx > x1f + 1 or fy < y0f - 1 or fy > y1f + 1:
                continue
            if mask[sy, sx] == 255:
                ok = False
                for rr in range(2, 30):
                    yy0, yy1 = max(0, sy - rr), min(Hh, sy + rr + 1)
                    xx0, xx1 = max(0, sx - rr), min(W, sx + rr + 1)
                    zy, zx = np.where(mask[yy0:yy1, xx0:xx1] == 0)
                    if len(zy):
                        k = np.argmin((zy - (sy - yy0)) ** 2 + (zx - (sx - xx0)) ** 2)
                        sx, sy = xx0 + int(zx[k]), yy0 + int(zy[k])
                        ok = True
                        break
                if not ok:
                    continue
            region = np.zeros((Hh + 2, W + 2), np.uint8)
            ff = mask.copy()
            cv2.floodFill(ff, region, (sx, sy), 128)
            zone = ((ff == 128) & (taken == 0)).astype(np.uint8) * 255
            if zone.sum() < 200:
                continue
            cnts, _ = cv2.findContours(zone, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not cnts:
                continue
            cnt = max(cnts, key=cv2.contourArea)
            eps = 0.01 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, eps, True)
            cxm, cym = (x0f + x1f) / 2, (y0f + y1f) / 2
            points = [Vector3(x=(p[0][0] * res + x0f - cxm) * self.FT2M, y=0,
                              z=-(p[0][1] * res + y0f - cym) * self.FT2M) for p in approx]
            clg = 10.0
            m = self.CLG_RE.search(up)
            if m:
                clg = int(m.group(1)) + (int(m.group(2)) / 12 if m.group(2) else 0)
            area = cv2.contourArea(cnt) * res * res * self.FT2M ** 2
            if area < 0.5 or area > 140.0:
                continue
            taken[zone > 0] = 1
            rooms.append(Room(name=name.replace("_", " ").title(),
                              points=points, area_sqm=round(area, 2),
                              ceiling_height=round(clg * self.FT2M, 2)))
        return rooms

    def _envelope_filter(self, walls_ft):
        if not walls_ft:
            return walls_ft
        allx, ally = [], []
        for w in walls_ft:
            allx += [w["a"], w["b"]] if w["o"] == "H" else [w["c"], w["c"]]
            ally += [w["c"], w["c"]] if w["o"] == "H" else [w["a"], w["b"]]
        px2, px98 = np.percentile(allx, [2, 98])
        py2, py98 = np.percentile(ally, [2, 98])
        mg = 0.8
        def in_env(w):
            wx = [w["a"], w["b"]] if w["o"] == "H" else [w["c"]]
            wy = [w["c"]] if w["o"] == "H" else [w["a"], w["b"]]
            return (min(wx) > px2 - mg and max(wx) < px98 + mg
                    and min(wy) > py2 - mg and max(wy) < py98 + mg)
        return [w for w in walls_ft if in_env(w)]

    def _drop_fixture_walls(self, walls_ft, touch_tol_ft=0.8, big_wall_ft=8.0):
        import math
        def endpoints(w):
            if w["o"] == "H":
                return (w["a"], w["c"]), (w["b"], w["c"])
            return (w["c"], w["a"]), (w["c"], w["b"])

        def seg_seg_dist(a1, a2, b1, b2):
            def pt_seg(p, a, b):
                dx, dy = b[0]-a[0], b[1]-a[1]
                l2 = dx*dx + dy*dy
                if l2 == 0:
                    return math.hypot(p[0]-a[0], p[1]-a[1])
                t = max(0.0, min(1.0, ((p[0]-a[0])*dx + (p[1]-a[1])*dy)/l2))
                return math.hypot(p[0]-a[0]-t*dx, p[1]-a[1]-t*dy)
            return min(pt_seg(a1, b1, b2), pt_seg(a2, b1, b2),
                       pt_seg(b1, a1, a2), pt_seg(b2, a1, a2))

        eps = [endpoints(w) for w in walls_ft]
        lens = [math.hypot(e[1][0]-e[0][0], e[1][1]-e[0][1]) for e in eps]
        n = len(walls_ft)
        parent = list(range(n))
        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        for i in range(n):
            for j in range(i+1, n):
                if seg_seg_dist(eps[i][0], eps[i][1], eps[j][0], eps[j][1]) < touch_tol_ft:
                    ri, rj = find(i), find(j)
                    if ri != rj:
                        parent[ri] = rj
        comp_len = {}
        for i in range(n):
            r = find(i)
            comp_len[r] = comp_len.get(r, 0.0) + lens[i]
        main = max(comp_len, key=comp_len.get)
        return [w for i, w in enumerate(walls_ft)
                if find(i) == main or lens[i] >= big_wall_ft]

    def _drop_cabinet_walls(self, walls_ft, gap_max_ft=1.4, cover_min=0.8):
        drop = set()
        for i, w in enumerate(walls_ft):
            if i in drop:
                continue
            for j, v in enumerate(walls_ft):
                if i == j or j in drop:
                    continue
                if w["o"] != v["o"]:
                    continue
                lw = w["b"] - w["a"]
                lv = v["b"] - v["a"]
                if lw <= 0 or lv <= 0:
                    continue
                if abs(w["c"] - v["c"]) > gap_max_ft:
                    continue
                lo, hi = max(w["a"], v["a"]), min(w["b"], v["b"])
                cover = (hi - lo) / min(lw, lv) if hi > lo else 0.0
                if cover < cover_min:
                    continue
                if lw < lv:
                    drop.add(i)
                    break
                elif lv < lw:
                    drop.add(j)
        return [w for i, w in enumerate(walls_ft) if i not in drop]
