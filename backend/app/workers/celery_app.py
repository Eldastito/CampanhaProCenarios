"""Celery application — broker e backend em Redis (Fase 2 do PRD v2).

Em produção:
    celery -A app.workers.celery_app worker -l info -Q default

Em testes:
    `settings.celery_task_always_eager` é True via conftest.
    As tasks rodam síncronamente no mesmo processo, sem broker.

Tasks novas devem ser registradas em ``include`` abaixo para que o worker
as encontre.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

_broker = settings.celery_broker_url or settings.redis_url
_backend = settings.celery_result_backend or settings.redis_url

celery_app = Celery(
    "campanhapro_cenarios",
    broker=_broker,
    backend=_backend,
    include=[
        "app.workers.snapshot_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=settings.celery_task_always_eager,
)
