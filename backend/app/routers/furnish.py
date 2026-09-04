from fastapi import APIRouter, HTTPException
from typing import List

from app.services.furnish_engine import FurnishEngine
from app.models.schemas import StylePreset, Room

router = APIRouter(prefix="/furnish", tags=["furnish"])
engine = FurnishEngine()

@router.post("/auto/{style}")
async def auto_furnish(rooms: List[Room], style: StylePreset):
    try:
        furniture = engine.auto_furnish(rooms, style)
        return {
            "style": style,
            "furniture_count": len(furniture),
            "furniture": furniture,
            "style_config": engine.get_style_config(style)
        }
    except Exception as e:
        raise HTTPException(500, f"Furnishing failed: {str(e)}")

@router.get("/styles")
async def list_styles():
    return {
        "styles": [
            {"id": StylePreset.MODERN_FARMHOUSE, "name": "Modern Farmhouse", "description": "Rustic warmth meets clean lines"},
            {"id": StylePreset.COASTAL, "name": "Coastal", "description": "Beach-inspired airy spaces"},
            {"id": StylePreset.MID_CENTURY, "name": "Mid-Century Modern", "description": "Retro elegance with organic shapes"},
            {"id": StylePreset.INDUSTRIAL, "name": "Industrial", "description": "Raw materials and urban edge"},
            {"id": StylePreset.CRAFTSMAN, "name": "Craftsman", "description": "Handcrafted wood detailing"},
            {"id": StylePreset.CONTEMPORARY, "name": "Contemporary", "description": "Sleek, current, bold"},
            {"id": StylePreset.MINIMALIST, "name": "Minimalist", "description": "Less is more"},
            {"id": StylePreset.SCANDINAVIAN, "name": "Scandinavian", "description": "Hygge and functionality"},
        ]
    }
