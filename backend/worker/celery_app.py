import faulthandler
import sys

_fault_log = open("/tmp/celery_crash.log", "a")
faulthandler.enable(file=_fault_log)
faulthandler.enable(file=sys.stderr)

import os

# Must be set BEFORE any other imports. On macOS, Celery's billiard library
# forks the worker process. Fork + Objective-C runtime = crash ("Python quit
# unexpectedly"). This env var disables the fork-safety check that kills the process.
os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

from celery import Celery
from app.config import settings

REDIS_URL = settings.database_url.replace(
    "postgresql", "redis"
).split("@")[0].rsplit("/", 1)[0] if "postgresql" in settings.database_url else "redis://localhost:6379/0"

CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", "redis://localhost:6379/0")

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

    # Use solo pool: no forking, no threads — runs tasks inline in the main process.
    # On macOS + Python 3.14, billiard forks the worker process even with pool=threads.
    # Forking after SQLAlchemy/OpenAI/Redis clients are initialized causes SIGSEGV:
    #   "multi-threaded process forked — crashed on child side of fork pre-exec"
    # Solo pool avoids this entirely. Tasks run sequentially which is fine since
    # the agent analysis is I/O-bound and processes one filing at a time anyway.
    worker_pool="solo",

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

    # NOTE: task_time_limit and task_soft_time_limit are DISABLED because
    # they rely on POSIX signals (SIGALRM) which only work in the main thread.
    # With worker_pool="threads", tasks run in worker threads where signals
    # can't be delivered — this causes the entire Python process to crash.
    # Timeout logic is handled in the task itself if needed.
)

# This tells Celery where to find the task functions.
celery_app.autodiscover_tasks(["worker"])
