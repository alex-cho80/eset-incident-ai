from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from eset_incident_ai.infrastructure.eset.auth_client import EsetAuthClient


class EsetApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class EsetTemporaryApiError(EsetApiError):
    pass


class EsetIncidentClient:
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

    async def iter_incidents(
        self,
        *,
        updated_after: str | None = None,
        page_size: int = 100,
    ) -> AsyncIterator[dict[str, Any]]:
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"pageSize": page_size}
            if updated_after:
                params["filter"] = f'updateTime > "{updated_after}"'
            if page_token:
                params["pageToken"] = page_token

            payload = await self._request("GET", "/v2/incidents", params=params)
            incidents = payload.get("incidents", [])
            if not isinstance(incidents, list):
                raise EsetApiError("ESET incidents field is not a list")
            for incident in incidents:
                if isinstance(incident, dict):
                    yield incident

            next_page_token = payload.get("nextPageToken")
            if not isinstance(next_page_token, str) or not next_page_token:
                break
            page_token = next_page_token

    async def get_incident(self, incident_uuid: str) -> dict[str, Any]:
        return await self._request("GET", f"/v2/incidents/{incident_uuid}")
