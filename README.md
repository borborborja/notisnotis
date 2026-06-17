# NotisNotis

Agregador de noticias self-hosted estilo **Ground News** + **lector RSS enriquecido**,
con análisis por LLM. Tú aportas las API keys (OpenRouter / Ollama / Ollama-cloud);
cada usuario aporta su propio **OPML**.

> **¿Vas a desarrollar/mantener (o eres un agente/LLM)?** Lee primero
> [`CLAUDE.md`](CLAUDE.md) (contrato de mantenimiento, convenciones y reglas de oro),
> [`docs/ROADMAP.md`](docs/ROADMAP.md), [`docs/DEPLOY.md`](docs/DEPLOY.md) y
> [`docs/REFERENCES.md`](docs/REFERENCES.md) (proyectos a mirar ante dudas de implementación).

## Qué hace

- **Agregador**: agrupa artículos de varias fuentes sobre el mismo suceso (embeddings +
  similitud coseno), estima el **sesgo** de cada fuente (LLM, cacheado), dibuja una
  **barra de sesgo**, detecta **blindspots** y redacta **resumen neutral + perspectivas**
  (izquierda/centro/derecha).
- **Lector RSS enriquecido**: artículos individuales con estado leído/guardado y un panel
  de **contexto** + **afirmaciones señaladas** (controvertidas/disputadas/opinión) + nota
  de encuadre, generado por LLM.
- **Texto completo / muros de pago**: recuperación en cascada (readability → user-agent de
  bot → archive). Desactivado por defecto (`FULLTEXT_ENABLED=0`); respeta copyright y ToS.
- **Servidor MCP**: expone tus historias/artículos a un LLM externo (Claude Desktop, etc.).

## Stack

Django 4.2 · PostgreSQL (SQLite en dev) · feedparser · BeautifulSoup · gunicorn + whitenoise.
Embeddings en `JSONField` con similitud coseno en Python (portable; sin pgvector).

## Desarrollo local (sin keys)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # DEBUG=1 para dev cómodo; AI_*_PROVIDER=mock
python manage.py migrate
python manage.py createsuperuser

# Datos de ejemplo
python manage.py import_opml --user <tu_usuario> --file sample.opml
python manage.py run_pipeline        # fetch → embed → cluster → rate → analyze (mock)

python manage.py runserver
```

Abre `http://localhost:8000`. Con `mock` todo funciona offline (los embeddings mock no
agrupan semánticamente como un modelo real, pero ejercitan el flujo completo).

## Con IA real

En `.env`:

```ini
AI_DEFAULT_PROVIDER=openrouter      # chat: resúmenes, sesgo, enriquecimiento
OPENROUTER_API_KEY=...
AI_EMBED_PROVIDER=ollama            # embeddings (OpenRouter NO da embeddings)
AI_EMBED_MODEL=nomic-embed-text
AI_EMBED_DIM=768                    # dimensión del modelo elegido
```

## Patrón de configuración en cascada (operador / usuario)

**Todas** las opciones (API keys de IA, SMTP, texto completo, etc.) siguen la misma
dinámica de 3 estados — implementada en `notisnotis/optconfig.py`:

1. **Global (operador):** si defines la variable en `.env` con un valor no vacío, queda
   **bloqueada**: la usan todos los usuarios y no pueden cambiarla (se muestra como solo
   lectura en Ajustes).
2. **Por usuario:** si la dejas vacía en `.env`, cada usuario la configura en sus Ajustes
   (válido solo para él).
3. **Por defecto:** si nadie la define, se usa el valor por defecto del campo.

Las funciones que se pueden apagar tienen además un **flag** booleano en `.env`
(p.ej. `DIGEST_ENABLED`, `FULLTEXT_ENABLED`). Combinado con el SMTP, el digest ilustra el
patrón completo:

| `DIGEST_ENABLED` | SMTP en `.env` | Resultado |
|---|---|---|
| `0` | — | Digest desactivado para todos. |
| `1` | configurado | Digest **global**: el usuario solo elige frecuencia/hora/email. |
| `1` | vacío | El usuario indica **su propio SMTP** + sus preferencias en Ajustes. |

Para añadir una opción nueva con esta dinámica: declara sus `Field`s (tupla
`key, env_var, default, type, secret, label, choices`) y, si aplica, una `Capability`
con su `flag_env` y `required`; reutiliza `optconfig.resolve/editable/locked` en la vista
y `optconfig.save_user_fields` al guardar. Es exactamente lo que hacen `aiproviders/config.py`
y `notifications/config.py`.

## Digest por email

`DIGEST_ENABLED=1` + SMTP (global en `.env` o por usuario en Ajustes → Notificaciones).
El operador programa el envío por cron:

```bash
python manage.py send_digest --frequency daily     # diario
python manage.py send_digest --frequency weekly     # semanal
python manage.py send_digest --frequency daily --dry-run   # prueba sin enviar
```

## Pipeline (cron / scheduler)

```bash
python manage.py run_pipeline       # encadena todos los pasos
```

Pasos individuales: `fetch_feeds`, `embed_articles`, `enrich_articles`,
`cluster_stories`, `rate_sources`, `analyze_stories`.

## Docker

```bash
cp .env.example .env                # ajusta SECRET_KEY, ALLOWED_HOSTS, keys
docker compose up -d                # web + db + scheduler
docker compose --profile mcp up -d  # + servidor MCP (HTTP en :8765)
```

`web` corre migraciones y `collectstatic` al arrancar. `scheduler` ejecuta el pipeline
cada `PIPELINE_INTERVAL` segundos.

## Servidor MCP (Python ≥ 3.10)

1. Genera un token en **Ajustes → Tokens de API**.
2. stdio (Claude Desktop): `NOTISNOTIS_API_TOKEN=<token> python manage.py run_mcp`
3. HTTP/SSE: `python manage.py run_mcp --http --port 8765`

Tools: `list_stories`, `get_story`, `search_articles` (semántica), `list_articles`,
`get_article`, `get_full_text`, `list_blindspots`, `list_feeds`.

## Tests

```bash
python manage.py test
```
