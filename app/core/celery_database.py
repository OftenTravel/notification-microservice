"""
Database configuration specifically for Celery tasks.
Creates a new engine for each task to avoid event loop conflicts.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator
from app.core.config import settings


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
    return sessionmaker(
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
            await session.bind.dispose()