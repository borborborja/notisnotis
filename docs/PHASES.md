# Fases pendientes — specs ejecutables

Cada tarea es **autocontenida**: objetivo, modelos/campos, endpoints, ficheros a tocar,
**criterios de aceptación** y **cómo verificar**. No necesitas nada fuera del repo.
Reglas transversales: patrón cascade (CLAUDE.md §6), provider `mock` operativo, filtrar
por usuario, migración+test+verificación por cambio. Implementa **fase a fase**.

---

## FASE B (resto)

### B1 · Web push
**Objetivo:** notificación push del navegador cuando aparece un *blindspot* nuevo o casa
una palabra clave seguida (ver C2). Requiere HTTPS + claves VAPID; solo se verifica del
todo en despliegue real.

**Config (cascade, en `notifications/config.py`):** `Capability("webpush", flag_env=
"WEBPUSH_ENABLED", fields=[vapid_public, vapid_private (secret), vapid_admin_email],
required=[vapid_public, vapid_private])`. Variables en `.env.example`.

**Modelo:** `notifications.PushSubscription(user FK, endpoint, p256dh, auth, created_at)`.
Migración nueva.

**Endpoints (`notifications/urls.py`):**
- `GET /sw-push.js` → service worker (o servir desde `static/`).
- `GET notifications/push/key/` → clave pública VAPID.
- `POST notifications/push/subscribe/` → guarda `PushSubscription` (JSON del navegador).
- `POST notifications/push/unsubscribe/`.

**Envío (`notifications/push.py`):** `send_push(user, title, body, url)` usando `pywebpush`
(añadir a `requirements.txt`; necesita Python ≥3.10 → corre en Docker). Import perezoso y
guard si falta la dependencia (como `mcpserver`). Disparadores: en `stories/analyze_stories`
al marcar un blindspot nuevo, y en C2 al casar un tema.

**Frontend:** en `static/js/app.js`, registrar SW y suscribir con la clave pública; botón
"Activar notificaciones" en Ajustes → Notificaciones.

**Aceptación:** con VAPID+HTTPS, suscribirse crea un `PushSubscription`; un blindspot nuevo
envía una notificación. Sin claves/HTTPS, la UI lo indica y no rompe.
**Verificar:** test unitario del endpoint subscribe (crea registro) y de `send_push`
(payload correcto, `pywebpush` mockeado). Real: navegador + HTTPS.

---

## FASE C — diferenciadores del agregador

### C1 · Dieta informativa (bias diet)
**Objetivo:** panel que muestra el sesgo de lo que el usuario **realmente lee** y sugiere
equilibrar (estilo "My News Bias" de Ground News).

**Sin modelo nuevo.** Vista `stories/views.bias_diet`: sobre
`Article.objects.filter(feed__user=request.user, is_read=True, read_at__gte=<ventana>)`
agrupa por `source__bias` y cuenta. Reusa `stories/views._bias_bars` para render.

**Ficheros:** `stories/views.py` (+url `stories:bias_diet`), `templates/stories/bias_diet.html`,
enlace en `templates/partials/sidebar.html` (sección Curación: "Mi dieta"). Ventana
configurable (7/30 días) por querystring.

