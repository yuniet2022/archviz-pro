from copy import deepcopy
import hashlib
import gzip
from io import BytesIO, StringIO
import json
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import ezdxf
from PIL import Image, ImageDraw
import pytest

from app.core.config import settings
from app.services.project_repository import ProjectRepository


def model():
    return {'walls':[
        {'id':'w1','start':{'x':0,'z':0},'end':{'x':4,'z':0},'height':2.8,'thickness':.2,'assembly':{'material':'CMU','fire_rating':'unverified'}},
        {'id':'w2','start':{'x':4,'z':0},'end':{'x':4,'z':3},'height':2.8,'thickness':.2},
        {'id':'w3','start':{'x':4,'z':3},'end':{'x':0,'z':3},'height':2.8,'thickness':.2},
        {'id':'w4','start':{'x':0,'z':3},'end':{'x':0,'z':0},'height':2.8,'thickness':.2}],
        'columns':[{'id':'col1','position':{'x':1,'z':2},'width':.4,'depth':.2,'height':3}],
        'doors':[{'id':'door','wall_id':'w1','position':.5,'width':.9,'height':2.1}],
        'windows':[{'id':'window','wall_id':'w2','position':.5,'width':1.2,'height':1.2,'sill_height':.9}],
        'architectural_info':{'project_name':'Prueba <script>alert(1)</script>', 'jurisdiction':'Florida'},
        'extensions':{'future_ifc_guid':'retained-original-id'}}


def upload(client, geometry=None, **options):
    source = json.dumps(geometry or model()).encode()
    response = client.post('/api/v1/plans/upload', files={'file':('casa.json',source,'application/json')},data=options)
    assert response.status_code == 200, response.text
    return response.json(), source


def review(client, project, **options):
    data = {'base_revision':project['revision'],'floor_plan':project['floor_plan'],
            'measurements_confirmed':True,'approved':True,'allow_learning':True,**options}
    return client.put('/api/v1/plans/'+project['project_id']+'/review',json=data)


@pytest.mark.parametrize('approved,confirmed,consent,eligible',[
    (False,False,False,False),(False,True,True,False),(True,True,False,False),(True,True,True,True)])
def test_only_reviewed_measured_consented_geometry_is_eligible(client, approved, confirmed, consent, eligible):
    project,_ = upload(client)
    assert client.get('/api/v1/plans/learning/status').json()['approved_examples'] == 0
    result = review(client,project,approved=approved,measurements_confirmed=confirmed,allow_learning=consent)
    assert result.status_code == 200
    assert result.json()['learning']['contributing'] is eligible
    dataset = client.get('/api/v1/plans/learning/dataset').text.strip().splitlines()
    assert len(dataset) == int(eligible)
    assert client.get('/api/v1/plans/learning/status').json()['trained_model'] is False


def test_approval_requires_measures_and_validation_preserves_previous_version(client):
    project,_ = upload(client)
    assert review(client,project,measurements_confirmed=False).status_code == 422
    bad = deepcopy(project['floor_plan']);bad['walls'][0]['end']=bad['walls'][0]['start']
    assert review(client,project,floor_plan=bad).status_code == 422
    bad = deepcopy(project['floor_plan']);bad['windows'][0]['wall_id']='nonexistent'
    assert review(client,project,floor_plan=bad).status_code == 422
    loaded = client.get('/api/v1/plans/'+project['project_id']).json()
    assert loaded['revision'] == 0
    assert loaded['floor_plan']['walls'][0]['end']['x'] == 4


