from fastapi import APIRouter, HTTPException
from app.services.video_generator import VideoGenerator
from app.models.schemas import VideoRequest, VideoResponse

router = APIRouter(prefix="/video", tags=["video"])
generator = VideoGenerator()

@router.post("/generate")
async def generate_video(request: VideoRequest):
    try:
        task = generator.generate_tour_video.delay(
            project_data={"path_points": [p.dict() for p in request.path_points]},
            quality=request.quality,
            duration=request.duration
        )

        return VideoResponse(
            video_id=task.id,
            status="processing",
            estimated_time=request.duration * 2
        )
    except Exception as e:
        raise HTTPException(500, f"Video generation failed: {str(e)}")

@router.get("/status/{video_id}")
async def video_status(video_id: str):
    return generator.get_video_status(video_id)
