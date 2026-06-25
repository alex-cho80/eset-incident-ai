from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest

from eset_incident_ai.application.dto.collection_run_dto import DetectionCollectionRunDTO
from eset_incident_ai.application.ports.detection_source import DetectionPage
from eset_incident_ai.application.use_cases.collect_and_notify_detections import (
    CollectAndNotifyDetections,
)
from eset_incident_ai.domain.entities.analysis import (
    EvidenceClaim,
    IncidentAnalysisResult,
    RemediationAction,
    RootCauseAnalysis,
)
from eset_incident_ai.domain.entities.incident import Incident
from eset_incident_ai.domain.enums.severity import Severity
from eset_incident_ai.infrastructure.discord.detection_notification_builder import (
    SanitizedDetectionNotificationBuilder,
)
from eset_incident_ai.infrastructure.discord.message_builder import build_idempotency_key
from eset_incident_ai.security.sanitizer import Sanitizer


class FakeDetectionSource:
    def __init__(self, pages: list[DetectionPage]) -> None:
        self._pages = pages
        self.calls: list[tuple[str | None, int]] = []

    async def get_detection_page(
        self,
        *,
        page_token: str | None = None,
        page_size: int,
    ) -> DetectionPage:
        self.calls.append((page_token, page_size))
        index = len(self.calls) - 1
        if index >= len(self._pages):
            return DetectionPage(detections=[], next_page_token=None)
        return self._pages[index]

    async def iter_detections(
        self,
        *,
        page_token: str | None = None,
        page_size: int,
    ) -> AsyncIterator[dict[str, Any]]:
        page = await self.get_detection_page(page_token=page_token, page_size=page_size)
        for detection in page.detections:
            yield detection


class FakeNotifier:
    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    async def send(self, payload: dict[str, Any]) -> None:
        self.payloads.append(payload)


class FakeNotificationRepository:
    def __init__(self, delivered: set[str] | None = None) -> None:
        self.delivered = delivered or set()
        self.marked: list[str] = []

    async def was_delivered(self, idempotency_key: str) -> bool:
        return idempotency_key in self.delivered

    async def mark_delivered(self, *, idempotency_key: str, destination: str) -> None:
        _ = destination
        self.marked.append(idempotency_key)
        self.delivered.add(idempotency_key)


class FakeDetectionApprovalRepository:
    def __init__(self) -> None:
        self.pending: list[dict[str, object]] = []

    async def save_pending(self, *, detection: dict[str, object], severity: str) -> None:
        self.pending.append({"detection": detection, "severity": severity})

    async def list_pending(self, *, limit: int) -> list[object]:
        _ = limit
        return []

    async def get_pending(self, *, approval_id: int) -> object | None:
        _ = approval_id
        return None

    async def mark_reviewed(self, *, approval_id: int, status: str) -> None:
        _ = (approval_id, status)


class FakeDetectionCollectionRunRepository:
    def __init__(self, latest: DetectionCollectionRunDTO | None = None) -> None:
        self._latest = latest
        self.success_tokens: list[str | None] = []
        self.cursor_tokens: list[str | None] = []
        self.failure_message: str | None = None

    async def save_success(self, result: object, *, last_page_token: str | None) -> None:
        _ = result
        self.success_tokens.append(last_page_token)

    async def save_cursor(self, *, last_page_token: str | None) -> None:
        self.cursor_tokens.append(last_page_token)
        self._latest = DetectionCollectionRunDTO(
            run_id=1,
            status="running",
            collected_count=0,
            notified_count=0,
            duplicate_skipped_count=0,
            pending_approval_count=0,
            skipped_count=0,
            observed_keys=[],
            last_page_token=last_page_token,
            created_at=datetime.now(UTC),
        )

    async def save_failure(self, *, error_message: str) -> None:
        self.failure_message = error_message

    async def list_recent(self, *, limit: int) -> list[DetectionCollectionRunDTO]:
        _ = limit
        return [self._latest] if self._latest is not None else []

    async def latest(self) -> DetectionCollectionRunDTO | None:
        return self._latest


class FakeAnalyzer:
    def __init__(self, *, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.incidents: list[Incident] = []

    async def execute(self, *, incident: Incident, tenant_scope: str) -> IncidentAnalysisResult:
        _ = tenant_scope
        self.incidents.append(incident)
        if incident.id == self.fail_on:
            raise RuntimeError("analysis failed")
        return _analysis_result()


class SpyDetectionNotificationBuilder:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, Any], IncidentAnalysisResult | None]] = []

    def severity(self, detection: dict[str, Any]) -> Severity:
        return Severity.parse(detection.get("severityLevel"))

    def build(
        self,
        detection: dict[str, Any],
        analysis: IncidentAnalysisResult | None = None,
    ) -> dict[str, Any]:
        self.calls.append((detection, analysis))
        return {"uuid": detection.get("uuid"), "has_analysis": analysis is not None}


