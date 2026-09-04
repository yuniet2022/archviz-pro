from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from enum import Enum
import uuid

class Vector3(BaseModel):
    x: float = 0
    y: float = 0
    z: float = 0

class Wall(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    start: Vector3
    end: Vector3
    height: float = 2.8
    thickness: float = 0.15
    has_drywall: bool = True

class Door(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    wall_id: str
    position: float
    width: float = 0.9
    height: float = 2.1
    frame_material: str = "wood"
    swing_direction: str = "left"

class Window(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    wall_id: str
    position: float
    width: float = 1.2
    height: float = 1.5
    sill_height: float = 0.9
    frame_material: str = "white_vinyl"

class Room(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Room"
    points: List[Vector3]
    area_sqm: float = 0
    ceiling_height: float = 2.8
    floor_material: str = "oak_hardwood"
    wall_material: str = "white_paint"

class FurnitureItem(BaseModel):
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
    walls: List[Wall] = []
    doors: List[Door] = []
    windows: List[Window] = []
    rooms: List[Room] = []
    dimensions: Dict[str, float] = {}

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
