# facet.news — guía para agentes/LLM

> **LÉEME ANTES DE TOCAR NADA.** Este archivo es el contrato de mantenimiento.
> Si vas a cambiar algo, primero busca el patrón existente y replícalo. No inventes
> arquitectura nueva ni dependencias sin necesidad. Documentos de apoyo:
> [`docs/ROADMAP.md`](docs/ROADMAP.md), [`docs/DEPLOY.md`](docs/DEPLOY.md),
> [`docs/REFERENCES.md`](docs/REFERENCES.md) (qué proyecto mirar ante cada duda).

## 1. Qué es facet.news
Lector de RSS **self-hosted** estilo Feedly + agregador estilo **Ground News**, con IA.
Dos productos en uno:
- **Agregador**: agrupa noticias de varias fuentes sobre un mismo suceso (embeddings +
  similitud), estima **sesgo** político por fuente (LLM), detecta **blindspots** y redacta
  **resúmenes por perspectiva**.
- **Lector enriquecido**: artículos individuales con **contexto/afirmaciones** (LLM),
  **traducir**, **resumir**, **chat** sobre la noticia, tags, leído/guardado.

Multi-usuario: cada usuario sube su OPML y ve sus feeds/historias. El **operador**
aporta las API keys (o las pone cada usuario — ver §6). Hay APIs de sincronización
(Fever + Google Reader) para lectores externos, y un servidor MCP.

Stack: **Django 4.2**, PostgreSQL (SQLite en dev), `feedparser`, `beautifulsoup4`,
`requests`, **htmx** (sin build), `gunicorn`+`whitenoise`. Sin framework JS, sin Node.

## 2. GOLDEN RULES (romper esto rompe el proyecto)
1. **Toda opción configurable usa el patrón de cascada** `notisnotis/optconfig.py`
   (.env del operador > ajustes del usuario > default). NO leas `os.environ` suelto
   ni añadas settings ad-hoc. Ver §6.
2. **Preferencias por usuario** se guardan en `accounts.UserConfig.data` (un dict JSON),
   NO en modelos nuevos salvo que haya relaciones. Usa claves únicas (`read_size`,
   `smtp_host`, `digest_optin`…).
3. **Sin emoji en la UI. Usa iconos SVG** del sprite `templates/partials/icons.html`:
   `<svg class="ic"><use href="#i-NOMBRE"/></svg>`. Si falta un icono, añádelo al sprite.
4. **Colores solo con variables CSS** (`var(--accent)`, etc.) definidas en `:root` y
   `[data-theme="dark"]` al inicio de `static/css/app.css`. El acento es **lila**
   (`--accent`). Nada de hex hardcodeado en componentes.
5. **Escrituras en BD secuenciales.** Si paralelizas (p.ej. red), haz solo la parte de
   red en hilos y escribe en BD en el hilo principal (SQLite se bloquea con writes
   concurrentes). Ver `feeds/management/commands/fetch_feeds.py`.
6. **Filtra SIEMPRE por usuario** (`feed__user=request.user`, `user=request.user`).
   `Source` es el único modelo global (compartido). Nunca expongas datos de otros users.
7. **Secretos**: en formularios, si el campo secreto llega vacío, NO lo sobrescribas
   (mantén el guardado). Ver `optconfig.save_user_fields`.
8. **Cada cambio: migración (si toca modelos) + test + `manage.py check` + verificación**
   (§7). No dejes migraciones sin crear.
9. **Provider `mock`** debe seguir funcionando sin claves (es como se prueba todo offline).
   Si añades una tarea de IA, añade su rama en `aiproviders/providers/mock.py`.
10. **No subas secretos.** `.env` está en `.gitignore`. Todo va a `.env.example` vacío.
11. **Toda función se declara en el registro de features** (`features/registry.py`) y se
    gatea con `@feature_required("key")` (vistas) y `{% if 'key' in features %}` (plantillas).
    El sistema está *dormido* por defecto (`FEATURES_ENFORCED=0` → todo activo); permite
    tiers/beta/overrides por usuario sin tocar el código. Ver [`docs/FEATURES.md`](docs/FEATURES.md).
    Distíngelo de optconfig: **feature = acceso (quién)**, **capability = configuración (cómo)**.

## 3. Organización del código
Proyecto Django `notisnotis/` (settings, urls, wsgi/asgi, **`optconfig.py`**).
Apps (cada una con `models.py`, `views.py`, `urls.py`, `tests.py`, `migrations/`):

