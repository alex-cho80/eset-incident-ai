from __future__ import annotations

import json
from typing import Any

from eset_incident_ai.domain.entities.analysis import IncidentAnalysisResult
from eset_incident_ai.domain.enums.severity import Severity
from eset_incident_ai.security.sanitizer import Sanitizer

RAW_DETECTION_FIELDS = frozenset({"userName", "device"})


class SanitizedDetectionNotificationBuilder:
    def __init__(self, sanitizer: Sanitizer) -> None:
        self._sanitizer = sanitizer

    def severity(self, detection: dict[str, Any]) -> Severity:
        return Severity.parse(detection.get("severityLevel"))

    def build(
        self,
        detection: dict[str, Any],
        analysis: IncidentAnalysisResult | None = None,
    ) -> dict[str, Any]:
        severity = self.severity(detection)
        title = self._safe_text(
            "displayName", detection.get("displayName") or detection.get("uuid")
        )
        context = self._safe_text("context", detection.get("context"), fallback="No context")
        fields: list[dict[str, object]] = [
            {
                "name": "Category",
                "value": self._safe_text("category", detection.get("category")),
                "inline": True,
            },
            {
                "name": "Occurred",
                "value": self._safe_text("occurTime", detection.get("occurTime")),
                "inline": True,
            },
            {
                "name": "User",
                "value": self._safe_text("userName", detection.get("userName")),
                "inline": True,
            },
            {
                "name": "Device",
                "value": self._safe_text("device", detection.get("device")),
                "inline": True,
            },
            {
                "name": "Object",
                "value": self._safe_text("objectName", detection.get("objectName")),
            },
            {
                "name": "Object URL",
                "value": self._safe_text("objectUrl", detection.get("objectUrl")),
            },
            {
                "name": "SHA1",
                "value": self._safe_text("objectHashSha1", detection.get("objectHashSha1")),
            },
            {
                "name": "Notice",
                "value": (
                    "Notification: email addresses and local user paths are pseudonymized in "
                    "free-text fields; Detection userName and device fields are shown as-is by "
                    "approved policy."
                ),
            },
        ]
        footer_text = "AI analysis is not yet attached. Collector notification only."
        if analysis is not None:
            fields.extend(self._analysis_fields(analysis))
            footer_text = "Local RAG analysis attached. Review before action."

        return {
            "username": "ESET Incident AI",
            "embeds": [
                {
                    "title": f"[{severity.value.upper()}] {title}",
                    "description": context,
                    "fields": fields,
                    "footer": {"text": footer_text},
                }
            ],
        }

    def _analysis_fields(self, analysis: IncidentAnalysisResult) -> list[dict[str, object]]:
        summary = self._safe_text("analysis", analysis.root_cause.executive_summary)
        evidence_ids = sorted(
            {
                evidence_id
                for claim in analysis.root_cause.direct_cause + analysis.root_cause.root_causes
                for evidence_id in claim.evidence_ids
            }
        )
        immediate_actions = [
            action.action for action in analysis.remediation if action.priority == "immediate"
        ]
        return [
            {"name": "Analysis Summary", "value": summary[:1024]},
            {
                "name": "Confidence",
                "value": f"{round(analysis.overall_confidence * 100)}%",
                "inline": True,
            },
            {
                "name": "Evidence Coverage",
                "value": f"{round(analysis.evidence_coverage * 100)}%",
                "inline": True,
            },
            {
                "name": "Evidence",
                "value": self._safe_text("analysis", ", ".join(evidence_ids[:5]) or "N/A"),
            },
            {
                "name": "Immediate Action",
                "value": self._safe_text(
                    "analysis",
                    "; ".join(immediate_actions[:2]) or "N/A",
                ),
            },
        ]

    def _safe_text(self, field_name: str, value: object, *, fallback: str = "N/A") -> str:
        raw_value = value or fallback
        if isinstance(raw_value, (dict, list)):
            text = json.dumps(raw_value, ensure_ascii=False)
        else:
            text = str(raw_value)
        if field_name in RAW_DETECTION_FIELDS:
            return text[:1000]
        return self._sanitizer.sanitize_text(text).text[:1000]
