import hashlib
import json
from io import BytesIO
from zipfile import ZipFile

import fitz
import pytest
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union

from app.models.schemas import FloorPlanData, FloorRegion, RoofSettings, Vector3, Wall
from app.services.roof_engine import roof_proposal, inspect_pdf, footprint_hash


def plan_with_patio():
    ring=[Vector3(x=x,z=z) for x,z in [(0,0),(10,0),(10,9),(6,9),(6,6),(0,6)]]
    hole=[Vector3(x=x,z=z) for x,z in [(2,2),(4,2),(4,4),(2,4)]]
    return FloorPlanData(walls=[Wall(start=ring[0],end=ring[1],height=3)],
                         floor_regions=[FloorRegion(points=ring,holes=[hole])])


@pytest.mark.parametrize('kind',['flat','shed','gable','hip'])
def test_roofs_cover_concave_house_without_filling_courtyard_or_changing_house(kind):
    plan=plan_with_patio();before=plan.model_dump()
    roof=roof_proposal(plan,RoofSettings(kind=kind,eave_height=3.12,overhang=.4))
    projected=[]
    for triangle in roof.surface.triangles:
        p=Polygon([(roof.surface.vertices[i].x,roof.surface.vertices[i].z) for i in triangle])
        if p.area>1e-10:projected.append(p)
    shape=unary_union(projected)
    assert not shape.covers(Point(3,3)), 'Patio must remain uncovered'
    assert shape.covers(Polygon([(0,0),(10,0),(10,9),(6,9),(6,6),(0,6)],holes=[[(2,2),(4,2),(4,4),(2,4)]]))
    assert not shape.covers(Point(1,8)), 'Concave entry must not become a roof rectangle'
    assert max(p.y for p in roof.surface.vertices)>3.12 if kind!='flat' else max(p.y for p in roof.surface.vertices)==3.12
    assert plan.model_dump()==before
    assert roof.footprint_hash==footprint_hash(plan)
    assert roof.status=='proposal'


def test_roof_cannot_intersect_tall_walls_and_hash_changes_with_height():
    plan=plan_with_patio()
    with pytest.raises(ValueError,match='atravesar'):
        roof_proposal(plan,RoofSettings(eave_height=2.8))
    old=footprint_hash(plan);plan.walls[0].height=4
    assert footprint_hash(plan)!=old


def notes_pdf():
    document=fitz.open();page=document.new_page()
    page.insert_text((50,60),'6/12 ROOF PITCH',fontsize=12)
    page.insert_text((50,90),'16" OVERHANG',fontsize=12)
    page.insert_text((50,120),'SHINGLES ROOF LOAD',fontsize=12)
    page.insert_text((50,150),'GABLE END DETAIL - NOT THE BUILDING ROOF TYPE',fontsize=8)
    data=document.tobytes();document.close();return data


def test_pdf_notes_are_evidence_not_an_inferred_roof_geometry():
    with fitz.open(stream=notes_pdf(),filetype='pdf') as doc:
        result=inspect_pdf(doc[0])
    assert result['parameters']=={'pitch':6,'overhang':.4064,'material':'shingle'}
    assert 'kind' not in result['parameters']
    assert len(result['evidence'])==3 and result['warnings']


def test_multiple_documents_are_scoped_deduplicated_previewed_and_archived_with_roof(client):
    from app.core.config import settings
    from app.services.project_repository import ProjectRepository
    repo=ProjectRepository(settings.PROJECT_DB)
    plan=plan_with_patio();project=repo.create('hash','{}','json',plan);pid=project['project_id']
    data=notes_pdf()
    upload=client.post(f'/api/v1/plans/{pid}/sources',files={'file':('roof.pdf',data,'application/pdf')},
                       data={'document_type':'structure','page':'1'})
    assert upload.status_code==200,upload.text
    source=upload.json()['sources'][0];sid=source['id']
    assert source['metadata']=={'document_type':'structure','page':1}
    duplicate=client.post(f'/api/v1/plans/{pid}/sources',files={'file':('same.pdf',data,'application/pdf')})
    assert len(duplicate.json()['sources'])==1
    assert duplicate.json()['sources'][0]['metadata']==source['metadata']
    assert client.get(f'/api/v1/plans/{pid}/sources/{sid}/inspect?page=2').status_code==422
    preview=client.get(f'/api/v1/plans/{pid}/sources/{sid}/preview?page=1')
    assert preview.status_code==200 and preview.content.startswith(b'\x89PNG')
    other=repo.create('other','{}','json',plan)['project_id']
    assert client.get(f'/api/v1/plans/{other}/sources/{sid}/inspect').status_code==404
    describe=client.patch(f'/api/v1/plans/{pid}/sources/{sid}',json={'document_type':'roof','page':1})
    assert describe.status_code==200
    response=client.post('/api/v1/roofs/preview',json={'floor_plan':plan.model_dump(),
        'settings':RoofSettings().model_dump(),'project_id':pid,'source_id':sid})
    assert response.status_code==200,response.text
    roof=response.json()['roof'];assert roof['origin']=='document_parameters'
    assert roof['source']['sha256']==hashlib.sha256(data).hexdigest() and roof['source']['page']==1
    assert repo.get(pid)==project, 'Attaching and reading documents must not edit house or revision'
    revised=plan.model_dump();revised['roof']=roof
    save=client.put(f'/api/v1/plans/{pid}/review',json={'base_revision':0,'floor_plan':revised})
    assert save.status_code==200,save.text
    assert save.json()['floor_plan']['roof']==roof
    archive=client.get(f'/api/v1/plans/{pid}/archive')
    with ZipFile(BytesIO(archive.content)) as zipped:
        manifest=json.loads(zipped.read('manifest.json'))
        assert manifest['sources'][0]['metadata']=={'document_type':'roof','page':1}
        assert json.loads(zipped.read('model.json'))['floor_plan']['roof']==roof
    compact=client.get(f'/api/v1/plans/{pid}/export/archviz')
    restored=client.post('/api/v1/plans/upload',files={'file':('house.archviz',compact.content,'application/octet-stream')})
    assert restored.status_code==200,restored.text
    assert restored.json()['floor_plan']['roof']==roof


def test_saved_roof_rejects_changed_walls_but_allows_interior_updates():
    from pydantic import ValidationError
    plan=plan_with_patio();plan.roof=roof_proposal(plan,RoofSettings())
    data=plan.model_dump();data['walls'][0]['height']=3.5
    with pytest.raises(ValidationError,match='geometría cambió'):
        FloorPlanData.model_validate(data)
    data=plan.model_dump();data['interior_style']={'id':'coastal'}
    assert FloorPlanData.model_validate(data).roof.footprint_hash==plan.roof.footprint_hash


def test_conflicting_pdf_notes_do_not_pick_a_pitch_silently():
    with fitz.open(stream=notes_pdf(),filetype='pdf') as document:
        document[0].insert_text((50,190),'4/12 ROOF PITCH',fontsize=12)
        result=inspect_pdf(document[0])
    assert 'pitch' not in result['parameters']
    assert any('conflicto' in message for message in result['warnings'])
