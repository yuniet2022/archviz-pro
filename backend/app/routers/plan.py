from io import BytesIO
import hashlib
import gzip
import json
from pathlib import Path
import tempfile
from uuid import UUID
from zipfile import ZipFile, ZIP_DEFLATED
from ezdxf import DXFError

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import Response
from pydantic import ValidationError

from app.core.config import settings
from app.models.schemas import FloorPlanData, PlanReview, PlanUploadResponse
from app.services.project_repository import ProjectRepository, RevisionConflict
from app.services.semantic_import import import_drawing, pdf_engine_recipe, dxf_engine_recipe
from typing import Literal
from app.services.plan_export import dxf_plan, svg_plan

router = APIRouter(prefix='/plans', tags=['plans'])
MAX_UPLOAD = 20*1024*1024


def repository():
    return ProjectRepository(settings.PROJECT_DB)


def uploaded(file):
    name = (file.filename or 'archivo').replace('\\','/').split('/')[-1][:200]
    data = file.file.read(MAX_UPLOAD+1)
    if not data:
        raise HTTPException(400, 'El archivo está vacío')
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, 'El archivo supera 20 MB')
    return name, data


def load_project(project_id):
    try:
        return repository().get(str(project_id))
    except KeyError:
        raise HTTPException(404, 'Proyecto no encontrado')


@router.post('/upload', response_model=PlanUploadResponse)
def upload_plan(file: UploadFile = File(...), page: int = Form(1, ge=1),
                meters_per_pixel: float = Form(.05, gt=0, le=10),
                dxf_units: str = Form('auto'), reuse_reviewed: bool = Form(True),
                pdf_mode: Literal['vector','raster'] = Form('vector')):
    name, data = uploaded(file)
    suffix = Path(name).suffix.lower()
    if suffix not in ('.pdf','.dxf','.png','.jpg','.jpeg','.json','.archviz'):
        raise HTTPException(415, 'Usa PDF, DXF, PNG, JPG, modelo JSON o proyecto .archviz')
    if dxf_units not in ('auto','m','cm','mm','ft','in'):
        raise HTTPException(422, 'Unidades DXF inválidas')
    parameters = {'version':1, 'format':suffix, 'page':page,
                  'meters_per_pixel':meters_per_pixel, 'dxf_units':dxf_units}
    if suffix == '.pdf':
        parameters['pdf_engine'] = pdf_engine_recipe(pdf_mode)
    if suffix == '.dxf':
        parameters['dxf_engine'] = dxf_engine_recipe()
    recipe = json.dumps(parameters, sort_keys=True)
    try:
        if suffix in ('.json','.archviz'):
            decoded = data
            if suffix == '.archviz':
                with gzip.GzipFile(fileobj=BytesIO(data)) as compressed:
                    decoded = compressed.read(MAX_UPLOAD+1)
                if len(decoded)>MAX_UPLOAD:
                    raise HTTPException(413, 'El proyecto descomprimido supera 20 MB')
            parsed = json.loads(decoded)
            if parsed.get('units', 'm') != 'm' or parsed.get('up_axis', 'Y') != 'Y' or parsed.get('schema_version', 1) != 1:
                raise ValueError('El modelo debe usar esquema 1, metros y eje vertical Y')
            model = parsed.get('floor_plan', parsed)
            if not isinstance(model, dict) or not ('walls' in model or 'columns' in model):
                raise ValueError('El JSON debe contener geometría arquitectónica en metros')
            if parsed.get('kind') == 'archviz-project':
                lineage = model.get('archive_provenance', [])
                if not isinstance(lineage, list):
                    raise ValueError('Historial de procedencia inválido')
                # Imported claims are preserved as evidence, never as active approval or consent.
                model['archive_provenance'] = [*lineage, {key:parsed.get(key) for key in
                    ('project','revisions','source_references','contains_originals')}]
            floor_plan = FloorPlanData.model_validate(model)
        else:
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp)/('drawing'+suffix)
                path.write_bytes(data)
                floor_plan = import_drawing(str(path), suffix, page, meters_per_pixel, dxf_units, pdf_mode)
        if not floor_plan.walls and not floor_plan.columns:
            raise ValueError('No se detectó geometría. Selecciona otra página o usa un modelo JSON revisado.')
    except (ValueError, ValidationError, RuntimeError, OSError, TypeError, AttributeError, DXFError) as error:
        raise HTTPException(422, f'No se pudo interpretar el archivo: {str(error)[:400]}')
    repo = repository()
    result = repo.create(hashlib.sha256(data).hexdigest(), recipe, suffix[1:], floor_plan, reuse_reviewed)
    repo.add_source(result['project_id'], name, hashlib.sha256(data).hexdigest(), 'original', data,
                    {'document_type':'floor_plan','page':page})
    plan = FloorPlanData.model_validate(result['floor_plan'])
    return PlanUploadResponse(project_id=result['project_id'], status='success', revision=result['revision'],
        detected_walls=len(plan.walls), detected_rooms=len(plan.rooms), detected_doors=len(plan.doors),
        detected_windows=len(plan.windows), floor_plan=plan, learning=result['learning'],
        detected_columns=len(plan.columns),
        message='Modelo recuperado de una revisión del mismo archivo.' if result['learning']['reused'] else
                'Modelo inicial. Comprueba las medidas antes de aprobarlo.')


@router.get('/learning/status')
def learning_status():
    return {**repository().stats(), 'release':settings.APP_RELEASE_ID}


