from __future__ import annotations

import argparse
import asyncio
import json
import logging

from eset_incident_ai.application.dto.approval_dto import PendingDetectionApprovalDTO
from eset_incident_ai.application.use_cases.analyze_incident import AnalyzeIncident
from eset_incident_ai.domain.entities.analysis import IncidentAnalysisResult
from eset_incident_ai.domain.entities.incident import Incident
from eset_incident_ai.domain.enums.severity import Severity
from eset_incident_ai.infrastructure.discord.detection_notification_builder import (
    SanitizedDetectionNotificationBuilder,
)
from eset_incident_ai.infrastructure.discord.message_builder import build_idempotency_key
from eset_incident_ai.infrastructure.discord.webhook_client import DiscordWebhookClient
from eset_incident_ai.infrastructure.llm.local_gateway import LocalAnalysisGateway
from eset_incident_ai.infrastructure.llm.ollama_gateway import OllamaGateway
from eset_incident_ai.infrastructure.persistence.detection_approval_repository import (
    PostgresDetectionApprovalRepository,
)
from eset_incident_ai.infrastructure.persistence.notification_repository import (
    PostgresNotificationRepository,
)
from eset_incident_ai.infrastructure.persistence.vector_repository import PgVectorRepository
from eset_incident_ai.security.sanitizer import Sanitizer
from eset_incident_ai.settings.config import Settings

logger = logging.getLogger(__name__)


def payload_to_analysis_incident(
    payload: dict[str, object],
    severity: Severity,
) -> Incident:
    detection_id = str(payload.get("uuid") or payload.get("displayName") or "unknown")
    title = str(payload.get("displayName") or detection_id)
    context = payload.get("context")
    summary = _stringify_context(context)
    return Incident(
        id=detection_id,
        external_id=detection_id,
        title=title,
        severity=severity,
        detected_at=None,
        summary=summary,
        normalized_payload={
            "source": "eset_detection",
            "raw_keys": sorted(str(key) for key in payload.keys()),
        },
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill pending ESET detection approvals through analysis and Discord."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10000,
        help="Maximum pending detection approvals to process.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the pending count without analyzing, notifying, or marking reviewed.",
    )
    return parser.parse_args()


async def run(*, limit: int, dry_run: bool = False) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings()
    _validate_settings(settings)

    sanitizer = Sanitizer(settings.sanitizer_hmac_secret)
    approval_repository = PostgresDetectionApprovalRepository(
        database_url=settings.database_url,
        sanitizer=sanitizer,
    )
    approvals = await approval_repository.list_pending(limit=limit)
    logger.info("Pending detection approvals found: count=%s", len(approvals))

    if dry_run:
        return

    notification_repository = PostgresNotificationRepository(settings.database_url)
    notification_builder = SanitizedDetectionNotificationBuilder(sanitizer)
    notifier = DiscordWebhookClient(webhook_url=settings.discord_webhook_url)
    analyzer = _build_analyzer(settings, sanitizer)

    for approval in approvals:
        await _process_approval(
            approval=approval,
            approval_repository=approval_repository,
            notification_repository=notification_repository,
            notification_builder=notification_builder,
            notifier=notifier,
            analyzer=analyzer,
        )


def _validate_settings(settings: Settings) -> None:
    if not settings.discord_enabled:
        raise SystemExit("DISCORD_ENABLED is not true")
    if not settings.discord_webhook_url:
        raise SystemExit("DISCORD_WEBHOOK_URL is empty")
    if not settings.sanitizer_hmac_secret:
        raise SystemExit("SANITIZER_HMAC_SECRET is empty")


def _build_analyzer(settings: Settings, sanitizer: Sanitizer) -> AnalyzeIncident:
    if settings.llm_provider == "ollama" and settings.ollama_model:
        llm_gateway = OllamaGateway(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            keep_alive=settings.ollama_keep_alive,
            sanitizer=sanitizer,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
    else:
        llm_gateway = LocalAnalysisGateway()
    return AnalyzeIncident(
        vector_repository=PgVectorRepository(settings.database_url),
        llm_gateway=llm_gateway,
    )


async def _process_approval(
    *,
    approval: PendingDetectionApprovalDTO,
    approval_repository: PostgresDetectionApprovalRepository,
    notification_repository: PostgresNotificationRepository,
    notification_builder: SanitizedDetectionNotificationBuilder,
    notifier: DiscordWebhookClient,
    analyzer: AnalyzeIncident,
) -> None:
    logger.info(
        "Processing pending detection approval: approval_id=%s detection_id=%s",
        approval.approval_id,
        approval.detection_id,
    )
    idempotency_key = _idempotency_key(approval.payload)
    if await notification_repository.was_delivered(idempotency_key):
        await approval_repository.mark_reviewed(
            approval_id=approval.approval_id,
            status="approved",
        )
        logger.info(
            "Pending detection approval already delivered; marked reviewed: "
            "approval_id=%s detection_id=%s",
            approval.approval_id,
            approval.detection_id,
        )
        return

    severity = Severity.parse(approval.severity)
    analysis = await _analyze_approval(
        approval=approval,
        analyzer=analyzer,
        severity=severity,
    )

    try:
        await notifier.send(notification_builder.build(approval.payload, analysis))
        await notification_repository.mark_delivered(
            idempotency_key=idempotency_key,
            destination="discord",
        )
    except Exception:
        logger.exception(
            "Pending detection approval delivery failed; leaving pending: "
            "approval_id=%s detection_id=%s",
            approval.approval_id,
            approval.detection_id,
        )
        return

    await approval_repository.mark_reviewed(
        approval_id=approval.approval_id,
        status="approved",
    )
    logger.info(
        "Pending detection approval delivered and marked reviewed: approval_id=%s detection_id=%s",
        approval.approval_id,
        approval.detection_id,
    )


async def _analyze_approval(
    *,
    approval: PendingDetectionApprovalDTO,
    analyzer: AnalyzeIncident,
    severity: Severity,
) -> IncidentAnalysisResult | None:
    try:
        return await analyzer.execute(
            incident=payload_to_analysis_incident(approval.payload, severity),
            tenant_scope="default",
        )
    except Exception:
        logger.exception(
            "Pending detection approval analysis failed; sending without analysis: "
            "approval_id=%s detection_id=%s",
            approval.approval_id,
            approval.detection_id,
        )
        return None


def _stringify_context(value: object) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _idempotency_key(payload: dict[str, object]) -> str:
    detection_id = str(payload.get("uuid") or payload.get("displayName") or "unknown")
    analysis_version = str(payload.get("occurTime") or "unknown")
    return build_idempotency_key(detection_id, analysis_version, "discord")


def main() -> None:
    args = parse_args()
    asyncio.run(run(limit=args.limit, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
