from __future__ import annotations

from typing import Any

try:
    from celery import Celery  # type: ignore[import-untyped]
    from celery.schedules import crontab  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    Celery = None
    crontab = None

from eset_incident_ai.settings.config import Settings

settings = Settings()

if Celery is not None:
    celery_app: Any = Celery(
        "eset_incident_ai",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["eset_incident_ai.infrastructure.queue.tasks"],
    )
    celery_app.conf.timezone = settings.incident_notify_timezone
    celery_app.conf.beat_schedule = {
        "daily-eset-incident-notification": {
            "task": "eset_incident_ai.collect_and_notify_incidents",
            "schedule": crontab(
                hour=settings.incident_notify_cron_hour,
                minute=settings.incident_notify_cron_minute,
            ),
            "args": (settings.incident_notify_limit,),
        },
        "periodic-eset-detection-notification": {
            "task": "eset_incident_ai.collect_and_notify_detections",
            "schedule": crontab(
                minute=f"*/{settings.detection_notify_cron_interval_minutes}",
            ),
        },
    }
else:
    celery_app = None