def test_exact_memory_reuses_corrected_version_and_respects_recipe_and_revocation(client):
    project,_ = upload(client)
    project['floor_plan']['walls'][0]['height']=3.5
    result = review(client,project)
    assert result.status_code == 200
    restored = ProjectRepository(settings.PROJECT_DB).get(project['project_id'])
    assert restored['floor_plan']['walls'][0]['height'] == 3.5
    reused,_ = upload(client)
    assert reused['learning']['reused'] is True
    assert reused['floor_plan']['walls'][0]['height'] == 3.5
    assert upload(client,meters_per_pixel=.02)[0]['learning']['reused'] is False
    assert upload(client,reuse_reviewed='false')[0]['learning']['reused'] is False
    different = model();different['walls'][0]['height']=2.9
    assert upload(client,different)[0]['learning']['reused'] is False
    assert client.delete(f"/api/v1/plans/{project['project_id']}/learning").status_code == 200
    assert upload(client)[0]['learning']['reused'] is False
    assert not client.get('/api/v1/plans/learning/dataset').text.strip()


def test_revision_conflict_and_draft_invalidate_old_example(client):
    project,_ = upload(client)
    saved = review(client,project).json()
    assert review(client,project).status_code == 409
    saved['floor_plan']['walls'][0]['height']=3
    response = review(client,saved,approved=False,measurements_confirmed=False)
    assert response.status_code == 200
    assert not upload(client)[0]['learning']['reused']
    assert not client.get('/api/v1/plans/learning/dataset').text.strip()


def test_training_pair_keeps_original_prediction_not_intermediate_edit(client):
    project,_ = upload(client)
    project['floor_plan']['walls'][0]['height']=3
    draft=review(client,project,approved=False).json()
    draft['floor_plan']['walls'][0]['height']=3.4
    assert review(client,draft).status_code == 200
    example=json.loads(client.get('/api/v1/plans/learning/dataset').text)
    assert example['predicted']['walls'][0]['height']==2.8
    assert example['corrected']['walls'][0]['height']==3.4


def test_archive_preserves_originals_hashes_semantics_and_history(client):
    project,original = upload(client)
    project['floor_plan']['walls'][0]['height']=3.4
    assert review(client,project,notes='Altura contrastada con alzado').status_code == 200
    raw3d = b'glTF-unparsed-original-reference'
    assert client.post(f"/api/v1/plans/{project['project_id']}/sources", files={'file':('../../source.glb',raw3d)}).status_code==200
    response=client.get(f"/api/v1/plans/{project['project_id']}/archive")
    assert response.status_code==200
    with ZipFile(BytesIO(response.content)) as archive:
        manifest=json.loads(archive.read('manifest.json'))
        assert manifest['project']['source']['import_recipe']['version']==1
        for source in manifest['sources']:
            data=archive.read(source['path'])
            assert source['sha256']==hashlib.sha256(data).hexdigest()
            assert data in (original,raw3d)
            assert '..' not in source['path']
        assert len(manifest['sources'])==2
        restored=json.loads(archive.read('model.json'))['floor_plan']
        assert restored['walls'][0]['assembly']['material']=='CMU'
        assert restored['walls'][0]['height']==3.4
        assert restored['extensions']['future_ifc_guid']=='retained-original-id'
        assert json.loads(archive.read('original-prediction.json'))['walls'][0]['height']==2.8
        revisions=json.loads(archive.read('revisions.json'))
        assert revisions[0]['notes']=='Altura contrastada con alzado'
        assert 'Estructura y cimentación' in manifest['missing_information']


def test_export_real_dimensions_openings_and_portable_json(client):
    project,_=upload(client)
    root=f"/api/v1/plans/{project['project_id']}"
    assert client.get(root+'/export/dxf?cut_height=10').status_code==422
    response=client.get(root+'/export/dxf')
    document=ezdxf.read(StringIO(response.text))
    assert document.units==6
    space=document.modelspace()
    assert len(space.query('DIMENSION'))==4
    assert len(space.query('LWPOLYLINE[layer=="COLUMNS"]'))==1
    assert len(space.query('LINE[layer=="WINDOWS"]'))==2
    # The door removes 0.9 m of the 4 m wall at the cut plane.
    base=[]
    for entity in space.query('LWPOLYLINE[layer=="WALLS"]'):
        pts=list(entity.get_points('xy'));xs=[p[0] for p in pts];ys=[p[1] for p in pts]
        if min(ys)==pytest.approx(-.1) and max(ys)==pytest.approx(.1):
            base.append(max(xs)-min(xs))
    assert sum(base)==pytest.approx(3.1)
    svg=client.get(root+'/export/svg').text
    tree=ET.fromstring(svg)
    assert '<script>' not in svg
    assert '4.00 m' in svg and '1:100' in svg
    assert tree.tag.endswith('svg')
    exported=client.get(root+'/export/json').content
    imported=client.post('/api/v1/plans/upload',files={'file':('model.json',exported)})
    assert imported.status_code==200
    assert imported.json()['floor_plan']==project['floor_plan']


