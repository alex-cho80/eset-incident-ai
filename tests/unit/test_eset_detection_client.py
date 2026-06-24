from __future__ import annotations

import httpx
import pytest
import respx
from tenacity import wait_none

from eset_incident_ai.infrastructure.eset.auth_client import EsetAuthClient
from eset_incident_ai.infrastructure.eset.detection_client import EsetDetectionClient
from eset_incident_ai.infrastructure.eset.incident_client import EsetApiError, EsetTemporaryApiError


def _client() -> EsetDetectionClient:
    return EsetDetectionClient(
        base_url="https://eset.example.invalid",
        auth_client=EsetAuthClient(
            auth_url="https://auth.example.invalid/oauth/token",
            username="",
            password="",
            access_token="test-token",  # noqa: S106
            access_token_expires_in=3600,
        ),
    )


@pytest.mark.asyncio
@respx.mock
async def test_detection_client_iterates_pages_without_unsupported_params() -> None:
    route = respx.get("https://eset.example.invalid/v1/detections").mock(
        side_effect=[
            httpx.Response(
                200,
                json={"detections": [{"uuid": "detection-1"}], "nextPageToken": "page-2"},
            ),
            httpx.Response(200, json={"detections": [{"uuid": "detection-2"}]}),
        ]
    )

    detections = [item async for item in _client().iter_detections(page_size=1000)]

    assert detections == [{"uuid": "detection-1"}, {"uuid": "detection-2"}]
    assert route.call_count == 2
    for call in route.calls:
        params = dict(call.request.url.params)
        assert params["pageSize"] == "1000"
        assert not {"filter", "orderBy", "sortBy", "sort"}.intersection(params)
    assert dict(route.calls[1].request.url.params)["pageToken"] == "page-2"


@pytest.mark.asyncio
async def test_detection_client_rejects_unsupported_params_before_request() -> None:
    client = _client()

    with pytest.raises(EsetApiError):
        await client._request("GET", "/v1/detections", params={"filter": "bad"})  # noqa: SLF001


@pytest.mark.asyncio
@respx.mock
async def test_detection_client_maps_4xx_errors() -> None:
    respx.get("https://eset.example.invalid/v1/detections").mock(
        return_value=httpx.Response(400, json={})
    )

    with pytest.raises(EsetApiError) as exc_info:
        await _client().get_detection_page(page_size=1000)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
@respx.mock
async def test_detection_client_retries_temporary_errors_without_sleep() -> None:
    client = _client()
    original_wait = client._request.retry.wait  # noqa: SLF001
    client._request.retry.wait = wait_none()  # noqa: SLF001
    route = respx.get("https://eset.example.invalid/v1/detections").mock(
        side_effect=[
            httpx.Response(500, json={}),
            httpx.Response(429, json={}),
            httpx.Response(200, json={"detections": [{"uuid": "recovered"}]}),
        ]
    )

    try:
        page = await client.get_detection_page(page_size=1000)
    finally:
        client._request.retry.wait = original_wait  # noqa: SLF001

    assert page.detections == [{"uuid": "recovered"}]
    assert route.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_detection_client_raises_temporary_error_after_retries() -> None:
    client = _client()
    original_wait = client._request.retry.wait  # noqa: SLF001
    client._request.retry.wait = wait_none()  # noqa: SLF001
    respx.get("https://eset.example.invalid/v1/detections").mock(
        return_value=httpx.Response(500, json={})
    )

    try:
        with pytest.raises(EsetTemporaryApiError):
            await client.get_detection_page(page_size=1000)
    finally:
        client._request.retry.wait = original_wait  # noqa: SLF001
