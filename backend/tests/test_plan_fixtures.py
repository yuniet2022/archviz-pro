import fitz
from shapely.geometry import Polygon
from app.models.schemas import FloorPlanData, Room, Vector3, FloorRegion
from app.services.plan_fixtures import extract_pdf_fixtures
from app.services.interior_geometry import floor_polygon


def drawing():
    doc=fitz.open();page=doc.new_page(width=500,height=500)
    page.draw_rect(fitz.Rect(50,50,200,80))
    for x in (90,160):
        page.draw_oval(fitz.Rect(x-10,55,x+10,75))
        page.insert_text((x-7,67),'LAV',fontsize=6)
    page.draw_oval(fitz.Rect(300,190,320,214))
    page.draw_rect(fitz.Rect(295,216,325,227))
    page.draw_rect(fitz.Rect(230,280,290,450))
    for y in (330,360):
        page.draw_rect(fitz.Rect(260,y-10,280,y+10),radius=.08)
        page.draw_circle(fitz.Point(270,y),1.5)
    page.draw_rect(fitz.Rect(260,380,290,415))
    page.insert_text((265,400),'D.W.',fontsize=6)
    page.draw_rect(fitz.Rect(380,300,420,480))
    page.draw_rect(fitz.Rect(380,360,419,405))
    for x in (389,409):
        for y in (371,394):page.draw_circle(fitz.Point(x,y),4)
    page.draw_rect(fitz.Rect(380,260,420,300))
    page.insert_text((390,282),'REF.',fontsize=6)
    points=[Vector3(x=-5,z=-5),Vector3(x=5,z=-5),Vector3(x=5,z=5),Vector3(x=-5,z=5)]
    plan=FloorPlanData(rooms=[Room(id='room',name='Kitchen',points=points,area_sqm=100)],
                      floor_regions=[FloorRegion(points=points)],
                      source_transform={'format':'pdf','origin_pdf_points':[250,250],'points_per_foot':15.24})
    return doc,plan


def test_pdf_symbols_keep_double_vanity_toilet_and_measured_kitchen_contours():
    document,plan=drawing()
    with document:
        fixtures,warnings=extract_pdf_fixtures(document[0],plan)
    by_kind={fixture.kind:fixture for fixture in fixtures}
    assert {'vanity','toilet','island','cooktop','counter','dishwasher','fridge'}<=set(by_kind)
    vanity=by_kind['vanity']
    assert vanity.basin_count==2 and vanity.source_basin_count==2
    assert abs(vanity.dimensions.x-3)<.01 and abs(vanity.dimensions.z-.6)<.01
    assert len(vanity.basin_centers)==2 and len(vanity.basin_sizes)==2
    island=by_kind['island']
    assert island.basin_count==2 and abs(island.dimensions.x-3.4)<.01
    assert by_kind['dishwasher'].parent_id==island.id
    floor=floor_polygon(plan)
    assert all(floor.buffer(.003).covers(Polygon([(p.x,p.z) for p in f.outline])) for f in fixtures)
    assert all(f.source['kind']=='pdf_fixture_outline' for f in fixtures)
    assert len({f.id for f in fixtures})==len(fixtures)


def test_recovery_is_read_only_and_does_not_treat_an_unaccompanied_circle_as_a_toilet():
    document,plan=drawing()
    document[0].draw_circle(fitz.Point(100,200),11)
    before=plan.model_dump()
    with document:
        fixtures,_=extract_pdf_fixtures(document[0],plan)
    assert len([f for f in fixtures if f.kind=='toilet'])==1
    assert plan.model_dump()==before


def test_saved_pdf_project_can_recover_equipment_without_replacing_geometry(client):
    document,plan=drawing()
    with document:data=document.tobytes()
    # Store the original PDF on a project whose geometry is already approved by
    # its user; recovery must not re-run the architectural detector or save a review.
    from app.core.config import settings
    from app.services.project_repository import ProjectRepository
    import hashlib
    repo=ProjectRepository(settings.PROJECT_DB)
    created=repo.create(hashlib.sha256(data).hexdigest(),'{"page":1}','pdf',plan)
    pid=created['project_id'];repo.add_source(pid,'plan.pdf',hashlib.sha256(data).hexdigest(),'original',data)
    response=client.post('/api/v1/furnish/fixtures',json={'project_id':pid,'floor_plan':plan.model_dump()})
    assert response.status_code==200,response.text
    assert response.json()['status']['status']=='detected'
    assert any(f['kind']=='vanity' and f['basin_count']==2 for f in response.json()['fixtures'])
    after=repo.get(pid)
    assert after['floor_plan']==created['floor_plan'] and after['revision']==0


def test_unrecognized_equipment_does_not_discard_the_architectural_model(tmp_path,monkeypatch):
    from test_vector_compatibility import cad_pdf
    from app.services import plan_fixtures
    from app.services.semantic_import import import_vector_pdf
    def unsupported(*args):raise ValueError('Unclosed optional equipment symbols')
    monkeypatch.setattr(plan_fixtures,'extract_pdf_fixtures',unsupported)
    path=tmp_path/'drawing.pdf';path.write_bytes(cad_pdf())
    plan=import_vector_pdf(str(path),1)
    assert len(plan.walls)==4 and not plan.fixtures
    assert plan.fixture_status['warnings']


def test_customer_variant_cannot_put_basins_outside_a_small_counter():
    import pytest
    from pydantic import ValidationError
    from app.models.schemas import FixedFixture
    fixture=FixedFixture(kind='vanity',name='Single',category='fixture',position=Vector3(x=.45,y=.45,z=.3),
        dimensions=Vector3(x=.9,y=.9,z=.6),outline=[Vector3(),Vector3(x=.9),Vector3(x=.9,z=.6),Vector3(z=.6)],
        basin_count=1,source_basin_count=1,basin_centers=[Vector3(x=.45,y=.9,z=.3)])
    data=fixture.model_dump();data['basin_count']=2;data['basin_centers']*=2
    with pytest.raises(ValidationError,match='ancho suficiente'):FixedFixture.model_validate(data)
    data=fixture.model_dump();data['basin_centers'][0]['x']=10
    with pytest.raises(ValidationError,match='dentro de la meseta'):FixedFixture.model_validate(data)