| App | Responsabilidad | Claves |
|---|---|---|
| `accounts` | auth, registro, **Ajustes (pestañas)**, `UserConfig` (prefs JSON), `ApiToken` (MCP) | `views.settings_view` orquesta todas las pestañas |
| `aiproviders` | abstracción LLM chat+embed; **config IA** | `client.get_chat_client/get_embed_client(user)`, `config.py` (FIELDS), `providers/{mock,openrouter,ollama,ollama_cloud}.py` |
| `feeds` | `Source`(global), `Feed`, `Category`, `Rule`; OPML; descubrimiento; fetch RSS; filtros; reglas | `opml.py`, `discovery.py`, `filters.py`, `rules.py`, `context_processors.sidebar` |
| `articles` | `Article`, `Tag`; lector (htmx); IA por artículo | `views.py` (lista/parciales/panel lectura), `ai_actions.py` (traducir/resumir/chat/related), `fulltext.py`, `enrich.py` |
| `stories` | `Story`, `StoryArticle`; clustering + análisis (sesgo/blindspot/perspectivas) | `similarity.py` (coseno en Python), `analysis.py` |
| `syncapi` | APIs **Fever** + **Google Reader**; `SyncCredential` | `fever.py`, `googlereader.py`, `auth.py` |
| `notifications` | **digest email** (capacidad sobre optconfig), webhook | `config.py` (SMTP + Capability), `digest.py`, cmd `send_digest` |
| `mcpserver` | servidor MCP (FastMCP) | `server.py`, cmd `run_mcp` (requiere Python ≥3.10) |

Plantillas en `templates/` (shell: `base.html`; sin sidebar: `base_plain.html`;
ajustes: `settings/base.html` + una por pestaña; parciales en `partials/` y `articles/_*`).
Estáticos en `static/` (`css/app.css`, `js/app.js`, `js/htmx.min.js`).

**Pipeline** (`stories/run_pipeline` encadena): `compute_intervals` → `fetch_feeds`
→ `embed_articles` → `enrich_articles` → `cluster_stories` → `rate_sources`
→ `fetch_favicons` → `analyze_stories`. Lo ejecuta el servicio `scheduler` en bucle.

## 4. Guidelines de programación
- **Python**: sigue el estilo existente (sin type hints pesados, funciones cortas,
  `# noqa: BLE001` en `except Exception` de borde). No añadas dependencias salvo que sea
  imprescindible (y entonces a `requirements.txt` + nota de compatibilidad de versión Python).
- **Vistas**: `@login_required`; acciones que mutan → `@require_POST`. Parciales htmx
  devuelven el fragmento (p.ej. `articles/_reading_pane.html`), no la página entera.
- **htmx**: interacciones con `hx-get/hx-post` + `hx-target`/`hx-swap`. El CSRF va por
  `hx-headers` en `<body>` de `base.html`; los `fetch()` manuales leen la cookie `csrftoken`.
- **Plantillas**: reusa parciales (`partials/biasbar.html`, `partials/source_icon.html`,
  `partials/sidebar.html`). Datos del sidebar vienen del context processor, no por vista.
- **Management commands**: idempotentes, con `--user`/`--limit`/`--dry-run` donde aplique.
  Tolera fallos de red/IA por elemento (try/except + continue), nunca abortes el lote.
- **IA por usuario**: usa `get_chat_client(user)` / `get_embed_client(user)` y
  `effective_config(user)`. Nunca el cliente global sin usuario en código por-usuario.
- **JS** (`static/js/app.js`): cada `init*()` se llama dentro de un `try/catch` en
  `DOMContentLoaded` para que un fallo no tumbe el resto. Mantén ese aislamiento.

## 5. Metas futuras (tenlas en cuenta AL programar ahora)
- **pgvector ya está implementado (solo Postgres).** La búsqueda NN vive desacoplada en
  `stories/nn.py`: en Postgres usa `Article.embedding_vec` (VectorField) + índice HNSW vía
  `CosineDistance`; en SQLite/dev cae al **coseno en Python** sobre `Article.embedding`
  (JSON portable). Mantén AMBOS caminos: el JSON es el fallback y la fuente de verdad
  portable; `embedding_vec` se puebla en paralelo solo en Postgres (`embed_articles`). Si
  tocas embeddings/clustering, hazlo a través de `top_k_articles` y no acoples lógica a que
  el embedding sea JSON ni a que exista pgvector.
- **Web push** pendiente (Fase B): necesitará `WEBPUSH_ENABLED` + claves VAPID por
  cascade, modelo `PushSubscription`, service worker y `pywebpush`. Diséñalo como capacidad.
- **PWA/offline, gestión de cuenta, 2FA, salud de feeds, backup/restore**: ya implementados
  (ver `docs/ROADMAP.md`). El 2FA (TOTP) vive en `accounts/twofa.py` + `accounts/middleware.py`,
  gateado por la función `twofa`. Backoff avanzado de feeds sigue abierto: no cierres puertas
  (p.ej. mantén el shell servible offline).
- **Búsqueda**: ya usa `SearchVector` en Postgres y fallback `icontains` en SQLite; al
  escalar, considera un índice GIN persistente (migración aparte).

