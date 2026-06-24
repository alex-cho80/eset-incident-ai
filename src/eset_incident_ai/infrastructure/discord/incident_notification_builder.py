from __future__ import annotations

from typing import Any

from eset_incident_ai.domain.entities.analysis import IncidentAnalysisResult
from eset_incident_ai.domain.enums.severity import Severity
from eset_incident_ai.security.sanitizer import Sanitizer


class SanitizedIncidentNotificationBuilder:
    def __init__(self, sanitizer: Sanitizer) -> None:
        self._sanitizer = sanitizer

    def severity(self, incident: dict[str, Any]) -> Severity:
        text = str(incident.get("severity") or "low").lower()
        if text in {"informational", "info"}:
            return Severity.LOW
        if text in {severity.value for severity in Severity}:
            return Severity(text)
        return Severity.LOW

    def build(
        self,
        incident: dict[str, Any],
        analysis: IncidentAnalysisResult | None = None,
    ) -> dict[str, Any]:
        severity = self.severity(incident)
        title = self._safe_text(incident.get("displayName") or incident.get("uuid"))
        description = self._safe_text(incident.get("description"), fallback="No description")
        status = self._safe_text(incident.get("status"))
        create_time = self._safe_text(incident.get("createTime"))
        update_time = self._safe_text(incident.get("updateTime"))
        fields: list[dict[str, object]] = [
            {"name": "Status", "value": status, "inline": True},
            {"name": "Created", "value": create_time, "inline": True},
            {"name": "Updated", "value": update_time, "inline": True},
        ]
        footer_text = "AI analysis is not yet attached. Collector notification only."
        if analysis is not None:
            fields.extend(self._analysis_fields(analysis))
            footer_text = "Local RAG analysis attached. Review before action."
        fields.append(
            {
                "name": "Notice",
                "value": (
                    "Notification: email addresses are pseudonymized; IP addresses and other "
                    "identifiers are shown as-is."
                ),
            }
        )

        return {
            "username": "ESET Incident AI",
            "embeds": [
                {
                    "title": f"[{severity.value.upper()}] {title}",
                    "description": description,
                    "fields": fields,
                    "footer": {"text": footer_text},
                }
            ],
        }

    def _analysis_fields(self, analysis: IncidentAnalysisResult) -> list[dict[str, object]]:
        summary = self._safe_text(analysis.root_cause.executive_summary)
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
                "value": self._safe_text(", ".join(evidence_ids[:5]) or "N/A"),
            },
            {
                "name": "Immediate Action",
                "value": self._safe_text("; ".join(immediate_actions[:2]) or "N/A"),
            },
        ]

    def _safe_text(self, value: object, *, fallback: str = "N/A") -> str:
        text = str(value or fallback)
        return self._sanitizer.sanitize_text(text).text[:1000]
