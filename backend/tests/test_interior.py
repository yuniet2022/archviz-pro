from shapely.geometry import LineString
from app.models.schemas import FloorPlanData, Room, Vector3, Wall, Door, FloorRegion, StylePreset
from app.services.furnish_engine import FurnishEngine
from app.services.interior_geometry import validate_item, footprint, floor_polygon, structural_obstacles, obstacle
from app.services.tour_planner import plan_tour
from shapely.ops import unary_union


def rectangle(x,z,w,d):
    return [Vector3(x=x,z=z),Vector3(x=x+w,z=z),Vector3(x=x+w,z=z+d),Vector3(x=x,z=z+d)]


def house():
    room1=Room(id='bedroom',name='Bedroom',points=rectangle(0,0,4,4),area_sqm=16)
    room2=Room(id='living',name='Great Room',points=rectangle(4,0,5,4),area_sqm=20)
    wall=Wall(id='partition',start=Vector3(x=4),end=Vector3(x=4,z=4),height=2.8,thickness=.16)
    return FloorPlanData(rooms=[room1,room2],floor_regions=[FloorRegion(points=rectangle(0,0,9,4))],
                         walls=[wall],doors=[Door(id='access',wall_id=wall.id,position=.5,width=.9,height=2.1)])


def test_layout_uses_real_polygons_door_clearance_and_canonical_dimensions():
    plan=house();engine=FurnishEngine()
    items,warnings=engine.layout(plan,StylePreset.WARM_MODERN)
    assert items and not warnings
    plan.furniture=items
    assert all(validate_item(plan,item) is None for item in items)
    bed=next(item for item in items if item.category=='bed')
    assert bed.dimensions.y==1.05 and bed.dimensions.z==2.1
    assert bed.position.y==bed.dimensions.y/2
    assert all(item.room_id in ('bedroom','living') for item in items)


def test_non_living_rooms_are_never_filled_with_beds_by_area():
    plan=FloorPlanData(rooms=[Room(name=name,points=rectangle(index*10,0,4,4),area_sqm=16)
                              for index,name in enumerate(('Garage','Entry','Unknown','Foyer'))])
    items,_=FurnishEngine().layout(plan,StylePreset.CLASSIC)
    assert items==[]
    bath=Room(id='bath',name='Master Bath',points=rectangle(0,0,4,4),area_sqm=16)
    plan=FloorPlanData(rooms=[bath]);items,_=FurnishEngine().layout(plan,StylePreset.CLASSIC)
    assert items==[]  # Decoration must not invent plumbing positions from a room name.


def test_an_unknown_room_requires_a_use_instead_of_guessing_a_bed():
    plan=FloorPlanData(rooms=[Room(name='Room 1',points=rectangle(0,0,4,4),area_sqm=16)])
    items,warnings=FurnishEngine().layout(plan,StylePreset.JAPANDI)
    assert items==[] and any('asigna el uso' in warning for warning in warnings)
    plan.rooms[0].room_type='dining'
    items,_=FurnishEngine().layout(plan,StylePreset.JAPANDI)
    assert any(item.model=='dining_table' for item in items)
    assert not any(item.category=='bed' for item in items)


def test_placement_rejects_courtyards_walls_doors_and_overlapping_furniture():
    engine=FurnishEngine();plan=house()
    item=engine.make_item('nightstand',StylePreset.WARM_MODERN,4,1)
    assert 'muro' in validate_item(plan,item)
    item.position.z=2
    assert 'puertas' in validate_item(plan,item)
    item.position.x=2
    assert validate_item(plan,item) is None
    plan.furniture=[item]
    duplicate=engine.make_item('nightstand',StylePreset.WARM_MODERN,2,2)
    assert 'solapa' in validate_item(plan,duplicate)
    plan.floor_regions[0].holes=[rectangle(1.5,1.5,1,1)]
    assert 'patios' in validate_item(plan,item)


def test_automatic_tour_visits_connected_rooms_without_crossing_solids():
    plan=house();plan.furniture=FurnishEngine().layout(plan,StylePreset.WARM_MODERN)[0]
    tour=plan_tour(plan)
    assert len(tour['stops'])==2
    assert not tour['warnings']
    free=floor_polygon(plan).difference(unary_union([structural_obstacles(plan),
         *[footprint(item) for item in plan.furniture if obstacle(item)]])).buffer(-.18)
    for a,b in zip(tour['points'],tour['points'][1:]):
        assert free.covers(LineString([(a['x'],a['z']),(b['x'],b['z'])]))
    # Stops must remain in the final polyline even when a shorter line bypasses them.
    for stop in tour['stops']:
        assert stop['point'] in tour['points']


def test_marked_tour_preserves_order_and_reports_disconnected_rooms(client):
    plan=house()
    points=[Vector3(x=1,z=1),Vector3(x=3,z=3),Vector3(x=1,z=1)]
    tour=plan_tour(plan,points)
    assert len(tour['stops'])==3
    assert tour['points'][0]==tour['points'][-1]
    plan.doors=[]
    response=client.post('/api/v1/furnish/tour',json={'floor_plan':plan.model_dump(),
                     'waypoints':[dict(x=1,z=1),dict(x=6,z=1)]})
    assert response.status_code==422
    assert 'No hay un paso' in response.json()['detail']


def test_catalog_styles_and_real_scene_routes(client):
    styles=client.get('/api/v1/furnish/styles').json()['styles']
    assert len(styles)==14
    assert set(style['id'] for style in styles)==set(style.value for style in StylePreset)
    catalog=client.get('/api/v1/furnish/catalog').json()
    assert catalog['units']=='m' and len(catalog['items'])>=20
    plan=house()
    response=client.post('/api/v1/furnish/add',json={'floor_plan':plan.model_dump(),
        'model':'desk','room_id':'bedroom','style':'japandi'})
    assert response.status_code==200
    item=response.json()['item']
    assert item['model']=='desk' and item['style']=='japandi'
    response=client.post('/api/v1/furnish/placement',json={'floor_plan':plan.model_dump(),'item':item})
    assert response.status_code==200
    assert client.post('/api/v1/video/generate',json={}).status_code==410


def test_layout_and_style_persist_in_project_archive(client):
    import gzip,json
    plan=house();plan.furniture=FurnishEngine().layout(plan,StylePreset.JAPANDI)[0]
    from app.services.interior_catalog import style_config
    plan.interior_style=style_config('japandi')
    plan.tour_waypoints=[{'x':1,'y':1.6,'z':1},{'x':6,'y':1.6,'z':1}]
    plan.tour_settings={'duration':45,'quality':'720p'}
    response=client.post('/api/v1/plans/upload',files={'file':('interior.json',plan.model_dump_json().encode(),'application/json')})
    assert response.status_code==200,response.text
    pid=response.json()['project_id']
    reloaded=client.get('/api/v1/plans/'+pid).json()['floor_plan']
    assert reloaded['interior_style']['id']=='japandi'
    assert reloaded['tour_waypoints']==plan.tour_waypoints
    archive=client.get(f'/api/v1/plans/{pid}/export/archviz').content
    json.loads(gzip.decompress(archive))
    assert b'japandi' in gzip.decompress(archive)
    assert len(reloaded['furniture'])==len(plan.furniture)
    assert reloaded['furniture'][0]['model']==plan.furniture[0].model
