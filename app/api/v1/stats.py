"""
Worker statistics API endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from app.core.worker_stats import worker_stats

router = APIRouter()


@router.get("/worker/{worker_name}")
async def get_worker_stats(worker_name: str) -> Dict[str, Any]:
    """Get statistics for a specific worker"""
    try:
        stats = worker_stats.get_stats(worker_name)
        return {
            "worker": worker_name,
            "statistics": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workers")
async def get_all_workers_stats() -> Dict[str, Any]:
    """Get statistics for all workers"""
    try:
        # For now, we'll just get stats for our known worker
        # In a real system, you'd track all worker names
        known_workers = ["worker1@celery-worker-1"]
        all_stats = {}
        
        for worker in known_workers:
            all_stats[worker] = worker_stats.get_stats(worker)
        
        return {"workers": all_stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/worker/{worker_name}/reset")
async def reset_worker_stats(worker_name: str) -> Dict[str, str]:
    """Reset statistics for a specific worker"""
    try:
        worker_stats.reset_stats(worker_name)
        return {"message": f"Statistics reset for worker {worker_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))