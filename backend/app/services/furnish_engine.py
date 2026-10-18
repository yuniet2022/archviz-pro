"""Place a measured local catalogue inside the semantic floor, preserving openings."""
import math
from shapely.affinity import rotate, translate
from shapely.geometry import Point, box
from shapely.ops import unary_union
from app.models.schemas import FurnitureItem, Vector3, StylePreset, FloorPlanData
from app.services.interior_catalog import CATALOG, style_config
from app.services.interior_geometry import (room_polygon, floor_polygon, footprint, obstacle,
                                             structural_obstacles, door_approaches)


class FurnishEngine:
    def get_style_config(self, style):
        return style_config(style)

    def _classify_name(self, name):
        name=name.lower().replace('.', '')
        if any(word in name for word in ('bath','baño','powder','sanitario')): return 'bathroom'
        if any(word in name for word in ('wic','closet','clóset','vestidor')): return 'closet'
        if any(word in name for word in ('bed','master','dorm','habitación')): return 'bedroom'
        if any(word in name for word in ('kitchen','cocina')): return 'kitchen'
        if any(word in name for word in ('dining','comedor')): return 'dining'
        if any(word in name for word in ('living','great','salón','sala')): return 'living'
        if any(word in name for word in ('laundry','lavander')): return 'laundry'
        if any(word in name for word in ('lanai','terraza','patio','porch')): return 'outdoor'
        if any(word in name for word in ('garage','garaje','entry','entrada','foyer','hall','pasillo','pantry')): return 'circulation'
        return 'unassigned'

    def _zones(self, plan):
        transform=getattr(plan,'source_transform',{})
        for room in plan.rooms:
            polygon=room_polygon(room)
            if polygon.is_empty or polygon.area<.3: continue
            assigned=getattr(room,'room_type',None)
            if assigned in ('living','bedroom','dining','kitchen','bathroom','laundry','outdoor','closet','circulation'):
                yield room,assigned,polygon.representative_point(),polygon
                continue
            labels=getattr(room,'source_labels',[])
            anchors=[]
            if transform.get('format')=='pdf' and labels:
                origin=transform.get('origin_pdf_points',[0,0])
                ratio=.3048/transform.get('points_per_foot',1)
                for label in labels:
                    kind=self._classify_name(label.get('text',''))
                    bbox=label.get('pdf_bbox',[])
                    if kind=='unassigned' or len(bbox)!=4: continue
                    anchor=Point(((bbox[0]+bbox[2])/2-origin[0])*ratio,
                                 ((bbox[1]+bbox[3])/2-origin[1])*ratio)
                    if not polygon.buffer(.1).covers(anchor): anchor=polygon.representative_point()
                    anchors.append((kind,anchor))
            if not anchors:
                kind=self._classify_name(room.name)
                anchors=[(kind,polygon.representative_point())]
            for kind,anchor in anchors:
                # A connected kitchen/living/dining polygon is kept connected, but furniture
                # stays near its own labelled zone instead of filling the whole bounding box.
                zone=polygon
                if len(anchors)>1:
                    zone=polygon.intersection(box(anchor.x-2.5,anchor.y-2.5,anchor.x+2.5,anchor.y+2.5))
                yield room,kind,anchor,zone

    def make_item(self, model, style, x=0, z=0, angle=0, room_id=''):
        definition=next((row for row in CATALOG if row[0]==model),None)
        if definition is None: raise ValueError('Mueble desconocido.')
        model,name,category,(w,h,d)=definition
        config=style_config(style)
        material='fabric' if category in ('seating','bed') or model=='rug' else 'wood'
        if category in ('fixture','appliance'): material='stone' if category=='fixture' else 'metal'
        color=config['fabric'] if material=='fabric' else config['wood']
        if category in ('fixture','appliance'): color='#f1f0e9'
        if model=='plant': color='#4e7651'
        return FurnitureItem(name=name,category=category,model=model,room_id=room_id,
                             position=Vector3(x=x,y=h/2,z=z),rotation=Vector3(y=angle),
                             dimensions=Vector3(x=w,y=h,z=d),color=color,material=material,
                             style=style.value if isinstance(style,StylePreset) else style)

    def layout(self, plan, style, room_ids=None, keep_existing=False):
        placed=list(plan.furniture) if keep_existing else []
        warnings=[]
        floor=floor_polygon(plan)
        structure=structural_obstacles(plan)
        approaches=door_approaches(plan)
        available=floor.difference(unary_union([structure.buffer(.045),approaches]))
        definitions={row[0]:row for row in CATALOG}

        def components(geometry):
            polygons=[geometry] if geometry.geom_type=='Polygon' else list(getattr(geometry,'geoms',[]))
            return sum(p.area>=.7 for p in polygons)

        def place(model, target, polygon, room_id, angle=0, primary=False):
            _,_,_,(w,h,d)=definitions[model]
            decorative=model=='rug'
            allowed=polygon.intersection(floor if decorative else available)
            if allowed.is_empty: return None
            occupied=unary_union([footprint(item,.055) for item in placed if obstacle(item)])
            fixed=unary_union([structure,*[footprint(item) for item in placed if obstacle(item)]])
            baseline_components=components(floor.difference(fixed).buffer(-.18))
            minx,minz,maxx,maxz=allowed.bounds
            step=max(.28,math.sqrt(max(allowed.area,1)/900))
            candidates=[(target.x,target.y)]
            candidates.extend((minx+i*step,minz+j*step) for i in range(math.ceil((maxx-minx)/step)+1)
                              for j in range(math.ceil((maxz-minz)/step)+1))
            candidates.sort(key=lambda p:(p[0]-target.x)**2+(p[1]-target.y)**2)
            best=None;score_best=float('inf')
            for theta in (angle,angle+math.pi/2,angle+math.pi,angle+math.pi*1.5):
                base=rotate(box(-w/2,-d/2,w/2,d/2),-theta,use_radians=True)
                for x,z in candidates:
                    shape=translate(base,x,z)
                    score=(x-target.x)**2+(z-target.y)**2
                    if primary:
                        back=Point(x-math.sin(theta)*d/2,z-math.cos(theta)*d/2)
                        score+=6*polygon.boundary.distance(back)**2
                    if score>=score_best: continue
                    if not allowed.covers(shape.buffer(.025,join_style=2)): continue
                    if not decorative and shape.intersects(occupied): continue
                    if not decorative:
                        remaining=floor.difference(unary_union([fixed,shape])).buffer(-.18)
                        if components(remaining)>baseline_components: continue
                    best=(x,z,theta);score_best=score
            if best is None: return None
            item=self.make_item(model,style,*best[:2],best[2],room_id)
            placed.append(item)
            return item

        for room,kind,anchor,polygon in self._zones(plan):
            if room_ids and room.id not in room_ids: continue
            if kind=='circulation': continue
            if kind=='unassigned':
                warnings.append(f'{room.name}: asigna el uso del ambiente antes de decorarlo automáticamente.')
                continue
            count=len(placed)
            if kind=='bedroom':
                model='bed_king' if 'master' in room.name.lower() and polygon.area>15 else 'bed_queen'
                bed=place(model,anchor,polygon,room.id,primary=True)
                if bed is None: bed=place('bed_single',anchor,polygon,room.id,primary=True)
                if bed:
                    for side in (-1,1):
                        dx,dz=side*(bed.dimensions.x/2+.29),-bed.dimensions.z*.3
                        c,s=math.cos(bed.rotation.y),math.sin(bed.rotation.y)
                        target=Point(bed.position.x+c*dx+s*dz,bed.position.z-s*dx+c*dz)
                        place('nightstand',target,polygon.intersection(target.buffer(.45)),room.id,bed.rotation.y)
                    place('dresser',anchor,polygon,room.id,primary=True)
            elif kind in ('living','outdoor'):
                sofa=place('outdoor_sofa' if kind=='outdoor' else 'sofa',anchor,polygon,room.id,primary=True)
                if sofa:
                    theta=sofa.rotation.y
                    front=Point(sofa.position.x+math.sin(theta)*1.05,sofa.position.z+math.cos(theta)*1.05)
                    place('coffee_table',front,polygon,room.id,theta)
                    if kind=='living':
                        place('rug',front,polygon,room.id,theta)
                        screen=Point(sofa.position.x+math.sin(theta)*2.65,sofa.position.z+math.cos(theta)*2.65)
                        place('tv_console',screen,polygon.intersection(screen.buffer(.85)),room.id,theta+math.pi)
                        side=Point(front.x+math.cos(theta)*1.35,front.y-math.sin(theta)*1.35)
                        place('armchair',side,polygon.intersection(side.buffer(.75)),room.id,theta-math.pi/2)
                place('plant',anchor,polygon,room.id)
            elif kind=='dining':
                table=place('dining_table',anchor,polygon,room.id)
                if table:
                    c,s=math.cos(table.rotation.y),math.sin(table.rotation.y)
                    for dx,dz,turn in [(-1.1,0,math.pi/2),(1.1,0,-math.pi/2),(0,-.74,0),(0,.74,math.pi)]:
                        point=Point(table.position.x+c*dx+s*dz,table.position.z-s*dx+c*dz)
                        place('dining_chair',point,polygon.intersection(point.buffer(.4)),room.id,table.rotation.y+turn)
            elif kind=='kitchen':
                island=place('island',anchor,polygon,room.id)
                if island:
                    for dx in (-.45,.45):
                        c,s=math.cos(island.rotation.y),math.sin(island.rotation.y)
                        point=Point(island.position.x+c*dx+s*.78,island.position.z-s*dx+c*.78)
                        place('stool',point,polygon.intersection(point.buffer(.4)),room.id,island.rotation.y)
                place('fridge',anchor,polygon,room.id,primary=True)
                place('range',anchor,polygon,room.id,primary=True)
            elif kind=='bathroom':
                place('toilet',anchor,polygon,room.id,primary=True)
                place('vanity',anchor,polygon,room.id,primary=True)
            elif kind=='laundry':
                place('washer',anchor,polygon,room.id,primary=True)
            elif kind=='closet':
                place('wardrobe',anchor,polygon,room.id,primary=True)
            if len(placed)==count:
                warnings.append(f'{room.name}: no se encontró espacio suficiente; puedes añadir muebles manualmente.')
        return placed,warnings

    def auto_furnish(self, rooms, style):
        return self.layout(FloorPlanData(rooms=rooms),style)[0]

    def add(self, plan, style, model, room_id):
        room=next((room for room in plan.rooms if room.id==room_id),None)
        if room is None: raise ValueError('Selecciona un ambiente del plano.')
        polygon=room_polygon(room)
        if polygon.is_empty: raise ValueError('El ambiente no tiene un contorno válido.')
        item=self.make_item(model,style,room_id=room_id)
        available=polygon.intersection(floor_polygon(plan)).difference(
            unary_union([structural_obstacles(plan).buffer(.04),door_approaches(plan),
                         *[footprint(other,.06) for other in plan.furniture if obstacle(other)]]))
        center=polygon.representative_point()
        minx,minz,maxx,maxz=polygon.bounds
        candidates=[(center.x,center.y)]+[(minx+i*.25,minz+j*.25)
             for i in range(min(160,math.ceil((maxx-minx)/.25)+1))
             for j in range(min(160,math.ceil((maxz-minz)/.25)+1))]
        candidates.sort(key=lambda p:(p[0]-center.x)**2+(p[1]-center.y)**2)
        for angle in (0,math.pi/2):
            item.rotation.y=angle
            for x,z in candidates:
                item.position.x=x;item.position.z=z
                if available.covers(footprint(item,.02)): return item
        raise ValueError('No hay espacio libre para ese mueble en el ambiente. Prueba uno más pequeño.')
