"""Read fixed equipment from vector symbols and their enclosing counter outlines.

Plan coordinates come exclusively from the stored PDF-to-metre transform. Furniture
layout rules never choose new plumbing locations. Unsupported symbols are omitted.
"""
import math
import re
import uuid
from collections import defaultdict
import fitz
from shapely.geometry import LineString, Polygon, Point, box
from shapely.ops import unary_union, polygonize
from app.models.schemas import FixedFixture, Vector3
from app.services.interior_geometry import floor_polygon, room_polygon


def _paths(page, bounds):
    unique={};drawings=[]
    for drawing in page.get_drawings():
        if drawing.get('fill') is not None or drawing.get('dashes','[] 0')!='[] 0': continue
        if drawing.get('color') is None or max(drawing['color'])>.5: continue
        if bounds.contains(drawing['rect']): drawings.append(drawing)
        for item in drawing['items']:
            kind=item[0];paths=[]
            if kind=='l':paths=[[item[1],item[2]]]
            elif kind=='c':
                a,b,c,d=item[1:]
                paths=[[(a.x*(1-t)**3+3*b.x*(1-t)**2*t+3*c.x*(1-t)*t*t+d.x*t**3,
                         a.y*(1-t)**3+3*b.y*(1-t)**2*t+3*c.y*(1-t)*t*t+d.y*t**3)
                        for t in [i/12 for i in range(13)]]]
            elif kind=='re':
                r=item[1];paths=[[r.tl,r.tr,r.br,r.bl,r.tl]]
            elif kind=='qu':
                q=item[1];paths=[[q.ul,q.ur,q.lr,q.ll,q.ul]]
            for path in paths:
                points=[(round(v[0],2),round(v[1],2)) for v in path]
                if not all(bounds.contains(fitz.Point(*q)) for q in points): continue
                if kind=='l' and abs(abs(points[-1][0]-points[0][0])-abs(points[-1][1]-points[0][1]))<.2 and math.dist(points[0],points[-1])<30: continue
                key=min(tuple(points),tuple(reversed(points)))
                unique[key]=points
    if len(unique)>30000: raise ValueError('Demasiados trazos para reconocer equipos en esta vista.')
    paths=list(unique.values())
    # CAD exports can leave 0.06-0.12 pt gaps between a line and its Bézier end.
    # Snap endpoints only, within 0.22 PDF points; the architectural model is untouched.
    endpoints=[point for path in paths for point in (path[0],path[-1])]
    parent=list(range(len(endpoints)));buckets=defaultdict(list)
    def root(i):
        while parent[i]!=i: parent[i]=parent[parent[i]];i=parent[i]
        return i
    for i,(x,y) in enumerate(endpoints):
        cell=(math.floor(x/.22),math.floor(y/.22))
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                for j in buckets[(cell[0]+dx,cell[1]+dy)]:
                    if math.dist(endpoints[i],endpoints[j])<.22:parent[root(i)]=root(j)
        buckets[cell].append(i)
    groups=defaultdict(list)
    for i,point in enumerate(endpoints):groups[root(i)].append(point)
    centers={i:(sum(x for x,y in points)/len(points),sum(y for x,y in points)/len(points)) for i,points in groups.items()}
    for i,path in enumerate(paths):path[0]=centers[root(i*2)];path[-1]=centers[root(i*2+1)]
    outlines=[Polygon(poly.exterior).simplify(.08) for poly in polygonize(unary_union([LineString(path) for path in paths]))]
    deduplicated={poly.wkb:poly for poly in outlines if poly.is_valid and poly.area>1}
    return list(deduplicated.values()),drawings


