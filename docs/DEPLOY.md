# Despliegue y operación

## 0. Estado del repositorio
El proyecto **todavía NO está en ningún repositorio Git**. Para inicializarlo:

```bash
cd /Users/borja/Codi/notisnotis
git init && git add -A && git commit -m "NotisNotis: estado inicial"
# crea el remoto (ejemplo) y sube:
gh repo create notisnotis --private --source=. --push      # o git remote add origin <url> && git push -u origin main
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

> Homelab Micapum: el `compose.yaml` puede alinearse con las convenciones del usuario
> (redes `cloudflare-net`/`xarxa_docker_micapum`, rutas `/opt/stacks`, labels Dockflare/
> Watchtower) — usar el skill `docker-deploy` para esa parte si aplica.

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
