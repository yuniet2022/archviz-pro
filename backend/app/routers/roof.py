from pathlib import Path
from typing import Literal
from uuid import UUID

import fitz
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.models.schemas import FloorPlanData, RoofSettings
from app.routers.plan import repository
from app.services.roof_engine import inspect_pdf, roof_proposal

router=APIRouter(tags=['roof and documents'])


class DocumentDescription(BaseModel):
    document_type: Literal['floor_plan','elevation','roof','structure','electrical','plumbing','reference'] = 'reference'
    page: int = Field(default=1,ge=1,le=1000)


class RoofRequest(BaseModel):
    floor_plan: FloorPlanData
    settings: RoofSettings
    project_id: UUID | None = None
    source_id: UUID | None = None
    source_page: int = Field(default=1,ge=1,le=1000)


def source_file(project_id,source_id):
    try:return repository().source(str(project_id),str(source_id))
    except KeyError:raise HTTPException(404,'Documento no encontrado en este proyecto')


def pdf_page(source,page,action):
    if Path(source['name']).suffix.lower()!='.pdf':
        raise HTTPException(415,'Esta lectura de datos y vista previa admite PDF. Otros formatos se conservan como referencia.')
    try:
        with fitz.open(stream=source['content'],filetype='pdf') as document:
            if document.is_encrypted:raise ValueError('El PDF está protegido por contraseña')
            if page>len(document):raise ValueError(f'El PDF tiene {len(document)} páginas')
            return action(document[page-1])
    except (ValueError,RuntimeError) as error:
        raise HTTPException(422,str(error)[:300])


@router.patch('/plans/{project_id}/sources/{source_id}')
def describe(project_id: UUID,source_id: UUID,description: DocumentDescription):
    source=source_file(project_id,source_id)
    if Path(source['name']).suffix.lower()=='.pdf':
        pdf_page(source,description.page,lambda p:None)
    return {'sources':repository().describe_source(str(project_id),str(source_id),description.model_dump())}


@router.get('/plans/{project_id}/sources/{source_id}/inspect')
def inspect_source(project_id: UUID,source_id: UUID,page: int=Query(1,ge=1,le=1000)):
    source=source_file(project_id,source_id)
    result=pdf_page(source,page,inspect_pdf)
    return {**result,'source':{'id':source['id'],'name':source['name'],'sha256':source['sha256'],'page':page}}


@router.get('/plans/{project_id}/sources/{source_id}/preview')
def preview_source(project_id: UUID,source_id: UUID,page: int=Query(1,ge=1,le=1000)):
    source=source_file(project_id,source_id)
    def image(p):
        scale=min(1600/max(p.rect.width,p.rect.height),2)
        return p.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False).tobytes('png')
    data=pdf_page(source,page,image)
    return Response(data,media_type='image/png',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})


@router.post('/roofs/preview')
def preview_roof(request: RoofRequest):
    source=None
    if request.source_id:
        if not request.project_id:raise HTTPException(422,'Selecciona el proyecto del documento')
        document=source_file(request.project_id,request.source_id)
        analysis=pdf_page(document,request.source_page,inspect_pdf)
        source={'id':document['id'],'name':document['name'],'sha256':document['sha256'],
                'page':request.source_page,'evidence':analysis['evidence'],
                'document_parameters':analysis['parameters']}
    try:
        roof=roof_proposal(request.floor_plan,request.settings,source)
    except ValueError as error:
        raise HTTPException(422,str(error))
    return {'roof':roof.model_dump()}
