from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from pathlib import Path
import fitz
from shapely.errors import GEOSException
from app.core.config import settings
from app.services.project_repository import ProjectRepository
from app.services.plan_fixtures import extract_pdf_fixtures
from app.services.furnish_engine import FurnishEngine
from app.services.interior_catalog import catalogue, STYLE_DATA, style_config
from app.services.interior_geometry import validate_item
from app.services.tour_planner import plan_tour
from app.models.schemas import StylePreset, Room, FloorPlanData, FurnitureItem, Vector3

router = APIRouter(prefix='/furnish', tags=['furnish'])
engine = FurnishEngine()


class LayoutRequest(BaseModel):
    floor_plan: FloorPlanData
    room_ids: Optional[List[str]] = Field(default=None, max_length=100)
    keep_existing: bool = False


class AddRequest(BaseModel):
    floor_plan: FloorPlanData
    model: str = Field(max_length=60)
    room_id: str = Field(max_length=100)
    style: StylePreset = StylePreset.WARM_MODERN


class PlacementRequest(BaseModel):
    floor_plan: FloorPlanData
    item: FurnitureItem


class TourRequest(BaseModel):
    floor_plan: FloorPlanData
    waypoints: List[Vector3] = Field(default_factory=list, max_length=64)


class FixtureRequest(BaseModel):
    project_id: UUID
    floor_plan: FloorPlanData


@router.post('/fixtures')
def recover_fixtures(request: FixtureRequest):
    repo=ProjectRepository(settings.PROJECT_DB)
    try:
        project=repo.get(str(request.project_id))
        source=repo.original_source(str(request.project_id))
    except KeyError:
        raise HTTPException(404,'Proyecto no encontrado.')
    if not source or Path(source['name']).suffix.lower()!='.pdf':
        return {'fixtures':[],'status':{'engine':1,'status':'source_unavailable','warnings':[
            'No hay un PDF original para recuperar equipos. Puedes añadirlos manualmente.']}}
    page=project['source']['import_recipe'].get('page',1)
    with fitz.open(stream=source['content'],filetype='pdf') as document:
        if not 1<=page<=len(document):raise HTTPException(422,'La página original no está disponible.')
        try:
            fixtures,warnings=extract_pdf_fixtures(document[page-1],request.floor_plan)
        except (ValueError,GEOSException):
            fixtures=[];warnings=['No se reconocieron contornos de equipos utilizables. Puedes añadirlos manualmente; la geometría de la casa se conserva.']
    return {'fixtures':fixtures,'status':{'engine':1,'status':'detected' if fixtures else 'not_detected',
        'source_sha256':source['sha256'],'warnings':warnings}}


@router.get('/styles')
def list_styles():
    return {'styles':[style_config(key) for key in STYLE_DATA]}


@router.get('/catalog')
def list_catalog():
    return {'items':catalogue(),'units':'m'}


@router.post('/layout/{style}')
def layout(request: LayoutRequest, style: StylePreset):
    if not request.floor_plan.rooms: raise HTTPException(422,'Define los ambientes antes de amueblar.')
    if len(request.floor_plan.rooms)>100: raise HTTPException(422,'Amuebla hasta 100 ambientes por operación.')
    furniture,warnings=engine.layout(request.floor_plan,style,request.room_ids,request.keep_existing)
    return dict(style=style, furniture=furniture, furniture_count=len(furniture),
                style_config=engine.get_style_config(style),warnings=warnings)


@router.post('/add')
def add(request: AddRequest):
    try: return {'item':engine.add(request.floor_plan,request.style,request.model,request.room_id)}
    except ValueError as error: raise HTTPException(422,str(error))


@router.post('/placement')
def placement(request: PlacementRequest):
    error=validate_item(request.floor_plan,request.item)
    if error: raise HTTPException(422,error)
    return {'item':request.item,'valid':True}


@router.post('/tour')
def tour(request: TourRequest):
    try: return plan_tour(request.floor_plan,request.waypoints)
    except ValueError as error: raise HTTPException(422,str(error))


@router.post('/auto/{style}')
def auto_furnish(rooms: List[Room], style: StylePreset):
    # Retain the older route for API clients; the UI sends the complete floor instead.
    if len(rooms)>100: raise HTTPException(422,'Amuebla hasta 100 ambientes por operación.')
    furniture=engine.auto_furnish(rooms,style)
    return dict(style=style,furniture_count=len(furniture),furniture=furniture,
                style_config=engine.get_style_config(style))