**Aceptación:** muestra distribución L/C/R de lo leído + mensaje de balance (p.ej. "lees 80%
de derecha"). **Verificar:** test client — crea artículos leídos de fuentes con bias distinto
→ conteos correctos; artículos no leídos no cuentan.

### C2 · Seguir temas + alertas
**Objetivo:** seguir un tema y destacar/avisar de nuevas historias que casen.

**Modelo:** `stories.Topic(user FK, name, keywords (texto, regex/términos), use_embedding
bool, embedding JSON null, notify bool)`. Migración.

**Matching (`stories/topics.py`):** al crear artículos/analizar historias, casar por keyword
(reusar `feeds/filters.compile_rules`) o, si `use_embedding`, por coseno
(`stories/similarity.cosine`) ≥ umbral contra `Topic.embedding`. Si `notify` → B1.

**UI:** CRUD de temas (página o pestaña), sección "Temas" en sidebar con contador de nuevos,
filtro `articles:list?topic=<id>` (añadir rama en `articles.views._filtered_articles`).

**Aceptación:** crear tema "IA" → artículos que casan aparecen al filtrar; con `notify`+B1
genera push. **Verificar:** test del matcher por keyword y del filtro por tema.

### C3 · Tendencias, comparar fuentes y línea temporal
**Objetivo:** descubrir lo más cubierto y comparar cobertura.

- **Trending:** `stories/views.trending` → Stories ordenadas por nº de fuentes y recencia
  (`annotate(Count('story_articles'))`, ventana reciente). Plantilla + enlace sidebar.
- **Comparar fuentes:** vista que toma 2 `Source` y muestra solapamiento de historias y
  qué cubre cada una (Stories con artículos de A, de B, de ambas).
- **Línea temporal:** en `stories/_story_reading.html`, además de agrupar por sesgo, ofrecer
  orden temporal de los `StoryArticle` por `article.published_at`.

**Aceptación:** trending lista las historias con más fuentes primero; la comparación muestra
exclusivas/comunes. **Verificar:** test client con datos sembrados.

---

## FASE D — plataforma

### D1 · PWA + offline
**Objetivo:** instalable y lectura offline del shell + artículos visitados.

**Ficheros:** `static/manifest.webmanifest` (name, icons, `theme_color` lila, `display:
standalone`, `start_url:/`), `static/js/sw.js` (cache-first para estáticos; network-first
con fallback a caché para artículos visitados). Enlazar manifest en `<head>` de `base.html`
y registrar el SW en `app.js`. Iconos PWA en `static/icons/`.

**Aceptación:** la app es instalable (criterios PWA) y el shell + último artículo cargan sin
red. **Verificar:** preview/Lighthouse; comprobar registro del SW y respuesta offline.

### D2 · Gestión de cuenta (+ 2FA opcional)
**Objetivo:** cambiar contraseña/email, borrar cuenta; 2FA opcional.

**Ficheros:** `accounts/views.py` (reusar `django.contrib.auth.views.PasswordChangeView`;
vistas de cambio de email y borrado con confirmación), pestaña **"Cuenta"** en Ajustes
(`TABS` + `templates/settings/account.html`). 2FA: integrar `django-otp`/TOTP (dependencia
nueva → documentar) o dejar como sub-tarea.

**Aceptación:** cambiar contraseña re-loguea correctamente; borrar cuenta elimina sus
datos (Feed/Article/Story/UserConfig/credenciales) por cascade FK. **Verificar:** test client.

### D3 · Salud de feeds + reactivación
**Objetivo:** ver y recuperar feeds con error (ya existe `Feed.fail_count`/`last_error`;
auto-desactiva a 10 fallos).

**Ficheros:** en `templates/feeds/feed_list.html` resaltar feeds con `fail_count>0` o
`enabled=False`; acción "Reactivar" (`feeds.views`) que pone `enabled=True, fail_count=0,
last_error=""`. Opcional: filtro "solo con problemas".

**Aceptación:** un feed con ≥10 fallos aparece desactivado y reactivable. **Verificar:** test
client (poner fail_count alto → listado → reactivar).

### D4 · pgvector (escala) — META MAYOR
**Objetivo:** sustituir el coseno en Python O(n) por búsqueda ANN en Postgres, sin reescribir
las vistas. Hoy: `Article.embedding` es `JSONField`; similitud en `stories/similarity.py` y
`articles/ai_actions.related_articles`.

**Pasos:**
1. `pip` `pgvector`; imagen `pgvector/pgvector:pg16` en `compose.yaml` (sustituye `postgres:16`);
   habilitar extensión (`CREATE EXTENSION vector` vía migración `RunSQL`).
2. Añadir `articles.Article.embedding_vec = pgvector.django.VectorField(dim, null=True)`
   **solo** efectivo en Postgres; mantener `embedding` JSON como fallback SQLite/dev.
   Backfill desde JSON (management command).
3. **Abstraer la búsqueda NN** detrás de una función (p.ej. `articles/similarity_backend.py`):
   en Postgres usa `order_by(CosineDistance('embedding_vec', q))[:k]`; en SQLite usa el
   coseno actual. `cluster_stories` y `related_articles`/`search` semántico llaman a esa
   función, no a la implementación.
4. Índice ANN (`HnswIndex`/IVFFlat) en migración.

**Aceptación:** clustering y búsqueda semántica usan el backend pgvector en Postgres y
mantienen el fallback en SQLite; resultados equivalentes. **Verificar:** Postgres+pgvector en
Docker; test que compara orden de vecinos vs coseno en un set pequeño.
**Cuidado:** NO acoples lógica a que `embedding` sea JSON (CLAUDE.md §5/§8).

### D5 · Backup/restore + import Pocket/Instapaper
**Objetivo:** export/import lógico de datos del usuario; importar guardados externos.

**Ficheros:** comandos `accounts`/nuevo: `export_data --user` → JSON (feeds, categorías, tags,
estados de artículo, `UserConfig`), `import_data --user --file`. Import Pocket (export HTML/
CSV) e Instapaper (CSV) → crear artículos guardados / feeds. Botones en Ajustes.

**Aceptación:** export produce JSON re-importable que reconstruye el estado; import de Pocket
crea entradas guardadas. **Verificar:** test round-trip export→import; parseo de un CSV de muestra.
