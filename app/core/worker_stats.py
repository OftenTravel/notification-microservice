"""
Worker statistics persistence using Redis
"""
import json
from datetime import datetime
from typing import Dict, Any
import redis
from app.core.config import settings


class WorkerStats:
    """Persist worker statistics in Redis"""
    
    def __init__(self):
        self.redis_client = redis.from_url(settings.CELERY_BROKER_URL)
        self.stats_key_prefix = "worker:stats:"
    
    def increment_stat(self, worker_name: str, stat_type: str, count: int = 1):
        """Increment a worker statistic"""
        key = f"{self.stats_key_prefix}{worker_name}:{stat_type}"
        self.redis_client.hincrby(key, "count", count)
        self.redis_client.hset(key, "last_updated", datetime.utcnow().isoformat())
    
    def get_stats(self, worker_name: str) -> Dict[str, Any]:
        """Get all statistics for a worker"""
        stats = {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "retried": 0,
        }
        
        for stat_type in stats.keys():
            key = f"{self.stats_key_prefix}{worker_name}:{stat_type}"
            data = self.redis_client.hgetall(key)
            if data:
                stats[stat_type] = int(data.get(b'count', 0))
        
        return stats
    
    def reset_stats(self, worker_name: str):
        """Reset statistics for a worker"""
        for stat_type in ["processed", "succeeded", "failed", "retried"]:
            key = f"{self.stats_key_prefix}{worker_name}:{stat_type}"
            self.redis_client.delete(key)


# Global instance
worker_stats = WorkerStats()