"""Transcripción con un Whisper self-hosted OpenAI-compatible (speaches / faster-whisper-server).

Endpoints usados:
  POST {url}/v1/audio/transcriptions  (multipart file + model + language) → texto
  GET  {url}/v1/models                → modelos instalados
  POST {url}/v1/models/{id}           → descarga (pull) un modelo

speaches también descarga el modelo solo en el primer uso si no está instalado.
"""
from __future__ import annotations

import requests

from ..base import AIError, BaseTranscribeProvider

# Tamaños comunes para poder elegir/descargar uno aún no instalado.
COMMON_MODELS = [
    "Systran/faster-whisper-tiny", "Systran/faster-whisper-base",
    "Systran/faster-whisper-small", "Systran/faster-whisper-medium",
    "Systran/faster-whisper-large-v3", "deepdml/faster-whisper-large-v3-turbo-ct2",
]


class WhisperLocalTranscribeProvider(BaseTranscribeProvider):
    def _base(self):
        return (self.config.get("url") or "http://whisper:8000").rstrip("/")

    def transcribe(self, audio_bytes, *, filename="audio.mp3", lang=""):
        data = {"model": self.model or "Systran/faster-whisper-small"}
        if lang:
            data["language"] = lang
        resp = requests.post(
            f"{self._base()}/v1/audio/transcriptions",
            files={"file": (filename, audio_bytes)},
            data=data,
            timeout=self.config.get("timeout", 1800),  # transcribir es lento
        )
        if resp.status_code >= 400:
            raise AIError(f"Whisper {resp.status_code}: {resp.text[:300]}")
        try:
            return (resp.json().get("text") or "").strip()
        except ValueError:
            return resp.text.strip()

    def list_models(self):
        """Modelos instalados (vía /v1/models) mezclados con los tamaños comunes."""
        installed = []
        try:
            resp = requests.get(f"{self._base()}/v1/models", timeout=15)
            if resp.status_code < 400:
                data = resp.json()
                rows = data.get("data", data) if isinstance(data, dict) else data
                installed = [r.get("id") for r in rows if isinstance(r, dict) and r.get("id")]
        except requests.RequestException:
            installed = []
        out = list(installed)
        for m in COMMON_MODELS:
            if m not in out:
                out.append(m)
        return out

    def download_model(self, model_id):
        """Descarga (pull) un modelo en el servidor speaches. Bloqueante (lento)."""
        resp = requests.post(f"{self._base()}/v1/models/{model_id}",
                             timeout=self.config.get("timeout", 1800))
        if resp.status_code >= 400:
            raise AIError(f"Descarga {resp.status_code}: {resp.text[:300]}")
        return True
