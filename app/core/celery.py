from celery import Celery
from app.core.config import settings

# Initialize Celery app
celery_app = Celery(
    "notification_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.notification_tasks",
        "app.tasks.webhook_tasks"
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=15 * 60,  # 15 minutes
    beat_schedule={
        'check-webhook-deliveries': {
            'task': 'check_webhook_deliveries',
            'schedule': 300.0,  # Run every 5 minutes
        },
    }
)
