from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from eset_incident_ai.application.use_cases.collect_and_notify_incidents import (
    CollectAndNotifyIncidents,
)
from eset_incident_ai.domain.entities.analysis import (
    EvidenceClaim,
    IncidentAnalysisResult,
    RemediationAction,
    RootCauseAnalysis,
)
from eset_incident_ai.domain.entities.incident import Incident
from eset_incident_ai.infrastructure.discord.incident_notification_builder import (
    SanitizedIncidentNotificationBuilder,
)
from eset_incident_ai.infrastructure.discord.message_builder import build_idempotency_key
from eset_incident_ai.security.sanitizer import Sanitizer


class FakeIncidentSource:
    def __init__(self, incidents: list[dict[str, Any]]) -> None:
        self._incidents = incidents

    async def iter_incidents(
        self, *, updated_after: str | None, page_size: int
    ) -> AsyncIterator[dict[str, Any]]:
        _ = (updated_after, page_size)
        for incident in self._incidents:
            yield incident

    async def get_incident(self, incident_uuid: str) -> dict[str, Any]:
        return {"uuid": incident_uuid}


class FailingIncidentSource:
    async def iter_incidents(
        self, *, updated_after: str | None, page_size: int
    ) -> AsyncIterator[dict[str, Any]]:
        _ = (updated_after, page_size)
        raise TimeoutError("ESET request timed out")
        yield {}

    async def get_incident(self, incident_uuid: str) -> dict[str, Any]:
        return {"uuid": incident_uuid}


class FakeNotifier:
    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    async def send(self, payload: dict[str, Any]) -> None:
        self.payloads.append(payload)


class FakeNotificationRepository:
    def __init__(self, delivered: set[str] | None = None) -> None:
        self.delivered = delivered or set()

    async def was_delivered(self, idempotency_key: str) -> bool:
        return idempotency_key in self.delivered

    async def mark_delivered(self, *, idempotency_key: str, destination: str) -> None:
        _ = destination
        self.delivered.add(idempotency_key)


class FakeApprovalRepository:
    def __init__(self) -> None:
        self.pending: list[dict[str, object]] = []

    async def save_pending(self, *, incident: dict[str, object], severity: str) -> None:
        self.pending.append({"incident": incident, "severity": severity})

    async def list_pending(self, *, limit: int) -> list[object]:
        _ = limit
        return []

    async def get_pending(self, *, approval_id: int) -> object | None:
        _ = approval_id
        return None

    async def mark_reviewed(self, *, approval_id: int, status: str) -> None:
        _ = (approval_id, status)


class FakeCollectionRunRepository:
    def __init__(self) -> None:
        self.saved_count = 0
        self.failure_message: str | None = None

    async def save_success(self, result: object) -> None:
        _ = result
        self.saved_count += 1

    async def save_failure(self, *, error_message: str) -> None:
        self.failure_message = error_message

    async def list_recent(self, *, limit: int) -> list[object]:
        _ = limit
        return []

    async def latest(self) -> object | None:
        return None


class FakeAnalyzer:
    def __init__(self) -> None:
        self.incidents: list[Incident] = []

    async def execute(self, *, incident: Incident, tenant_scope: str) -> IncidentAnalysisResult:
        _ = tenant_scope
        self.incidents.append(incident)
        return IncidentAnalysisResult(
            root_cause=RootCauseAnalysis(
                executive_summary="RAG evidence indicates collector failure handling.",
                direct_cause=[
                    EvidenceClaim(
                        claim="Collector failure workflow matched.",
                        evidence_ids=["evidence-1"],
                        confidence=0.8,
                    )
                ],
                root_causes=[
                    EvidenceClaim(
                        claim="Root cause requires telemetry confirmation.",
                        evidence_ids=["evidence-1"],
                        confidence=0.6,
                    )
                ],
                false_positive_probability=0.3,
            ),
            remediation=[
                RemediationAction(
                    priority="immediate",
                    action="Check worker logs.",
                    rationale="Worker logs identify failed collection steps.",
                    rollback=None,
                    requires_approval=False,
                )
            ],
            overall_confidence=0.8,
            evidence_coverage=0.2,
        )


