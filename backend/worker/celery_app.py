from celery import Celery
from app.config import settings

REDIS_URL = settings.database_url.replace(
    "postgresql", "redis"
).split("@")[0].rsplit("/", 1)[0] if "postgresql" in settings.database_url else "redis://localhost:6379/0"

CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"

# create celery app
celery_app = Celery(
    "worker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND
)

# celery config

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    
    timezone="UTC",
    enable_utc=True,
    
    # Task acknowledgement:
    # task_acks_late=True means the worker acknowledges ("I'm done") AFTER
    # processing, not when it picks up the task. This means if the worker
    # crashes mid-task, the task goes back to the queue instead of being lost.
    task_acks_late=True,
    
    # Only fetch one task at a time per worker.
    # Without this, Celery prefetches multiple tasks, which means if a
    # worker is busy with a 60-second analysis, it's also holding onto
    # the next task — even if another idle worker could process it.
    worker_prefetch_multiplier=1,
    
    # Task time limit: kill the task if it runs longer than 5 minutes.
    task_time_limit=300,
    
    # Soft time limit: raise SoftTimeLimitExceeded after 4 minutes.
    # This gives the task a chance to clean up (update job status to
    # "failed") before the hard kill at 5 minutes.
    task_soft_time_limit=240,
)

# This tells Celery where to find the task functions.
celery_app.autodiscover_tasks(["worker"])
