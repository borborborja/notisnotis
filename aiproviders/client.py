"""Factoría de clientes de IA con resolución de config por usuario (.env > usuario > default)."""
from __future__ import annotations

from django.conf import settings

from .config import effective_config
from .providers.jina import JinaEmbedProvider
from .providers.mock import MockChatProvider, MockEmbedProvider
from .providers.ollama import OllamaChatProvider, OllamaEmbedProvider
from .providers.ollama_cloud import OllamaCloudChatProvider, OllamaCloudEmbedProvider
from .providers.mock import MockTranscribeProvider
from .providers.openai import OpenAIChatProvider, OpenAIEmbedProvider, OpenAITranscribeProvider
from .providers.openrouter import OpenRouterChatProvider, OpenRouterEmbedProvider
from .providers.whisper_local import WhisperLocalTranscribeProvider

_CHAT = {
    "mock": MockChatProvider,
    "openrouter": OpenRouterChatProvider,
    "openai": OpenAIChatProvider,
    "ollama": OllamaChatProvider,
    "ollama_cloud": OllamaCloudChatProvider,
}
_EMBED = {
    "mock": MockEmbedProvider,
    "openrouter": OpenRouterEmbedProvider,
    "openai": OpenAIEmbedProvider,
    "jina": JinaEmbedProvider,
    "ollama": OllamaEmbedProvider,
    "ollama_cloud": OllamaCloudEmbedProvider,
}
_TRANSCRIBE = {
    "mock": MockTranscribeProvider,
    "whisper_local": WhisperLocalTranscribeProvider,
    "openai": OpenAITranscribeProvider,
}


def _provider_kwargs(provider, cfg):
    return {
        "openrouter": {"api_key": cfg["openrouter_api_key"], "base_url": cfg["openrouter_base_url"]},
        "openai": {"api_key": cfg["openai_api_key"], "base_url": cfg["openai_base_url"]},
        "jina": {"api_key": cfg["jina_api_key"], "base_url": cfg["jina_base_url"]},
        "ollama": {"base_url": cfg["ollama_base_url"]},
        "ollama_cloud": {"api_key": cfg["ollama_cloud_api_key"], "base_url": cfg["ollama_cloud_base_url"]},
        "whisper_local": {"url": cfg["whisper_url"]},
        "mock": {},
    }.get(provider, {})


def build_chat_client(cfg):
    """Construye el cliente de chat a partir de un cfg ya resuelto (dict)."""
    provider = cfg["chat_provider"]
    cls = _CHAT.get(provider)
    if cls is None:
        raise ValueError(f"Proveedor de chat desconocido: {provider}")
    kwargs = _provider_kwargs(provider, cfg)
    kwargs["timeout"] = settings.AI["TIMEOUT"]
    return cls(model=cfg["chat_model"], **kwargs)


def build_embed_client(cfg):
    """Construye el cliente de embeddings a partir de un cfg ya resuelto (dict)."""
    provider = cfg["embed_provider"]
    cls = _EMBED.get(provider)
    if cls is None:
        raise ValueError(f"Proveedor de embeddings desconocido: {provider}")
    kwargs = _provider_kwargs(provider, cfg)
    kwargs["timeout"] = settings.AI["TIMEOUT"]
    return cls(model=cfg["embed_model"], dim=cfg["embed_dim"], **kwargs)


def build_transcribe_client(cfg):
    """Construye el cliente de transcripción a partir de un cfg ya resuelto (dict)."""
    provider = cfg["transcribe_provider"]
    cls = _TRANSCRIBE.get(provider)
    if cls is None:
        raise ValueError(f"Proveedor de transcripción desconocido: {provider}")
    kwargs = _provider_kwargs(provider, cfg)
    kwargs["timeout"] = settings.AI.get("TRANSCRIBE_TIMEOUT", 1800)
    return cls(model=cfg["transcribe_model"], **kwargs)


def get_chat_client(user=None):
    return build_chat_client(effective_config(user))


def get_embed_client(user=None):
    return build_embed_client(effective_config(user))


def get_transcribe_client(user=None):
    return build_transcribe_client(effective_config(user))
