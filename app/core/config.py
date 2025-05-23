from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API Config
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Notification Microservice"

    # Database
    DATABASE_URL: str
    
    # PostgreSQL connection parameters
    POSTGRES_PASSWORD: Optional[str] = None  # Added to prevent validation error
    
    # MSG91 Configuration
    MSG91_API_KEY: Optional[str] = None
    MSG91_SENDER_ID: Optional[str] = "NOTIFY"

    # Celery Configuration
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"
    CELERY_WORKER_CONCURRENCY: int = 4  # Configurable concurrency level

    class Config:
        env_file = ".env"
        case_sensitive = True
        # Alternatively, you could use the following to ignore extra fields:
        # extra = "ignore"


settings = Settings()
