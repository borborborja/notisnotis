"""Configuración de IA. Usa el patrón de cascada genérico de notisnotis.optconfig.

(.env del operador > ajustes del usuario > default). Ver `notisnotis/optconfig.py`
para la dinámica completa; aquí solo se declara la lista de campos de IA.
"""
from __future__ import annotations

from notisnotis import optconfig

# (key, env_var, default, type, secret, label, choices)
FIELDS = [
    ("chat_provider", "AI_DEFAULT_PROVIDER", "mock", "str", False,
     "Proveedor de chat", ["mock", "openrouter", "ollama", "ollama_cloud"]),
    ("chat_model", "AI_DEFAULT_MODEL", "", "str", False, "Modelo de chat", None),
    ("embed_provider", "AI_EMBED_PROVIDER", "mock", "str", False,
     "Proveedor de embeddings", ["mock", "ollama", "ollama_cloud"]),
    ("embed_model", "AI_EMBED_MODEL", "nomic-embed-text", "str", False, "Modelo de embeddings", None),
    ("embed_dim", "AI_EMBED_DIM", "256", "int", False, "Dimensión de embeddings", None),
    ("openrouter_api_key", "OPENROUTER_API_KEY", "", "str", True, "OpenRouter API key", None),
    ("openrouter_base_url", "OPENROUTER_BASE_URL",
     "https://openrouter.ai/api/v1/chat/completions", "str", False, "OpenRouter base URL", None),
    ("ollama_base_url", "OLLAMA_BASE_URL", "http://host.docker.internal:11434", "str", False,
     "Ollama base URL", None),
    ("ollama_cloud_api_key", "OLLAMA_CLOUD_API_KEY", "", "str", True, "Ollama Cloud API key", None),
    ("ollama_cloud_base_url", "OLLAMA_CLOUD_BASE_URL", "https://ollama.com/api/chat", "str", False,
     "Ollama Cloud base URL", None),
    ("enrich_mode", "AI_ENRICH_MODE", "on_demand", "str", False,
     "Modo de enriquecimiento", ["on_demand", "batch"]),
    ("cluster_threshold", "AI_CLUSTER_THRESHOLD", "0.78", "float", False, "Umbral de clustering", None),
    ("cluster_window_days", "AI_CLUSTER_WINDOW_DAYS", "3", "int", False, "Ventana de clustering (días)", None),
    ("fulltext_enabled", "FULLTEXT_ENABLED", "0", "bool", False, "Texto completo / paywall", None),
]
FIELDS_BY_KEY = {f[0]: f for f in FIELDS}


def is_env_locked(key) -> bool:
    return optconfig.is_locked(FIELDS_BY_KEY[key])


def env_raw(key):
    return optconfig.env_raw(FIELDS_BY_KEY[key])


def effective_config(user=None) -> dict:
    return optconfig.resolve(FIELDS, user)


def editable_fields(user=None):
    return optconfig.editable(FIELDS, user)


def locked_fields():
    return optconfig.locked(FIELDS)
