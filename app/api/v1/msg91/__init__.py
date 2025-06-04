from fastapi import APIRouter
from .templates import router as templates_router
from .webhooks import router as webhooks_router

# Create main MSG91 router
router = APIRouter()

# Include sub-routers
router.include_router(templates_router, prefix="/templates")
router.include_router(webhooks_router, tags=["msg91-webhooks"])