def _detection(
    uuid: str,
    *,
    severity: str = "SEVERITY_LEVEL_LOW",
    occur_time: str = "2026-06-20T00:00:00Z",
) -> dict[str, Any]:
    return {
        "uuid": uuid,
        "displayName": uuid,
        "severityLevel": severity,
        "occurTime": occur_time,
    }


def _analysis_result() -> IncidentAnalysisResult:
    return IncidentAnalysisResult(
        root_cause=RootCauseAnalysis(
            executive_summary="RAG evidence indicates detection handling.",
            direct_cause=[
                EvidenceClaim(
                    claim="Detection matched a known workflow.",
                    evidence_ids=["evidence-1"],
                    confidence=0.8,
                )
            ],
            root_causes=[
                EvidenceClaim(
                    claim="Endpoint telemetry needs confirmation.",
                    evidence_ids=["evidence-2"],
                    confidence=0.7,
                )
            ],
            false_positive_probability=0.2,
        ),
        remediation=[
            RemediationAction(
                priority="immediate",
                action="Check endpoint isolation status.",
                rationale="Immediate containment should be verified.",
                rollback=None,
                requires_approval=False,
            )
        ],
        overall_confidence=0.8,
        evidence_coverage=0.4,
    )


def _use_case(
    source: FakeDetectionSource,
    runs: FakeDetectionCollectionRunRepository,
    approvals: FakeDetectionApprovalRepository | None = None,
    notifications: FakeNotificationRepository | None = None,
    notifier: FakeNotifier | None = None,
    analyzer: object | None = None,
) -> tuple[
    CollectAndNotifyDetections,
    FakeDetectionApprovalRepository,
    FakeNotificationRepository,
    FakeNotifier,
]:
    approval_repo = approvals or FakeDetectionApprovalRepository()
    notification_repo = notifications or FakeNotificationRepository()
    fake_notifier = notifier or FakeNotifier()
    return (
        CollectAndNotifyDetections(
            detection_source=source,
            approval_repository=approval_repo,
            collection_run_repository=runs,
            notification_builder=SanitizedDetectionNotificationBuilder(Sanitizer("test-secret")),
            notification_repository=notification_repo,
            notifier=fake_notifier,
            analyzer=analyzer,  # type: ignore[arg-type]
            now=datetime(2026, 6, 24, tzinfo=UTC),
        ),
        approval_repo,
        notification_repo,
        fake_notifier,
    )


@pytest.mark.asyncio
async def test_collect_detections_skips_pre_cutoff_records_without_side_effects() -> None:
    source = FakeDetectionSource(
        [
            DetectionPage(
                detections=[
                    _detection("old-1", occur_time="2026-05-01T00:00:00Z"),
                    _detection("old-2", occur_time="2026-05-10T00:00:00Z"),
                ],
                next_page_token=None,
            )
        ]
    )
    runs = FakeDetectionCollectionRunRepository()
    use_case, approvals, notifications, notifier = _use_case(source, runs)

    result = await use_case.execute(
        limit=1,
        page_size=1000,
        max_pages_per_run=10,
        backfill_window_days=30,
    )

    assert result.collected_count == 2
    assert result.skipped_count == 2
    assert notifier.payloads == []
    assert approvals.pending == []
    assert notifications.marked == []


@pytest.mark.asyncio
async def test_collect_detections_processes_only_post_cutoff_records() -> None:
    source = FakeDetectionSource(
        [
            DetectionPage(
                detections=[
                    _detection("old", occur_time="2026-05-01T00:00:00Z"),
                    _detection("new", occur_time="2026-06-20T00:00:00Z"),
                    _detection(
                        "high",
                        severity="SEVERITY_LEVEL_HIGH",
                        occur_time="2026-06-20T00:00:00Z",
                    ),
                ],
                next_page_token=None,
            )
        ]
    )
    use_case, approvals, _, notifier = _use_case(source, FakeDetectionCollectionRunRepository())

    result = await use_case.execute(
        limit=10,
        page_size=1000,
        max_pages_per_run=10,
        backfill_window_days=30,
    )

    assert result.skipped_count == 1
    assert result.notified_count == 2
    assert result.pending_approval_count == 0
    assert len(notifier.payloads) == 2
    assert approvals.pending == []


