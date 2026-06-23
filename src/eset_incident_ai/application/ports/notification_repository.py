from __future__ import annotations

from typing import Protocol


class NotificationRepository(Protocol):
    async def was_delivered(self, idempotency_key: str) -> bool: ...

    async def mark_delivered(self, *, idempotency_key: str, destination: str) -> None: ...
