from __future__ import annotations

import json
import logging
from contextlib import suppress
from datetime import UTC, datetime, timedelta

from eset_incident_ai.application.dto.collection_result import DetectionCollectionResult
from eset_incident_ai.application.ports.detection_approval_repository import (
    DetectionApprovalRepository,
)
from eset_incident_ai.application.ports.detection_collection_run_repository import (
    DetectionCollectionRunRepository,
)
from eset_incident_ai.application.ports.detection_notification_builder import (
    DetectionNotificationBuilder,
)
from eset_incident_ai.application.ports.detection_source import DetectionSource
from eset_incident_ai.application.ports.notification_repository import NotificationRepository
from eset_incident_ai.application.ports.notifier import Notifier
from eset_incident_ai.application.use_cases.analyze_incident import AnalyzeIncident
from eset_incident_ai.domain.entities.analysis import IncidentAnalysisResult
from eset_incident_ai.domain.entities.incident import Incident
from eset_incident_ai.domain.enums.severity import Severity
from eset_incident_ai.infrastructure.discord.message_builder import build_idempotency_key

logger = logging.getLogger(__name__)


class CollectAndNotifyDetections:
    def __init__(
        self,
        *,
        detection_source: DetectionSource,
        approval_repository: DetectionApprovalRepository,
        collection_run_repository: DetectionCollectionRunRepository,
        notification_builder: DetectionNotificationBuilder,
        notification_repository: NotificationRepository,
        notifier: Notifier,
        analyzer: AnalyzeIncident | None = None,
        destination: str = "discord",
        now: datetime | None = None,
        min_severity: Severity = Severity.MEDIUM,
    ) -> None:
        self._detection_source = detection_source
        self._approval_repository = approval_repository
        self._collection_run_repository = collection_run_repository
        self._notification_builder = notification_builder
        self._notification_repository = notification_repository
        self._notifier = notifier
        self._analyzer = analyzer
        self._destination = destination
        self._now = now
        self._min_severity = min_severity

    async def execute(
        self,
        *,
        limit: int,
        page_size: int,
        max_pages_per_run: int,
        backfill_window_days: int,
    ) -> DetectionCollectionResult:
        try:
            return await self._execute(
                limit=limit,
                page_size=page_size,
                max_pages_per_run=max_pages_per_run,
                backfill_window_days=backfill_window_days,
            )
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
        page_size: int,
        max_pages_per_run: int,
        backfill_window_days: int,
    ) -> DetectionCollectionResult:
        latest_run = await self._collection_run_repository.latest()
        current_page_token = latest_run.last_page_token if latest_run is not None else None
        last_persistable_page_token = current_page_token
        cutoff = self._clock() - timedelta(days=backfill_window_days)
        collected_count = 0
        notified_count = 0
        duplicate_skipped_count = 0
        pending_approval_count = 0
        skipped_count = 0
        processed_count = 0
        pages_fetched = 0
        observed_keys: set[str] = set()

        while pages_fetched < max(max_pages_per_run, 0):
            page = await self._detection_source.get_detection_page(
                page_token=current_page_token,
                page_size=page_size,
            )
            pages_fetched += 1
            page_completed = True

            for detection in page.detections:
                collected_count += 1
                observed_keys.update(str(key) for key in detection.keys())
                occurred_at = self._parse_occur_time(detection.get("occurTime"))
                if occurred_at is not None and occurred_at < cutoff:
                    skipped_count += 1
                    continue

                if processed_count >= limit:
                    page_completed = False
                    break

                processed_count += 1
                severity = self._notification_builder.severity(detection)
                if not severity.meets_threshold(self._min_severity):
                    skipped_count += 1
                    continue
                idempotency_key = self._idempotency_key(detection)
                if await self._notification_repository.was_delivered(idempotency_key):
                    duplicate_skipped_count += 1
                    continue

                analysis = await self._analyze_detection(detection, severity)
                await self._notifier.send(self._notification_builder.build(detection, analysis))
                await self._notification_repository.mark_delivered(
                    idempotency_key=idempotency_key,
                    destination=self._destination,
                )
                notified_count += 1

            if page_completed and page.next_page_token is not None:
                current_page_token = page.next_page_token
                last_persistable_page_token = current_page_token
                await self._collection_run_repository.save_cursor(
                    last_page_token=last_persistable_page_token
                )
            elif page.next_page_token is None:
                break

            if not page_completed or processed_count >= limit:
                break

        result = DetectionCollectionResult(
            collected_count=collected_count,
            notified_count=notified_count,
            duplicate_skipped_count=duplicate_skipped_count,
            pending_approval_count=pending_approval_count,
            skipped_count=skipped_count,
            observed_keys=sorted(observed_keys),
        )
        await self._collection_run_repository.save_success(
            result,
            last_page_token=last_persistable_page_token,
        )
        return result

    def _clock(self) -> datetime:
        return self._now if self._now is not None else datetime.now(UTC)

    def _parse_occur_time(self, value: object) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def _safe_error_message(self, exc: Exception) -> str:
        message = str(exc).replace("\n", " ").strip()
        if not message:
            message = "No error detail provided."
        return f"{type(exc).__name__}: {message}"[:500]

    async def _analyze_detection(
        self,
        detection: dict[str, object],
        severity: Severity,
    ) -> IncidentAnalysisResult | None:
        if self._analyzer is None:
            return None
        try:
            return await self._analyzer.execute(
                incident=self._to_analysis_incident(detection, severity),
                tenant_scope="default",
            )
        except Exception:
            detection_id = str(detection.get("uuid") or detection.get("displayName") or "unknown")
            logger.warning(
                "Detection analysis failed; sending notification without analysis",
                extra={"detection_id": detection_id},
                exc_info=True,
            )
            return None

    def _to_analysis_incident(
        self,
        detection: dict[str, object],
        severity: Severity,
    ) -> Incident:
        detection_id = str(detection.get("uuid") or detection.get("displayName") or "unknown")
        title = str(detection.get("displayName") or detection_id)
        context = detection.get("context")
        summary = self._stringify_context(context)
        return Incident(
            id=detection_id,
            external_id=detection_id,
            title=title,
            severity=severity,
            detected_at=None,
            summary=summary,
            normalized_payload={
                "source": "eset_detection",
                "raw_keys": sorted(str(key) for key in detection.keys()),
            },
        )

    def _stringify_context(self, value: object) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    def _idempotency_key(self, detection: dict[str, object]) -> str:
        detection_id = str(detection.get("uuid") or detection.get("displayName") or "unknown")
        analysis_version = str(detection.get("occurTime") or "unknown")
        return build_idempotency_key(detection_id, analysis_version, self._destination)
