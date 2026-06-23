from __future__ import annotations

from eset_incident_ai.domain.entities.analysis import (
    EvidenceClaim,
    IncidentAnalysisResult,
    RemediationAction,
    RootCauseAnalysis,
)
from eset_incident_ai.domain.entities.evidence import RetrievedEvidence
from eset_incident_ai.domain.entities.incident import Incident
from eset_incident_ai.domain.enums.severity import Severity


class LocalAnalysisGateway:
    async def analyze(
        self, *, incident: Incident, evidence: list[RetrievedEvidence]
    ) -> IncidentAnalysisResult:
        evidence_ids = [item.evidence_id for item in evidence[:5]]
        if not evidence_ids:
            evidence_ids = ["no-supporting-evidence"]

        confidence = self._confidence(incident=incident, evidence=evidence)
        summary = (
            f"Incident '{incident.title}' requires investigation. "
            f"The analysis used {len(evidence)} retrieved evidence item(s)."
        )

        return IncidentAnalysisResult(
            root_cause=RootCauseAnalysis(
                executive_summary=summary,
                direct_cause=[
                    EvidenceClaim(
                        claim=self._direct_cause_claim(incident),
                        evidence_ids=evidence_ids,
                        confidence=confidence,
                    )
                ],
                root_causes=[
                    EvidenceClaim(
                        claim="Root cause is not confirmed without endpoint-level evidence.",
                        evidence_ids=evidence_ids,
                        confidence=max(confidence - 0.2, 0.1),
                    )
                ],
                false_positive_probability=self._false_positive_probability(incident),
                unknowns=[
                    "Endpoint process tree is not attached.",
                    "User and asset context may be redacted or unavailable.",
                ],
                additional_checks=[
                    "Review ESET detection details and affected device timeline.",
                    "Compare indicators against internal allowlists and recent change records.",
                ],
            ),
            remediation=[
                RemediationAction(
                    priority="immediate",
                    action="Validate the detection in ESET and confirm affected device scope.",
                    rationale="Initial validation reduces false positives before escalation.",
                    rollback=None,
                    requires_approval=False,
                ),
                RemediationAction(
                    priority="short_term",
                    action="Isolate or contain affected endpoint only after human approval.",
                    rationale=(
                        "Containment can disrupt business activity and requires operator review."
                    ),
                    rollback=(
                        "Remove isolation from the endpoint after approval if validated benign."
                    ),
                    requires_approval=incident.severity in {Severity.HIGH, Severity.CRITICAL},
                ),
            ],
            overall_confidence=confidence,
            evidence_coverage=min(len(evidence) / 5, 1.0),
            limitations=[
                "Local deterministic analysis does not call an external LLM.",
                "Findings are advisory and must be reviewed by a security operator.",
            ],
        )

    def _confidence(self, *, incident: Incident, evidence: list[RetrievedEvidence]) -> float:
        base = 0.35
        if incident.summary:
            base += 0.15
        if evidence:
            base += min(len(evidence), 5) * 0.08
        if incident.severity in {Severity.HIGH, Severity.CRITICAL}:
            base += 0.1
        return min(base, 0.85)

    def _direct_cause_claim(self, incident: Incident) -> str:
        return (
            f"Observed ESET incident severity is {incident.severity.value}; "
            "direct cause should be confirmed with detection telemetry."
        )

    def _false_positive_probability(self, incident: Incident) -> float:
        if incident.severity in {Severity.HIGH, Severity.CRITICAL}:
            return 0.25
        if incident.severity is Severity.MEDIUM:
            return 0.4
        return 0.55
