import os
from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv

# Force load environment variables from .env file
load_dotenv(override=True)

# Debug print to see what the raw environment variable contains
api_key_env = os.getenv("MSG91_API_KEY", "not_found")
print(f"Raw environment variable MSG91_API_KEY: '{api_key_env}'")


class Settings(BaseSettings):
    # API Config
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Notification Microservice"
    ENVIRONMENT: str = "development"  # Options: development, production, testing
    SEED_PROVIDERS: bool = True  # Set to true to force seeding

    # Security
    INTERNAL_API_KEY: str = "your-default-development-key"
    API_KEY_SALT: str = "change-this-to-a-secure-random-string"
    SERVICE_REGISTRATION_PASSWORD: str = "your-registration-password"

    # Database
    DATABASE_URL: str

    # PostgreSQL connection parameters
    POSTGRES_PASSWORD: Optional[str] = None  # Added to prevent validation error

    # MSG91 Configuration
    # Use direct environment variable without a default
    MSG91_API_KEY: str
    MSG91_SENDER_ID: str = "often"

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


# Initialize settings and print loaded values for debugging
settings = Settings()
print(f"Loaded MSG91_API_KEY: '{settings.MSG91_API_KEY}'")  # Debug statement
