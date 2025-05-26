# Flower configuration
import os

# Basic settings
port = 5555
address = '0.0.0.0'

# Enable persistent storage
persistent = True
db = '/data/flower.db'  # SQLite database for persistent storage

# State persistence
state_save_interval = 60  # Save state every 60 seconds

# Authentication (optional, uncomment to enable)
# basic_auth = ['admin:password']

# URL prefix if running behind a proxy
# url_prefix = '/flower'

# Task runtime limits
task_runtime_metric_buckets = [0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]

# Enable API
enable_api = True

# Max number of tasks to keep in memory
max_tasks = 10000

# Purge old tasks
purge_offline_workers = 3600  # Purge offline workers after 1 hour

# Natural time refresh
natural_time_refresh = 5  # Refresh every 5 seconds

# Debug mode
debug = False

# Broker API settings
broker_api = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0')