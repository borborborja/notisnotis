"""Transcripción con un Whisper self-hosted (whisper-asr-webservice / faster-whisper).

Endpoint: POST {url}/asr?task=transcribe&language=..&output=txt con multipart `audio_file`.
Devuelve el texto plano. `url` viene de la config (whisper_url), por defecto el del stack.
"""
from __future__ import annotations

import requests

from ..base import AIError, BaseTranscribeProvider


class WhisperLocalTranscribeProvider(BaseTranscribeProvider):
    def transcribe(self, audio_bytes, *, filename="audio.mp3", lang=""):
        base = (self.config.get("url") or "http://whisper:9000").rstrip("/")
        params = {"task": "transcribe", "output": "txt", "encode": "true"}
        if lang:
            params["language"] = lang
        resp = requests.post(
            f"{base}/asr", params=params,
            files={"audio_file": (filename, audio_bytes)},
            timeout=self.config.get("timeout", 1800),  # transcribir es lento
        )
        if resp.status_code >= 400:
            raise AIError(f"Whisper {resp.status_code}: {resp.text[:300]}")
        return resp.text.strip()

    def list_models(self):
        # El modelo lo fija el contenedor (ASR_MODEL); estos son los habituales.
        return ["tiny", "base", "small", "medium", "large-v3"]
