from fastapi import APIRouter

from app.api.v1 import notifications
from app.api.v1.msg91 import router as msg91_router
# Add import for the health router
from app.api.v1.health import router as health_router
from app.api.v1.stats import router as stats_router
from app.api.v1.webhooks import router as webhooks_router

api_router = APIRouter()

# Include v1 endpoints
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(msg91_router, prefix="/msg91", tags=["MSG91-Templates"])
# Add the health router
api_router.include_router(health_router, prefix="/system", tags=["System"])
# Add the stats router
api_router.include_router(stats_router, prefix="/stats", tags=["Statistics"])
# Add the webhooks router
api_router.include_router(webhooks_router, prefix="/webhooks", tags=["Webhooks"])
