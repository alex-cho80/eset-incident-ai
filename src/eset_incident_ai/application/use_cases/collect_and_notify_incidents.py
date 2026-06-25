from __future__ import annotations

import logging
from contextlib import suppress

from eset_incident_ai.application.dto.collection_result import IncidentCollectionResult
from eset_incident_ai.application.ports.approval_repository import ApprovalRepository
from eset_incident_ai.application.ports.collection_run_repository import (
    CollectionRunRepository,
)
from eset_incident_ai.application.ports.incident_notification_builder import (
    IncidentNotificationBuilder,
)
from eset_incident_ai.application.ports.incident_source import IncidentSource
from eset_incident_ai.application.ports.notification_repository import NotificationRepository
from eset_incident_ai.application.ports.notifier import Notifier
from eset_incident_ai.application.use_cases.analyze_incident import AnalyzeIncident
from eset_incident_ai.domain.entities.incident import Incident
from eset_incident_ai.domain.enums.severity import Severity
from eset_incident_ai.infrastructure.discord.message_builder import build_idempotency_key

logger = logging.getLogger(__name__)


class CollectAndNotifyIncidents:
    def __init__(
        self,
        *,
        incident_source: IncidentSource,
        approval_repository: ApprovalRepository,
        collection_run_repository: CollectionRunRepository,
        notification_builder: IncidentNotificationBuilder,
        notification_repository: NotificationRepository,
        notifier: Notifier,
        analyzer: AnalyzeIncident | None = None,
        destination: str = "discord",
    ) -> None:
        self._incident_source = incident_source
        self._approval_repository = approval_repository
        self._collection_run_repository = collection_run_repository
        self._notification_builder = notification_builder
        self._notification_repository = notification_repository
        self._notifier = notifier
        self._analyzer = analyzer
        self._destination = destination

    async def execute(
        self,
        *,
        limit: int,
        updated_after: str | None = None,
    ) -> IncidentCollectionResult:
        try:
            return await self._execute(limit=limit, updated_after=updated_after)
        except Exception as exc:
            with suppress(Exception):
                await self._collection_run_repository.save_failure(
                    error_message=self._safe_error_message(exc)
                )
            raise

    async def _execute(
        self,
        *,
        limit: int,
        updated_after: str | None = None,
    ) -> IncidentCollectionResult:
        collected_count = 0
        notified_count = 0
        duplicate_skipped_count = 0
        pending_approval_count = 0
        observed_keys: set[str] = set()
        async for incident in self._incident_source.iter_incidents(
            updated_after=updated_after,
            page_size=max(limit, 1),
        ):
            collected_count += 1
            observed_keys.update(str(key) for key in incident.keys())

            severity = self._notification_builder.severity(incident)
            if severity in {Severity.HIGH, Severity.CRITICAL}:
                await self._approval_repository.save_pending(
                    incident=incident,
                    severity=severity.value,
                )
                pending_approval_count += 1
            else:
                idempotency_key = self._idempotency_key(incident)
                if await self._notification_repository.was_delivered(idempotency_key):
                    duplicate_skipped_count += 1
                    if collected_count >= limit:
                        break
                    continue
                analysis = None
                if self._analyzer is not None:
                    try:
                        analysis = await self._analyzer.execute(
                            incident=self._to_domain_incident(incident, severity),
                            tenant_scope="default",
                        )
                    except Exception:
                        incident_id = str(
                            incident.get("uuid") or incident.get("displayName") or "unknown"
                        )
                        logger.warning(
                            "Incident analysis failed; sending notification without analysis",
                            extra={"incident_id": incident_id},
                            exc_info=True,
                        )
                await self._notifier.send(self._notification_builder.build(incident, analysis))
                await self._notification_repository.mark_delivered(
                    idempotency_key=idempotency_key,
                    destination=self._destination,
                )
                notified_count += 1

            if collected_count >= limit:
                break

        result = IncidentCollectionResult(
            collected_count=collected_count,
            notified_count=notified_count,
            duplicate_skipped_count=duplicate_skipped_count,
            pending_approval_count=pending_approval_count,
            skipped_count=max(
                collected_count - notified_count - pending_approval_count - duplicate_skipped_count,
                0,
            ),
            observed_keys=sorted(observed_keys),
        )
        await self._collection_run_repository.save_success(result)
        return result

    def _safe_error_message(self, exc: Exception) -> str:
        message = str(exc).replace("\n", " ").strip()
        if not message:
            message = "No error detail provided."
        return f"{type(exc).__name__}: {message}"[:500]

    def _to_domain_incident(self, incident: dict[str, object], severity: Severity) -> Incident:
        incident_id = str(incident.get("uuid") or incident.get("displayName") or "unknown")
        title = str(incident.get("displayName") or incident_id)
        summary = str(incident.get("description") or "") or None
        return Incident(
            id=incident_id,
            external_id=incident_id,
            title=title,
            severity=severity,
            detected_at=None,
            summary=summary,
            normalized_payload={
                "source": "eset",
                "raw_keys": sorted(str(key) for key in incident.keys()),
            },
        )

    def _idempotency_key(self, incident: dict[str, object]) -> str:
        incident_id = str(incident.get("uuid") or incident.get("displayName") or "unknown")
        analysis_version = str(
            incident.get("updateTime") or incident.get("createTime") or "unknown"
        )
        return build_idempotency_key(incident_id, analysis_version, self._destination)
