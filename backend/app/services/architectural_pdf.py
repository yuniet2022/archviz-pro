"""CAD PDF reconstruction from wall faces, hatch support and opening symbols.

All coordinates remain in PDF points until the final, isotropic metric transform.
The original vector engine is used only to locate the architectural view.
"""
from collections import defaultdict
from dataclasses import dataclass
import math
import re

import cv2
import fitz
import numpy as np
from shapely.geometry import Polygon, Point

from app.models.schemas import Column, Door, FloorPlanData, Room, Vector3, Wall, Window
from app.services.vector_engine import VectorEngine

FT = .3048
DIM = re.compile(r"^(\d+)'\s*[-–]?\s*(\d+(?:\s+\d+/\d+)?)?\s*\"?$")
CLG = re.compile(r"(\d+)'\s*[-–]?\s*(\d+)?\s*\"?\s*(?:COFFER\s+)?CLG", re.I)
ROOM = re.compile(r'^(?:MASTER SUITE|GREAT ROOM|KITCHEN|DINING|FOYER|ENTRY|LANAI|BEDROOM\s*#?\s*\d*|(?:1/2\s+)?BATH|M/BATH|GARAGE|LAUNDRY|PANTRY|W\.?I\.?C\.?|CLOSET)$', re.I)
COL = re.compile(r'(\d+)\s*[X×]\s*(\d+)\s*(?:BLOCK\s+)?COL', re.I)


@dataclass
class Axis:
    o: str
    c: float
    a: float
    b: float
    t: float = 0


def axis(a, b, tolerance=.3):
    if abs(a.y-b.y) < tolerance and abs(a.x-b.x) > .5:
        return Axis('H', (a.y+b.y)/2, min(a.x,b.x), max(a.x,b.x))
    if abs(a.x-b.x) < tolerance and abs(a.y-b.y) > .5:
        return Axis('V', (a.x+b.x)/2, min(a.y,b.y), max(a.y,b.y))


def drawing_lines(drawing):
    for item in drawing['items']:
        if item[0] == 'l':
            yield item[1], item[2]
        elif item[0] in ('qu', 're'):
            q = item[1]
            points = [q.ul,q.ur,q.lr,q.ll] if item[0]=='qu' else [q.top_left,q.top_right,q.bottom_right,q.bottom_left]
            for i in range(4):
                yield points[i], points[(i+1)%4]


def merge_axes(lines, gap=.5, tolerance=.25):
    groups=[]
    for line in sorted(lines,key=lambda s:(s.o,s.c,s.a)):
        if groups and line.o==groups[-1][0].o and abs(line.c-groups[-1][0].c)<=tolerance:
            groups[-1].append(line)
        else:
            groups.append([line])
    result=[]
    for group in groups:
        c=float(np.median([s.c for s in group])); merged=[]
        for s in sorted(group,key=lambda s:s.a):
            if merged and s.a<=merged[-1].b+gap:
                merged[-1].b=max(merged[-1].b,s.b)
            else:
                merged.append(Axis(s.o,c,s.a,s.b,s.t))
        result.extend(merged)
    return result


def text_lines(page):
    return [(fitz.Rect(line['bbox']), ' '.join(s['text'] for s in line['spans']).strip(), line['dir'])
            for block in page.get_text('dict')['blocks'] for line in block.get('lines',[])]


def feet(text):
    m=DIM.match(text.strip())
    if not m:return None
    inches=0
    for part in (m.group(2) or '').split():
        if '/' in part:
            a,b=part.split('/');inches+=float(a)/float(b)
        else:inches+=float(part)
    return int(m.group(1))+inches/12


