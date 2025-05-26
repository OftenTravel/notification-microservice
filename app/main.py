from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List

from app.core.config import settings
from app.core.database import engine, Base, get_db
from app.models.messages import SMSMessage, EmailMessage, WhatsAppMessage
from app.models.responses import NotificationResponse, NotificationStatus
from app.services.notification_service import NotificationService
from app.core.exceptions import NotificationException, ProviderNotFoundError
from app.repositories.provider_repository import ProviderRepository
from sqlalchemy.ext.asyncio import AsyncSession

# Import models to ensure they are registered with SQLAlchemy metadata
from app.models.provider import Provider  
from app.models.notification import Notification
from app.models.delivery_attempt import DeliveryAttempt

from app.api.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic: Create tables (for development)
    # In production, use Alembic migrations
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    # Seed mock provider for testing if it doesn't exist
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        repo = ProviderRepository(db)
        
        mock_provider = await repo.get_provider_by_name("mock")
        if not mock_provider:
            print("Seeding mock provider for testing...")
            await repo.create_provider({
                "name": "mock",
                "supported_types": ["sms", "email", "whatsapp"],
                "is_active": True,
                "priority": 10,
                "config": {
                    "success_rate": 0.9,
                    "delay_ms": 500
                }
            })
            print("Mock provider seeded successfully")
        else:
            print(f"Mock provider already exists with UUID: {mock_provider.id}")
    
    yield
    # Shutdown logic (if needed)
    # Place any cleanup code here


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Notification microservice for managing and sending notifications",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Set CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Create notification service instance with correct parameter name
notification_service = NotificationService(default_provider_name="mock")


@app.get("/", tags=["System"])
async def root():
    """Root endpoint that returns service information and basic health status."""
    return {
        "service": settings.PROJECT_NAME,
        "version": "0.1.0",
        "status": "operational",
        "documentation": "/docs or /redoc",
    }


