"""A bounded walking graph. Every route segment stays in the free floor polygon."""
import heapq
import math
from collections import deque
from shapely.geometry import Point, LineString
from shapely.ops import unary_union
from shapely.prepared import prep
from app.services.interior_geometry import floor_polygon, structural_obstacles, footprint, obstacle, room_polygon


def plan_tour(plan, waypoints=None):
    floor=floor_polygon(plan)
    if floor.is_empty: raise ValueError('El modelo necesita un contorno de suelo o ambientes válidos.')
    solids=[structural_obstacles(plan),*[footprint(item) for item in plan.furniture if obstacle(item)]]
    # Camera radius is a visualization clearance, not an accessibility/code assessment.
    free=floor.difference(unary_union(solids)).buffer(-.18)
    if free.is_empty: raise ValueError('No hay espacio libre para caminar por esta planta.')
    minx,minz,maxx,maxz=free.bounds
    step=max(.10,math.sqrt((maxx-minx)*(maxz-minz)/32000))
    nx,nz=math.ceil((maxx-minx)/step)+1,math.ceil((maxz-minz)/step)+1
    prepared=prep(free)
    def xy(node): return (minx+node[0]*step,minz+node[1]*step)
    allowed={(i,j) for i in range(nx) for j in range(nz) if prepared.covers(Point(*xy((i,j))))}
    if not allowed: raise ValueError('Los pasos libres son demasiado estrechos para preparar el recorrido.')
    warnings=[]
    edge_cache={}
    def neighbours(node):
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            nxt=(node[0]+dx,node[1]+dz)
            if nxt not in allowed: continue
            key=tuple(sorted((node,nxt)))
            if key not in edge_cache: edge_cache[key]=prepared.covers(LineString([xy(node),xy(nxt)]))
            if edge_cache[key]: yield nxt,step*math.hypot(dx,dz)
    def search(start,end):
        queue=[(0.,0.,start)];cost={start:0.};parents={}
        while queue:
            _,travel,node=heapq.heappop(queue)
            if node==end:
                path=[end]
                while path[-1]!=start: path.append(parents[path[-1]])
                return list(reversed(path))
            if travel>cost[node]+1e-8: continue
            for nxt,weight in neighbours(node):
                value=travel+weight
                if value<cost.get(nxt,float('inf')):
                    cost[nxt]=value;parents[nxt]=node
                    heapq.heappush(queue,(value+math.dist(xy(nxt),xy(end)),value,nxt))
        return None
    targets=[]
    if waypoints:
        for index,point in enumerate(waypoints):
            node=min(allowed,key=lambda n:math.dist(xy(n),(point.x,point.z)))
            if math.dist(xy(node),(point.x,point.z))>.5:
                raise ValueError(f'El punto {index+1} está fuera del suelo libre o demasiado cerca de un obstáculo.')
            targets.append((node,f'Punto {index+1}'))
    else:
        reachable=None
        def priority(room):
            name=room.name.lower()
            return 0 if any(n in name for n in ('entry','entrada','foyer')) else 1 if any(n in name for n in ('great','living','kitchen','sala')) else 2
        for room in sorted(plan.rooms,key=priority):
            name=room.name.lower()
            if name in ('garage','garaje','pantry') or 'w.i.c' in name or 'closet' in name: continue
            polygon=room_polygon(room)
            if polygon.is_empty: continue
            candidates=[node for node in allowed if polygon.covers(Point(*xy(node)))]
            if reachable is not None:
                candidates=[node for node in candidates if node in reachable]
            if not candidates:
                warnings.append(f'{room.name}: no hay un punto de visita libre.')
                continue
            center=polygon.representative_point()
            node=min(candidates,key=lambda n:math.dist(xy(n),(center.x,center.y)))
            if reachable is None:
                reachable={node};queue=deque([node])
                while queue:
                    for neighbour,_ in neighbours(queue.popleft()):
                        if neighbour not in reachable:
                            reachable.add(neighbour);queue.append(neighbour)
            targets.append((node,room.name))
        if not targets:
            targets=[(min(allowed), 'Inicio')]
    route=[];stops=[];mandatory=[]
    for node,name in targets:
        if not route:
            route=[node];mandatory.append(0);stops.append({'name':name,'point':dict(x=xy(node)[0],y=1.6,z=xy(node)[1])});continue
        path=search(route[-1],node)
        if path is None:
            if waypoints: raise ValueError(f'No hay un paso transitable hasta {name}. Revisa las puertas y los muebles.')
            warnings.append(f'{name}: sin conexión transitable con el inicio; no se atraviesan muros.')
            continue
        route.extend(path[1:]);mandatory.append(len(route)-1);stops.append({'name':name,'point':dict(x=xy(node)[0],y=1.6,z=xy(node)[1])})
    if len(route)<2:
        # A single room still gets a real, collision-free route.
        origin=route[0]
        for node in sorted(allowed,key=lambda n:math.dist(xy(n),xy(origin)),reverse=True)[:80]:
            path=search(origin,node)
            if path and len(path)>2:
                route=path;break
    if len(route)<2: raise ValueError('No se pudo conectar dos puntos libres para el recorrido.')
    # Simplify only along visible, unobstructed straight segments; no spline cuts corners.
    simplified=[route[0]];index=0
    while index<len(route)-1:
        last=index+1
        next_stop=next((stop for stop in mandatory if stop>index),len(route)-1)
        for nxt in range(index+2,min(len(route),index+90,next_stop+1)):
            if prepared.covers(LineString([xy(route[index]),xy(route[nxt])])): last=nxt
            else: break
        simplified.append(route[last]);index=last
    points=[dict(x=xy(node)[0],y=1.6,z=xy(node)[1]) for node in simplified]
    distance=sum(math.dist(xy(a),xy(b)) for a,b in zip(simplified,simplified[1:]))
    return dict(points=points,stops=stops,distance_m=round(distance,2),warnings=warnings,
                clearance_m=.18,eye_height_m=1.6)
