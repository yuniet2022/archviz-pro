"""Measured plan projection of the semantic model, not image tracing."""
from html import escape
from io import StringIO
import math
import ezdxf
from app.models.schemas import FloorPlanData


def primitives(plan: FloorPlanData, cut_height=1.2):
    polygons, lines, labels, dimensions = [], [], [], []
    for wall in plan.walls:
        if wall.height < cut_height:
            continue
        a, b = (wall.start.x, -wall.start.z), (wall.end.x, -wall.end.z)
        length = math.dist(a, b)
        u = ((b[0]-a[0])/length, (b[1]-a[1])/length)
        n = (-u[1], u[0])
        def point(t, offset):
            return (a[0]+u[0]*t+n[0]*offset, a[1]+u[1]*t+n[1]*offset)
        holes = []
        for opening in [*plan.doors, *plan.windows]:
            if opening.wall_id != wall.id:
                continue
            sill = getattr(opening, 'sill_height', 0)
            if not sill <= cut_height < sill+opening.height:
                continue
            start, end = opening.position*length-opening.width/2, opening.position*length+opening.width/2
            holes.append((start, end))
            is_window = hasattr(opening, 'sill_height')
            layer = 'WINDOWS' if is_window else 'DOORS'
            for offset in (-wall.thickness/3, wall.thickness/3) if is_window else (0,):
                lines.append((layer, point(start, offset), point(end, offset)))
        cursor = 0
        for start, end in sorted(holes)+[(length, length)]:
            if start > cursor+1e-8:
                polygons.append(('WALLS', [point(cursor, -wall.thickness/2), point(start, -wall.thickness/2),
                                          point(start, wall.thickness/2), point(cursor, wall.thickness/2)]))
            cursor = max(cursor, end)
        dimensions.append((a, b, length))
        labels.append(((a[0]+b[0])/2+n[0]*.25, (a[1]+b[1])/2+n[1]*.25, f'{length:.2f} m'))
    for column in plan.columns:
        if column.height < cut_height:
            continue
        x, y, w, d = column.position.x, -column.position.z, column.width/2, column.depth/2
        polygons.append(('COLUMNS', [(x-w,y-d), (x+w,y-d), (x+w,y+d), (x-w,y+d)]))
    return polygons, lines, labels, dimensions


def dxf_plan(plan: FloorPlanData, cut_height=1.2):
    document = ezdxf.new('R2010')
    document.units = 6  # meters; geometry is exported 1:1
    document.header['$MEASUREMENT'] = 1
    for name, color in [('WALLS',7), ('COLUMNS',2), ('DOORS',3), ('WINDOWS',4), ('DIMENSIONS',8), ('NOTES',1)]:
        document.layers.new(name, dxfattribs={'color':color})
    space = document.modelspace()
    polygons, lines, _, dimensions = primitives(plan, cut_height)
    if not polygons:
        raise ValueError('No hay geometría a la altura de corte elegida')
    for layer, points in polygons:
        space.add_lwpolyline(points, close=True, dxfattribs={'layer':layer})
    for layer, a, b in lines:
        space.add_line(a, b, dxfattribs={'layer':layer})
    for a, b, length in dimensions:
        ux, uy = (b[0]-a[0])/length, (b[1]-a[1])/length
        base = ((a[0]+b[0])/2-uy*.5, (a[1]+b[1])/2+ux*.5)
        dim = space.add_linear_dim(base=base, p1=a, p2=b,
            angle=math.degrees(math.atan2(uy,ux)),
            override={'dimtxt':.12, 'dimasz':.08, 'dimdec':2, 'dimpost':'<> m'},
            dxfattribs={'layer':'DIMENSIONS'})
        dim.render()
    pts = [p for _, polygon in polygons for p in polygon]
    top = max((p[1] for p in pts), default=0)
    left = min((p[0] for p in pts), default=0)
    space.add_text('BORRADOR - Requiere revision profesional', dxfattribs={'insert':(left, top+1), 'height':.2, 'layer':'NOTES'})
    output = StringIO()
    document.write(output)
    return output.getvalue()


def svg_plan(plan: FloorPlanData, cut_height=1.2):
    polygons, lines, labels, _ = primitives(plan, cut_height)
    points = [p for _, polygon in polygons for p in polygon]
    if not points:
        raise ValueError('No hay geometría a la altura de corte elegida')
    minx, maxx = min(p[0] for p in points)-1, max(p[0] for p in points)+1
    miny, maxy = min(p[1] for p in points)-1, max(p[1] for p in points)+2
    width, height = maxx-minx, maxy-miny
    # A nominal 1:100 printed scale; viewBox units are meters.
    elements = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width*10:.3f}mm" height="{height*10:.3f}mm" viewBox="{minx} {-maxy} {width} {height}">',
                '<rect x="-100000" y="-100000" width="200000" height="200000" fill="white"/>',
                f'<text x="{minx+.2}" y="{-maxy+.3}" font-size=".2">{escape(plan.architectural_info.project_name)}</text>',
                f'<text x="{minx+.2}" y="{-maxy+.65}" font-size=".12">BORRADOR · metros · 1:100 al imprimir al 100% · corte {cut_height:g} m</text>',
                '<g transform="scale(1,-1)" stroke="#172033" stroke-width=".02">']
    for layer, polygon in polygons:
        elements.append(f'<polygon data-layer="{layer}" points="'+ ' '.join(f'{x},{y}' for x,y in polygon)+'" fill="#d4d8dd"/>')
    for layer, a, b in lines:
        color = '#1573aa' if layer == 'WINDOWS' else '#9c671a'
        elements.append(f'<path data-layer="{layer}" d="M {a[0]} {a[1]} L {b[0]} {b[1]}" stroke="{color}"/>')
    elements.append('</g>')
    for x,y,label in labels:
        elements.append(f'<text x="{x}" y="{-y}" font-size=".12" text-anchor="middle">{label}</text>')
    elements.append(f'<text x="{minx+.2}" y="{-miny-.15}" font-size=".12">{escape(plan.architectural_info.floor_name)} · Geometría del modelo; estructura e instalaciones no calculadas.</text></svg>')
    return ''.join(elements)
