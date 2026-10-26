from fastapi import FastAPI
import os

from app.core.config import settings
from app.routers import plan, furnish, video, roof, auth
from app.core.auth import authenticate

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="ArchViz Pro API - Professional Architectural Visualization"
)

app.middleware('http')(authenticate)

os.makedirs(settings.EXPORT_DIR, exist_ok=True)

app.include_router(plan.router, prefix=settings.API_V1_PREFIX)
app.include_router(furnish.router, prefix=settings.API_V1_PREFIX)
app.include_router(video.router, prefix=settings.API_V1_PREFIX)
app.include_router(roof.router, prefix=settings.API_V1_PREFIX)
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)

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
            "Measured Furniture Catalogue",
            "Collision-Aware Walking Routes",
            "Browser Scene Recording",
            "Archviz Project Archive"
        ]
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}
