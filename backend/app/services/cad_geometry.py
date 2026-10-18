"""Layer-aware DXF geometry; preserve source coordinates and explicit units."""
from collections import defaultdict
from dataclasses import dataclass
import math
import re

import ezdxf
from ezdxf import bbox
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union

from app.models.schemas import Column, Door, FloorPlanData, FloorRegion, Vector3, Wall, Window

WALL_LAYER=re.compile(r'(?:^|[-_.\s])(WALLS?|MUROS?|PAREDES?|PARTITIONS?)(?:$|[-_.\s])',re.I)
COL_LAYER=re.compile(r'(?:^|[-_.\s])(COL(?:UMN)?S?|PILARES?|PILLARS?)(?:$|[-_.\s])',re.I)
DOOR_LAYER=re.compile(r'DOOR|PUERTA',re.I)
WINDOW_LAYER=re.compile(r'WINDOW|VENTANA|GLAZ',re.I)
EXCLUDE=re.compile(r'DIM|COTA|TEXT|NOTE|FURN|MUEBLE|PLUMB|SANIT|FIXT|CAB|ELECT|HATCH|CEIL|ROOF|GRID|BORDER|TITLE',re.I)


def point(x,y):return Vector3(x=x,z=-y)


def floor_regions(walls):
    lines=[LineString([(w.start.x,w.start.z),(w.end.x,w.end.z)]) for w in walls]
    polygons=list(polygonize(unary_union(lines)))
    # An enclosed courtyard is a hole, not an extra floor polygon.
    outer=[p for p in polygons if not any(q!=p and Polygon(q.exterior).contains(p) for q in polygons)]
    merged=unary_union(outer)
    polygons=list(merged.geoms) if merged.geom_type=='MultiPolygon' else [merged] if merged.geom_type=='Polygon' else []
    return [FloorRegion(points=[Vector3(x=x,z=z) for x,z in p.exterior.coords[:-1]],
                        holes=[[Vector3(x=x,z=z) for x,z in ring.coords[:-1]] for ring in p.interiors]) for p in polygons if p.area>.01]


@dataclass
class Rectangle:
    x: float
    y: float
    width: float
    depth: float
    rotation: float


def _rectangle(points,limit=5):
    if len(points)!=4:return None
    edges=[(points[(i+1)%4][0]-p[0],points[(i+1)%4][1]-p[1]) for i,p in enumerate(points)]
    lengths=[math.hypot(*e) for e in edges]
    if min(lengths)<.05 or max(lengths)>limit:return None
    for i,e in enumerate(edges):
        nxt=edges[(i+1)%4]
        if abs(e[0]*nxt[0]+e[1]*nxt[1])>lengths[i]*lengths[(i+1)%4]*1e-4:return None
    if abs(lengths[0]-lengths[2])>.001 or abs(lengths[1]-lengths[3])>.001:return None
    x=sum(p[0] for p in points)/4;y=sum(p[1] for p in points)/4
    return Rectangle(x,y,lengths[0],lengths[1],math.atan2(edges[0][1],edges[0][0]))


def _column(points,source):
    r=_rectangle(points)
    return Column(position=point(r.x,r.y),width=r.width,depth=r.depth,rotation=r.rotation,source=source) if r else None


def _decompose(space):
    stack=[(e,'',0) for e in reversed(list(space))];seen=0
    while stack:
        e,parent,depth=stack.pop();seen+=1
        if seen>60000:raise ValueError('DXF demasiado complejo: limita el archivo a una planta.')
        own=e.dxf.get('layer','0');layer=parent if own=='0' and parent else own
        if e.dxftype()=='INSERT':
            if depth>=8:raise ValueError('El DXF tiene bloques anidados demasiado profundamente.')
            block_name=e.dxf.name
            inherited=layer if layer!='0' else block_name
            inserts=e.multi_insert() if e.mcount>1 else [e]
            for insert in inserts:
                stack.extend((child,inherited,depth+1) for child in insert.virtual_entities())
        else:yield e,layer


