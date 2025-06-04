from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv

# Force load environment variables from .env file
load_dotenv(override=True)


class Settings(BaseSettings):
    # API Config
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Notification Microservice"
    ENVIRONMENT: str = "development"  # Options: development, production, testing
    SEED_PROVIDERS: bool = True  # Set to true to force seeding

    # Security
    API_KEY_SALT: str = "change-this-to-a-secure-random-string"
    MSG91_WEBHOOK_SECRET: Optional[str] = None  # Secret for MSG91 webhook signature verification

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://notification_user:dev_password@postgres:5432/notification_service"

    # PostgreSQL connection parameters
    POSTGRES_PASSWORD: Optional[str] = None  # Added to prevent validation error

    # Celery Configuration
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"
    CELERY_WORKER_CONCURRENCY: int = 4  # Configurable concurrency level

    # Force loading environment variables
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }


# Initialize settings
settings = Settings()