def calibration(lines, labels):
    """Match dimension baselines and their witness lines; reject ceiling notes."""
    candidates=[]
    for rect,text,direction in labels:
        length=feet(text)
        if not length or length<8:continue
        horizontal=abs(direction[0])>.9
        cx,cy=(rect.x0+rect.x1)/2,(rect.y0+rect.y1)/2
        found=[]
        for s in lines:
            if s.o!=('H' if horizontal else 'V'):continue
            center=cx if horizontal else cy
            distance=abs(s.c-(rect.y1 if horizontal else rect.x1))
            if distance>max(3,rect.height*.35 if horizontal else rect.width*.35):continue
            if not s.a<center<s.b:continue
            if not 2<(s.b-s.a)/length<100:continue
            # Dimension baselines commonly extend beyond the witness intersections.
            ends=[]
            for target in (s.a,s.b):
                witnesses=[w.c for w in lines if w.o!=s.o and w.a-.3<=s.c<=w.b+.3
                           and abs(w.c-target)<min(10,(s.b-s.a)*.03)]
                ends.append(min(witnesses,key=lambda c:abs(c-target)) if witnesses else target)
            span=abs(ends[1]-ends[0]);found.append((distance,span/length,length))
        if found:
            distance,ratio,length=min(found,key=lambda x:x[0]);candidates.append((ratio,length))
    if not candidates:
        raise ValueError('No se encontró una cota vectorial fiable para calibrar. Usa DXF con unidades o indica la escala del PDF.')
    # Prefer long dimensions: small arrow extensions have less relative influence.
    long=[ratio for ratio,length in candidates if length>=20] or [r for r,_ in candidates]
    center=float(np.median(long));inliers=[r for r in long if abs(r-center)<center*.06]
    return float(np.median(inliers or long))


def door_size(code):
    match=re.fullmatch(r'(?:(\d+)-)?(\d+)(\d)(\d)(\d)',code.strip())
    if not match:return None
    count,wf,wi,hf,hi=(int(x or 1) for x in match.groups())
    return (wf+wi/12)*FT*count,(hf+hi/12)*FT


def schedules(labels):
    result={'door':{},'window':{}}
    for box,title,_ in labels:
        kind='door' if title=='DOOR SCHEDULE' else 'window' if title=='WINDOW SCHEDULE' else None
        if not kind:continue
        rows=[(r,t) for r,t,_ in labels if box.y1<r.y0<box.y1+250 and box.x0-200<r.x0<box.x1+200]
        for r,text in rows:
            if not re.fullmatch(r'[1-9]' if kind=='door' else r'[A-Z]',text):continue
            sizes=[]
            for sr,st in rows:
                if not 10<sr.x0-r.x1<180 or abs((sr.y0+sr.y1-r.y0-r.y1)/2)>12:continue
                value=door_size(st) if kind=='door' else None
                if kind=='window' and (m:=re.fullmatch(r'(\d+)"\s*[Xx]\s*(\d+)"',st.strip())):
                    value=(int(m.group(1))*.0254,int(m.group(2))*.0254)
                if value:sizes.append((abs(sr.y0-r.y0),value,st))
            if sizes:
                _,value,st=min(sizes)
                row_text=' '.join(t for rr,t in rows if rr.x0>r.x1 and abs((rr.y0+rr.y1-r.y0-r.y1)/2)<16)
                operation='overhead' if 'O.H.D.' in row_text else 'sliding' if 'SLIDER' in row_text else 'double_hinged' if st.startswith('2-') else 'hinged'
                transom=re.search(r'WITH\s+(\d+)"\s*[Xx]\s*(\d+)"',row_text)
                result[kind][text]={'width':value[0],'height':value[1],'text':st,'operation':operation,
                    'transom':(int(transom.group(1))*.0254,int(transom.group(2))*.0254) if transom else None}
    return result