def _paired_walls(lines):
    result=[];used=set()
    # Pair nearest parallel faces, retaining the actual thickness.
    pairs=[]
    for i,(a,b,layer) in enumerate(lines):
        length=math.dist(a,b);ux,uy=(b[0]-a[0])/length,(b[1]-a[1])/length
        for j in range(i+1,len(lines)):
            c,d,other=lines[j]
            if layer!=other:continue
            length2=math.dist(c,d)
            if abs(ux*(d[1]-c[1])-uy*(d[0]-c[0]))>length2*.001:continue
            distance=abs(ux*(c[1]-a[1])-uy*(c[0]-a[0]))
            if not .06<=distance<=.45:continue
            pc=(c[0]-a[0])*ux+(c[1]-a[1])*uy;pd=(d[0]-a[0])*ux+(d[1]-a[1])*uy
            lo,hi=max(0,min(pc,pd)),min(length,max(pc,pd))
            if hi-lo<.25 or (hi-lo)/min(length,length2)<.65:continue
            offset=((c[0]-a[0])*(-uy)+(c[1]-a[1])*ux)/2
            start=(a[0]+lo*ux-uy*offset,a[1]+lo*uy+ux*offset)
            end=(a[0]+hi*ux-uy*offset,a[1]+hi*uy+ux*offset)
            pairs.append((distance,i,j,start,end,layer))
    for thickness,i,j,a,b,layer in sorted(pairs):
        if i in used or j in used:continue
        used.update((i,j));result.append(Wall(start=point(*a),end=point(*b),thickness=thickness,source={'kind':'dxf_paired_faces','layer':layer}))
    for i,(a,b,layer) in enumerate(lines):
        if i not in used:result.append(Wall(start=point(*a),end=point(*b),source={'kind':'dxf_axis','layer':layer}))
    return result


def _openings(walls,symbols):
    # Join collinear fragments only when an opening symbol supports the gap.
    for kind,polygon,layer in symbols:
        center=polygon.centroid
        for i,first in enumerate(list(walls)):
            a=(first.start.x,-first.start.z);b=(first.end.x,-first.end.z);length=math.dist(a,b)
            ux,uy=(b[0]-a[0])/length,(b[1]-a[1])/length
            if abs((center.x-a[0])*(-uy)+(center.y-a[1])*ux)>.7:continue
            found=False
            for second in walls[i+1:]:
                c=(second.start.x,-second.start.z);d=(second.end.x,-second.end.z)
                if max(abs((p[0]-a[0])*(-uy)+(p[1]-a[1])*ux) for p in (c,d))>.03:continue
                projected=sorted((p[0]-a[0])*ux+(p[1]-a[1])*uy for p in (c,d))
                span=(center.x-a[0])*ux+(center.y-a[1])*uy
                if not length-.1<=span<=projected[0]+.1 or not .3<projected[0]-length<6:continue
                first.end=point(a[0]+projected[1]*ux,a[1]+projected[1]*uy);walls.remove(second);found=True;break
            if found:break
    doors=[];windows=[]
    for kind,poly,layer in symbols:
        options=[]
        for wall in walls:
            a=(wall.start.x,-wall.start.z);b=(wall.end.x,-wall.end.z);length=math.dist(a,b)
            ux,uy=(b[0]-a[0])/length,(b[1]-a[1])/length
            c=poly.centroid;normal=abs((c.x-a[0])*(-uy)+(c.y-a[1])*ux)
            if normal>max(.7,wall.thickness):continue
            projection=[(x-a[0])*ux+(y-a[1])*uy for x,y in poly.exterior.coords]
            lo,hi=max(0,min(projection)),min(length,max(projection))
            if .35<hi-lo<6 and max(projection)-min(projection)<=length+.05:
                options.append((normal,wall,lo,hi,length))
        if not options:continue
        _,wall,lo,hi,length=min(options,key=lambda o:o[0]);position=(lo+hi)/2/length;width=hi-lo
        collection=doors if kind=='door' else windows
        if any(o.wall_id==wall.id and abs(o.position-position)*length<max(o.width,width)*.6 for o in collection):continue
        args={'wall_id':wall.id,'position':position,'width':width,'source':{'kind':'dxf_opening_layer','layer':layer}}
        collection.append(Door(**args) if kind=='door' else Window(**args))
    return doors,windows


