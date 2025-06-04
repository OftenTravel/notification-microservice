"""
Database configuration specifically for Celery tasks.
Creates a new engine for each task to avoid event loop conflicts.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from typing import AsyncGenerator
from app.core.config import settings
from redis import asyncio as redis


def create_celery_async_engine():
    """Create a new async engine for Celery tasks"""
    return create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        future=True,
        pool_pre_ping=True,
        pool_size=1,  # Smaller pool for individual tasks
        max_overflow=0,  # No overflow for task-specific engines
    )


def create_celery_session():
    """Create a new session factory for Celery tasks"""
    engine = create_celery_async_engine()
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_celery_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session for Celery tasks"""
    SessionLocal = create_celery_session()
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
            # Close the engine to prevent connection pool issues
            if hasattr(session, 'get_bind') and session.get_bind():
                await session.get_bind().dispose()  # type: ignore


# Redis client singleton
_redis_client = None


async def get_redis_client():
    """Get or create Redis client for async operations"""
    global _redis_client
    if _redis_client is None:
        _redis_client = await redis.from_url(settings.CELERY_BROKER_URL)
    return _redis_client