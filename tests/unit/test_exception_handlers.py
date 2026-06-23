from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from eset_incident_ai.api.exception_handlers import register_exception_handlers
from eset_incident_ai.domain.exceptions import DomainError
from eset_incident_ai.infrastructure.eset.auth_client import EsetAuthenticationError
from eset_incident_ai.infrastructure.eset.incident_client import EsetApiError


@pytest.mark.asyncio
async def test_eset_api_401_maps_to_safe_response() -> None:
    app = FastAPI()
    register_exception_handlers(app)
    handler = app.exception_handlers[EsetApiError]

    response = await handler(
        cast(Any, None),
        EsetApiError("ESET API request failed: status=401", status_code=401),
    )

    assert isinstance(response, JSONResponse)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_domain_error_maps_to_400() -> None:
    app = FastAPI()
    register_exception_handlers(app)
    handler = app.exception_handlers[DomainError]

    response = await handler(cast(Any, None), DomainError("bad request"))

    assert isinstance(response, JSONResponse)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_eset_auth_error_maps_to_401() -> None:
    app = FastAPI()
    register_exception_handlers(app)
    handler = app.exception_handlers[EsetAuthenticationError]

    response = await handler(cast(Any, None), EsetAuthenticationError("failed"))

    assert isinstance(response, JSONResponse)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_eset_api_non_401_maps_to_502() -> None:
    app = FastAPI()
    register_exception_handlers(app)
    handler = app.exception_handlers[EsetApiError]

    response = await handler(
        cast(Any, None),
        EsetApiError("ESET API request failed: status=500", status_code=500),
    )

    assert isinstance(response, JSONResponse)
    assert response.status_code == 502
