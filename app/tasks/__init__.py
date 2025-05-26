# Package initialization

# This file ensures that all task modules are properly imported
from app.tasks.notification_tasks import send_notification_task, send_instant_notification, mark_notification_failed

# Export the task names for easy importing elsewhere
__all__ = ['send_notification_task', 'send_instant_notification', 'mark_notification_failed']
