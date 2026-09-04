import os
import subprocess
import uuid
from typing import List
from celery import Celery
from app.models.schemas import Vector3

celery_app = Celery("video_generator", broker="redis://redis:6379/0")

class VideoGenerator:
    def __init__(self, output_dir: str = "/app/exports/videos"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    @celery_app.task(bind=True)
    def generate_tour_video(self, project_data: dict, quality: str = "1080p", duration: int = 30):
        video_id = str(uuid.uuid4())
        output_path = os.path.join(self.output_dir, f"{video_id}.mp4")

        resolutions = {
            "720p": ("1280", "720"),
            "1080p": ("1920", "1080"),
            "4K": ("3840", "2160")
        }
        width, height = resolutions.get(quality, ("1920", "1080"))

        path_points = project_data.get("path_points", [])
        if not path_points:
            path_points = [
                {"x": -5, "y": 1.7, "z": -5},
                {"x": 0, "y": 1.7, "z": 0},
                {"x": 5, "y": 1.7, "z": 5},
                {"x": 5, "y": 1.7, "z": -5},
                {"x": -5, "y": 1.7, "z": 5},
            ]

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "lavfi",
            "-i", f"testsrc=duration={duration}:size={width}x{height}:rate=30",
            "-f", "lavfi", 
            "-i", "anullsrc=r=48000:cl=stereo",
            "-vf", f"format=yuv420p, drawtext=text='ArchViz Pro Tour':fontsize=40:fontcolor=white:x=(w-text_w)/2:y=50",
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return {"video_id": video_id, "status": "completed", "url": f"/exports/videos/{video_id}.mp4"}
        except subprocess.CalledProcessError as e:
            return {"video_id": video_id, "status": "failed", "error": str(e.stderr)}

    def get_video_status(self, video_id: str) -> dict:
        path = os.path.join(self.output_dir, f"{video_id}.mp4")
        if os.path.exists(path):
            size = os.path.getsize(path)
            return {"status": "completed", "size_mb": size / (1024*1024)}
        return {"status": "processing", "progress": 0.5}