def test_pdf_and_dxf_sources_are_interpreted_and_preserved(client):
    image=Image.new('RGB',(300,240),'white');ImageDraw.Draw(image).rectangle((40,40,260,200),outline='black',width=8)
    output=BytesIO();image.save(output,format='PDF')
    pdf=client.post('/api/v1/plans/upload',files={'file':('plan.pdf',output.getvalue())},data={'meters_per_pixel':'.02','pdf_mode':'raster'})
    assert pdf.status_code==200,pdf.text
    assert pdf.json()['detected_walls']>0
    assert pdf.json()['detected_doors']==0
    doc=ezdxf.new();doc.units=4
    doc.modelspace().add_line((0,0),(4000,0))
    text=StringIO();doc.write(text)
    dxf=client.post('/api/v1/plans/upload',files={'file':('plan.dxf',text.getvalue().encode())})
    assert dxf.status_code==200,dxf.text
    assert dxf.json()['floor_plan']['walls'][0]['end']['x']==4


def test_light_project_omits_binary_sources_and_reimports_without_trusting_approval(client):
    project,_=upload(client)
    project['floor_plan']['walls'][0]['height']=3.4
    saved=review(client,project).json()
    client.post(f"/api/v1/plans/{project['project_id']}/sources",files={'file':('modelo.glb',b'heavy-reference'*80000)})
    response=client.get(f"/api/v1/plans/{project['project_id']}/export/archviz")
    assert response.status_code==200
    assert len(response.content)<10000
    decoded=gzip.decompress(response.content)
    content=json.loads(decoded)
    assert content['contains_originals'] is False
    assert b'heavy-reference' not in decoded
    assert len(content['source_references'])==2
    assert content['revisions'][0]['after']['walls'][0]['height']==3.4
    restored=client.post('/api/v1/plans/upload',files={'file':('proyecto.archviz',response.content)})
    assert restored.status_code==200,restored.text
    assert restored.json()['floor_plan']['walls'][0]['height']==3.4
    assert restored.json()['floor_plan']['walls'][0]['assembly']==saved['floor_plan']['walls'][0]['assembly']
    assert restored.json()['floor_plan']['archive_provenance'][0]['source_references'][1]['name']=='modelo.glb'
    assert restored.json()['learning']['contributing'] is False


def test_light_project_rejects_expansion_beyond_limit(client):
    bomb=gzip.compress(b'x'*(20*1024*1024+1))
    response=client.post('/api/v1/plans/upload',files={'file':('proyecto.archviz',bomb)})
    assert response.status_code==413


@pytest.mark.parametrize('name,data,expected',[
    ('bad.json',b'{',422),('bad.pdf',b'fake pdf',422),('bad.dxf',b'fake dxf',422),
    ('bad.json',b'{"units":"ft","floor_plan":{"walls":[]}}',422),
    ('bad.json',b'{"walls":[],"extra":NaN}',422),('image.exe',b'ab',415),
    ('empty.json',b'',400),('large.json',b'x'*(20*1024*1024+1),413)])
def test_invalid_input_does_not_become_learning_data(client,name,data,expected):
    response=client.post('/api/v1/plans/upload',files={'file':(name,data)})
    assert response.status_code==expected,response.text
    assert client.get('/api/v1/plans/learning/status').json()['approved_examples']==0