@router.get('/learning/dataset')
def learning_dataset():
    data = ''.join(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n' for row in repository().dataset())
    return Response(data, media_type='application/x-ndjson',
                    headers={'Content-Disposition':'attachment; filename="reviewed-examples.jsonl"'})


@router.get('/{project_id}')
def get_plan(project_id: UUID):
    return load_project(project_id)


@router.put('/{project_id}/review')
def review_plan(project_id: UUID, review: PlanReview):
    try:
        return repository().review(str(project_id), review)
    except KeyError:
        raise HTTPException(404, 'Proyecto no encontrado')
    except RevisionConflict as error:
        raise HTTPException(409, str(error))


@router.delete('/{project_id}/learning')
def revoke_learning(project_id: UUID):
    try:
        return repository().revoke(str(project_id))
    except KeyError:
        raise HTTPException(404, 'Proyecto no encontrado')


@router.get('/{project_id}/sources')
def sources(project_id: UUID):
    load_project(project_id)
    return {'sources':repository().sources(str(project_id))}


@router.post('/{project_id}/sources')
def attach_source(project_id: UUID, file: UploadFile = File(...),
                  document_type: Literal['floor_plan','elevation','roof','structure','electrical','plumbing','reference'] = Form('reference'),
                  page: int = Form(1,ge=1,le=1000)):
    load_project(project_id)
    name, data = uploaded(file)
    if Path(name).suffix.lower() not in ('.pdf','.dxf','.png','.jpg','.jpeg','.json','.glb','.gltf','.obj','.ifc','.archviz'):
        raise HTTPException(415, 'Formato de referencia no compatible')
    try:
        result = repository().add_source(str(project_id), name, hashlib.sha256(data).hexdigest(), 'reference', data,
                                        {'document_type':document_type,'page':page})
        return {'sources':result}
    except ValueError as error:
        raise HTTPException(413, str(error))


@router.get('/{project_id}/export/{format}')
def export_plan(project_id: UUID, format: str, cut_height: float = Query(1.2, gt=0, le=10)):
    if format == 'archviz':
        try:
            result, _, history, references = repository().archive_snapshot(str(project_id), include_content=False)
        except KeyError:
            raise HTTPException(404, 'Proyecto no encontrado')
        envelope = {'schema_version':1, 'kind':'archviz-project', 'units':'m', 'up_axis':'Y',
            'floor_plan':result['floor_plan'], 'project':{key:result[key] for key in
                ('project_id','revision','approved','measurements_confirmed','source')},
            'revisions':history, 'source_references':references, 'contains_originals':False}
        content = gzip.compress(json.dumps(envelope,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode(), mtime=0)
        return Response(content,media_type='application/octet-stream',headers={
            'Content-Disposition':f'attachment; filename="proyecto-{project_id}.archviz"'})
    result = load_project(project_id)
    plan = FloorPlanData.model_validate(result['floor_plan'])
    if format == 'json':
        content = json.dumps({'schema_version':1, 'units':'m', 'up_axis':'Y', 'floor_plan':result['floor_plan']}, ensure_ascii=False)
        mime = 'application/json'
    elif format in ('dxf','svg'):
        if not (plan.walls or plan.columns):
            raise HTTPException(422, 'El modelo está vacío')
        try:
            content = dxf_plan(plan, cut_height) if format == 'dxf' else svg_plan(plan, cut_height)
        except ValueError as error:
            raise HTTPException(422, str(error))
        mime = 'application/dxf' if format == 'dxf' else 'image/svg+xml'
    else:
        raise HTTPException(404, 'Exportación no disponible')
    return Response(content, media_type=mime,
        headers={'Content-Disposition':f'attachment; filename="planta-{project_id}.{format}"'})


@router.get('/{project_id}/archive')
def archive_project(project_id: UUID):
    repo = repository()
    try:
        result, predicted, history, originals = repo.archive_snapshot(str(project_id))
    except KeyError:
        raise HTTPException(404, 'Proyecto no encontrado')
    source_metadata = []
    output = BytesIO()
    with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
        for source in originals:
            # Use generated IDs; filenames from uploads never become ZIP paths.
            path = 'sources/'+source['id']+Path(source['name']).suffix.lower()
            archive.writestr(path, source['content'])
            source_metadata.append({k:source[k] for k in ('id','name','sha256','role','metadata')}
                                   | {'path':path, 'size_bytes':len(source['content'])})
        manifest = {'schema_version':1, 'units':'m', 'up_axis':'Y',
                    'project':result, 'sources':source_metadata,
                    'missing_information':result['floor_plan']['architectural_info']['missing_information'],
                    'limitation':'Una planta semántica. Fuentes 3D adjuntas se conservan sin interpretar; no equivale a un expediente aprobado.'}
        archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr('model.json', json.dumps({'schema_version':1,'units':'m','up_axis':'Y',
                            'floor_plan':result['floor_plan']}, ensure_ascii=False, indent=2))
        archive.writestr('original-prediction.json', json.dumps(predicted, ensure_ascii=False, indent=2))
        archive.writestr('revisions.json', json.dumps(history, ensure_ascii=False, indent=2))
        archive.writestr('LEEME.txt', 'Conserva este paquete: incluye fuentes originales, modelo en metros y revisiones.\n'
            'Las referencias GLB/IFC/OBJ no se han convertido automáticamente en elementos arquitectónicos.\n'
            'Requiere completar estructura, instalaciones, secciones, detalles y revisión profesional.\n')
    return Response(output.getvalue(), media_type='application/zip',
        headers={'Content-Disposition':f'attachment; filename="proyecto-{project_id}.zip"'})