## 6. CONVENCIÓN CLAVE — configuración en cascada (lo que pidió el usuario)
Implementada en **`notisnotis/optconfig.py`**. Toda opción (API keys, SMTP, flags…) se
resuelve así:
1. Si el operador la fija en **`.env`** (no vacía) → **global/bloqueada**; todos la
   heredan y la ven solo lectura en Ajustes.
2. Si está vacía → cada **usuario** la configura en sus Ajustes (`UserConfig.data`).
3. Si nadie la define → **default** del campo.

Funciones apagables = `Capability(flag_env, fields, required)`:
- flag off → desactivada; flag on + `required` en `.env` → global; flag on + `required`
  vacíos → el usuario rellena la conexión. (Ejemplo canónico: digest, ver `notifications/config.py`.)

**Para añadir una opción nueva:** declara `Field`s
`(key, env_var, default, type, secret, label, choices)` y usa
`optconfig.resolve/editable/locked/save_user_fields` en vista+plantilla. Ejemplos:
`aiproviders/config.py` (IA) y `notifications/config.py` (SMTP/digest). Documenta la
variable en `.env.example`. **No crees un mecanismo de settings paralelo.**

## 7. Cómo verificar CADA cambio
Antes de dar por bueno un cambio, ejecuta lo que aplique (venv: `.venv/bin/python`):

| Cambio | Verificación |
|---|---|
| Cualquiera | `python manage.py check` y `python manage.py test` (debe quedar verde; hoy ~37 tests) |
| Modelos | `python manage.py makemigrations <app>` (¡apps nuevas necesitan el label explícito!) + `migrate` |
| Lógica (filtros, reglas, parsers, IA) | añade test unitario en `<app>/tests.py`; usa provider `mock` |
| Comando de pipeline | ejecútalo con `--user demo --dry-run`/`--limit` y revisa el resumen |
| **UI (htmx/CSS/JS)** | navegador real vía **Preview MCP**: `preview_start` (config en `.claude/launch.json`), login (`demo`/`demo12345`), `preview_eval` para simular y leer estado. OJO: el **CSRF rota al hacer login** → pide token fresco tras login. |
| APIs (Fever/GReader) | `curl` o `preview_eval`; ver `syncapi/tests.py` |
| Estáticos en prod | con `DEBUG=0` hace falta `collectstatic` (Manifest storage); en dev no |

Usuario de pruebas: **`demo` / `demo12345`** (tiene datos reales cargados). Sirve en
`http://127.0.0.1:8000`. Con `AI_*_PROVIDER=mock` todo funciona sin claves.

## 8. Trampas conocidas (no te estrelles)
- `makemigrations` sin args **no detecta apps nuevas** la primera vez → pásale el label.
- **CSRF rota al login** (afecta a tests por fetch en navegador; el test client de Django
  no lo aplica salvo `enforce_csrf_checks`).
- `ManifestStaticFilesStorage` exige `collectstatic`; por eso el storage es condicional a
  `DEBUG` en `settings.py`. No lo quites.
- `mcp` (servidor MCP) requiere **Python ≥3.10**; el dev local usa 3.9. El núcleo
  (incl. `pywebpush`, `django-otp`, `pgvector`) funciona en 3.9; el MCP corre en Docker (3.12).
- No nombres módulos/apps como paquetes pip (`mcp` → app se llama `mcpserver`).
- `Article.embedding` (JSON) es el fallback portable y la similitud va en Python en SQLite;
  en Postgres además existe `embedding_vec` (pgvector). Accede SIEMPRE vía `stories/nn.py`.

## 9. Estado y tareas planificadas
Estado en [`docs/ROADMAP.md`](docs/ROADMAP.md); **specs ejecutables autocontenidas** de
todo lo pendiente en [`docs/PHASES.md`](docs/PHASES.md) (objetivo, modelos, endpoints,
ficheros, aceptación y verificación por tarea — no necesitas nada fuera del repo).
Hecho: agregador, lector enriquecido, UI Feedly, fetch concurrente+ETag, búsqueda,
suscripción/descubrimiento, categorías, filtros/reglas, tags, sync Fever+GReader, MCP,
digest email, web push (Fase B), Fase C (dieta de sesgo, temas, tendencias) y Fase D
(PWA, cuenta + **2FA TOTP**, **pgvector**, backup). Hardening de prod: cookies seguras,
HSTS/SSL, logging, Docker no-root (ver `settings.py` y `docs/DEPLOY.md`). Abierto:
backoff avanzado de feeds y verificación real en HTTPS de PWA/push.

## 10. Deploy
Ver [`docs/DEPLOY.md`](docs/DEPLOY.md). Resumen: `docker compose up` (web + db + scheduler;
perfil `mcp` opcional). Repo: https://github.com/borborborja/notisnotis (CI publica
la imagen en `ghcr.io/borborborja/notisnotis`).
