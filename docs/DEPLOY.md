# Despliegue y operación

## 0. Repositorio
Código en **https://github.com/borborborja/notisnotis**. Clonar:

```bash
git clone https://github.com/borborborja/notisnotis.git && cd notisnotis
```
`.gitignore` ya excluye `.venv/`, `db.sqlite3`, `.env`, `staticfiles/`, `__pycache__`.
**Nunca** comitees `.env` ni claves. Las migraciones **sí** se comitean.

## 1. Desarrollo local (sin claves, offline)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # DEBUG=1 para dev; AI_*_PROVIDER=mock
python manage.py migrate
python manage.py createsuperuser
python manage.py import_opml --user <usuario> --file sample.opml
python manage.py run_pipeline           # fetch → embed → cluster → analyze (mock)
python manage.py runserver              # http://127.0.0.1:8000
```
Con `mock` todo funciona sin claves. Usuario de pruebas existente: `demo` / `demo12345`.

## 1b. Imagen Docker publicada (GitHub Actions → GHCR)
Cada push a `main` (o un tag `v*`) ejecuta `.github/workflows/docker.yml`: corre los
tests y, si pasan, construye y publica la imagen en **GitHub Container Registry**:
`ghcr.io/borborborja/notisnotis` (tags: `latest`, `sha-xxxx`, y `vX.Y.Z` en tags).

Para usarla en vez de construir localmente, en `compose.yaml` cambia `build: .` por
`image: ghcr.io/borborborja/notisnotis:latest` (en `web`, `scheduler` y `mcp`). Si el
repo es privado, primero `docker login ghcr.io` con un PAT con scope `read:packages`.

## 2. Producción con Docker (build local)
```bash
cp .env.example .env     # rellena SECRET_KEY, ALLOWED_HOSTS, DATABASE_URL, claves...
docker compose up -d                 # web (gunicorn) + db (postgres) + scheduler
docker compose --profile mcp up -d   # + servidor MCP (HTTP en :8765), opcional
```
- `web`: ejecuta `migrate` + `collectstatic` en el entrypoint y sirve por gunicorn+whitenoise.
- `scheduler`: bucle que corre `run_pipeline` cada `PIPELINE_INTERVAL` s (def. 300).
- Variables clave en `.env`: `DEBUG=0`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`,
  `DATABASE_URL`, `TIME_ZONE`, y las de IA/SMTP según el patrón cascade (ver CLAUDE.md §6).

> El `compose.yaml` se puede adaptar a tu infraestructura (redes externas, rutas de
> volúmenes, labels de reverse-proxy/auto-update) según tu propio homelab.

## 2b. TLS / reverse proxy y endurecimiento
La app **no termina TLS**: ponla detrás de un reverse proxy (Nginx, Caddy, Traefik)
que sirva HTTPS y reenvíe a `web:8000`. El proxy debe enviar la cabecera
`X-Forwarded-Proto: https` (Django ya está configurado para leerla vía
`SECURE_PROXY_SSL_HEADER`).

Con `DEBUG=0` se activan automáticamente: cookies `Secure`/`HttpOnly`/`SameSite=Lax`,
`nosniff`, y redirección a HTTPS (`SECURE_SSL_REDIRECT=1`). Notas:
- **HSTS**: deja `SECURE_HSTS_SECONDS=0` hasta confirmar que el dominio sirve siempre
  por HTTPS; entonces súbelo gradualmente (p.ej. `3600` → `31536000`). Es difícil de
  revertir si lo activas con preload demasiado pronto.
- **`SECRET_KEY`**: con `DEBUG=0` el arranque **aborta** si sigues con el valor de
  ejemplo. Genera una fuerte (ver `.env.example`).
- **Postgres**: cambia `POSTGRES_PASSWORD` en `.env` (y en `DATABASE_URL`); no uses el
  valor de ejemplo en producción.
- **Contenedor**: la imagen corre como usuario no-root (`app`).
- **Healthchecks**: `db` (pg_isready) y `web` (GET `/accounts/login/`) están definidos
  en `compose.yaml`. `docker compose ps` muestra el estado `healthy`.
- **Logs**: salen a stdout (`LOG_LEVEL`, def. INFO); los recoge `docker compose logs`.

## 2c. Almacenamiento de media en S3 (opcional)
Por defecto los ficheros subidos van a disco local (`MEDIA_ROOT`). Para usar S3 o un
servicio compatible (MinIO, Cloudflare R2, DigitalOcean Spaces), define en `.env`:
```
AWS_STORAGE_BUCKET_NAME=mi-bucket
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_REGION_NAME=eu-west-1
AWS_S3_ENDPOINT_URL=          # solo para MinIO/R2/Spaces (URL del endpoint)
```
Con el bucket definido, el backend de media pasa a S3 automáticamente (django-storages
+ boto3, ya en la imagen). Los estáticos siguen en whitenoise salvo que pongas
`AWS_S3_STATIC=1` (entonces `collectstatic` los sube al bucket). Si lo dejas vacío, no
se importa boto3 y todo funciona en local.

## 3. Tareas programadas (cron)
El `scheduler` ya corre el pipeline. El **digest** se programa aparte (es time-based):
```bash
docker compose exec web python manage.py send_digest --frequency daily    # 1×/día (cron)
docker compose exec web python manage.py send_digest --frequency weekly   # 1×/semana
```
Requiere `DIGEST_ENABLED=1` + SMTP (global en `.env` o por usuario en Ajustes).

## 4. Checklist primer arranque
1. `.env` con `DEBUG=0`, `SECRET_KEY` fuerte, `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` y `DATABASE_URL`.
2. `docker compose up -d` → comprobar logs de `web` (migraciones OK) y `scheduler`.
3. Crear superusuario: `docker compose exec web python manage.py createsuperuser`.
4. Registrar usuario(s), importar OPML, esperar al scheduler o forzar `run_pipeline`.
5. (IA real) configurar proveedores en `.env` o por usuario en Ajustes → Análisis con IA.
6. (Lectores externos) Ajustes → API/MCP: copiar endpoint + app-password.

## 5. Backups
- **Postgres**: `docker compose exec db pg_dump -U notisnotis notisnotis > backup.sql`.
- Restaurar: `cat backup.sql | docker compose exec -T db psql -U notisnotis notisnotis`.
- (Pendiente roadmap) export/restore lógico en JSON desde la app.

## 6. Actualizar
```bash
git pull
docker compose build web scheduler
docker compose up -d         # el entrypoint aplica migraciones y collectstatic
```
Tras cambios de modelos: confirma que las migraciones están comiteadas. Tras cambios de
estáticos: el entrypoint hace `collectstatic`; si sirves detrás de CDN, invalida caché.

## 7. Salud / diagnóstico
- Logs: `docker compose logs -f web scheduler`.
- Estado de feeds con error: Feeds (UI) muestra el `last_error`; un feed con ≥10 fallos
  se auto-desactiva (revisar y reactivar al corregir la URL).
- `python manage.py check` debe estar limpio.
