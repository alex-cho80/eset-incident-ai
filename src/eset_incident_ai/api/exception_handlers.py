from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from eset_incident_ai.domain.exceptions import DomainError
from eset_incident_ai.infrastructure.eset.auth_client import EsetAuthenticationError
from eset_incident_ai.infrastructure.eset.incident_client import EsetApiError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(EsetAuthenticationError)
    async def handle_eset_authentication_error(
        _: Request, exc: EsetAuthenticationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"detail": "ESET authentication failed. Check configured credentials."},
        )

    @app.exception_handler(EsetApiError)
    async def handle_eset_api_error(_: Request, exc: EsetApiError) -> JSONResponse:
        if exc.status_code == 401:
            return JSONResponse(
                status_code=401,
                content={"detail": "ESET API rejected the configured access token."},
            )
        return JSONResponse(
            status_code=502,
            content={"detail": "ESET API request failed."},
        )
