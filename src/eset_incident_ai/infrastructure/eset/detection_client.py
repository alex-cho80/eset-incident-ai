from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from eset_incident_ai.application.ports.detection_source import DetectionPage
from eset_incident_ai.infrastructure.eset.auth_client import EsetAuthClient
from eset_incident_ai.infrastructure.eset.incident_client import EsetApiError, EsetTemporaryApiError

UNSUPPORTED_DETECTION_PARAMS = frozenset({"filter", "orderBy", "sortBy", "sort"})


class EsetDetectionClient:
    def __init__(
        self,
        *,
        base_url: str,
        auth_client: EsetAuthClient,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth_client = auth_client
        self._timeout = httpx.Timeout(timeout_seconds)

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, EsetTemporaryApiError)),
        wait=wait_exponential_jitter(initial=1, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if params is not None:
            blocked_params = UNSUPPORTED_DETECTION_PARAMS.intersection(params)
            if blocked_params:
                blocked = ", ".join(sorted(blocked_params))
                raise EsetApiError(f"Unsupported ESET Detection query parameters: {blocked}")

        token = await self._auth_client.get_access_token()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.request(
                method,
                f"{self._base_url}{path}",
                params=params,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )

        if response.status_code == 429 or response.status_code >= 500:
            raise EsetTemporaryApiError(
                f"Temporary ESET API failure: {response.status_code}",
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            raise EsetApiError(
                f"ESET API request failed: status={response.status_code}",
                status_code=response.status_code,
            )
        body = response.json()
        if not isinstance(body, dict):
            raise EsetApiError("ESET API returned non-object JSON")
        return body

    async def iter_detections(
        self,
        *,
        page_token: str | None = None,
        page_size: int = 1000,
    ) -> AsyncIterator[dict[str, Any]]:
        current_page_token = page_token
        while True:
            page = await self.get_detection_page(
                page_token=current_page_token,
                page_size=page_size,
            )
            for detection in page.detections:
                yield detection
            if page.next_page_token is None:
                break
            current_page_token = page.next_page_token

    async def get_detection_page(
        self,
        *,
        page_token: str | None = None,
        page_size: int = 1000,
    ) -> DetectionPage:
        params: dict[str, Any] = {"pageSize": page_size}
        if page_token:
            params["pageToken"] = page_token

        payload = await self._request("GET", "/v1/detections", params=params)
        detections = payload.get("detections", [])
        if not isinstance(detections, list):
            raise EsetApiError("ESET detections field is not a list")
        next_page_token = payload.get("nextPageToken")
        return DetectionPage(
            detections=[detection for detection in detections if isinstance(detection, dict)],
            next_page_token=next_page_token
            if isinstance(next_page_token, str) and next_page_token
            else None,
        )
