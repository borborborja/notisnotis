"""Django settings for NotisNotis."""
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(int(default))).strip().lower() in ("1", "true", "yes", "on")


SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-insecure-dev-key")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # NotisNotis apps
    "accounts",
    "aiproviders",
    "feeds",
    "articles",
    "stories",
    "mcpserver",
    "syncapi",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "notisnotis.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "feeds.context_processors.sidebar",
            ],
        },
    },
]

WSGI_APPLICATION = "notisnotis.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=600,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es"
TIME_ZONE = os.environ.get("TIME_ZONE", "Europe/Madrid")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        # Manifest (con hashes) solo en producción; en DEBUG evita exigir collectstatic.
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "stories:home"
LOGOUT_REDIRECT_URL = "login"

# ---------------------------------------------------------------------------
# NotisNotis / IA
# ---------------------------------------------------------------------------
AI = {
    # Proveedor para chat (resúmenes, sesgo, enriquecimiento): mock|openrouter|ollama|ollama_cloud
    "CHAT_PROVIDER": os.environ.get("AI_DEFAULT_PROVIDER", "mock"),
    "CHAT_MODEL": os.environ.get("AI_DEFAULT_MODEL", ""),
    # Proveedor para embeddings (OpenRouter NO soporta embeddings de forma fiable):
    "EMBED_PROVIDER": os.environ.get("AI_EMBED_PROVIDER", os.environ.get("AI_DEFAULT_PROVIDER", "mock")),
    "EMBED_MODEL": os.environ.get("AI_EMBED_MODEL", "nomic-embed-text"),
    "EMBED_DIM": int(os.environ.get("AI_EMBED_DIM", "256")),
    # Endpoints / keys
    "OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY", ""),
    "OPENROUTER_BASE_URL": os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/chat/completions"),
    "OLLAMA_BASE_URL": os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434"),
    "OLLAMA_CLOUD_API_KEY": os.environ.get("OLLAMA_CLOUD_API_KEY", ""),
    "OLLAMA_CLOUD_BASE_URL": os.environ.get("OLLAMA_CLOUD_BASE_URL", "https://ollama.com/api/chat"),
    # Comportamiento
    "ENRICH_MODE": os.environ.get("AI_ENRICH_MODE", "on_demand"),  # batch|on_demand
    "CLUSTER_THRESHOLD": float(os.environ.get("AI_CLUSTER_THRESHOLD", "0.78")),
    "CLUSTER_WINDOW_DAYS": int(os.environ.get("AI_CLUSTER_WINDOW_DAYS", "3")),
    "TIMEOUT": int(os.environ.get("AI_TIMEOUT", "120")),
}

RSS_USER_AGENT = os.environ.get("RSS_USER_AGENT", "NotisNotis/0.1")
# Recuperación de texto completo / muros de pago (off por defecto)
FULLTEXT_ENABLED = env_bool("FULLTEXT_ENABLED", False)
FULLTEXT_BOT_UA = os.environ.get(
    "FULLTEXT_BOT_UA",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
)
