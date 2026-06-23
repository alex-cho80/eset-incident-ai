from __future__ import annotations

from eset_incident_ai.application.dto.readiness import ReadinessDTO
from eset_incident_ai.application.ports.readiness_probe import ReadinessProbe


class CheckReadiness:
    def __init__(self, readiness_probe: ReadinessProbe) -> None:
        self._readiness_probe = readiness_probe

    async def execute(self) -> ReadinessDTO:
        checks = await self._readiness_probe.check()
        status = "ready" if all(value == "ok" for value in checks.values()) else "not_ready"
        return ReadinessDTO(status=status, checks=checks)
