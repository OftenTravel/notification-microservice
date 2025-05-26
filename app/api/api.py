from fastapi import APIRouter

from app.api.v1 import notifications
from app.api.v1.msg91 import templates as msg91_templates

api_router = APIRouter()

# Include v1 endpoints
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(msg91_templates.router, prefix="/msg91/templates", tags=["MSG91-Templates"])
