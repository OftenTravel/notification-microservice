from celery import Celery
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Initialize Celery
celery_app = Celery(
    "notification_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "app.tasks.notification_tasks.send_notification": {"queue": "notifications"},
        "app.tasks.notification_tasks.send_instant_notification": {"queue": "instant"},
    },
    task_default_queue="notifications",
    broker_connection_retry_on_startup=True,
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
)

# Load tasks modules
celery_app.autodiscover_tasks(["app.tasks"])
