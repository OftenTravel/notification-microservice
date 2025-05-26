from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging
from datetime import datetime

from app.core.database import get_db

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/health", tags=["System"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Comprehensive health check endpoint that verifies:
    - API status
    - Database connectivity
    - Database query functionality
    """
    start_time = datetime.now()
    health_info = {
        "status": "healthy",
        "timestamp": start_time.isoformat(),
        "components": {
            "api": {"status": "healthy"},
            "database": {"status": "unknown"}
        },
        "checks": []
    }
    
    # Check database connectivity
    try:
        # Execute a simple query to verify db connection
        result = await db.execute(text("SELECT 1"))
        db_result = result.scalar()
        
        if db_result == 1:
            health_info["components"]["database"] = {
                "status": "healthy",
                "message": "Connection successful, query executed"
            }
            health_info["checks"].append({
                "name": "database_query", 
                "status": "pass"
            })
        else:
            health_info["components"]["database"] = {
                "status": "degraded",
                "message": f"Unexpected query result: {db_result}"
            }
            health_info["checks"].append({
                "name": "database_query", 
                "status": "warn",
                "message": f"Unexpected result: {db_result}"
            })
            health_info["status"] = "degraded"
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        health_info["components"]["database"] = {
            "status": "critical",
            "message": f"Database query failed: {str(e)}"
        }
        health_info["checks"].append({
            "name": "database_query", 
            "status": "fail",
            "message": str(e)
        })
        health_info["status"] = "critical"
        
    # Calculate response time
    end_time = datetime.now()
    response_time = (end_time - start_time).total_seconds() * 1000
    health_info["response_time_ms"] = round(response_time, 2)
    
    # If critical, return appropriate status code
    if health_info["status"] == "critical":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health_info
        )
        
    return health_info
