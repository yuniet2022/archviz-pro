"""Shared layout/route geometry: real floor contours, wall cuts and furniture."""
import math
from shapely.affinity import rotate, translate
from shapely.geometry import Polygon, LineString, Point, box
from shapely.ops import unary_union


def room_polygon(room):
    if len(room.points) < 3:
        return Polygon()
    polygon = Polygon([(p.x, p.z) for p in room.points])
    return polygon if polygon.is_valid else polygon.buffer(0)


def floor_polygon(plan):
    if plan.floor_regions:
        return unary_union([Polygon([(p.x,p.z) for p in r.points],
                                    [[(p.x,p.z) for p in h] for h in r.holes]) for r in plan.floor_regions])
    return unary_union([room_polygon(room) for room in plan.rooms])


def footprint(item, clearance=0):
    w, d = item.dimensions.x*item.scale.x, item.dimensions.z*item.scale.z
    # Three.js positive Y rotation maps +X towards -Z.
    shape = rotate(box(-w/2, -d/2, w/2, d/2), -item.rotation.y, use_radians=True)
    return translate(shape, item.position.x, item.position.z).buffer(clearance, join_style=2)


def obstacle(item):
    return getattr(item, 'model', '') != 'rug' and item.dimensions.y*item.scale.y > .06


def structural_obstacles(plan):
    solids = []
    for wall in plan.walls:
        dx, dz = wall.end.x-wall.start.x, wall.end.z-wall.start.z
        length = math.hypot(dx,dz)
        edges = [(0.,length)]
        for door in plan.doors:
            if door.wall_id != wall.id or door.height < 1.9:
                continue
            a, b = door.position*length-door.width/2, door.position*length+door.width/2
            edges = [(c,d) for start,end in edges for c,d in ((start,min(a,end)),(max(b,start),end)) if d>c]
        for start,end in edges:
            solids.append(LineString([(wall.start.x+dx*start/length,wall.start.z+dz*start/length),
                                      (wall.start.x+dx*end/length,wall.start.z+dz*end/length)])
                          .buffer(wall.thickness/2,cap_style=2))
    for column in plan.columns:
        if column.shape == 'circular':
            solids.append(Point(column.position.x,column.position.z).buffer(column.width/2))
        else:
            shape=rotate(box(-column.width/2,-column.depth/2,column.width/2,column.depth/2),
                         -column.rotation,use_radians=True)
            solids.append(translate(shape,column.position.x,column.position.z))
    for fixture in plan.fixtures:
        if fixture.outline:
            solids.append(Polygon([(p.x,p.z) for p in fixture.outline]))
        else:
            solids.append(footprint(fixture))
    return unary_union(solids)


def door_approaches(plan):
    walls = {wall.id:wall for wall in plan.walls}
    shapes = []
    for door in plan.doors:
        wall=walls[door.wall_id]
        dx,dz=wall.end.x-wall.start.x,wall.end.z-wall.start.z
        length=math.hypot(dx,dz)
        cx,cz=wall.start.x+dx*door.position,wall.start.z+dz*door.position
        # Space on both sides of the opening; conservative because swing hand is unknown.
        shape=rotate(box(-door.width/2-.12,-.85,door.width/2+.12,.85),
                     math.atan2(dz,dx),use_radians=True)
        shapes.append(translate(shape,cx,cz))
    return unary_union(shapes)


def validate_item(plan, item, existing=None):
    values=[item.dimensions.x,item.dimensions.y,item.dimensions.z,*item.scale.model_dump().values()]
    if any(not .005 <= n <= 30 for n in values) or abs(item.rotation.x)>1e-6 or abs(item.rotation.z)>1e-6:
        return 'Usa dimensiones y escala positivas; solo se admite giro sobre el suelo.'
    if abs(item.position.y-item.dimensions.y*item.scale.y/2)>.005:
        return 'El mueble debe apoyarse sobre el suelo.'
    shape=footprint(item)
    floor=floor_polygon(plan)
    if floor.is_empty or not floor.buffer(.002).covers(shape):
        return 'El mueble debe quedar dentro del suelo, sin invadir patios.'
    if shape.intersection(structural_obstacles(plan)).area>1e-5:
        return 'El mueble invade un muro o una columna.'
    if obstacle(item):
        if shape.intersection(door_approaches(plan)).area>1e-5:
            return 'Deja libre el acceso y la apertura de las puertas.'
        for other in plan.furniture if existing is None else existing:
            if other.id!=item.id and obstacle(other) and footprint(other,.04).intersection(shape).area>1e-5:
                return 'El mueble se solapa con otro elemento.'
    return None
