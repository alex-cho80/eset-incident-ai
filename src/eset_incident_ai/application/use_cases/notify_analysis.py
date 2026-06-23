from __future__ import annotations

from typing import Any

from eset_incident_ai.application.ports.notifier import Notifier


class NotifyAnalysis:
    def __init__(self, notifier: Notifier) -> None:
        self._notifier = notifier

    async def execute(self, payload: dict[str, Any]) -> None:
        await self._notifier.send(payload)