@pytest.mark.asyncio
async def test_skipped_records_do_not_count_against_notify_limit() -> None:
    source = FakeDetectionSource(
        [
            DetectionPage(
                detections=[
                    _detection(f"old-{index}", occur_time="2026-05-01T00:00:00Z")
                    for index in range(5)
                ],
                next_page_token="page-2",  # noqa: S106
            ),
            DetectionPage(
                detections=[_detection("new", occur_time="2026-06-20T00:00:00Z")],
                next_page_token=None,
            ),
        ]
    )
    use_case, _, _, notifier = _use_case(source, FakeDetectionCollectionRunRepository())

    result = await use_case.execute(
        limit=1,
        page_size=1000,
        max_pages_per_run=10,
        backfill_window_days=30,
    )

    assert len(source.calls) == 2
    assert result.skipped_count == 5
    assert result.notified_count == 1
    assert len(notifier.payloads) == 1


@pytest.mark.asyncio
async def test_collect_detections_persists_cursor_and_resumes_from_latest_token() -> None:
    runs = FakeDetectionCollectionRunRepository()
    source = FakeDetectionSource(
        [
            DetectionPage(
                detections=[_detection("new-1", occur_time="2026-06-20T00:00:00Z")],
                next_page_token="page-2",  # noqa: S106
            )
        ]
    )
    use_case, _, _, _ = _use_case(source, runs)
    await use_case.execute(limit=10, page_size=1000, max_pages_per_run=10, backfill_window_days=30)

    assert runs.cursor_tokens == ["page-2"]
    assert runs.success_tokens == ["page-2"]

    next_source = FakeDetectionSource(
        [DetectionPage(detections=[_detection("new-2")], next_page_token=None)]
    )
    next_use_case, _, _, _ = _use_case(next_source, runs)
    await next_use_case.execute(
        limit=10,
        page_size=1000,
        max_pages_per_run=10,
        backfill_window_days=30,
    )

    assert next_source.calls[0] == ("page-2", 1000)


@pytest.mark.asyncio
async def test_collect_detections_stops_at_page_cap_and_persists_cursor() -> None:
    runs = FakeDetectionCollectionRunRepository()
    source = FakeDetectionSource(
        [
            DetectionPage(detections=[_detection("new-1")], next_page_token="page-2"),  # noqa: S106
            DetectionPage(detections=[_detection("new-2")], next_page_token="page-3"),  # noqa: S106
        ]
    )
    use_case, _, _, _ = _use_case(source, runs)

    result = await use_case.execute(
        limit=10,
        page_size=1000,
        max_pages_per_run=1,
        backfill_window_days=30,
    )

    assert len(source.calls) == 1
    assert result.notified_count == 1
    assert runs.success_tokens == ["page-2"]


@pytest.mark.asyncio
async def test_collect_detections_routes_high_and_low_to_notify() -> None:
    source = FakeDetectionSource(
        [
            DetectionPage(
                detections=[
                    _detection("high", severity="SEVERITY_LEVEL_HIGH"),
                    _detection("low", severity="SEVERITY_LEVEL_LOW"),
                ],
                next_page_token=None,
            )
        ]
    )
    use_case, approvals, notifications, notifier = _use_case(
        source, FakeDetectionCollectionRunRepository()
    )

    result = await use_case.execute(
        limit=10,
        page_size=1000,
        max_pages_per_run=10,
        backfill_window_days=30,
    )

    assert result.pending_approval_count == 0
    assert result.notified_count == 2
    assert approvals.pending == []
    assert len(notifier.payloads) == 2
    assert len(notifications.marked) == 2


