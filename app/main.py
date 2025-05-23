from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List

from app.core.config import settings
from app.core.database import engine, Base
from app.models.messages import SMSMessage, EmailMessage, WhatsAppMessage
from app.models.responses import NotificationResponse, NotificationStatus
from app.services.notification_service import NotificationService
from app.providers.registry import ProviderRegistry
from app.core.exceptions import NotificationException, ProviderNotFoundError

# Import models to ensure they are registered with SQLAlchemy metadata
from app.models.provider import Provider  # This import is crucial
from app.models.notification import Notification  # This import is crucial

from app.api.routes import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic: Create tables (for development)
    # In production, use Alembic migrations
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
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


@app.get("/", tags=["Health Check"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": "0.1.0",
    }


# Create notification service instance
notification_service = NotificationService(default_provider_id="mock")


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint that returns service information."""
    return {
        "service": "Notification Microservice",
        "version": "0.1.0",
        "status": "operational",
        "documentation": "/docs or /redoc",
    }


@app.get("/providers", tags=["Providers"], response_model=List[str])
async def list_providers():
    """List all available notification providers."""
    return list(ProviderRegistry.list_providers().keys())


@app.post(
    "/send/sms", tags=["Notifications"], response_model=NotificationResponse
)
async def send_sms(
    message: SMSMessage,
    background_tasks: BackgroundTasks,
    provider_id: Optional[str] = None,
):
    """
    Send an SMS message.

    - **recipient**: Phone number of the recipient
    - **content**: SMS content to send
    - **provider_id** (optional): Override the default provider
    - **sender_id** (optional): Sender ID to use if supported by the provider
    """
    try:
        response = await notification_service.send_sms(message, provider_id)
        return response
    except ProviderNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotificationException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


@app.post(
    "/send/email", tags=["Notifications"], response_model=NotificationResponse
)
async def send_email(
    message: EmailMessage,
    background_tasks: BackgroundTasks,
    provider_id: Optional[str] = None,
):
    """
    Send an email message.

    - **to**: List of recipient email addresses
    - **subject**: Email subject
    - **body**: Email body content (plain text)
    - **html_body** (optional): HTML version of the email body
    - **provider_id** (optional): Override the default provider
    """
    try:
        response = await notification_service.send_email(message, provider_id)
        return response
    except ProviderNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotificationException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


@app.post(
    "/send/whatsapp", tags=["Notifications"], response_model=NotificationResponse
)
async def send_whatsapp(
    message: WhatsAppMessage,
    background_tasks: BackgroundTasks,
    provider_id: Optional[str] = None,
):
    """
    Send a WhatsApp message.

    - **recipient**: Phone number of the recipient (with country code)
    - **content**: Message content to send
    - **media_url** (optional): URL to media to include
    - **template_id** (optional): Template ID if using WhatsApp templates
    - **provider_id** (optional): Override the default provider
    """
    try:
        response = await notification_service.send_whatsapp(message, provider_id)
        return response
    except ProviderNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotificationException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
