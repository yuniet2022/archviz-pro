from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import uuid
import shutil

from app.services.plan_processor import PlanProcessor
from app.models.schemas import PlanUploadResponse

router = APIRouter(prefix="/plans", tags=["plans"])
processor = PlanProcessor()

UPLOAD_DIR = "/app/uploads"

@router.post("/upload", response_model=PlanUploadResponse)
async def upload_plan(file: UploadFile = File(...)):
    if file.content_type not in ["image/jpeg", "image/png", "image/jpg", "application/pdf"]:
        raise HTTPException(400, "Invalid file type. Use JPG, PNG or PDF")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    project_id = str(uuid.uuid4())
    ext = file.filename.split(".")[-1]
    file_path = os.path.join(UPLOAD_DIR, f"{project_id}.{ext}")

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        floor_plan = processor.process_image(file_path)

        return PlanUploadResponse(
            project_id=project_id,
            status="success",
            detected_walls=len(floor_plan.walls),
            detected_rooms=len(floor_plan.rooms),
            detected_doors=len(floor_plan.doors),
            detected_windows=len(floor_plan.windows),
            floor_plan=floor_plan,
            message=f"Successfully processed plan. Detected {len(floor_plan.walls)} walls, {len(floor_plan.rooms)} rooms."
        )
    except Exception as e:
        raise HTTPException(500, f"Processing failed: {str(e)}")

@router.get("/{project_id}")
async def get_plan(project_id: str):
    return {"project_id": project_id, "status": "loaded"}
