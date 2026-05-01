from typing import List, ClassVar, Optional
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env_path: ClassVar[Path] = Path(__file__).resolve().parents[1] / ".env"
    model_config = SettingsConfigDict(env_file=str(env_path), extra="ignore")

    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB: str = "yelp_db"

    SECRET_KEY: str = "changeme"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 5
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    SERVICE_NAME: str = "all"

    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_CLIENT_ID: str = "yelp-service"
    KAFKA_CONSUMER_GROUP: str = "yelp-worker"

    YELP_API_KEY: Optional[str] = None
    OLLAMA_URL: Optional[str] = None
    OLLAMA_MODEL: Optional[str] = None
    TAVILY_URL: Optional[str] = None
    TAVILY_API_KEY: Optional[str] = None


settings = Settings()
