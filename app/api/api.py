from fastapi import APIRouter

from app.api.v1 import notifications, templates

api_router = APIRouter()

# Include v1 endpoints
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(templates.router, prefix="/templates", tags=["Templates"])
