from __future__ import annotations

import hashlib
from pathlib import Path

from eset_incident_ai.rag.document_factory import KnowledgeDocument

SUPPORTED_SUFFIXES = {".md", ".txt"}


def iter_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )


def document_from_file(path: Path, *, root: Path) -> KnowledgeDocument:
    content = path.read_text(encoding="utf-8")
    relative_path = path.relative_to(root).as_posix()
    source_id = relative_path
    if len(source_id) > 128:
        source_id = hashlib.sha256(relative_path.encode("utf-8")).hexdigest()
    title = first_heading(content) or path.stem.replace("_", " ").replace("-", " ").title()
    category = path.relative_to(root).parts[0] if path.relative_to(root).parts else "knowledge"
    return KnowledgeDocument(
        source_type="knowledge",
        source_id=source_id,
        title=title,
        content=content,
        metadata={
            "path": relative_path,
            "category": category,
        },
    )


def first_heading(content: str) -> str | None:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or None
    return None
