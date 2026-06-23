from __future__ import annotations


class Metrics:
    def increment(self, name: str, *, value: int = 1) -> None:
        _ = (name, value)
