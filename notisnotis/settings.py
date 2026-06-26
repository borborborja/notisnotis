"""Django settings for NotisNotis."""
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(int(default))).strip().lower() in ("1", "true", "yes", "on")


INSECURE_DEV_KEY = "change-me-insecure-dev-key"
SECRET_KEY = os.environ.get("SECRET_KEY", INSECURE_DEV_KEY)
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

# En producción (DEBUG=0) no se permite arrancar con la SECRET_KEY de desarrollo.
if not DEBUG and SECRET_KEY == INSECURE_DEV_KEY:
    raise ImproperlyConfigured(
        "SECRET_KEY no configurada: define SECRET_KEY en el entorno antes de arrancar con DEBUG=0."
    )

# ---------------------------------------------------------------------------
# Seguridad (activa en producción; en dev/DEBUG no fuerza HTTPS)
# ---------------------------------------------------------------------------
# Cookies: por defecto solo por HTTPS (Secure) en producción. Si además sirves la app
# por http en la LAN, pon COOKIE_SECURE=0 en .env para no perder la sesión al recargar.
_cookie_secure = env_bool("COOKIE_SECURE", not DEBUG)
SESSION_COOKIE_SECURE = _cookie_secure
CSRF_COOKIE_SECURE = _cookie_secure
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
# Detrás de un reverse proxy (Nginx/Traefik) que termina TLS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", not DEBUG)
# HSTS apagado por defecto (0); súbelo en .env solo cuando el dominio sirva siempre HTTPS.
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)

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
    "features",
    "aifeeds",
    "podcasts",
    # 2FA (TOTP + códigos de recuperación)
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # OTP debe ir tras Authentication; añade request.user.is_verified().
    "django_otp.middleware.OTPMiddleware",
    # Fuerza el reto 2FA a usuarios con dispositivo confirmado aún no verificados.
    "accounts.middleware.Require2FAMiddleware",
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
                "features.context_processors.features",
                "features.context_processors.modules",
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

# Media (ficheros subidos). En local va a disco; ver bloque S3 abajo.
MEDIA_URL = os.environ.get("MEDIA_URL", "/media/")
MEDIA_ROOT = BASE_DIR / "media"

# Subida de ficheros: los grandes (p.ej. backups AntennaPod) se streamean a disco temporal.
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024            # >5MB → TemporaryUploadedFile (disco)
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get("DATA_UPLOAD_MAX_MEMORY_SIZE", str(512 * 1024 * 1024)))

# ---------------------------------------------------------------------------
# Almacenamiento S3 / compatible (opcional, configurado por el operador)
# ---------------------------------------------------------------------------
from notisnotis import storagecfg  # noqa: E402  (módulo puro, sin deps de Django)

if storagecfg.s3_enabled(os.environ):
    for _k, _v in storagecfg.aws_settings(os.environ).items():
        globals()[_k] = _v
    STORAGES["default"] = {"BACKEND": storagecfg.S3_BACKEND}
    if storagecfg.static_to_s3(os.environ):
        # Estáticos también en S3 (sustituye a whitenoise); colección bajo /static.
        AWS_LOCATION = "static"
        STORAGES["staticfiles"] = {"BACKEND": storagecfg.S3_BACKEND}

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
    "TRANSCRIBE_TIMEOUT": int(os.environ.get("AI_TRANSCRIBE_TIMEOUT", "1800")),
}

RSS_USER_AGENT = os.environ.get("RSS_USER_AGENT", "NotisNotis/0.1")
# Buscador web para los "feeds con IA" (SearXNG con salida JSON). Por defecto el del stack.
SEARCH_URL = os.environ.get("SEARCH_URL", "http://searxng:8080")
SEARCH_LANG = os.environ.get("SEARCH_LANG", "es")
# Recuperación de texto completo / muros de pago (off por defecto)
FULLTEXT_ENABLED = env_bool("FULLTEXT_ENABLED", False)
FULLTEXT_BOT_UA = os.environ.get(
    "FULLTEXT_BOT_UA",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
)

# ---------------------------------------------------------------------------
# Logging (a stdout; nivel configurable por entorno)
# ---------------------------------------------------------------------------
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        # Apps de NotisNotis: heredan del root, pero las dejamos explícitas para ajustarlas.
        "notisnotis": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}
