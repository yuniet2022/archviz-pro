from io import StringIO
import math

import ezdxf
import fitz
import pytest
from pydantic import ValidationError
from shapely.geometry import Polygon

from app.models.schemas import FloorPlanData
from app.services.architectural_pdf import ArchitecturalPDFEngine
from app.services.cad_geometry import import_dxf
from app.services.plan_export import dxf_plan


def hatched_pdf():
    doc=fitz.open();p=doc.new_page(width=900,height=750)
    def strip(x0,y0,x1,y1):
        r=fitz.Rect(x0,y0,x1,y1);p.draw_rect(r,width=.5)
        # Hatch diagonals are clipped to each wall strip, rather than fixture boxes.
        for intercept in range(int(y0-x1)-4,int(y1-x0)+5,3):
            lo=max(x0,y0-intercept);hi=min(x1,y1-intercept)
            if hi>lo:p.draw_line((lo,lo+intercept),(hi,hi+intercept),color=(.7,.7,.7),width=.4)
    for rect in [(95,95,300,105),(360,95,705,105),(695,100,705,605),
                 (395,595,700,605),(395,500,405,600),(95,495,400,505),(95,100,105,500),
                 (395,100,405,300),(395,360,405,500)]:strip(*rect)
    # One exterior window, one internal door and an unhatched kitchen fixture.
    for y in (97,100,103):p.draw_line((300,y),(360,y),width=.4)
    p.draw_line((400,300),(460,300),width=.5)
    p.draw_rect((450,220,600,250),width=.5)
    p.insert_text((180,250),'GREAT ROOM',fontsize=10)
    p.insert_text((180,265),'11\' 0" COFFER CLG.',fontsize=8)
    p.insert_text((500,350),'KITCHEN',fontsize=10)
    p.insert_text((500,365),'10\' 0" CLG.',fontsize=8)
    p.draw_line((100,75),(700,75),width=.5)
    p.draw_line((100,65),(100,110),width=.5);p.draw_line((700,65),(700,110),width=.5)
    p.insert_text((385,72),"30'",fontsize=8)
    result=doc.tobytes();doc.close();return result


def test_hatches_reject_fixture_walls_keep_window_and_l_shaped_floor(tmp_path):
    path=tmp_path/'plan.pdf';path.write_bytes(hatched_pdf())
    plan=ArchitecturalPDFEngine().process_pdf(path)
    assert plan.dimensions['px_per_ft_x']==pytest.approx(20)
    assert plan.dimensions['px_per_ft_y']==pytest.approx(20)
    assert len(plan.windows)==1
    assert plan.doors
    assert any(r.ceiling_height==pytest.approx(3.3528) for r in plan.rooms)
    for wall in plan.walls:
        a,b=wall.source['pdf_points']
        assert not (220<=a[1]<=250 and 220<=b[1]<=250 and 449<=a[0]<=601 and 449<=b[0]<=601)
        assert wall.height<4
    assert plan.floor_regions
    floor=plan.floor_regions[0]
    polygon=Polygon([(p.x,p.z) for p in floor.points])
    minx,minz,maxx,maxz=polygon.bounds
    assert polygon.area < (maxx-minx)*(maxz-minz)*.95
    assert polygon.is_valid


def save_dxf(tmp_path,doc):
    path=tmp_path/'plan.dxf';doc.saveas(path);return path


def test_dxf_layers_and_nested_blocks_keep_rectangular_rotated_and_circular_columns(tmp_path):
    doc=ezdxf.new();doc.units=4
    for layer in ('A-WALL','S-COLS','FURNITURE','DIMENSIONS'):doc.layers.new(layer)
    space=doc.modelspace()
    space.add_line((0,0),(6000,0),dxfattribs={'layer':'A-WALL'})
    space.add_line((0,200),(6000,200),dxfattribs={'layer':'A-WALL'})
    space.add_line((0,3000),(6000,3000),dxfattribs={'layer':'FURNITURE'})
    space.add_line((0,-1000),(6000,-1000),dxfattribs={'layer':'DIMENSIONS'})
    block=doc.blocks.new('COL_RECT')
    block.add_lwpolyline([(-200,-100),(200,-100),(200,100),(-200,100)],close=True)
    nested=doc.blocks.new('ASSEMBLY');nested.add_blockref('COL_RECT',(0,0))
    space.add_blockref('ASSEMBLY',(2000,2000),dxfattribs={'layer':'S-COLS','rotation':30})
    space.add_circle((4000,2000),250,dxfattribs={'layer':'S-COLS'})
    plan=import_dxf(save_dxf(tmp_path,doc),'auto')
    assert len(plan.walls)==1
    assert plan.walls[0].thickness==pytest.approx(.2)
    assert plan.walls[0].start.z==pytest.approx(-.1)
    assert len(plan.columns)==2
    rectangular=next(c for c in plan.columns if c.shape=='rectangular')
    assert rectangular.width==pytest.approx(.4)
    assert rectangular.depth==pytest.approx(.2)
    assert rectangular.rotation==pytest.approx(math.pi/6)
    circular=next(c for c in plan.columns if c.shape=='circular')
    assert circular.width==pytest.approx(.5)
    exported=ezdxf.read(StringIO(dxf_plan(plan)))
    assert len(exported.modelspace().query('CIRCLE[layer=="COLUMNS"]'))==1
    path=tmp_path/'roundtrip.dxf';exported.saveas(path)
    imported=import_dxf(path,'auto')
    assert len(imported.columns)==2
    # Dimension blocks and the draft label cannot become walls when reimported.
    assert len(imported.walls)==1


