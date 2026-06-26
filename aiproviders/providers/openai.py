"""Proveedor OpenAI (chat + embeddings).

`base_url` es la raíz de la API (def. https://api.openai.com/v1); también sirve para
gateways compatibles (Azure OpenAI, LocalAI, vLLM…) cambiándola. La misma clave/URL se
usa tanto si OpenAI se elige para chat como para embeddings.
"""
from __future__ import annotations

import requests

from ..base import AIError, BaseChatProvider, BaseEmbedProvider, BaseTranscribeProvider


def _auth_headers(api_key):
    return {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}


def _openai_models(api_key, base_url, timeout):
    resp = requests.get(f"{base_url}/models", headers=_auth_headers(api_key), timeout=timeout)
    if resp.status_code >= 400:
        raise AIError(f"OpenAI {resp.status_code}: {resp.text[:300]}")
    return [m["id"] for m in resp.json().get("data", [])]


class OpenAIChatProvider(BaseChatProvider):
    def list_models(self):
        ids = _openai_models(self.config.get("api_key"),
                             self.config.get("base_url") or "https://api.openai.com/v1",
                             self.config.get("timeout", 30))
        # Modelos de chat (descarta embeddings, audio, imagen, moderación…).
        chat = [m for m in ids if any(t in m for t in ("gpt", "o1", "o3", "o4", "chat"))
                and "embedding" not in m]
        return sorted(chat or ids)

    def chat(self, messages, *, json: bool = False):
        api_key = self.config.get("api_key")
        base_url = self.config.get("base_url") or "https://api.openai.com/v1"
        if not api_key:
            raise AIError("OPENAI_API_KEY no configurada.")
        payload = {
            "model": self.model or "gpt-4o-mini",
            "messages": messages,
        }
        if json:
            payload["response_format"] = {"type": "json_object"}
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers=_auth_headers(api_key),
            json=payload,
            timeout=self.config.get("timeout", 120),
        )
        if resp.status_code >= 400:
            raise AIError(f"OpenAI {resp.status_code}: {resp.text[:300]}")
        content = resp.json()["choices"][0]["message"]["content"]
        return self.parse_json(content) if json else content


class OpenAIEmbedProvider(BaseEmbedProvider):
    def list_models(self):
        ids = _openai_models(self.config.get("api_key"),
                             self.config.get("base_url") or "https://api.openai.com/v1",
                             self.config.get("timeout", 30))
        return sorted(m for m in ids if "embedding" in m)

    def embed(self, texts):
        api_key = self.config.get("api_key")
        base_url = self.config.get("base_url") or "https://api.openai.com/v1"
        if not api_key:
            raise AIError("OPENAI_API_KEY no configurada.")
        # Batch: un solo request con la lista. `dimensions` recorta la salida a self.dim
        # (soportado por text-embedding-3-*) para que encaje en la columna pgvector.
        resp = requests.post(
            f"{base_url}/embeddings",
            headers=_auth_headers(api_key),
            json={
                "model": self.model or "text-embedding-3-small",
                "input": list(texts),
                "dimensions": self.dim,
            },
            timeout=self.config.get("timeout", 120),
        )
        if resp.status_code >= 400:
            raise AIError(f"OpenAI embeddings {resp.status_code}: {resp.text[:300]}")
        data = sorted(resp.json()["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in data]


class OpenAITranscribeProvider(BaseTranscribeProvider):
    def transcribe(self, audio_bytes, *, filename="audio.mp3", lang=""):
        api_key = self.config.get("api_key")
        base_url = self.config.get("base_url") or "https://api.openai.com/v1"
        if not api_key:
            raise AIError("OPENAI_API_KEY no configurada.")
        data = {"model": self.model or "whisper-1"}
        if lang:
            data["language"] = lang
        resp = requests.post(
            f"{base_url}/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},  # multipart: no fijar Content-Type
            files={"file": (filename, audio_bytes)},
            data=data,
            timeout=self.config.get("timeout", 600),
        )
        if resp.status_code >= 400:
            raise AIError(f"OpenAI transcripción {resp.status_code}: {resp.text[:300]}")
        return (resp.json().get("text") or "").strip()

    def list_models(self):
        return ["whisper-1", "gpt-4o-transcribe", "gpt-4o-mini-transcribe"]
