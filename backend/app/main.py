from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.routers import plan, furnish, video

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="ArchViz Pro API - Professional Architectural Visualization"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.EXPORT_DIR, exist_ok=True)
app.mount("/exports", StaticFiles(directory=settings.EXPORT_DIR), name="exports")

app.include_router(plan.router, prefix=settings.API_V1_PREFIX)
app.include_router(furnish.router, prefix=settings.API_V1_PREFIX)
app.include_router(video.router, prefix=settings.API_V1_PREFIX)

@app.get("/")
async def root():
    return {
        "name": "ArchViz Pro API",
        "version": "1.0.0",
        "status": "operational",
        "features": [
            "2D Plan Processing",
            "3D Model Generation",
            "Auto-Furnish by Style",
            "Video Tour Export",
            "GLB Export"
        ]
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}
