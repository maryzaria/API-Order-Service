import os

from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "netology_pd_diplom.settings")

celery_app = Celery("netology_pd_diplom", broker=settings.CELERY_BROKER_URL)

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes
celery_app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps
celery_app.autodiscover_tasks()
