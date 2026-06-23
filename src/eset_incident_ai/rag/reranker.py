from __future__ import annotations

from eset_incident_ai.domain.entities.evidence import RetrievedEvidence


class Reranker:
    def by_relevance(self, evidence: list[RetrievedEvidence]) -> list[RetrievedEvidence]:
        return sorted(evidence, key=lambda item: item.relevance_score, reverse=True)