def extract_pdf_fixtures(page, plan):
    transform=getattr(plan,'source_transform',{})
    if transform.get('format')!='pdf':return [],['Los equipos necesitan una planta PDF vectorial con escala.']
    origin=transform.get('origin_pdf_points');scale=transform.get('points_per_foot',0)
    if not origin or not scale or not math.isfinite(scale) or scale<=0:
        return [],['No se encontró la transformación del plano para situar los equipos.']
    ratio=.3048/scale
    def metric(x,y):return (x-origin[0])*ratio,(y-origin[1])*ratio
    def pdf(x,z):return x/ratio+origin[0],z/ratio+origin[1]
    # Reject a stale source transform after a global/manual rescale rather than
    # placing a second, misaligned house's fixtures on the current geometry.
    for wall in plan.walls:
        source=getattr(wall,'source',{})
        if source.get('kind')=='pdf_wall_faces':
            points=source.get('pdf_points',[])
            if len(points)==2 and any(math.dist(metric(*p),(v.x,v.z))>.04 for p,v in zip(points,(wall.start,wall.end))):
                return [],['La geometría se movió o reescaló respecto al PDF. Revisa su transformación antes de recuperar equipos.']
    floor=floor_polygon(plan)
    if floor.is_empty:return [],['El modelo no tiene un contorno de suelo para situar equipos.']
    minx,minz,maxx,maxz=floor.bounds
    a,b=pdf(minx,minz),pdf(maxx,maxz)
    bounds=fitz.Rect(a[0]-3,a[1]-3,b[0]+3,b[1]+3)
    polygons,drawings=_paths(page,bounds)
    labels=[];seen=set()
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines',[]):
            text=' '.join(span['text'] for span in line['spans']).strip().upper()
            rect=fitz.Rect(line['bbox']);center=((rect.x0+rect.x1)/2,(rect.y0+rect.y1)/2)
            key=(text,round(center[0],1),round(center[1],1))
            if bounds.contains(fitz.Point(*center)) and key not in seen:
                labels.append((text,Point(*center)));seen.add(key)
    def area(poly):return poly.area*ratio*ratio
    def dims(poly):
        a,b,c,d=poly.bounds;return ((c-a)*ratio,(d-b)*ratio)
    def metric_polygon(poly):
        return Polygon([metric(x,y) for x,y in poly.exterior.coords])
    def containers(point,minimum=.1,maximum=5):
        return sorted([poly for poly in polygons if minimum<=area(poly)<=maximum and poly.buffer(.1).covers(point)],key=lambda p:p.area)
    def nearest_room(point):
        x,z=metric(point.x,point.y)
        return min(plan.rooms,key=lambda room:room_polygon(room).distance(Point(x,z)),default=None)
    def front_for(poly):
        cx,cz=metric(poly.centroid.x,poly.centroid.y)
        distances=[]
        for wall in plan.walls:
            segment=LineString([(wall.start.x,wall.start.z),(wall.end.x,wall.end.z)])
            close=segment.interpolate(segment.project(Point(cx,cz)))
            distance=Point(cx,cz).distance(close)
            if distance>.005:distances.append((distance,cx-close.x,cz-close.y))
        if distances:
            _,dx,dz=min(distances);return math.atan2(dx,dz)
        return 0.
    result=[];warnings=[]
    def fixture(kind,poly,name,angle=None,height=.9,basins=None,basin_shapes=None,parent_id=None,body_poly=None,top_poly=None):
        world=metric_polygon(poly)
        if not floor.buffer(.003).covers(world):return None
        cx,cz=world.centroid.x,world.centroid.y
        angle=front_for(poly) if angle is None else angle
        c,s=math.cos(angle),math.sin(angle)
        local=[(c*(x-cx)-s*(z-cz),s*(x-cx)+c*(z-cz)) for x,z in world.exterior.coords]
        w=max(x for x,z in local)-min(x for x,z in local);d=max(z for x,z in local)-min(z for x,z in local)
        room=nearest_room(poly.centroid)
        centers=[Vector3(x=metric(p.x,p.y)[0],y=height,z=metric(p.x,p.y)[1]) for p in (basins or [])]
        basin_sizes=[]
        for basin in basin_shapes or []:
            points=[metric(x,y) for x,y in basin.exterior.coords]
            local_points=[(c*x-s*z,s*x+c*z) for x,z in points]
            basin_sizes.append(Vector3(x=max(x for x,z in local_points)-min(x for x,z in local_points),
                                       z=max(z for x,z in local_points)-min(z for x,z in local_points)))
        identifier=str(uuid.uuid5(uuid.NAMESPACE_URL,'archviz-pdf-fixture:'+kind+str([round(v,2) for v in poly.bounds])))
        item=FixedFixture(id=identifier,name=name,category='fixture',model=kind,kind=kind,
            position=Vector3(x=cx,y=height/2,z=cz),rotation=Vector3(y=angle),dimensions=Vector3(x=w,y=height,z=d),
            outline=[Vector3(x=x,z=z) for x,z in list(world.exterior.coords)[:-1]],
            body_outline=[Vector3(x=x,z=z) for x,z in list(metric_polygon(body_poly).exterior.coords)[:-1]] if body_poly is not None else [],
            top_outline=[Vector3(x=x,z=z) for x,z in list(metric_polygon(top_poly).exterior.coords)[:-1]] if top_poly is not None else [],
            basin_count=len(centers),source_basin_count=len(centers),basin_centers=centers,source_basin_centers=centers,
            basin_sizes=basin_sizes,source_basin_sizes=basin_sizes,room_id=room.id if room else '',source={'kind':'pdf_fixture_outline','pdf_bbox':list(poly.bounds),
            'recognition':kind,'height_source':'visualization_default_requires_confirmation'},parent_id=parent_id)
        item.source_basin_outlines=[[Vector3(x=metric(x,y)[0],z=metric(x,y)[1]) for x,y in list(basin.exterior.coords)[:-1]] for basin in (basin_shapes or [])]
        result.append(item);return item

    # LAV text inside an oval basin is strong semantic evidence. The next larger
    # enclosing, shallow polygon is its cabinet/counter, not the bathroom boundary.
    lavs=[point for text,point in labels if re.fullmatch(r'LAV\.?',text)]
    vanity_groups={}
    for point in lavs:
        candidates=[poly for poly in containers(point,.22,4) if .40<=min(dims(poly))<=.85 and max(dims(poly))>=.65]
        if not candidates:continue
        counter=candidates[0]
        key=counter.wkb
        ovals=[poly for poly in containers(point,.07,.22) if len(poly.exterior.coords)>12 and .3<=min(dims(poly))<=.6]
        basin=max(ovals,key=lambda p:p.area) if ovals else None
        vanity_groups.setdefault(key,(counter,[]))[1].append((basin.centroid if basin is not None else point,basin))
    for counter,basins in vanity_groups.values():
        basins=basins[:2]
        fixture('vanity',counter,'Lavamanos doble' if len(basins)==2 else 'Lavamanos sencillo',basins=[p for p,_ in basins],
                basin_shapes=[shape for _,shape in basins if shape is not None])

    # Toilets require both the oval bowl and a close, aligned tank. Circles such
    # as water heaters or cooktop rings alone never become a toilet.
    ellipses=[];small_circles=[];burners=[]
    distinct=set()
    for drawing in drawings:
        if len(drawing['items'])!=4 or any(item[0]!='c' for item in drawing['items']):continue
        r=drawing['rect'];key=tuple(round(v,1) for v in r)
        if key in distinct:continue
        distinct.add(key)
        w,d=r.width*ratio,r.height*ratio;center=Point((r.x0+r.x1)/2,(r.y0+r.y1)/2)
        if .32<=min(w,d)<=.52 and .36<=max(w,d)<=.65 and min(w,d)/max(w,d)>.7:
            if not any(center.distance(lav)*ratio<.28 for lav in lavs):ellipses.append((r,center))
        if .03<=w<=.09 and .8<w/d<1.2:small_circles.append(center)
        if .13<=w<=.28 and .8<w/d<1.2:burners.append((r,center))
    for r,center in ellipses:
        tanks=[]
        for poly in polygons:
            w,d=dims(poly)
            if not (.12<=min(w,d)<=.31 and .35<=max(w,d)<=.7):continue
            delta=Point(poly.centroid).distance(center)*ratio
            if not .22<delta<.55:continue
            cx,cy=poly.centroid.x,poly.centroid.y
            if (w>d and abs(cx-center.x)*ratio<.06) or (d>w and abs(cy-center.y)*ratio<.06):tanks.append((delta,poly))
        if not tanks:continue
        tank=min(tanks,key=lambda pair:pair[0])[1]
        angle=math.atan2(center.x-tank.centroid.x,center.y-tank.centroid.y)
        aligned=round(angle/(math.pi/2))*(math.pi/2)
        if abs(angle-aligned)<.08:angle=aligned
        bowl=box(*r)
        fixture('toilet',box(*unary_union([tank,bowl]).bounds),'Taza de baño',angle=angle,height=.78)

    # Four burner rings identify a cooker. Its enclosing rectangular outline is
    # kept; adjacent counter contours are joined across the appliance cut-out.
    cooker_polys=[]
    pending=list(burners)
    while pending:
        group=[pending.pop()];changed=True
        while changed:
            changed=False
            for candidate in pending[:]:
                if any(candidate[1].distance(other[1])*ratio<.55 for other in group):
                    group.append(candidate);pending.remove(candidate);changed=True
        if not 3<=len(group)<=6:continue
        centers=[point for _,point in group]
        candidates=[poly for poly in polygons if .23<=area(poly)<=1 and all(poly.buffer(.15).covers(p) for p in centers)]
        if not candidates:continue
        cooker=min(candidates,key=lambda p:p.area);cooker_polys.append(cooker)
        cooking=fixture('cooktop',cooker,'Estufa / cocina',height=.92)
        counter_candidates=[poly for poly in polygons if .7<=area(poly)<=5 and .40<=min(dims(poly))<=.85
                            and box(*poly.bounds).buffer(.3).covers(cooker.centroid) and poly.distance(cooker)<1]
        if counter_candidates:
            counter=min(counter_candidates,key=lambda p:p.area)
            outline=unary_union([counter,cooker]).buffer(.25,join_style=2).buffer(-.25,join_style=2)
            if outline.geom_type=='Polygon':
                cabinet=fixture('counter',outline,'Meseta de cocina',height=.9,body_poly=counter,top_poly=counter)
                if cooking and cabinet:cooking.parent_id=cabinet.id

    # Rectangular sink bowls contain a small drain circle. Keep only bowls near
    # a kitchen/outdoor label and outside the LAV basins already identified.
    bowls=[]
    for center in small_circles:
        if any(center.distance(point)*ratio<.35 for point in lavs):continue
        room=nearest_room(center)
        if room is None or not any(word in room.name.lower() for word in ('kitchen','cocina','lanai','terraza')):continue
        candidates=[poly for poly in containers(center,.035,.18) if .20<=min(dims(poly))<=.55 and max(dims(poly))<=.7]
        if candidates:
            bowl=candidates[0]
            if not any(bowl.centroid.distance(other.centroid)*ratio<.1 for other in bowls):bowls.append(bowl)
    sink_groups=[]
    while bowls:
        group=[bowls.pop()]
        for bowl in bowls[:]:
            if bowl.distance(group[0])*ratio<.25:group.append(bowl);bowls.remove(bowl)
        sink_groups.append(group[:2])
    dw_labels=[point for text,point in labels if re.fullmatch(r'D\.?\s*W\.?',text)]
    used_islands=[]
    for group in sink_groups:
        centers=[poly.centroid for poly in group]
        carriers=[poly for poly in polygons if .8<=area(poly)<=6 and all(box(*poly.bounds).covers(p) for p in centers)
                  and .65<=min(dims(poly))<=1.5 and max(dims(poly))>=1.4]
        if not carriers:continue
        carrier=min(carriers,key=lambda p:p.area)
        if any(carrier.intersection(other).area/min(carrier.area,other.area)>.7 for other in used_islands):continue
        used_islands.append(carrier)
        dishwasher=None
        for point in dw_labels:
            if not box(*carrier.bounds).buffer(.12/ratio).covers(point):continue
            candidates=[box(*drawing['rect']) for drawing in drawings if drawing['rect'].contains(fitz.Point(point.x,point.y))
                        and .4<=drawing['rect'].width*ratio<=.8 and .4<=drawing['rect'].height*ratio<=.85]
            if candidates:dishwasher=min(candidates,key=lambda p:p.area)
        outline=unary_union([carrier,dishwasher] if dishwasher is not None else [carrier]).buffer(.25,join_style=2).buffer(-.25,join_style=2)
        if outline.geom_type!='Polygon':continue
        centroid=unary_union(centers).centroid
        dx,dz=centroid.x-outline.centroid.x,centroid.y-outline.centroid.y
        w,d=dims(outline)
        angle=math.copysign(math.pi/2,dx) if d>w else (0 if dz>=0 else math.pi)
        # For an island the basins lie toward the cabinet front, perpendicular
        # to its long axis; avoid a tiny asymmetric drawing offset tilting it.
        angle=round(angle/(math.pi/2))*(math.pi/2)
        island=fixture('island',outline,'Isla con fregadero doble' if len(centers)==2 else 'Isla con fregadero',angle=angle,basins=centers,basin_shapes=group,body_poly=carrier)
        if dishwasher is not None and island:fixture('dishwasher',dishwasher,'Lavavajillas',angle=angle,height=.86,parent_id=island.id)
    for text,point in labels:
        if not re.fullmatch(r'REF\.?',text):continue
        candidates=[poly for poly in containers(point,.3,1.2) if .45<=min(dims(poly))<=.9 and .65<=max(dims(poly))<=1.4]
        if candidates:fixture('fridge',candidates[0],'Refrigerador',height=1.85)
    # Some PDFs repeat symbols on top of themselves; stable IDs suppress duplicates.
    result=list({item.id:item for item in result}.values())
    return result,warnings
