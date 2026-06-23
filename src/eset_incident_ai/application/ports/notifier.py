from __future__ import annotations

from typing import Any, Protocol


class Notifier(Protocol):
    async def send(self, payload: dict[str, Any]) -> None: ...
