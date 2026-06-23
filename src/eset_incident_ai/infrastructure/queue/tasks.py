# mypy: disable-error-code=untyped-decorator

from __future__ import annotations

import asyncio

from eset_incident_ai.api.dependencies import get_collect_and_notify_incidents
from eset_incident_ai.infrastructure.queue.celery_app import celery_app

if celery_app is not None:

    @celery_app.task(name="eset_incident_ai.collect_and_notify_incidents")
    def collect_and_notify_incidents_task(limit: int) -> dict[str, object]:
        result = asyncio.run(get_collect_and_notify_incidents().execute(limit=limit))
        return result.model_dump()
