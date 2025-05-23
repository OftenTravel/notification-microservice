from fastapi import APIRouter
from app.api.endpoints import notifications, templates

router = APIRouter()



# Include notifications router with appropriate tags
router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
router.include_router(templates.router, prefix="/templates", tags=["Templates"])