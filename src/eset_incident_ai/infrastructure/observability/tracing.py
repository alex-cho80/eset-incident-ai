from __future__ import annotations

from contextlib import nullcontext
from typing import Any


def start_span(name: str) -> Any:
    _ = name
    return nullcontext()
