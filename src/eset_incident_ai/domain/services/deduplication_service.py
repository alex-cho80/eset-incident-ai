from __future__ import annotations

import hashlib
import json
from typing import Any


class DeduplicationService:
    def content_hash(self, payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
