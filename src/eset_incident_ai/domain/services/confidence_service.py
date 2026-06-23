from __future__ import annotations


class ConfidenceService:
    def combine(self, *, model_confidence: float, evidence_coverage: float) -> float:
        bounded_model = min(max(model_confidence, 0.0), 1.0)
        bounded_evidence = min(max(evidence_coverage, 0.0), 1.0)
        return round((bounded_model * 0.6) + (bounded_evidence * 0.4), 4)
