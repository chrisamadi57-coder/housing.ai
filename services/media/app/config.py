from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    storage_backend: str = "local"
    upload_dir: str = "./uploads"
    gps_max_distance_meters: int = 100
    redis_url: str = "redis://localhost:6379/0" 

    # Object storage (S3-compatible)
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket_name: str = ""
    s3_region: str = "auto"

    # ffmpeg binaries (absolute paths — do NOT rely on PATH)
    ffmpeg_bin: str = "ffmpeg"      # default: assume it's on PATH
    ffprobe_bin: str = "ffprobe"



    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()