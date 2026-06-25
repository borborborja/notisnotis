"""Selección del backend de almacenamiento de media: disco local vs S3 / compatible.

Patrón de operador (infra, como DATABASE_URL): si el operador define
`AWS_STORAGE_BUCKET_NAME` en `.env`, los ficheros de media se guardan en S3 (o en un
servicio compatible: MinIO, Cloudflare R2, DigitalOcean Spaces, vía
`AWS_S3_ENDPOINT_URL`); si está vacío, se usa el disco local (FileSystemStorage).

El backend de estáticos sigue siendo whitenoise salvo que se pida `AWS_S3_STATIC=1`.

Funciones puras (reciben el dict de entorno) para poder testear sin boto3 ni red.
"""
from __future__ import annotations


def _bool(env, key, default=False):
    return env.get(key, str(int(default))).strip().lower() in ("1", "true", "yes", "on")


def s3_enabled(env) -> bool:
    return bool(env.get("AWS_STORAGE_BUCKET_NAME", "").strip())


def static_to_s3(env) -> bool:
    return s3_enabled(env) and _bool(env, "AWS_S3_STATIC", False)


def aws_settings(env) -> dict:
    """Variables `AWS_*` para django-storages (solo relevantes si `s3_enabled`)."""
    return {
        "AWS_STORAGE_BUCKET_NAME": env.get("AWS_STORAGE_BUCKET_NAME", "").strip(),
        "AWS_ACCESS_KEY_ID": env.get("AWS_ACCESS_KEY_ID", ""),
        "AWS_SECRET_ACCESS_KEY": env.get("AWS_SECRET_ACCESS_KEY", ""),
        "AWS_S3_REGION_NAME": env.get("AWS_S3_REGION_NAME", "") or None,
        # Endpoint personalizado para S3-compatible (MinIO/R2/Spaces). Vacío = AWS real.
        "AWS_S3_ENDPOINT_URL": env.get("AWS_S3_ENDPOINT_URL", "") or None,
        "AWS_S3_CUSTOM_DOMAIN": env.get("AWS_S3_CUSTOM_DOMAIN", "") or None,
        "AWS_DEFAULT_ACL": env.get("AWS_DEFAULT_ACL", "") or None,
        # URLs firmadas por defecto (bucket privado); ponlo a 0 si el bucket es público.
        "AWS_QUERYSTRING_AUTH": _bool(env, "AWS_S3_QUERYSTRING_AUTH", True),
        "AWS_S3_FILE_OVERWRITE": _bool(env, "AWS_S3_FILE_OVERWRITE", False),
    }


S3_BACKEND = "storages.backends.s3.S3Storage"
