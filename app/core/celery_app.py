from celery import Celery
from celery.signals import task_prerun, task_success, task_failure, task_retry
from app.core.config import settings
import logging
import importlib

logger = logging.getLogger(__name__)

# Initialize Celery
celery_app = Celery(
    "notification_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['app.tasks.notification_tasks']  # Explicitly include this module
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Use simple task names that match exactly the name in the decorator
    task_routes={
        "send_notification_task": {"queue": "notifications"},
        "send_instant_notification": {"queue": "instant"},
    },
    task_default_queue="notifications",
    task_acks_late=True,  # Only acknowledge tasks after they succeed or fail
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
    # Result backend settings for persistence
    result_expires=86400,  # Keep results for 24 hours (in seconds)
    result_persistent=True,  # Persist results across restarts
    result_backend_transport_options={
        'master_name': 'mymaster',
        'visibility_timeout': 3600,
    },
    # Task tracking
    task_track_started=True,  # Track when tasks start
    task_send_sent_event=True,  # Send task-sent events for monitoring
    # Worker settings
    worker_send_task_events=True,  # Send events for tasks
    worker_hijack_root_logger=False,  # Don't hijack root logger
    worker_enable_remote_control=True,  # Enable remote control
)

# Force load task modules
try:
    # Force immediate importing of task modules
    importlib.import_module("app.tasks.notification_tasks")
    print("Successfully imported notification_tasks module")
except ImportError as e:
    print(f"Error importing tasks: {e}")

# Discover tasks from all modules in app
celery_app.autodiscover_tasks(["app.tasks"])

# Print all registered tasks for debugging
print("Registered tasks:")
for task in sorted(celery_app.tasks.keys()):
    if not task.startswith('celery.'):  # Skip built-in celery tasks
        print(f"  - {task}")


# Signal handlers for statistics tracking
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, **kwargs):
    """Track when a task starts"""
    try:
        from app.core.worker_stats import worker_stats
        worker_name = task.request.hostname or "unknown"
        worker_stats.increment_stat(worker_name, "processed")
    except Exception as e:
        logger.error(f"Error tracking task prerun: {e}")


@task_success.connect
def task_success_handler(sender=None, result=None, **kwargs):
    """Track successful task completion"""
    try:
        from app.core.worker_stats import worker_stats
        worker_name = sender.request.hostname or "unknown"
        worker_stats.increment_stat(worker_name, "succeeded")
    except Exception as e:
        logger.error(f"Error tracking task success: {e}")


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
    """Track task failures"""
    try:
        from app.core.worker_stats import worker_stats
        worker_name = sender.request.hostname or "unknown"
        worker_stats.increment_stat(worker_name, "failed")
    except Exception as e:
        logger.error(f"Error tracking task failure: {e}")


@task_retry.connect
def task_retry_handler(sender=None, request=None, reason=None, **kwargs):
    """Track task retries"""
    try:
        from app.core.worker_stats import worker_stats
        worker_name = request.hostname or "unknown"
        worker_stats.increment_stat(worker_name, "retried")
    except Exception as e:
        logger.error(f"Error tracking task retry: {e}")
