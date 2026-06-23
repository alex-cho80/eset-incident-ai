from __future__ import annotations


def metadata_matches(metadata: dict[str, str], required: dict[str, str]) -> bool:
    return all(metadata.get(key) == value for key, value in required.items())
