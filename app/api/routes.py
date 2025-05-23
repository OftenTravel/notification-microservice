from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List
import uuid

from app.core.database import get_db
from app.models.notification import NotificationType
from app.services.notification import NotificationService
from pydantic import BaseModel, Field

from app.api.endpoints import notifications, templates

router = APIRouter()

# Include notifications router with appropriate tags
router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])

# Include templates router
router.include_router(templates.router, prefix="/templates", tags=["Templates"])

