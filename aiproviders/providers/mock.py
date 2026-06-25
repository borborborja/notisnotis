"""Proveedor mock: determinista, sin red. Permite probar todo el pipeline sin keys."""
from __future__ import annotations

import hashlib
import json as jsonlib
import math

from ..base import BaseChatProvider, BaseEmbedProvider


class MockChatProvider(BaseChatProvider):
    def list_models(self):
        return ["mock-small", "mock-large"]

    def chat(self, messages, *, json: bool = False):
        user_text = "\n".join(m.get("content", "") for m in messages if m.get("role") == "user")
        if json:
            return self._mock_json(user_text)
        return f"[mock] resumen determinista de {len(user_text)} caracteres."

    def _mock_json(self, text: str):
        low = text.lower()
        # Heurística para servir distintas formas según la tarea solicitada.
        if "traduce" in low or "traductor" in low:
            return {"title": "[mock] título traducido", "body": "[mock] cuerpo traducido del artículo."}
        if "sesgo" in low or "bias" in low:
            digest = int(hashlib.sha1(text.encode()).hexdigest(), 16)
            buckets = ["left", "lean_left", "center", "lean_right", "right"]
            return {
                "bias": buckets[digest % len(buckets)],
                "factuality": "mixed",
                "reasoning": "[mock] estimación determinista para desarrollo.",
            }
        if "perspectiv" in low or "headline" in low or "blindspot" in low:
            return {
                "headline": "[mock] Titular agregado de la historia",
                "neutral_summary": "[mock] Resumen neutral generado sin LLM real.",
                "perspectives": {
                    "left": "[mock] encuadre de izquierda.",
                    "center": "[mock] encuadre de centro.",
                    "right": "[mock] encuadre de derecha.",
                },
            }
        # enriquecimiento de lector
        return {
            "context": "[mock] contexto de fondo determinista para este artículo.",
            "claims": [
                {"text": "[mock] afirmación destacada", "flag": "controversial", "note": "[mock] nota"},
            ],
            "framing_note": "[mock] nota de encuadre.",
        }


class MockEmbedProvider(BaseEmbedProvider):
    def list_models(self):
        return ["mock-embed"]

    def embed(self, texts):
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str):
        # Vector determinista basado en hash de tokens; agrupa textos idénticos/similares
        # de forma estable (suficiente para ejercitar el clustering, no semántico real).
        vec = [0.0] * self.dim
        for token in text.lower().split():
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]
