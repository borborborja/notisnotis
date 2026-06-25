"""Proveedor Ollama Cloud (chat + embeddings) vía ollama.com."""
from __future__ import annotations

import requests

from ..base import AIError, BaseChatProvider, BaseEmbedProvider


def _auth_headers(api_key):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _cloud_tags(base_url, api_key, timeout):
    tags_url = base_url.replace("/api/chat", "/api/tags")
    resp = requests.get(tags_url, headers=_auth_headers(api_key), timeout=timeout)
    if resp.status_code >= 400:
        raise AIError(f"Ollama Cloud {resp.status_code}: {resp.text[:300]}")
    return sorted(m["name"] for m in resp.json().get("models", []))


class OllamaCloudChatProvider(BaseChatProvider):
    def list_models(self):
        return _cloud_tags(self.config.get("base_url", ""), self.config.get("api_key"),
                           self.config.get("timeout", 30))

    def chat(self, messages, *, json: bool = False):
        base_url = self.config.get("base_url")
        payload = {
            "model": self.model or "gpt-oss:20b",
            "messages": messages,
            "stream": False,
        }
        if json:
            payload["format"] = "json"
        resp = requests.post(
            base_url,
            headers=_auth_headers(self.config.get("api_key")),
            json=payload,
            timeout=self.config.get("timeout", 120),
        )
        if resp.status_code >= 400:
            raise AIError(f"Ollama Cloud {resp.status_code}: {resp.text[:300]}")
        content = resp.json()["message"]["content"]
        return self.parse_json(content) if json else content


class OllamaCloudEmbedProvider(BaseEmbedProvider):
    def list_models(self):
        return _cloud_tags(self.config.get("base_url", ""), self.config.get("api_key"),
                           self.config.get("timeout", 30))

    def embed(self, texts):
        # Deriva el endpoint de embeddings del host base de chat.
        base_url = self.config.get("base_url", "")
        embed_url = base_url.replace("/api/chat", "/api/embeddings")
        out = []
        for text in texts:
            resp = requests.post(
                embed_url,
                headers=_auth_headers(self.config.get("api_key")),
                json={"model": self.model or "nomic-embed-text", "prompt": text},
                timeout=self.config.get("timeout", 120),
            )
            if resp.status_code >= 400:
                raise AIError(f"Ollama Cloud embeddings {resp.status_code}: {resp.text[:300]}")
            out.append(resp.json()["embedding"])
        return out
