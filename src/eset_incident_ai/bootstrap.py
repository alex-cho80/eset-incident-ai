from __future__ import annotations

from fastapi import FastAPI

from eset_incident_ai.api.exception_handlers import register_exception_handlers
from eset_incident_ai.api.routes import (
    analyses,
    approvals,
    detections,
    health,
    incidents,
    knowledge,
)
from eset_incident_ai.settings.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()
    app = FastAPI(title=resolved_settings.app_name)
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(incidents.router, prefix="/api/v1")
    app.include_router(detections.router, prefix="/api/v1")
    app.include_router(analyses.router, prefix="/api/v1")
    app.include_router(approvals.router, prefix="/api/v1")
    app.include_router(knowledge.router, prefix="/api/v1")
    return app