@pytest.mark.asyncio
async def test_collect_and_notify_sends_only_low_and_medium() -> None:
    notifier = FakeNotifier()
    approvals = FakeApprovalRepository()
    runs = FakeCollectionRunRepository()
    use_case = CollectAndNotifyIncidents(
        incident_source=FakeIncidentSource(
            [
                {"uuid": "low-1", "displayName": "low incident", "severity": "low"},
                {"uuid": "high-1", "displayName": "high incident", "severity": "high"},
            ]
        ),
        approval_repository=approvals,
        collection_run_repository=runs,
        notification_builder=SanitizedIncidentNotificationBuilder(Sanitizer("test-secret")),
        notification_repository=FakeNotificationRepository(),
        notifier=notifier,
    )

    result = await use_case.execute(limit=10)

    assert result.collected_count == 2
    assert result.notified_count == 1
    assert result.pending_approval_count == 1
    assert len(approvals.pending) == 1
    assert len(notifier.payloads) == 1
    assert runs.saved_count == 1


@pytest.mark.asyncio
async def test_collect_and_notify_attaches_analysis_for_notified_incidents() -> None:
    notifier = FakeNotifier()
    analyzer = FakeAnalyzer()
    use_case = CollectAndNotifyIncidents(
        incident_source=FakeIncidentSource(
            [
                {
                    "uuid": "low-1",
                    "displayName": "collector failure on worker",
                    "description": "ESET collection failed",
                    "severity": "low",
                }
            ]
        ),
        approval_repository=FakeApprovalRepository(),
        collection_run_repository=FakeCollectionRunRepository(),
        notification_builder=SanitizedIncidentNotificationBuilder(Sanitizer("test-secret")),
        notification_repository=FakeNotificationRepository(),
        notifier=notifier,
        analyzer=analyzer,  # type: ignore[arg-type]
    )

    result = await use_case.execute(limit=10)

    rendered = str(notifier.payloads[0])
    assert result.notified_count == 1
    assert analyzer.incidents[0].title == "collector failure on worker"
    assert "Analysis Summary" in rendered
    assert "RAG evidence indicates collector failure handling." in rendered
    assert "80%" in rendered


@pytest.mark.asyncio
async def test_collect_and_notify_stops_at_limit() -> None:
    notifier = FakeNotifier()
    use_case = CollectAndNotifyIncidents(
        incident_source=FakeIncidentSource(
            [
                {"uuid": "low-1", "displayName": "first", "severity": "low"},
                {"uuid": "low-2", "displayName": "second", "severity": "low"},
            ]
        ),
        approval_repository=FakeApprovalRepository(),
        collection_run_repository=FakeCollectionRunRepository(),
        notification_builder=SanitizedIncidentNotificationBuilder(Sanitizer("test-secret")),
        notification_repository=FakeNotificationRepository(),
        notifier=notifier,
    )

    result = await use_case.execute(limit=1)

    assert result.collected_count == 1
    assert result.notified_count == 1
    assert len(notifier.payloads) == 1


@pytest.mark.asyncio
async def test_collect_and_notify_skips_duplicates() -> None:
    notifier = FakeNotifier()
    repository = FakeNotificationRepository()
    use_case = CollectAndNotifyIncidents(
        incident_source=FakeIncidentSource(
            [
                {
                    "uuid": "low-1",
                    "displayName": "first",
                    "severity": "low",
                    "updateTime": "2026-06-23T10:00:00Z",
                },
                {
                    "uuid": "low-1",
                    "displayName": "first",
                    "severity": "low",
                    "updateTime": "2026-06-23T10:00:00Z",
                },
            ]
        ),
        approval_repository=FakeApprovalRepository(),
        collection_run_repository=FakeCollectionRunRepository(),
        notification_builder=SanitizedIncidentNotificationBuilder(Sanitizer("test-secret")),
        notification_repository=repository,
        notifier=notifier,
    )

    result = await use_case.execute(limit=10)

    assert result.collected_count == 2
    assert result.notified_count == 1
    assert result.duplicate_skipped_count == 1
    assert len(notifier.payloads) == 1


@pytest.mark.asyncio
async def test_collect_and_notify_stops_at_duplicate_limit() -> None:
    repository = FakeNotificationRepository()
    repository.delivered.add(build_idempotency_key("low-1", "2026-06-23T10:00:00Z", "discord"))
    use_case = CollectAndNotifyIncidents(
        incident_source=FakeIncidentSource(
            [
                {
                    "uuid": "low-1",
                    "displayName": "first",
                    "severity": "low",
                    "updateTime": "2026-06-23T10:00:00Z",
                }
            ]
        ),
        approval_repository=FakeApprovalRepository(),
        collection_run_repository=FakeCollectionRunRepository(),
        notification_builder=SanitizedIncidentNotificationBuilder(Sanitizer("test-secret")),
        notification_repository=repository,
        notifier=FakeNotifier(),
    )

    result = await use_case.execute(limit=1)

    assert result.collected_count == 1
    assert result.duplicate_skipped_count == 1


