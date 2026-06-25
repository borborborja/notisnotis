"""Configuración de IA. Usa el patrón de cascada genérico de notisnotis.optconfig.

(.env del operador > ajustes del usuario > default). Ver `notisnotis/optconfig.py`
para la dinámica completa; aquí solo se declara la lista de campos de IA.
"""
from __future__ import annotations

from notisnotis import optconfig

# (key, env_var, default, type, secret, label, choices)
FIELDS = [
    ("chat_provider", "AI_DEFAULT_PROVIDER", "mock", "str", False,
     "Proveedor de chat", ["mock", "openrouter", "openai", "ollama", "ollama_cloud"]),
    ("chat_model", "AI_DEFAULT_MODEL", "", "str", False, "Modelo de chat", None),
    ("embed_provider", "AI_EMBED_PROVIDER", "mock", "str", False,
     "Proveedor de embeddings", ["mock", "openai", "jina", "ollama", "ollama_cloud"]),
    ("embed_model", "AI_EMBED_MODEL", "nomic-embed-text", "str", False, "Modelo de embeddings", None),
    ("embed_dim", "AI_EMBED_DIM", "256", "int", False, "Dimensión de embeddings", None),
    ("openrouter_api_key", "OPENROUTER_API_KEY", "", "str", True, "OpenRouter API key", None),
    ("openrouter_base_url", "OPENROUTER_BASE_URL",
     "https://openrouter.ai/api/v1/chat/completions", "str", False, "OpenRouter base URL", None),
    ("openai_api_key", "OPENAI_API_KEY", "", "str", True, "OpenAI API key", None),
    ("openai_base_url", "OPENAI_BASE_URL", "https://api.openai.com/v1", "str", False,
     "OpenAI base URL", None),
    ("jina_api_key", "JINA_API_KEY", "", "str", True, "Jina API key", None),
    ("jina_base_url", "JINA_BASE_URL", "https://api.jina.ai/v1", "str", False, "Jina base URL", None),
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


def fields_state(user=None) -> dict:
    """Estado por campo para pintar la UI agrupada por proveedor.

    Devuelve dict key -> {key,label,type,secret,choices,default,locked,value,
    has_value,env_value,effective}. `value` es lo editable (vacío en secretos);
    `effective` es el valor resuelto (cascada) para preseleccionar.
    """
    data = optconfig.user_data(user)
    resolved = optconfig.resolve(FIELDS, user)
    out = {}
    for f in FIELDS:
        key, secret = f[optconfig.KEY], f[optconfig.SECRET]
        locked = optconfig.is_locked(f)
        out[key] = {
            "key": key,
            "label": f[optconfig.LABEL],
            "type": f[optconfig.TYPE],
            "secret": secret,
            "choices": f[optconfig.CHOICES],
            "default": f[optconfig.DEFAULT],
            "locked": locked,
            "value": "" if secret else (optconfig.env_raw(f) if locked else data.get(key, "")),
            "has_value": str(resolved.get(key, "")).strip() != "",
            "env_value": optconfig.env_raw(f) if locked else "",
            "effective": resolved.get(key, ""),
        }
    return out


def editable_fields(user=None):
    return optconfig.editable(FIELDS, user)


def locked_fields():
    return optconfig.locked(FIELDS)
