from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API Config
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Notification Microservice"

    # Database
    DATABASE_URL: str

    # MSG91 Configuration
    MSG91_API_KEY: Optional[str] = None
    MSG91_SENDER_ID: Optional[str] = "NOTIFY"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
