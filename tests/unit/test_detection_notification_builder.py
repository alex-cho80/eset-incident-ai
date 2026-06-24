from __future__ import annotations

from eset_incident_ai.domain.entities.analysis import (
    EvidenceClaim,
    IncidentAnalysisResult,
    RemediationAction,
    RootCauseAnalysis,
)
from eset_incident_ai.infrastructure.discord.detection_notification_builder import (
    RAW_DETECTION_FIELDS,
    SanitizedDetectionNotificationBuilder,
)
from eset_incident_ai.security.sanitizer import Sanitizer


def _analysis_result() -> IncidentAnalysisResult:
    return IncidentAnalysisResult(
        root_cause=RootCauseAnalysis(
            executive_summary="증거 기반으로 탐지를 검토했습니다.",
            direct_cause=[
                EvidenceClaim(
                    claim="Known detection behavior matched.",
                    evidence_ids=["evidence-1"],
                    confidence=0.8,
                )
            ],
            root_causes=[
                EvidenceClaim(
                    claim="Endpoint policy requires review.",
                    evidence_ids=["evidence-2"],
                    confidence=0.6,
                )
            ],
            false_positive_probability=0.2,
        ),
        remediation=[
            RemediationAction(
                priority="immediate",
                action="영향받은 엔드포인트 상태를 확인하세요.",
                rationale="Containment status should be known before action.",
                rollback=None,
                requires_approval=False,
            )
        ],
        overall_confidence=0.8,
        evidence_coverage=0.4,
    )


def test_detection_notification_builder_preserves_only_approved_raw_fields() -> None:
    builder = SanitizedDetectionNotificationBuilder(Sanitizer("test-secret"))

    payload = builder.build(
        {
            "uuid": "detection-1",
            "displayName": "Threat for bob@example.com",
            "severityLevel": "SEVERITY_LEVEL_MEDIUM",
            "context": "Observed by analyst alice@example.com",
            "objectName": "C:\\Users\\alice\\Downloads\\sample.exe",
            "objectUrl": "https://example.invalid/alice@example.com",
            "userName": "raw.user@example.com",
            "device": "C:\\Users\\raw-device\\HostA",
            "occurTime": "2026-06-24T00:00:00Z",
        }
    )

    rendered = str(payload)
    fields = payload["embeds"][0]["fields"]  # type: ignore[index]
    values_by_name = {str(field["name"]): field["value"] for field in fields}  # type: ignore[index]
    assert RAW_DETECTION_FIELDS == {"userName", "device"}
    assert values_by_name["User"] == "raw.user@example.com"
    assert values_by_name["Device"] == "C:\\Users\\raw-device\\HostA"
    assert "alice@example.com" not in rendered
    assert "bob@example.com" not in rendered
    assert "C:\\Users\\alice\\" not in rendered
    assert "Detection userName and device fields are shown as-is" in rendered


def test_detection_notification_builder_renders_dict_context_as_json() -> None:
    builder = SanitizedDetectionNotificationBuilder(Sanitizer("test-secret"))

    payload = builder.build(
        {
            "uuid": "detection-1",
            "severityLevel": "SEVERITY_LEVEL_LOW",
            "context": {"message": "탐지됨", "items": ["one", "two"]},
        }
    )

    description = payload["embeds"][0]["description"]  # type: ignore[index]
    assert description == '{"message": "탐지됨", "items": ["one", "two"]}'
    assert "'message':" not in str(payload)


def test_detection_notification_builder_footer_without_analysis() -> None:
    builder = SanitizedDetectionNotificationBuilder(Sanitizer("test-secret"))

    payload = builder.build({"uuid": "detection-1", "severityLevel": "SEVERITY_LEVEL_LOW"})

    assert (
        payload["embeds"][0]["footer"]["text"]  # type: ignore[index]
        == "AI analysis is not yet attached. Collector notification only."
    )


def test_detection_notification_builder_attaches_analysis_fields_after_notice() -> None:
    builder = SanitizedDetectionNotificationBuilder(Sanitizer("test-secret"))

    payload = builder.build(
        {
            "uuid": "detection-1",
            "severityLevel": "SEVERITY_LEVEL_MEDIUM",
            "context": "Observed by analyst",
        },
        _analysis_result(),
    )

    fields = payload["embeds"][0]["fields"]  # type: ignore[index]
    names = [field["name"] for field in fields]  # type: ignore[index]
    values_by_name = {str(field["name"]): field["value"] for field in fields}  # type: ignore[index]
    rendered = str(payload)
    assert names[:8] == [
        "Category",
        "Occurred",
        "User",
        "Device",
        "Object",
        "Object URL",
        "SHA1",
        "Notice",
    ]
    assert names[8:] == [
        "Analysis Summary",
        "Confidence",
        "Evidence Coverage",
        "Evidence",
        "Immediate Action",
    ]
    assert values_by_name["Notice"] == (
        "Notification: email addresses and local user paths are pseudonymized in free-text "
        "fields; Detection userName and device fields are shown as-is by approved policy."
    )
    assert values_by_name["Confidence"] == "80%"
    assert values_by_name["Evidence Coverage"] == "40%"
    assert "evidence-1" in rendered
    assert "evidence-2" in rendered
    assert "영향받은 엔드포인트 상태를 확인하세요." in rendered
    assert (
        payload["embeds"][0]["footer"]["text"]  # type: ignore[index]
        == "Local RAG analysis attached. Review before action."
    )
