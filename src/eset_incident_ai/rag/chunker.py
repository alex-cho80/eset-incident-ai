from __future__ import annotations


class TextChunker:
    def __init__(self, *, max_chars: int = 1200, overlap_chars: int = 150) -> None:
        if overlap_chars >= max_chars:
            raise ValueError("overlap_chars must be smaller than max_chars")
        self._max_chars = max_chars
        self._overlap_chars = overlap_chars

    def chunk(self, text: str) -> list[str]:
        if not text:
            return []
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + self._max_chars)
            chunks.append(text[start:end])
            if end == len(text):
                break
            start = end - self._overlap_chars
        return chunks
