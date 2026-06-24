# mypy: disable-error-code=untyped-decorator

from __future__ import annotations

import asyncio

from eset_incident_ai.api.dependencies import (
    get_collect_and_notify_detections,
    get_collect_and_notify_incidents,
    get_settings,
)
from eset_incident_ai.infrastructure.queue.celery_app import celery_app

if celery_app is not None:

    @celery_app.task(name="eset_incident_ai.collect_and_notify_incidents")
    def collect_and_notify_incidents_task(limit: int) -> dict[str, object]:
        result = asyncio.run(get_collect_and_notify_incidents().execute(limit=limit))
        return result.model_dump()

    @celery_app.task(name="eset_incident_ai.collect_and_notify_detections")
    def collect_and_notify_detections_task() -> dict[str, object]:
        settings = get_settings()
        result = asyncio.run(
            get_collect_and_notify_detections().execute(
                limit=settings.detection_notify_limit,
                page_size=settings.eset_detection_page_size,
                max_pages_per_run=settings.detection_max_pages_per_run,
                backfill_window_days=settings.detection_backfill_window_days,
            )
        )
        return result.model_dump()
