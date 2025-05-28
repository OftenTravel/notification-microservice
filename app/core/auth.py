from fastapi import HTTPException, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.core.database import get_db
from app.models.service_user import ServiceUser
from app.core.celery_database import get_redis_client
from datetime import datetime, timedelta
import json


class RateLimiter:
    """Rate limiter for failed authentication attempts."""
    
    def __init__(self, max_attempts: int = 20, window_hours: int = 2):
        self.max_attempts = max_attempts
        self.window_seconds = window_hours * 3600
    
    async def check_rate_limit(self, service_id: str, redis_client):
        """Check if service has exceeded rate limit for failed auth attempts."""
        key = f"auth_failures:{service_id}"
        
        # Get current attempt count
        attempts = await redis_client.get(key)
        if attempts:
            attempts = int(attempts)
            if attempts >= self.max_attempts:
                # Check TTL to give accurate error message
                ttl = await redis_client.ttl(key)
                minutes_remaining = ttl // 60
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many failed authentication attempts. Please try again in {minutes_remaining} minutes."
                )
        
        return True
    
    async def record_failure(self, service_id: str, redis_client):
        """Record a failed authentication attempt."""
        key = f"auth_failures:{service_id}"
        
        # Increment counter
        await redis_client.incr(key)
        
        # Set expiry on first failure
        current_count = await redis_client.get(key)
        if current_count and int(current_count) == 1:
            await redis_client.expire(key, self.window_seconds)
    
    async def reset_failures(self, service_id: str, redis_client):
        """Reset failed attempts on successful authentication."""
        key = f"auth_failures:{service_id}"
        await redis_client.delete(key)


# Global rate limiter instance
rate_limiter = RateLimiter()


async def get_current_service(
    service_id: Optional[str] = Header(None, alias="X-Service-Id"),
    api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis_client)
) -> ServiceUser:
    """
    Dependency to get the current authenticated service.
    
    Headers required:
    - X-Service-Id: The service UUID
    - X-API-Key: The service API key
    """
    
    # Check if headers are provided
    if not service_id or not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication headers. Please provide X-Service-Id and X-API-Key headers."
        )
    
    # Check rate limit before attempting authentication
    await rate_limiter.check_rate_limit(service_id, redis_client)
    
    # Authenticate the service
    service = await ServiceUser.authenticate_service(db, api_key)
    
    if not service:
        # Record failed attempt
        await rate_limiter.record_failure(service_id, redis_client)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service credentials"
        )
    
    # Verify service_id matches
    if str(service.id) != service_id:
        await rate_limiter.record_failure(service_id, redis_client)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Service ID mismatch"
        )
    
    # Check if service is active
    if not service.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service is inactive. Please contact support."
        )
    
    # Reset failures on successful auth
    await rate_limiter.reset_failures(service_id, redis_client)
    
    return service


async def get_optional_service(
    service_id: Optional[str] = Header(None, alias="X-Service-Id"),
    api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
    redis_client = Depends(get_redis_client)
) -> Optional[ServiceUser]:
    """
    Optional authentication - returns None if no credentials provided.
    """
    if not service_id or not api_key:
        return None
    
    try:
        return await get_current_service(service_id, api_key, db, redis_client)
    except HTTPException:
        return None