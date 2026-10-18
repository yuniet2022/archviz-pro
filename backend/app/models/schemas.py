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
    shape: Literal['rectangular', 'circular'] = 'rectangular'
    rotation: float = Field(default=0, allow_inf_nan=False)

    @model_validator(mode='after')
    def on_floor(self):
        if abs(self.position.y) > 1e-6:
            raise ValueError('La columna debe apoyarse en Y=0')
        if self.shape=='circular':
            self.depth=self.width
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
    operation: Literal['hinged','double_hinged','sliding','overhead','bifold'] = 'hinged'

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

class FloorRegion(BaseModel):
    points: List[Vector3] = Field(min_length=3, max_length=10000)
    holes: List[List[Vector3]] = Field(default_factory=list, max_length=100)

    @model_validator(mode='after')
    def valid_polygon(self):
        from shapely.geometry import Polygon
        if any(abs(p.y)>1e-6 for ring in [self.points,*self.holes] for p in ring):
            raise ValueError('El suelo debe estar en Y=0')
        if any(not 3<=len(ring)<=10000 for ring in self.holes):
            raise ValueError('Contorno de patio inválido')
        polygon=Polygon([(p.x,p.z) for p in self.points], [[(p.x,p.z) for p in ring] for ring in self.holes])
        if not polygon.is_valid or polygon.area<.001:
            raise ValueError('El contorno del suelo no es un polígono válido')
        return self


class FixedFixture(FurnitureItem):
    kind: Literal['vanity','toilet','island','counter','cooktop','dishwasher','fridge']
    outline: List[Vector3] = Field(default_factory=list, max_length=1000)
    body_outline: List[Vector3] = Field(default_factory=list, max_length=1000)
    top_outline: List[Vector3] = Field(default_factory=list, max_length=1000)
    basin_count: int = Field(default=0, ge=0, le=2)
    source_basin_count: int = Field(default=0, ge=0, le=2)
    basin_centers: List[Vector3] = Field(default_factory=list, max_length=2)
    source_basin_centers: List[Vector3] = Field(default_factory=list, max_length=2)
    basin_sizes: List[Vector3] = Field(default_factory=list, max_length=2)
    source_basin_sizes: List[Vector3] = Field(default_factory=list, max_length=2)
    source_basin_outlines: List[List[Vector3]] = Field(default_factory=list, max_length=2)

    @model_validator(mode='after')
    def valid_equipment(self):
        from shapely.geometry import Polygon, Point
        if any(not .01<=value<=30 for value in (self.dimensions.x,self.dimensions.y,self.dimensions.z)):
            raise ValueError('Dimensiones de equipo fijo fuera de rango')
        for ring in (self.outline,self.body_outline,self.top_outline,*self.source_basin_outlines):
            if ring and (len(ring)<3 or len(ring)>1000 or any(abs(p.y)>1e-6 for p in ring)
                         or not Polygon([(p.x,p.z) for p in ring]).is_valid):
                raise ValueError('Contorno de equipo fijo inválido')
        if self.basin_count!=len(self.basin_centers):
            raise ValueError('El número de lavamanos no coincide con sus posiciones')
        if self.kind=='vanity' and self.basin_count==2 and self.source_basin_count!=2 and self.dimensions.x<1.2:
            raise ValueError('La meseta no tiene ancho suficiente para la variante doble')
        if self.outline and any(not Polygon([(p.x,p.z) for p in self.outline]).buffer(.005).covers(
                Point(center.x,center.z)) for center in self.basin_centers):
            raise ValueError('El lavamanos debe quedar dentro de la meseta')
        return self

class FloorPlanData(BaseModel):
    model_config = ConfigDict(extra='allow', allow_inf_nan=False)
    walls: List[Wall] = []
    doors: List[Door] = []
    windows: List[Window] = []
    rooms: List[Room] = []
    dimensions: Dict[str, float] = {}
    columns: List[Column] = Field(default_factory=list, max_length=2000)
    floor_regions: List[FloorRegion] = Field(default_factory=list, max_length=100)
    warnings: List[str] = Field(default_factory=list, max_length=100)
    architectural_info: ArchitecturalInfo = Field(default_factory=ArchitecturalInfo)
    furniture: List[FurnitureItem] = Field(default_factory=list, max_length=3000)
    fixtures: List[FixedFixture] = Field(default_factory=list, max_length=1000)

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
    WARM_MODERN = "warm_modern"
    CLASSIC = "classic"
    JAPANDI = "japandi"
    MEDITERRANEAN = "mediterranean"
    TROPICAL = "tropical"
    LUXURY = "luxury"
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
    detected_columns: int = 0
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
