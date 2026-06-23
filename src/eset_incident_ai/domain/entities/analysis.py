from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EvidenceClaim(BaseModel):
    claim: str
    evidence_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class RootCauseAnalysis(BaseModel):
    executive_summary: str
    direct_cause: list[EvidenceClaim]
    root_causes: list[EvidenceClaim]
    attack_path: list[str] = Field(default_factory=list)
    affected_assets: list[str] = Field(default_factory=list)
    false_positive_probability: float = Field(ge=0.0, le=1.0)
    unknowns: list[str] = Field(default_factory=list)
    additional_checks: list[str] = Field(default_factory=list)


class RemediationAction(BaseModel):
    priority: Literal["immediate", "short_term", "long_term"]
    action: str
    rationale: str
    rollback: str | None = None
    requires_approval: bool


class IncidentAnalysisResult(BaseModel):
    root_cause: RootCauseAnalysis
    remediation: list[RemediationAction]
    overall_confidence: float = Field(ge=0.0, le=1.0)
    evidence_coverage: float = Field(ge=0.0, le=1.0)
    limitations: list[str] = Field(default_factory=list)

    @property
    def requires_destructive_approval(self) -> bool:
        return any(action.requires_approval for action in self.remediation)
