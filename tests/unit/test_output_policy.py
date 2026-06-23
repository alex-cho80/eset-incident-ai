from eset_incident_ai.domain.entities.analysis import (
    EvidenceClaim,
    IncidentAnalysisResult,
    RemediationAction,
    RootCauseAnalysis,
)
from eset_incident_ai.domain.enums.severity import Severity
from eset_incident_ai.security.output_policy import OutputPolicy


def _analysis(confidence: float = 0.9, coverage: float = 0.9) -> IncidentAnalysisResult:
    return IncidentAnalysisResult(
        root_cause=RootCauseAnalysis(
            executive_summary="Summary",
            direct_cause=[
                EvidenceClaim(claim="Observed fact", evidence_ids=["EVD-1"], confidence=0.9)
            ],
            root_causes=[EvidenceClaim(claim="Root cause", evidence_ids=["EVD-1"], confidence=0.8)],
            false_positive_probability=0.1,
        ),
        remediation=[
            RemediationAction(
                priority="short_term",
                action="Review logs",
                rationale="Evidence indicates suspicious activity",
                rollback=None,
                requires_approval=False,
            )
        ],
        overall_confidence=confidence,
        evidence_coverage=coverage,
    )


def test_low_confident_clean_analysis_can_auto_notify() -> None:
    decision = OutputPolicy().evaluate(
        severity=Severity.LOW,
        analysis=_analysis(),
        unsupported_claim_count=0,
        pii_finding_count=0,
        secret_finding_count=0,
    )

    assert decision.allowed is True
    assert decision.requires_human_approval is False


def test_high_severity_requires_approval() -> None:
    decision = OutputPolicy().evaluate(
        severity=Severity.HIGH,
        analysis=_analysis(),
        unsupported_claim_count=0,
        pii_finding_count=0,
        secret_finding_count=0,
    )

    assert decision.allowed is False
    assert decision.requires_human_approval is True
    assert "human_approval_required" in decision.reasons


def test_policy_blocks_unsafe_findings() -> None:
    unsafe = _analysis(confidence=0.5, coverage=0.5)
    unsafe.remediation[0].requires_approval = True

    decision = OutputPolicy().evaluate(
        severity=Severity.MEDIUM,
        analysis=unsafe,
        unsupported_claim_count=1,
        pii_finding_count=1,
        secret_finding_count=1,
    )

    assert decision.allowed is False
    assert decision.requires_human_approval is True
    assert "destructive_action_recommended" in decision.reasons
    assert "unsupported_claims_present" in decision.reasons
    assert "pii_findings_present" in decision.reasons
    assert "secret_findings_present" in decision.reasons
    assert "confidence_below_auto_notify_threshold" in decision.reasons
    assert "evidence_coverage_below_threshold" in decision.reasons
