from __future__ import annotations

from celery import Celery

from core.config import settings

celery_app = Celery("crispr_worker")

celery_app.conf.update(
    broker_url=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_RESULT_BACKEND,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)

celery_app.autodiscover_tasks(["backend.tasks.design"])
