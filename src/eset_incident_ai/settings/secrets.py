from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SecretRef:
    name: str
    value: str

    def redacted(self) -> str:
        return "<SECRET_REDACTED>" if self.value else ""
