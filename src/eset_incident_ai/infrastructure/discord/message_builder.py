from __future__ import annotations

import hashlib
from typing import Any

from eset_incident_ai.domain.entities.analysis import IncidentAnalysisResult
from eset_incident_ai.domain.enums.severity import Severity


def build_idempotency_key(incident_id: str, analysis_version: str, destination: str) -> str:
    raw = f"{incident_id}:{analysis_version}:{destination}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class DiscordMessageBuilder:
    def build(
        self,
        *,
        incident_title: str,
        severity: Severity,
        analysis: IncidentAnalysisResult,
        evidence_ids: list[str],
    ) -> dict[str, Any]:
        return {
            "username": "ESET Incident AI",
            "embeds": [
                {
                    "title": f"[{severity.value.upper()}] {incident_title}",
                    "description": "인시던트 분석이 완료되었습니다.",
                    "fields": [
                        {"name": "요약", "value": analysis.root_cause.executive_summary[:1024]},
                        {
                            "name": "신뢰도",
                            "value": f"{round(analysis.overall_confidence * 100)}%",
                        },
                        {"name": "근거", "value": ", ".join(evidence_ids[:10]) or "N/A"},
                    ],
                    "footer": {"text": "AI 분석 결과이며 보안 담당자의 검토가 필요합니다."},
                }
            ],
        }
