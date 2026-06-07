"""Celery application for async ingestion (and future background work).

Broker + result backend are Redis (already provisioned in docker-compose and on
Upstash in the cloud topology). Tasks live in ``app.tasks`` and are imported here so
a ``celery -A app.celery_app.celery_app worker`` process registers them.
"""

from __future__ import annotations

from celery import Celery

from app.config import settings

celery_app = Celery(
    "proofpack",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
)

# Register task modules. Tasks live in app.tasks and bind to THIS app via
# @celery_app.task, so importing app.tasks anywhere (API or worker) uses this
# Redis broker — not Celery's default amqp://localhost.
celery_app.autodiscover_tasks(["app"])
