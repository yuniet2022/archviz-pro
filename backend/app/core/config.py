from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    APP_NAME: str = "ArchViz Pro API"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "postgresql://archviz:archviz@db:5432/archviz"
    REDIS_URL: str = "redis://redis:6379/0"

    UPLOAD_DIR: str = "/app/uploads"
    EXPORT_DIR: str = "/app/exports"
    ASSET_DIR: str = "/app/assets"

    FFMPEG_PATH: str = "ffmpeg"
    VIDEO_OUTPUT_DIR: str = "/app/exports/videos"

    YOLO_MODEL_PATH: str = "/app/models/yolov8_floorplan.pt"
    OCR_ENABLED: bool = True

    SECRET_KEY: str = "archviz-pro-secret-key-2024"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080

    class Config:
        env_file = ".env"

settings = Settings()