def import_dxf(path,units):
    document=ezdxf.readfile(path)
    unit_codes={1:.0254,2:.3048,4:.001,5:.01,6:1}
    factor={'m':1,'cm':.01,'mm':.001,'in':.0254,'ft':.3048}.get(units) if units!='auto' else unit_codes.get(document.units)
    if factor is None:raise ValueError('El DXF no declara unidades reconocidas. Selecciona sus unidades.')
    entities=list(_decompose(document.modelspace()));named_walls=any(WALL_LAYER.search(layer) for _,layer in entities)
    lines=[];direct=[];columns=[];column_edges=defaultdict(list);symbol_edges=defaultdict(list);ignored=0
    for entity,layer in entities:
        kind=entity.dxftype();column_layer=bool(COL_LAYER.search(layer));opening_kind='door' if DOOR_LAYER.search(layer) else 'window' if WINDOW_LAYER.search(layer) else None
        source={'kind':'dxf_column','layer':layer,'handle':entity.dxf.get('handle','')}
        vertices=None;closed=False
        if kind=='LWPOLYLINE':
            if abs(entity.dxf.elevation)*factor>.001 or any(abs(p[4])>1e-8 for p in entity.get_points()):ignored+=1;continue
            vertices=[(x*factor,y*factor) for x,y in entity.get_points('xy')];closed=entity.closed
        elif kind=='POLYLINE' and entity.is_2d_polyline:
            if any(abs(v.dxf.get('bulge',0))>1e-8 for v in entity.vertices):ignored+=1;continue
            vertices=[(p.x*factor,p.y*factor) for p in entity.points()];closed=entity.is_closed
        elif kind=='LINE':
            a,b=entity.dxf.start,entity.dxf.end
            if max(abs(a.z),abs(b.z))*factor>.001:continue
            vertices=[(a.x*factor,a.y*factor),(b.x*factor,b.y*factor)]
        elif kind=='CIRCLE' and column_layer:
            c=entity.dxf.center;diameter=entity.dxf.radius*factor*2
            if abs(c.z)*factor<.001 and .05<=diameter<=5:
                columns.append(Column(position=point(c.x*factor,c.y*factor),width=diameter,depth=diameter,shape='circular',source=source))
            continue
        elif kind=='ARC' and opening_kind:
            box=bbox.extents([entity]);a,b=box.extmin,box.extmax
            poly=Polygon([(a.x*factor,a.y*factor),(b.x*factor,a.y*factor),(b.x*factor,b.y*factor),(a.x*factor,b.y*factor)])
            if poly.area>0:symbol_edges[(opening_kind,layer)].append(poly.boundary)
            continue
        else:continue
        if not vertices or len(vertices)<2:continue
        if closed and math.dist(vertices[0],vertices[-1])<1e-7:vertices=vertices[:-1]
        if column_layer:
            if closed and (column:=_column(vertices,source)):columns.append(column)
            else:column_edges[layer].extend(LineString([a,b]) for a,b in zip(vertices,vertices[1:]+(vertices[:1] if closed else [])) if math.dist(a,b)>.001)
            continue
        segments=list(zip(vertices,vertices[1:]+(vertices[:1] if closed else [])))
        if opening_kind:
            symbol_edges[(opening_kind,layer)].extend(LineString([a,b]) for a,b in segments if math.dist(a,b)>.001);continue
        if EXCLUDE.search(layer) or (named_walls and not WALL_LAYER.search(layer)):continue
        # A closed, thin wall outline is one wall, rather than four inflated faces.
        if closed and len(vertices)==4:
            shape=_rectangle(vertices,limit=1000)
            if shape and max(shape.width,shape.depth)/min(shape.width,shape.depth)>=3 and min(shape.width,shape.depth)<=.6:
                a,b,c,d=vertices
                if math.dist(a,b)>math.dist(b,c):start=((a[0]+d[0])/2,(a[1]+d[1])/2);end=((b[0]+c[0])/2,(b[1]+c[1])/2)
                else:start=((a[0]+b[0])/2,(a[1]+b[1])/2);end=((c[0]+d[0])/2,(c[1]+d[1])/2)
                direct.append(Wall(start=point(*start),end=point(*end),thickness=min(shape.width,shape.depth),source={'kind':'dxf_wall_outline','layer':layer}));continue
        lines.extend((a,b,layer) for a,b in segments if .05<=math.dist(a,b)<=1000)
    for layer,edges in column_edges.items():
        for polygon in polygonize(unary_union(edges)):
            if column:=_column(list(polygon.exterior.coords)[:-1],{'kind':'dxf_column_lines','layer':layer}):columns.append(column)
    if len(lines)>3000 or len(columns)>2000:raise ValueError('DXF demasiado complejo: selecciona una planta y simplifica las capas.')
    walls=[*direct,*_paired_walls(lines)]
    symbols=[]
    for (kind,layer),edges in symbol_edges.items():
        union=unary_union(edges).buffer(.005)
        groups=list(union.geoms) if union.geom_type=='MultiPolygon' else [union]
        for group in groups:
            lo,bot,hi,top=group.bounds
            if max(hi-lo,top-bot)>.35:
                symbols.append((kind,Polygon([(lo,bot),(hi,bot),(hi,top),(lo,top)]),layer))
    doors,windows=_openings(walls,symbols)
    if not walls and not columns:raise ValueError('No se reconocieron muros ni columnas en las capas del DXF.')
    warnings=['DXF: alturas y antepechos no definidos en planta quedan propuestos para revisión.']
    if not named_walls:warnings.append('No hay capas de muro identificadas: se usaron líneas no anotativas. Revisa la clasificación.')
    if ignored:warnings.append(f'{ignored} polilíneas curvas o fuera del plano no se extruyeron como muros rectos.')
    return FloorPlanData(walls=walls,columns=columns,doors=doors,windows=windows,floor_regions=floor_regions(walls),dimensions={'unit_factor_m':factor},warnings=warnings)
