from __future__ import annotations

from eset_incident_ai.domain.entities.evidence import RetrievedEvidence


class CitationBuilder:
    def evidence_ids(self, evidence: list[RetrievedEvidence]) -> list[str]:
        return [item.evidence_id for item in evidence]
