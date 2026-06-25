"""Proveedor Jina AI (solo embeddings) vía https://api.jina.ai.

`jina-embeddings-v3` soporta `dimensions` (Matryoshka): pedimos self.dim para encajar en
la columna pgvector. Con modelos sin soporte de dimensión variable, ajusta AI_EMBED_DIM
a la dimensión nativa y regenera la migración del campo.
"""
from __future__ import annotations

import requests

from ..base import AIError, BaseEmbedProvider


class JinaEmbedProvider(BaseEmbedProvider):
    # Jina no expone un endpoint de listado; lista curada de modelos de embeddings.
    KNOWN_MODELS = [
        "jina-embeddings-v3",
        "jina-embeddings-v2-base-en",
        "jina-embeddings-v2-base-es",
        "jina-embeddings-v2-base-code",
        "jina-clip-v2",
    ]

    def list_models(self):
        return list(self.KNOWN_MODELS)

    def embed(self, texts):
        api_key = self.config.get("api_key")
        base_url = self.config.get("base_url") or "https://api.jina.ai/v1"
        if not api_key:
            raise AIError("JINA_API_KEY no configurada.")
        resp = requests.post(
            f"{base_url}/embeddings",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            json={
                "model": self.model or "jina-embeddings-v3",
                "input": list(texts),
                "dimensions": self.dim,
            },
            timeout=self.config.get("timeout", 120),
        )
        if resp.status_code >= 400:
            raise AIError(f"Jina embeddings {resp.status_code}: {resp.text[:300]}")
        data = sorted(resp.json()["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in data]
