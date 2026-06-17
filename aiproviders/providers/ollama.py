"""Proveedor Ollama local (chat + embeddings)."""
from __future__ import annotations

import requests

from ..base import AIError, BaseChatProvider, BaseEmbedProvider


class OllamaChatProvider(BaseChatProvider):
    def chat(self, messages, *, json: bool = False):
        base_url = self.config.get("base_url", "").rstrip("/")
        payload = {
            "model": self.model or "llama3.1",
            "messages": messages,
            "stream": False,
        }
        if json:
            payload["format"] = "json"
        resp = requests.post(
            f"{base_url}/api/chat",
            json=payload,
            timeout=self.config.get("timeout", 120),
        )
        if resp.status_code >= 400:
            raise AIError(f"Ollama {resp.status_code}: {resp.text[:300]}")
        content = resp.json()["message"]["content"]
        return self.parse_json(content) if json else content


class OllamaEmbedProvider(BaseEmbedProvider):
    def embed(self, texts):
        base_url = self.config.get("base_url", "").rstrip("/")
        out = []
        for text in texts:
            resp = requests.post(
                f"{base_url}/api/embeddings",
                json={"model": self.model or "nomic-embed-text", "prompt": text},
                timeout=self.config.get("timeout", 120),
            )
            if resp.status_code >= 400:
                raise AIError(f"Ollama embeddings {resp.status_code}: {resp.text[:300]}")
            out.append(resp.json()["embedding"])
        return out
