"""Proveedor OpenRouter (solo chat). OpenRouter no expone embeddings fiables."""
from __future__ import annotations

import requests

from ..base import AIError, BaseChatProvider, BaseEmbedProvider, EmbeddingNotSupported


class OpenRouterChatProvider(BaseChatProvider):
    def list_models(self):
        base_url = self.config.get("base_url") or ""
        models_url = base_url.replace("/chat/completions", "/models")
        resp = requests.get(models_url, timeout=self.config.get("timeout", 30))
        if resp.status_code >= 400:
            raise AIError(f"OpenRouter {resp.status_code}: {resp.text[:300]}")
        return sorted(m["id"] for m in resp.json().get("data", []))

    def chat(self, messages, *, json: bool = False):
        api_key = self.config.get("api_key")
        base_url = self.config.get("base_url")
        if not api_key:
            raise AIError("OPENROUTER_API_KEY no configurada.")
        payload = {
            "model": self.model or "openai/gpt-4o-mini",
            "messages": messages,
        }
        if json:
            payload["response_format"] = {"type": "json_object"}
        resp = requests.post(
            base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/notisnotis",
                "X-Title": "facet.news",
            },
            json=payload,
            timeout=self.config.get("timeout", 120),
        )
        if resp.status_code >= 400:
            raise AIError(f"OpenRouter {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return self.parse_json(content) if json else content


class OpenRouterEmbedProvider(BaseEmbedProvider):
    def embed(self, texts):
        raise EmbeddingNotSupported(
            "OpenRouter no soporta embeddings. Usa AI_EMBED_PROVIDER=ollama u ollama_cloud."
        )
