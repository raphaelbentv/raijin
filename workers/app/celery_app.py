import os

from celery import Celery
from celery.signals import worker_process_init

from app.core.logging import configure_logging
from app.core.observability import init_sentry

celery_app = Celery(
    "raijin",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/1"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/2"),
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=270,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    beat_schedule={
        "email-sync-all-outlook": {
            "task": "email.sync_all_outlook",
            "schedule": 900.0,  # 15 minutes
        },
        "email-sync-all-gmail": {
            "task": "email.sync_all_gmail",
            "schedule": 900.0,
        },
        "drive-sync-all-gdrive": {
            "task": "drive.sync_all_gdrive",
            "schedule": 900.0,
        },
    },
)


@worker_process_init.connect
def _init_worker(**_kwargs) -> None:
    configure_logging()
    init_sentry("raijin-worker")


@celery_app.task(name="health.ping")
def ping() -> str:
    return "pong"
