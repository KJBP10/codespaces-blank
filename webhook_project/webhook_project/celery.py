# webhook_project/celery.py
import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webhook_project.settings')

app = Celery('webhook_project', broker='redis://redis:6379/0')
app.conf.update(
    task_track_started=True,
    worker_concurrency=1,
)

# Autodiscover tasks in the 'webhook' app
app.autodiscover_tasks(['webhook'])