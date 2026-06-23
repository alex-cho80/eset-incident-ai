from __future__ import annotations

from dataclasses import dataclass, field

from eset_incident_ai.domain.entities.incident import Incident


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    source_type: str
    source_id: str
    title: str
    content: str
    metadata: dict[str, str] = field(default_factory=dict)


class IncidentDocumentFactory:
    def from_incident(self, incident: Incident) -> KnowledgeDocument:
        content = "\n".join(
            part
            for part in [
                f"Title: {incident.title}",
                f"Severity: {incident.severity.value}",
                f"Summary: {incident.summary or ''}",
            ]
            if part
        )
        return KnowledgeDocument(
            source_type="incident",
            source_id=incident.external_id,
            title=incident.title,
            content=content,
            metadata={"severity": incident.severity.value},
        )
