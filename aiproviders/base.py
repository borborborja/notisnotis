"""Interfaz común de los proveedores de IA.

Cada proveedor implementa:
    chat(messages, *, json=False) -> str | dict
    embed(texts: list[str]) -> list[list[float]]
"""
from __future__ import annotations

import json as jsonlib
import re


class AIError(RuntimeError):
    pass


class EmbeddingNotSupported(AIError):
    pass


class BaseChatProvider:
    def __init__(self, model: str = "", **kwargs):
        self.model = model
        self.config = kwargs

    def chat(self, messages, *, json: bool = False):  # pragma: no cover - interface
        raise NotImplementedError

    @staticmethod
    def parse_json(text: str):
        """Extrae el primer objeto JSON de una respuesta de chat, tolerante a ```json fences."""
        text = text.strip()
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
        try:
            return jsonlib.loads(text)
        except jsonlib.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return jsonlib.loads(match.group(0))
            raise AIError(f"Respuesta del LLM no es JSON válido: {text[:200]!r}")


class BaseEmbedProvider:
    def __init__(self, model: str = "", dim: int = 256, **kwargs):
        self.model = model
        self.dim = dim
        self.config = kwargs

    def embed(self, texts):  # pragma: no cover - interface
        raise NotImplementedError