@pytest.mark.asyncio
async def test_collect_detections_attaches_analysis_for_low_and_medium() -> None:
    source = FakeDetectionSource(
        [
            DetectionPage(
                detections=[
                    {
                        **_detection("medium", severity="SEVERITY_LEVEL_MEDIUM"),
                        "displayName": "Endpoint threat",
                        "context": {"경로": "C:\\Users\\alice\\Downloads\\sample.exe"},
                    }
                ],
                next_page_token=None,
            )
        ]
    )
    runs = FakeDetectionCollectionRunRepository()
    approvals = FakeDetectionApprovalRepository()
    notifications = FakeNotificationRepository()
    notifier = FakeNotifier()
    analyzer = FakeAnalyzer()
    builder = SpyDetectionNotificationBuilder()
    use_case = CollectAndNotifyDetections(
        detection_source=source,
        approval_repository=approvals,
        collection_run_repository=runs,
        notification_builder=builder,
        notification_repository=notifications,
        notifier=notifier,
        analyzer=analyzer,  # type: ignore[arg-type]
        now=datetime(2026, 6, 24, tzinfo=UTC),
    )

    result = await use_case.execute(
        limit=10,
        page_size=1000,
        max_pages_per_run=10,
        backfill_window_days=30,
    )

    assert result.notified_count == 1
    assert analyzer.incidents[0].title == "Endpoint threat"
    assert (
        analyzer.incidents[0].summary
        == '{"경로": "C:\\\\Users\\\\alice\\\\Downloads\\\\sample.exe"}'
    )
    assert analyzer.incidents[0].severity == Severity.MEDIUM
    assert analyzer.incidents[0].normalized_payload == {
        "source": "eset_detection",
        "raw_keys": ["context", "displayName", "occurTime", "severityLevel", "uuid"],
    }
    assert builder.calls[0][1] == _analysis_result()
    assert notifier.payloads == [{"uuid": "medium", "has_analysis": True}]
    assert runs.success_tokens == [None]


@pytest.mark.asyncio
async def test_collect_detections_analyzes_high_and_critical() -> None:
    source = FakeDetectionSource(
        [
            DetectionPage(
                detections=[
                    _detection("high", severity="SEVERITY_LEVEL_HIGH"),
                    _detection("critical", severity="SEVERITY_LEVEL_CRITICAL"),
                ],
                next_page_token=None,
            )
        ]
    )
    analyzer = FakeAnalyzer()
    use_case, approvals, _, notifier = _use_case(
        source,
        FakeDetectionCollectionRunRepository(),
        analyzer=analyzer,
    )

    result = await use_case.execute(
        limit=10,
        page_size=1000,
        max_pages_per_run=10,
        backfill_window_days=30,
    )

    assert result.pending_approval_count == 0
    assert result.notified_count == 2
    assert approvals.pending == []
    assert len(notifier.payloads) == 2
    assert [incident.severity for incident in analyzer.incidents] == [
        Severity.HIGH,
        Severity.CRITICAL,
    ]


@pytest.mark.asyncio
async def test_collect_detections_analysis_failure_notifies_and_saves_success() -> None:
    source = FakeDetectionSource(
        [
            DetectionPage(
                detections=[
                    _detection("fails", severity="SEVERITY_LEVEL_LOW"),
                    _detection("works", severity="SEVERITY_LEVEL_LOW"),
                ],
                next_page_token=None,
            )
        ]
    )
    runs = FakeDetectionCollectionRunRepository()
    notifier = FakeNotifier()
    builder = SpyDetectionNotificationBuilder()
    use_case = CollectAndNotifyDetections(
        detection_source=source,
        approval_repository=FakeDetectionApprovalRepository(),
        collection_run_repository=runs,
        notification_builder=builder,
        notification_repository=FakeNotificationRepository(),
        notifier=notifier,
        analyzer=FakeAnalyzer(fail_on="fails"),  # type: ignore[arg-type]
        now=datetime(2026, 6, 24, tzinfo=UTC),
    )

    result = await use_case.execute(
        limit=10,
        page_size=1000,
        max_pages_per_run=10,
        backfill_window_days=30,
    )

    assert result.notified_count == 2
    assert [call[1] for call in builder.calls] == [None, _analysis_result()]
    assert notifier.payloads == [
        {"uuid": "fails", "has_analysis": False},
        {"uuid": "works", "has_analysis": True},
    ]
    assert runs.failure_message is None
    assert runs.success_tokens == [None]


@pytest.mark.asyncio
async def test_collect_detections_skips_already_delivered_detection() -> None:
    detection = _detection("duplicate", occur_time="2026-06-20T00:00:00Z")
    delivered_key = build_idempotency_key("duplicate", "2026-06-20T00:00:00Z", "discord")
    source = FakeDetectionSource([DetectionPage(detections=[detection], next_page_token=None)])
    notifications = FakeNotificationRepository(delivered={delivered_key})
    use_case, _, _, notifier = _use_case(
        source,
        FakeDetectionCollectionRunRepository(),
        notifications=notifications,
    )

    result = await use_case.execute(
        limit=10,
        page_size=1000,
        max_pages_per_run=10,
        backfill_window_days=30,
    )

    assert result.duplicate_skipped_count == 1
    assert result.notified_count == 0
    assert notifier.payloads == []
