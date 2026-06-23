from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


class DiscordDeliveryError(RuntimeError):
    pass


class DiscordWebhookClient:
    def __init__(self, *, webhook_url: str, timeout_seconds: float = 10.0) -> None:
        self._webhook_url = webhook_url
        self._timeout = httpx.Timeout(timeout_seconds)

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=20), stop=stop_after_attempt(4), reraise=True
    )
    async def send(self, payload: dict[str, Any]) -> None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(self._webhook_url, json=payload)

        if response.status_code == 429 or response.status_code >= 500:
            raise DiscordDeliveryError(f"Temporary Discord failure: {response.status_code}")
        if response.status_code not in {200, 204}:
            raise DiscordDeliveryError(f"Discord delivery failed: {response.status_code}")