class ArchitecturalPDFEngine:
    def process_pdf(self,path):
        with fitz.open(path) as doc:
            page=doc[0];drawings=page.get_drawings();labels=text_lines(page)
            tables=schedules(labels)
            self.tables=tables
            self.door_notes=[(r,t,size) for r,t,_ in labels
                             if (match:=re.search(r'(?<!\d)(\d{4,5})\s*(?:DR\.?|DOOR)',t,re.I))
                             and (size:=door_size(match.group(1)))]
            all_axes=[s for d in drawings for a,b in drawing_lines(d) if (s:=axis(a,b))]
            scale=calibration(all_axes,labels)
            legacy=VectorEngine();h,v,words=legacy._extract(page)
            h,v,_=legacy._isolate_view(page,h,v,words)
            broad=fitz.Rect(min(s[0] for s in v),min(s[0] for s in h),max(s[0] for s in v),max(s[0] for s in h))
            self.scale=scale
            # Repeated diagonal hatch is construction evidence, unlike fixture outlines.
            styles=defaultdict(list)
            for d in drawings:
                if d.get('fill') is not None:continue
                for a,b in drawing_lines(d):
                    dx,dy=abs(a.x-b.x),abs(a.y-b.y);length=math.hypot(dx,dy)
                    if (broad.contains(a) and broad.contains(b) and min(dx,dy)>.3
                        and abs(dx-dy)<.12*max(dx,dy) and scale*.05<length<scale*1.5):
                        styles[(d.get('layer',''),d.get('color'))].append((a,b))
            supported=[items for items in styles.values() if len(items)>=30]
            strongest=max((sum(abs(b.x-a.x) for a,b in items) for items in supported),default=0)
            self.hatches=[pair for items in supported if sum(abs(b.x-a.x) for a,b in items)>=strongest*.04 for pair in items]
            if self.hatches:
                pts=[p for pair in self.hatches for p in pair]
                self.box=fitz.Rect(min(p.x for p in pts)-2,min(p.y for p in pts)-2,max(p.x for p in pts)+2,max(p.y for p in pts)+2)
                self.pixel_scale=min(2,math.sqrt(6_000_000/max(1,self.box.width*self.box.height)))
                self._hatch_image()
            else:
                self.box=fitz.Rect(broad.x0-1,broad.y0-1,broad.x1+1,broad.y1+1);self.hatch_mask=None
            labels=[l for l in labels if broad.contains(fitz.Point((l[0].x0+l[0].x1)/2,(l[0].y0+l[0].y1)/2))]
            raw=[]
            for d in drawings:
                color=d.get('color')
                if color is None or max(color)>.4:continue
                for a,b in drawing_lines(d):
                    if self.box.contains(a) and self.box.contains(b) and (s:=axis(a,b)):
                        raw.append(s)
            faces=merge_axes(raw,gap=.5)
            solids=self._wall_faces(faces)
            if not solids:
                raise ValueError('No se reconocieron pares de caras de muro. Usa una planta vectorial con muros delimitados o DXF por capas.')
            columns=self._columns(drawings,labels)
            solids=[s for s in self._snap(solids) if (s.b-s.a)/scale*FT>=.05]
            walls_px,openings,boundaries=self._join_openings(solids,raw,drawings,labels)
            # Footprints and room regions include symbolic closures, never an enclosing rectangle.
            boundaries.extend(self._end_closures(walls_px,columns))
            self._opening_headers(walls_px,openings,boundaries,raw,labels)
            regions,footprints=self._regions(walls_px,boundaries,columns,labels)
            xs=[s.c if s.o=='V' else x for s in walls_px for x in (s.a,s.b)]
            ys=[s.c if s.o=='H' else y for s in walls_px for y in (s.a,s.b)]
            self.center=((min(xs)+max(xs))/2,(min(ys)+max(ys))/2)
            ceiling=[(r,t,float(m.group(1))+float(m.group(2) or 0)/12) for r,t,_ in labels if (m:=CLG.search(t))]
            walls=[]
            for s in walls_px:
                mid=fitz.Point((s.a+s.b)/2,s.c) if s.o=='H' else fitz.Point(s.c,(s.a+s.b)/2)
                note=min(ceiling,key=lambda n:math.hypot((n[0].x0+n[0].x1)/2-mid.x,(n[0].y0+n[0].y1)/2-mid.y)) if ceiling else None
                height=note[2]*FT if note else 2.8
                a,b=((s.a,s.c),(s.b,s.c)) if s.o=='H' else ((s.c,s.a),(s.c,s.b))
                walls.append(Wall(start=self.metric(*a),end=self.metric(*b),thickness=s.t/scale*FT,height=height,
                    source={'kind':'pdf_wall_faces','pdf_points':[list(a),list(b)],'thickness_points':s.t},
                    height_source={'kind':'nearby_ceiling_note','text':note[1],'requires_confirmation':True} if note else {'kind':'default','requires_confirmation':True}))
            doors,windows=[],[]
            for idx,kind,lo,hi,details in openings:
                wall=walls[idx];span=walls_px[idx].b-walls_px[idx].a
                kwargs={'wall_id':wall.id,'position':((lo+hi)/2-walls_px[idx].a)/span,'width':(hi-lo)/scale*FT,
                        'source':{'kind':details,'pdf_interval':[lo,hi]}}
                source_axis=walls_px[idx]
                center=((lo+hi)/2,source_axis.c) if source_axis.o=='H' else (source_axis.c,(lo+hi)/2)
                markers=[]
                for rect,text,_ in labels:
                    if text not in tables[kind]:continue
                    distance=math.hypot((rect.x0+rect.x1)/2-center[0],(rect.y0+rect.y1)/2-center[1])
                    if distance<scale*2:markers.append((distance,text,tables[kind][text]))
                scheduled=min(markers) if markers else None
                if scheduled:
                    _,tag,size=scheduled;kwargs['schedule_tag']=tag;kwargs['nominal_width']=size['width']
                    kwargs['height_source']={'kind':'schedule','text':size['text']}
                if kind=='door':
                    height=scheduled[2]['height'] if scheduled else 2.4384
                    operation=scheduled[2]['operation'] if scheduled else 'hinged'
                    if not scheduled and any('BI-FOLD' in text.upper() and math.hypot((r.x0+r.x1)/2-center[0],(r.y0+r.y1)/2-center[1])<scale*2 for r,text,_ in labels):operation='bifold'
                    door=Door(**kwargs,height=min(height,wall.height),operation=operation);doors.append(door)
                    transom=scheduled[2]['transom'] if scheduled else None
                    if transom and wall.height>=door.height+transom[1]:
                        windows.append(Window(wall_id=wall.id,position=kwargs['position'],width=min(kwargs['width'],transom[0]),height=transom[1],sill_height=door.height,
                            transom_of=door.id,height_source={'kind':'door_schedule_transom','text':scheduled[2]['text']}))
                else:
                    height=scheduled[2]['height'] if scheduled else 1.524
                    sill=max(0,2.4384-height)
                    windows.append(Window(**kwargs,height=min(height,wall.height-sill),sill_height=sill,
                        sill_source='proposed_8ft_head_requires_confirmation'))
            room_models=[]
            for poly,names in regions:
                name=' / '.join(t for _,t,_ in names)
                r,t,_=names[0];cx,cy=(r.x0+r.x1)/2,(r.y0+r.y1)/2
                nearby=[n for n in ceiling if n[0].y0>=r.y0 and n[0].y0-r.y1<scale*2 and abs((n[0].x0+n[0].x1)/2-cx)<scale*4]
                note=min(nearby,key=lambda n:math.hypot((n[0].x0+n[0].x1)/2-cx,(n[0].y0+n[0].y1)/2-cy)) if nearby else None
                zones=[{'height':n[2]*FT,'text':n[1],'position':self.metric((n[0].x0+n[0].x1)/2,(n[0].y0+n[0].y1)/2).model_dump()} for n in ceiling
                       if poly.covers(Point((n[0].x0+n[0].x1)/2,(n[0].y0+n[0].y1)/2))]
                room_models.append(Room(name=name.title(),points=[self.metric(x,y) for x,y in poly.exterior.coords[:-1]],
                    area_sqm=round(poly.area*(FT/scale)**2,3),ceiling_height=note[2]*FT if note else 2.8,
                    ceiling_notes=zones,
                    source_labels=[{'text':t,'pdf_bbox':list(r)} for r,t,_ in names]))
            column_models=[]
            for rect,width,depth,text in columns:
                c=((rect.x0+rect.x1)/2,(rect.y0+rect.y1)/2)
                note=min(ceiling,key=lambda n:math.hypot((n[0].x0+n[0].x1)/2-c[0],(n[0].y0+n[0].y1)/2-c[1])) if ceiling else None
                column_models.append(Column(position=self.metric(*c),width=width*.0254,depth=depth*.0254,height=note[2]*FT if note else 2.8,
                    source={'kind':'column_callout','text':text,'pdf_bbox':list(rect)}))
            footprint=[{'points':[self.metric(x,y).model_dump() for x,y in p.exterior.coords[:-1]],
                        'holes':[[self.metric(x,y).model_dump() for x,y in ring.coords[:-1]] for ring in p.interiors]} for p in footprints]
            minx=min(s.c-s.t/2 if s.o=='V' else s.a for s in walls_px)
            maxx=max(s.c+s.t/2 if s.o=='V' else s.b for s in walls_px)
            miny=min(s.c-s.t/2 if s.o=='H' else s.a for s in walls_px)
            maxy=max(s.c+s.t/2 if s.o=='H' else s.b for s in walls_px)
            return FloorPlanData(walls=walls,doors=doors,windows=windows,columns=column_models,rooms=room_models,
                floor_regions=footprint,dimensions={'px_per_ft_x':scale,'px_per_ft_y':scale,
                    'estimated_width_m':(maxx-minx)/scale*FT,'estimated_height_m':(maxy-miny)/scale*FT},
                source_transform={'format':'pdf','origin_pdf_points':list(self.center),'points_per_foot':scale,'units':'m','up_axis':'Y'},
                warnings=['Muros obtenidos de caras y tramas; revisa las uniones contra el original.',
                    'Alturas de muro propuestas desde notas de techo cercanas; no equivalen a cotas estructurales de alzado.',
                    'Alturas y antepechos de huecos pendientes de confirmar con cuadros y alzados.'])

    def metric(self,x,y):
        return Vector3(x=(x-self.center[0])/self.scale*FT,z=(y-self.center[1])/self.scale*FT)

    def _hatch_image(self):
        self.hatch_mask=np.zeros((int(self.box.height*self.pixel_scale)+4,int(self.box.width*self.pixel_scale)+4),np.uint8)
        for a,b in self.hatches:
            cv2.line(self.hatch_mask,self._pixel(a.x,a.y),self._pixel(b.x,b.y),255,2)
        self.hatch_mask=cv2.dilate(self.hatch_mask,np.ones((5,5),np.uint8))

    def _pixel(self,x,y):return (int(round((x-self.box.x0)*self.pixel_scale)),int(round((y-self.box.y0)*self.pixel_scale)))

    def _support(self,o,c,a,b):
        positions=np.linspace(a,b,max(3,int((b-a)*2)))
        if self.hatch_mask is None:return positions,np.ones(len(positions),bool)
        points=[self._pixel(v,c) if o=='H' else self._pixel(c,v) for v in positions]
        h,w=self.hatch_mask.shape
        support=np.array([0<=x<w and 0<=y<h and self.hatch_mask[y,x]>0 for x,y in points])
        return positions,support

    def _wall_faces(self,faces):
        candidates=[]
        for i,s in enumerate(faces):
            for t in faces[i+1:]:
                if s.o!=t.o:continue
                thickness=t.c-s.c
                if not self.scale*.22<=thickness<=self.scale*1.1:continue
                a,b=max(s.a,t.a),min(s.b,t.b)
                if b-a<self.scale*.35:
                    # Small jamb stubs still support narrow linen/closet doors.
                    midpoint=((a+b)/2,(s.c+t.c)/2) if s.o=='H' else ((s.c+t.c)/2,(a+b)/2)
                    near_note=any(math.hypot((r.x0+r.x1)/2-midpoint[0],(r.y0+r.y1)/2-midpoint[1])<self.scale*2
                                  for r,_,_ in self.door_notes)
                    if b-a<self.scale*.15 or not near_note:continue
                c=(s.c+t.c)/2;positions,support=self._support(s.o,c,a,b)
                for offset in (-.32,.32):
                    _,side=self._support(s.o,c+thickness*offset,a,b)
                    support &= side
                if self.hatch_mask is None and b-a<thickness*4:continue
                # Split at unhatched openings; do not fill windows with solid walls.
                if support.mean()>.65 and support.any():
                    first,last=np.flatnonzero(support)[[0,-1]]
                    if positions[first]-a<self.scale*3 and not self._annotated_door(s.o,c,a,positions[first]):support[:first]=True
                    if b-positions[last]<self.scale*3 and not self._annotated_door(s.o,c,positions[last],b):support[last:]=True
                support=cv2.morphologyEx(support.astype(np.uint8)[None,:],cv2.MORPH_CLOSE,np.ones((1,max(3,int(self.scale*.3))),np.uint8)).ravel().astype(bool)
                run=None
                for index,covered in enumerate([*support,False]):
                    if covered and run is None:run=index
                    if not covered and run is not None:
                        lo,hi=positions[run],positions[index-1]
                        if lo-a<thickness*1.5:lo=a
                        if b-hi<thickness*1.5:hi=b
                        if hi-lo>=self.scale*.12:candidates.append(Axis(s.o,c,float(lo),float(hi),thickness))
                        run=None
        # Remove alternative face pairings of the same strip.
        kept=[]
        for s in sorted(candidates,key=lambda w:(-w.b+w.a,w.t)):
            overlap=False
            for k in kept:
                common=min(k.b,s.b)-max(k.a,s.a)
                if k.o==s.o and abs(k.c-s.c)<min(k.t,s.t)*.6 and common>min(k.b-k.a,s.b-s.a)*.9:
                    overlap=True;break
            if not overlap:kept.append(s)
        return self._merge_solids(kept)

    def _annotated_door(self,orientation,c,a,b):
        """Do not extend hatch over an unhatched gap supported by a door note."""
        cx,cy=((a+b)/2,c) if orientation=='H' else (c,(a+b)/2)
        return any(abs((b-a)-size[0]/FT*self.scale)<self.scale*.65
                   and math.hypot((r.x0+r.x1)/2-cx,(r.y0+r.y1)/2-cy)<self.scale*2
                   for r,_,size in self.door_notes)

    def _merge_solids(self,solids):
        result=[]
        for s in sorted(solids,key=lambda w:(w.o,round(w.c,1),w.a)):
            match=next((k for k in result if k.o==s.o and abs(k.c-s.c)<self.scale*.045
                        and max(k.a,s.a)<=min(k.b,s.b)+self.scale*.08),None)
            if match:match.a=min(match.a,s.a);match.b=max(match.b,s.b)
            else:result.append(Axis(s.o,s.c,s.a,s.b,s.t))
        return result

    def _snap(self,solids,merge=True):
        for s in solids:
            for end in ('a','b'):
                p=getattr(s,end);options=[]
                for t in solids:
                    if s.o==t.o:continue
                    if (end=='a' and t.c>p) or (end=='b' and t.c<p):continue
                    tolerance=max(s.t,t.t)/2+self.scale*.07
                    if abs(p-t.c)<=tolerance and t.a-tolerance<=s.c<=t.b+tolerance:
                        options.append(t.c)
                if options:setattr(s,end,min(options,key=lambda c:abs(c-p)))
        return self._merge_solids(solids) if merge else solids

    def _columns(self,drawings,labels):
        result=[];used=set()
        candidates=[]
        for d in drawings:
            r=d['rect']
            if not self.box.intersects(r) or not self.scale*.25<min(r.width,r.height)<=max(r.width,r.height)<self.scale*2:continue
            edges=[axis(a,b) for a,b in drawing_lines(d)]
            if sum(e is not None for e in edges)<4:continue
            candidates.append(r)
        for label,text,_ in labels:
            m=COL.search(text)
            if not m:continue
            width,depth=map(int,m.groups());cx,cy=(label.x0+label.x1)/2,(label.y0+label.y1)/2
            options=[]
            for i,r in enumerate(candidates):
                if i in used:continue
                expected=sorted((width/12*self.scale,depth/12*self.scale));actual=sorted((r.width,r.height))
                if any(abs(a-e)>e*.15 for a,e in zip(actual,expected)):continue
                distance=math.hypot((r.x0+r.x1)/2-cx,(r.y0+r.y1)/2-cy)
                if distance<self.scale*6:options.append((distance,i,r))
            if options:
                _,i,r=min(options);used.add(i)
                if abs(r.width-width/12*self.scale)>abs(r.width-depth/12*self.scale):width,depth=depth,width
                result.append((r,width,depth,text))
        return result

    def _join_openings(self,solids,raw,drawings,labels):
        groups=[]
        for s in sorted(solids,key=lambda w:(w.o,w.c,w.a)):
            match=next((g for g in groups if g[0].o==s.o and abs(g[0].c-s.c)<self.scale*.08),None)
            if match is None:groups.append([s])
            else:match.append(s)
        walls=[];openings=[];boundaries=[]
        curves=[d['rect'] for d in drawings if any(i[0]=='c' for i in d['items'])]
        for group in groups:
            group.sort(key=lambda s:s.a)
            current=Axis(group[0].o,group[0].c,group[0].a,group[0].b,group[0].t);pending=[]
            for s in group[1:]:
                gap=s.a-current.b;lo,hi=current.b,s.a
                kind=None;details=''
                if self.scale*.5<gap<self.scale*18:
                    # Glazing uses multiple continuous parallel strokes inside the wall strip.
                    glass=[r for r in raw if r.o==s.o and abs(r.c-current.c)<max(current.t,s.t)*.6
                           and r.a<=lo+self.scale*.4 and r.b>=hi-self.scale*.4 and r.b-r.a>=gap*.8]
                    if len({round(g.c,1) for g in glass})>=2:
                        kind='window';details='parallel_glazing_lines'
                    # Swing arcs meet the wall at one jamb. Fixtures elsewhere cannot close a gap.
                    for r in curves:
                        start,end=(r.x0,r.x1) if s.o=='H' else (r.y0,r.y1)
                        cross0,cross1=(r.y0,r.y1) if s.o=='H' else (r.x0,r.x1)
                        if abs((end-start)-gap)<self.scale*.55 and abs((start+end-lo-hi)/2)<self.scale*.55 and min(abs(cross0-s.c),abs(cross1-s.c))<self.scale*.4:
                            kind='door';details='door_swing';break
                    if not kind:
                        leaves=[r for r in raw if r.o!=s.o and min(abs(r.c-lo),abs(r.c-hi))<self.scale*.18
                                and min(abs(r.a-s.c),abs(r.b-s.c))<self.scale*.4
                                and abs((r.b-r.a)-gap)<self.scale*.45]
                        if leaves:kind='door';details='door_leaf_at_jamb'
                    # Large openings marked with a door size/callout (including overhead doors).
                    if kind in (None,'window'):
                        center=fitz.Point((lo+hi)/2,s.c) if s.o=='H' else fitz.Point(s.c,(lo+hi)/2)
                        markers=[t for r,t,_ in labels if (re.fullmatch(r'[1-9]',t) or re.search(r'\b\d{4,5}\s*(?:DR|DOOR)',t,re.I))
                                 and math.hypot((r.x0+r.x1)/2-center.x,(r.y0+r.y1)/2-center.y)<self.scale*2.2]
                        if markers:kind='door';details='door_callout_gap'
                if kind=='window' and self.tables['window']:
                    mid=fitz.Point((lo+hi)/2,s.c) if s.o=='H' else fitz.Point(s.c,(lo+hi)/2)
                    tagged=any(t in self.tables['window'] and math.hypot((r.x0+r.x1)/2-mid.x,(r.y0+r.y1)/2-mid.y)<self.scale*2 for r,t,_ in labels)
                    if not tagged:kind='profile'
                if not kind and self.scale*.4<gap<self.scale*18:
                    boundaries.append(Axis(s.o,current.c,lo,hi,max(current.t,s.t)))
                if kind:
                    if kind!='profile':pending.append((kind,lo,hi,details))
                    current.b=max(current.b,s.b)
                elif gap<=self.scale*.12:
                    current.b=max(current.b,s.b)
                else:
                    idx=len(walls);walls.append(current)
                    openings.extend((idx,*opening) for opening in pending)
                    current=Axis(s.o,s.c,s.a,s.b,s.t);pending=[]
            idx=len(walls);walls.append(current);openings.extend((idx,*o) for o in pending)
        # Dashed, paired porch/entry outlines close a floor slab without becoming walls.
        dashed=merge_axes(raw,gap=self.scale*.35)
        for i,s in enumerate(dashed):
            for t in dashed[i+1:]:
                if s.o!=t.o or not self.scale*.25<t.c-s.c<self.scale*1.5:continue
                lo,hi=max(s.a,t.a),min(s.b,t.b)
                if hi-lo<self.scale*3:continue
                _,support=self._support(s.o,(s.c+t.c)/2,lo,hi)
                if support.mean()>.15:continue
                portions=[r for r in raw if r.o==s.o and abs(r.c-s.c)<.3 and lo-.1<=r.a and r.b<=hi+.1]
                if len(portions)<4:continue
                boundaries.append(Axis(s.o,(s.c+t.c)/2,lo,hi,t.c-s.c))
        return self._snap(walls,merge=False),openings,boundaries

    def _opening_headers(self,walls,openings,boundaries,raw,labels):
        # A door at the end of a partition also needs a header, not a full-height gap.
        candidates=[]
        for s in boundaries:
            span=s.b-s.a
            if not self.scale*1<span<self.scale*4.5:continue
            cx,cy=((s.a+s.b)/2,s.c) if s.o=='H' else (s.c,(s.a+s.b)/2)
            for r,text,direction in labels:
                if text in self.tables['door']:
                    size=self.tables['door'][text]
                    if abs(size['width']/FT*self.scale-span)<self.scale*.65 and math.hypot((r.x0+r.x1)/2-cx,(r.y0+r.y1)/2-cy)<self.scale*2.2:
                        candidates.append(s);break
                m=re.search(r'(?<!\d)(\d{4,5})\s*(?:DR\.?|DOOR)',text,re.I)
                if not m or not (size:=door_size(m.group(1))):continue
                if abs(size[0]/FT*self.scale-span)>self.scale*.65:continue
                if math.hypot((r.x0+r.x1)/2-cx,(r.y0+r.y1)/2-cy)>self.scale*2.5:continue
                # Door notes can run along a neighbouring wall, not the opening.
                # Width and proximity, rather than text rotation, locate the gap.
                candidates.append(s);break
        for s in candidates:
            duplicate=any(w.o==s.o and abs(w.c-s.c)<self.scale*.18 and min(w.b,s.b)-max(w.a,s.a)>min(w.b-w.a,s.b-s.a)*.7 for w in walls)
            if duplicate:continue
            idx=len(walls);walls.append(s)
            openings.append((idx,'door',s.a,s.b,'door_size_label_at_partition_end'))

    def _end_closures(self,walls,columns):
        closures=[]
        anchors=list(walls)
        for r,*_ in columns:
            anchors.extend([Axis('H',(r.y0+r.y1)/2,r.x0,r.x1,r.height),Axis('V',(r.x0+r.x1)/2,r.y0,r.y1,r.width)])
        for s in walls:
            for end in ('a','b'):
                position=getattr(s,end);options=[]
                for t in anchors:
                    if s.o==t.o:continue
                    gap=(position-t.c) if end=='a' else (t.c-position)
                    if self.scale*.08<gap<self.scale*4.5 and t.a-max(t.t,s.t)/2<=s.c<=t.b+max(t.t,s.t)/2:
                        options.append(t.c)
                if options:
                    target=min(options,key=lambda c:abs(c-position))
                    closures.append(Axis(s.o,s.c,min(position,target),max(position,target),s.t))
        return closures

    def _regions(self,walls,boundaries,columns,labels):
        factor=getattr(self,'pixel_scale',min(2,math.sqrt(6_000_000/max(1,self.box.width*self.box.height))));w=int(self.box.width*factor)+40;h=int(self.box.height*factor)+40
        barrier=np.zeros((h,w),np.uint8)
        def pixel(x,y):return (int(round((x-self.box.x0)*factor))+20,int(round((y-self.box.y0)*factor))+20)
        for s in [*walls,*boundaries]:
            a,b=((s.a,s.c),(s.b,s.c)) if s.o=='H' else ((s.c,s.a),(s.c,s.b))
            cv2.line(barrier,pixel(*a),pixel(*b),255,max(2,int(s.t*factor)+2))
        for r,*_ in columns:cv2.rectangle(barrier,pixel(r.x0,r.y0),pixel(r.x1,r.y1),255,-1)
        count,components,stats,_=cv2.connectedComponentsWithStats(255-barrier)
        outside=set(np.unique(np.concatenate((components[0],components[-1],components[:,0],components[:,-1]))))
        assignments=defaultdict(list)
        for r,text,direction in labels:
            if not ROOM.fullmatch(text):continue
            x,y=pixel((r.x0+r.x1)/2,(r.y0+r.y1)/2)
            if 0<=x<w and 0<=y<h and (cid:=components[y,x]) not in outside and cid:
                assignments[int(cid)].append((r,text,direction))
        regions=[];combined=barrier.copy()
        for cid,names in assignments.items():
            if stats[cid,cv2.CC_STAT_AREA]/factor**2*(FT/self.scale)**2<.4:continue
            zone=(components==cid).astype(np.uint8)*255;combined[zone>0]=255
            contours,_=cv2.findContours(zone,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            contour=max(contours,key=cv2.contourArea);approx=cv2.approxPolyDP(contour,1.5,True)
            points=[(float(p[0][0]-20)/factor+self.box.x0,float(p[0][1]-20)/factor+self.box.y0) for p in approx]
            if len(points)>=3:
                poly=Polygon(points)
                if poly.is_valid:regions.append((poly,names))
        # Only enclosed named spaces produce floors; preserve actual setbacks and courtyards.
        contours,hierarchy=cv2.findContours(combined,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
        footprints=[]
        if hierarchy is not None:
            for i,contour in enumerate(contours):
                if hierarchy[0][i][3]!=-1 or cv2.contourArea(contour)*(FT/self.scale/factor)**2<1:continue
                contour=cv2.approxPolyDP(contour,2,True)
                points=[((p[0][0]-20)/factor+self.box.x0,(p[0][1]-20)/factor+self.box.y0) for p in contour]
                poly=Polygon(points)
                # Include a polygon only when it encloses a named interior region.
                if poly.is_valid and any(poly.covers(region.representative_point()) for region,_ in regions):footprints.append(poly)
        return regions,footprints