def test_dxf_closed_wall_outline_is_one_wall_with_real_thickness(tmp_path):
    doc=ezdxf.new();doc.units=6
    doc.layers.new('WALLS')
    doc.modelspace().add_lwpolyline([(0,0),(8,0),(8,.2),(0,.2)],close=True,dxfattribs={'layer':'WALLS'})
    plan=import_dxf(save_dxf(tmp_path,doc),'auto')
    assert len(plan.walls)==1
    assert plan.walls[0].thickness==pytest.approx(.2)
    assert plan.walls[0].end.x-plan.walls[0].start.x==pytest.approx(8)


def test_dxf_column_outline_of_separate_lines_is_not_lost(tmp_path):
    doc=ezdxf.new();doc.units=6;doc.layers.new('COLUMNS')
    points=[(0,0),(.4,0),(.4,.3),(0,.3)]
    for i in range(4):doc.modelspace().add_line(points[i],points[(i+1)%4],dxfattribs={'layer':'COLUMNS'})
    plan=import_dxf(save_dxf(tmp_path,doc),'auto')
    assert not plan.walls
    assert len(plan.columns)==1
    assert plan.columns[0].width==pytest.approx(.4)


def test_floor_contours_and_courtyard_survive_save_and_archive(client):
    points=[{'x':0,'z':0},{'x':8,'z':0},{'x':8,'z':6},{'x':0,'z':6}]
    hole=[{'x':2,'z':2},{'x':4,'z':2},{'x':4,'z':4},{'x':2,'z':4}]
    model={'walls':[{'id':'wall','start':{'x':0,'z':0},'end':{'x':8,'z':0}}],
           'floor_regions':[{'points':points,'holes':[hole]}]}
    import json
    response=client.post('/api/v1/plans/upload',files={'file':('contour.json',json.dumps(model))})
    assert response.status_code==200,response.text
    saved=response.json();root='/api/v1/plans/'+saved['project_id']
    assert client.get(root).json()['floor_plan']['floor_regions']==saved['floor_plan']['floor_regions']
    exported=client.get(root+'/export/archviz').content
    restored=client.post('/api/v1/plans/upload',files={'file':('contour.archviz',exported)})
    assert restored.status_code==200
    assert restored.json()['floor_plan']['floor_regions']==saved['floor_plan']['floor_regions']
    model['floor_regions'][0]['holes']=[[{'x':12,'z':2},{'x':14,'z':2},{'x':14,'z':4}]]
    with pytest.raises(ValidationError):FloorPlanData.model_validate(model)


def test_dxf_symbols_become_openings_without_becoming_walls(tmp_path):
    doc=ezdxf.new();doc.units=6
    for layer in ('WALLS','DOORS','WINDOWS'):doc.layers.new(layer)
    space=doc.modelspace()
    space.add_line((0,0),(6,0),dxfattribs={'layer':'WALLS'})
    space.add_line((0,4),(6,4),dxfattribs={'layer':'WALLS'})
    space.add_line((1,0),(1.9,0),dxfattribs={'layer':'DOORS'})
    for y in (3.95,4.05):space.add_line((2,y),(3.2,y),dxfattribs={'layer':'WINDOWS'})
    plan=import_dxf(save_dxf(tmp_path,doc),'auto')
    assert len(plan.walls)==2
    assert len(plan.doors)==1
    assert len(plan.windows)==1
    assert plan.doors[0].width==pytest.approx(.9,abs=.02)
    assert plan.windows[0].width==pytest.approx(1.2,abs=.02)


def test_dxf_memory_is_isolated_by_detector_version(client, monkeypatch):
    from app.services import semantic_import
    doc=ezdxf.new();doc.units=6;doc.modelspace().add_line((0,0),(4,0))
    out=StringIO();doc.write(out);content=out.getvalue().encode()
    def upload():return client.post('/api/v1/plans/upload',files={'file':('plan.dxf',content)})
    first=upload();assert first.status_code==200
    project=first.json()
    review=client.put('/api/v1/plans/'+project['project_id']+'/review',json={
        'base_revision':0,'floor_plan':project['floor_plan'],'approved':True,'measurements_confirmed':True,'allow_learning':True})
    assert review.status_code==200
    assert upload().json()['learning']['reused'] is True
    monkeypatch.setattr('app.routers.plan.dxf_engine_recipe',lambda:{'version':3,'sha256':'different-detector'})
    assert upload().json()['learning']['reused'] is False