@pytest.mark.asyncio
async def test_collect_and_notify_records_failure_and_reraises() -> None:
    runs = FakeCollectionRunRepository()
    use_case = CollectAndNotifyIncidents(
        incident_source=FailingIncidentSource(),
        approval_repository=FakeApprovalRepository(),
        collection_run_repository=runs,
        notification_builder=SanitizedIncidentNotificationBuilder(Sanitizer("test-secret")),
        notification_repository=FakeNotificationRepository(),
        notifier=FakeNotifier(),
    )

    with pytest.raises(TimeoutError):
        await use_case.execute(limit=10)

    assert runs.failure_message == "TimeoutError: ESET request timed out"


def test_collect_and_notify_uses_default_failure_message() -> None:
    use_case = CollectAndNotifyIncidents(
        incident_source=FakeIncidentSource([]),
        approval_repository=FakeApprovalRepository(),
        collection_run_repository=FakeCollectionRunRepository(),
        notification_builder=SanitizedIncidentNotificationBuilder(Sanitizer("test-secret")),
        notification_repository=FakeNotificationRepository(),
        notifier=FakeNotifier(),
    )

    assert (
        use_case._safe_error_message(Exception())  # noqa: SLF001
        == "Exception: No error detail provided."
    )


def test_collect_and_notify_truncates_failure_message() -> None:
    use_case = CollectAndNotifyIncidents(
        incident_source=FakeIncidentSource([]),
        approval_repository=FakeApprovalRepository(),
        collection_run_repository=FakeCollectionRunRepository(),
        notification_builder=SanitizedIncidentNotificationBuilder(Sanitizer("test-secret")),
        notification_repository=FakeNotificationRepository(),
        notifier=FakeNotifier(),
    )

    assert len(use_case._safe_error_message(RuntimeError("x" * 1000))) == 500  # noqa: SLF001


def test_notification_builder_sanitizes_payload() -> None:
    builder = SanitizedIncidentNotificationBuilder(Sanitizer("test-secret"))

    payload = builder.build(
        {
            "uuid": "incident-1",
            "displayName": "user alice@example.com from 10.1.1.25",
            "description": "path C:\\Users\\alice\\Downloads\\a.exe",
            "severity": "medium",
        }
    )

    rendered = str(payload)
    assert "alice@example.com" not in rendered
    assert "10.1.1.25" in rendered
    assert "C:\\Users\\alice\\" not in rendered


def test_notification_builder_attaches_analysis_fields() -> None:
    builder = SanitizedIncidentNotificationBuilder(Sanitizer("test-secret"))
    analysis = IncidentAnalysisResult(
        root_cause=RootCauseAnalysis(
            executive_summary="Review collector failure evidence.",
            direct_cause=[
                EvidenceClaim(
                    claim="Collector failure matched runbook.",
                    evidence_ids=["evidence-1"],
                    confidence=0.8,
                )
            ],
            root_causes=[
                EvidenceClaim(
                    claim="Redis broker may be unavailable.",
                    evidence_ids=["evidence-2"],
                    confidence=0.6,
                )
            ],
            false_positive_probability=0.3,
        ),
        remediation=[
            RemediationAction(
                priority="immediate",
                action="Check worker logs.",
                rationale="Confirm collection failure source.",
                rollback=None,
                requires_approval=False,
            )
        ],
        overall_confidence=0.8,
        evidence_coverage=0.4,
    )

    payload = builder.build({"uuid": "incident-1", "severity": "medium"}, analysis)
    rendered = str(payload)

    assert "Analysis Summary" in rendered
    assert "Evidence Coverage" in rendered
    assert "evidence-1" in rendered
    assert "Local RAG analysis attached" in rendered


def test_notification_builder_normalizes_unknown_severities() -> None:
    builder = SanitizedIncidentNotificationBuilder(Sanitizer("test-secret"))

    assert builder.severity({"severity": "info"}).value == "low"
    assert builder.severity({"severity": "unknown"}).value == "low"
