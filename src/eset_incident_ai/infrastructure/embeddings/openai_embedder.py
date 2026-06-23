from __future__ import annotations


class OpenAiEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("OpenAI embeddings require provider credentials")
