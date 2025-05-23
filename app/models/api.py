from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from app.models.responses import NotificationStatus

class ErrorResponse(BaseModel):
    """Standard error response model."""
    detail: str

class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    version: str
    providers: List[str]

class ProviderInfoResponse(BaseModel):
    """Provider information response model."""
    id: str
    name: str
    features: List[str]
    enabled: bool
