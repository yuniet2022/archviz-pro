from pydantic import BaseModel, Field, ConfigDict, model_validator
import math
import json
from typing import List, Optional, Dict, Any, Literal
from enum import Enum
import uuid

class Vector3(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    x: float = Field(default=0, ge=-1e7, le=1e7)
    y: float = Field(default=0, ge=-1e7, le=1e7)
    z: float = Field(default=0, ge=-1e7, le=1e7)

class Wall(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    start: Vector3
    end: Vector3
    height: float = 2.8
    thickness: float = 0.15
    has_drywall: bool = True

    @model_validator(mode='after')
    def valid_wall(self):
        if not .01 <= self.height <= 30 or not .01 <= self.thickness <= 3:
            raise ValueError('Altura o grosor del muro fuera de rango')
        if abs(self.start.y) > 1e-6 or abs(self.end.y) > 1e-6:
            raise ValueError('Esta versión admite una planta con base Y=0')
        if not .05 <= math.hypot(self.end.x-self.start.x, self.end.z-self.start.z) <= 1000:
            raise ValueError('La longitud de un muro debe estar entre 0,05 y 1000 metros')
        return self

class Column(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    position: Vector3
    width: float = Field(default=.3, ge=.05, le=5, allow_inf_nan=False)
    depth: float = Field(default=.3, ge=.05, le=5, allow_inf_nan=False)
    height: float = Field(default=2.8, ge=.05, le=30, allow_inf_nan=False)

    @model_validator(mode='after')
    def on_floor(self):
        if abs(self.position.y) > 1e-6:
            raise ValueError('La columna debe apoyarse en Y=0')
        return self

class Door(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    wall_id: str
    position: float
    width: float = 0.9
    height: float = 2.1
    frame_material: str = "wood"
    swing_direction: str = "left"

class Window(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    wall_id: str
    position: float
    width: float = 1.2
    height: float = 1.5
    sill_height: float = 0.9
    frame_material: str = "white_vinyl"

class Room(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Room"
    points: List[Vector3]
    area_sqm: float = 0
    ceiling_height: float = 2.8
    floor_material: str = "oak_hardwood"
    wall_material: str = "white_paint"

class ArchitecturalInfo(BaseModel):
    model_config = ConfigDict(extra='allow')
    project_name: str = Field(default='Proyecto sin nombre', max_length=200)
    floor_name: str = Field(default='Planta baja', max_length=100)
    jurisdiction: str = Field(default='', max_length=200)
    north_degrees: float = Field(default=0, ge=0, lt=360, allow_inf_nan=False)
    construction_notes: str = Field(default='', max_length=10000)
    # Explicitly recorded, never inferred from a rendered surface.
    missing_information: List[str] = Field(default_factory=lambda: [
        'Revisión profesional', 'Estructura y cimentación', 'Instalaciones',
        'Cubierta y detalles constructivos', 'Normativa y permisos'
    ], max_length=100)

class FurnitureItem(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    category: str
    position: Vector3
    rotation: Vector3 = Vector3()
    scale: Vector3 = Vector3(x=1, y=1, z=1)
    style: str = "modern"
    material: str = "default"
    color: str = "#ffffff"
    dimensions: Vector3 = Vector3(x=1, y=1, z=1)

class FloorPlanData(BaseModel):
    model_config = ConfigDict(extra='allow', allow_inf_nan=False)
    walls: List[Wall] = []
    doors: List[Door] = []
    windows: List[Window] = []
    rooms: List[Room] = []
    dimensions: Dict[str, float] = {}
    columns: List[Column] = Field(default_factory=list, max_length=2000)
    warnings: List[str] = Field(default_factory=list, max_length=100)
    architectural_info: ArchitecturalInfo = Field(default_factory=ArchitecturalInfo)
    furniture: List[FurnitureItem] = Field(default_factory=list, max_length=3000)

    @model_validator(mode='after')
    def valid_geometry(self):
        json.dumps(self.model_dump(), allow_nan=False)
        if max(len(self.walls), len(self.doors), len(self.windows), len(self.rooms)) > 3000:
            raise ValueError('Demasiados elementos en el modelo')
        items = [*self.walls, *self.columns, *self.doors, *self.windows, *self.rooms]
        if len({item.id for item in items}) != len(items):
            raise ValueError('Los identificadores deben ser únicos')
        if not all(math.isfinite(value) for value in self.dimensions.values()):
            raise ValueError('Las dimensiones deben ser finitas')
        walls = {wall.id: wall for wall in self.walls}
        for opening in [*self.doors, *self.windows]:
            wall = walls.get(opening.wall_id)
            if wall is None:
                raise ValueError('La abertura debe pertenecer a un muro')
            length = math.hypot(wall.end.x-wall.start.x, wall.end.z-wall.start.z)
            sill = getattr(opening, 'sill_height', 0)
            values = [opening.position, opening.width, opening.height, sill]
            if not all(math.isfinite(v) for v in values) or not 0 <= opening.position <= 1:
                raise ValueError('Abertura inválida')
            if opening.width <= 0 or opening.height <= 0 or sill < 0 or sill+opening.height > wall.height:
                raise ValueError('La abertura excede la altura del muro')
            center = opening.position*length
            if center-opening.width/2 < -1e-6 or center+opening.width/2 > length+1e-6:
                raise ValueError('La abertura excede la longitud del muro')
        return self

class StylePreset(str, Enum):
    MODERN_FARMHOUSE = "modern_farmhouse"
    COASTAL = "coastal"
    MID_CENTURY = "mid_century"
    INDUSTRIAL = "industrial"
    CRAFTSMAN = "craftsman"
    CONTEMPORARY = "contemporary"
    MINIMALIST = "minimalist"
    SCANDINAVIAN = "scandinavian"

class Project(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Untitled Project"
    created_at: str = ""
    updated_at: str = ""
    floor_plan: FloorPlanData = FloorPlanData()
    furniture: List[FurnitureItem] = []
    style: Optional[StylePreset] = None
    thumbnail: Optional[str] = None

class PlanUploadResponse(BaseModel):
    project_id: str
    status: str
    detected_walls: int
    detected_rooms: int
    detected_doors: int
    detected_windows: int
    floor_plan: FloorPlanData
    message: str
    revision: int = 0
    learning: Dict[str, Any] = Field(default_factory=dict)

class PlanReview(BaseModel):
    base_revision: int = Field(ge=0)
    floor_plan: FloorPlanData
    approved: bool = False
    measurements_confirmed: bool = False
    allow_learning: bool = False
    notes: str = Field(default='', max_length=2000)

    @model_validator(mode='after')
    def eligible(self):
        if self.approved and not self.measurements_confirmed:
            raise ValueError('Confirma medidas y escala antes de aprobar')
        if self.approved and not (self.floor_plan.walls or self.floor_plan.columns):
            raise ValueError('No se puede aprobar un modelo vacío')
        return self

class VideoRequest(BaseModel):
    project_id: str
    quality: Literal["720p", "1080p", "4K"] = "1080p"
    duration: int = 30
    path_points: List[Vector3] = []
    look_at_points: List[Vector3] = []
    music_track: Optional[str] = None
    include_labels: bool = True

class VideoResponse(BaseModel):
    video_id: str
    status: str
    progress: float = 0
    url: Optional[str] = None
    estimated_time: int = 60
