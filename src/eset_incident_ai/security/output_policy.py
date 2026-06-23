from __future__ import annotations

from dataclasses import dataclass

from eset_incident_ai.domain.entities.analysis import IncidentAnalysisResult
from eset_incident_ai.domain.enums.severity import Severity


@dataclass(frozen=True, slots=True)
class NotificationPolicyDecision:
    allowed: bool
    requires_human_approval: bool
    reasons: tuple[str, ...]


class OutputPolicy:
    def evaluate(
        self,
        *,
        severity: Severity,
        analysis: IncidentAnalysisResult,
        unsupported_claim_count: int,
        pii_finding_count: int,
        secret_finding_count: int,
    ) -> NotificationPolicyDecision:
        reasons: list[str] = []
        requires_approval = severity in {Severity.HIGH, Severity.CRITICAL}

        if analysis.requires_destructive_approval:
            requires_approval = True
            reasons.append("destructive_action_recommended")
        if unsupported_claim_count > 0:
            reasons.append("unsupported_claims_present")
        if pii_finding_count > 0:
            reasons.append("pii_findings_present")
        if secret_finding_count > 0:
            reasons.append("secret_findings_present")
        if analysis.overall_confidence < 0.80:
            reasons.append("confidence_below_auto_notify_threshold")
        if analysis.evidence_coverage < 0.75:
            reasons.append("evidence_coverage_below_threshold")
        if requires_approval:
            reasons.append("human_approval_required")

        allowed = not reasons
        return NotificationPolicyDecision(
            allowed=allowed,
            requires_human_approval=requires_approval,
            reasons=tuple(dict.fromkeys(reasons)),
        )
