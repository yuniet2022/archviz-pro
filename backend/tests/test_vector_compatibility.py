from io import BytesIO
import fitz
import pytest

from app.services.semantic_import import import_drawing, pdf_engine_recipe
from app.services.vector_engine import VectorEngine
from app.services.architectural_pdf import ArchitecturalPDFEngine


def cad_pdf():
    with fitz.open() as doc:
        page = doc.new_page(width=900, height=700)
        # A labelled architectural view with repeated wall faces and a dimension.
        for offset in range(8):
            page.draw_rect(fitz.Rect(100+offset,100+offset,700-offset,550-offset), width=.5)
        page.insert_text((250,250), 'GREAT', fontsize=12)
        page.insert_text((520,300), 'KITCHEN', fontsize=12)
        page.insert_text((350,548), "20'", fontsize=10)
        return doc.tobytes()


def geometry(plan):
    return {
        'walls': [w.model_dump(exclude={'id'}) for w in plan.walls],
        'rooms': [r.model_dump(exclude={'id'}) for r in plan.rooms],
        'dimensions': plan.dimensions,
    }


def test_pdf_adapter_uses_isotropic_scale_and_replaces_fixed_exterior_heights(tmp_path):
    path=tmp_path/'plan.pdf';path.write_bytes(cad_pdf())
    existing=VectorEngine().process_pdf(str(path))
    updated=import_drawing(str(path),'.pdf',1,.001,'auto','vector')
    assert len(existing.walls)>0
    assert len(existing.rooms)>0
    assert len(updated.walls)==4
    assert len(updated.rooms)==1
    assert updated.warnings
    assert updated.dimensions['px_per_ft_x'] == updated.dimensions['px_per_ft_y']
    assert existing.dimensions['px_per_ft_x'] != existing.dimensions['px_per_ft_y']
    assert all(w.height==2.8 for w in updated.walls)
    assert any(w.height>4 for w in existing.walls)


def test_pdf_page_selection_keeps_the_same_vectors_and_labels(tmp_path):
    original=tmp_path/'one.pdf';original.write_bytes(cad_pdf())
    multi=tmp_path/'two.pdf'
    with fitz.open() as doc, fitz.open(original) as selected:
        doc.new_page(width=900,height=700)
        doc.insert_pdf(selected)
        doc.save(multi)
    assert geometry(import_drawing(str(multi),'.pdf',2,.05,'auto','vector')) == geometry(ArchitecturalPDFEngine().process_pdf(str(original)))
    with pytest.raises(ValueError,match='página'):
        import_drawing(str(multi),'.pdf',3,.05,'auto','vector')


def test_vector_mode_is_default_and_memory_cannot_cross_to_raster(client):
    pdf=cad_pdf()
    response=client.post('/api/v1/plans/upload',files={'file':('cad.pdf',pdf)})
    assert response.status_code==200,response.text
    data=response.json()
    assert data['floor_plan']['dimensions'].get('px_per_ft_x')
    reviewed=client.put(f"/api/v1/plans/{data['project_id']}/review",json={
        'floor_plan':data['floor_plan'],'base_revision':0,'approved':True,
        'measurements_confirmed':True,'allow_learning':True})
    assert reviewed.status_code==200,reviewed.text
    repeated=client.post('/api/v1/plans/upload',files={'file':('cad.pdf',pdf)})
    assert repeated.json()['learning']['reused'] is True
    raster=client.post('/api/v1/plans/upload',files={'file':('cad.pdf',pdf)},data={'pdf_mode':'raster'})
    assert raster.status_code==200,raster.text
    assert raster.json()['learning']['reused'] is False
    project=client.get(f"/api/v1/plans/{data['project_id']}").json()
    assert project['source']['import_recipe']['pdf_engine']==pdf_engine_recipe('vector')


def test_vector_errors_do_not_silently_generate_raster_geometry(client):
    with fitz.open() as doc:
        doc.new_page()
        empty=doc.tobytes()
    response=client.post('/api/v1/plans/upload',files={'file':('blank.pdf',empty)})
    assert response.status_code==422
    assert client.get('/api/v1/plans/learning/status').json()['approved_examples']==0
