from fastapi import APIRouter

# Create main API router
router = APIRouter()

# Import and include routers from route modules
from app.api.routes.notifications import router as notifications_router
router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])

# As you add more route modules, import and include them here
