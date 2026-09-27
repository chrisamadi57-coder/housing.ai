from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    storage_backend: str = "local"
    upload_dir: str = "./uploads"
    gps_max_distance_meters: int = 100
    redis_url: str = "redis://localhost:6379/0" 

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()