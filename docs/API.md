# API propia — `/api/v1/`

API JSON para apps cliente (móvil/web) que cubre **RSS + Podcasts + Curación IA**, consciente de
qué módulos están activos y con **sincronización incremental rápida** (sirve el contenido que el
servidor ya tiene; el cliente no re-descarga de la fuente).

## Autenticación
Dos vías (ambas usan el mismo `ApiToken`):

1. **Login** (recomendado para apps):
   ```
   POST /api/v1/auth/token
   {"username": "...", "password": "...", "otp": "123456"}   # otp solo si hay 2FA
   → {"data": {"token": "<token>", "user": "..."}}
   ```
2. **Token manual**: generado en Ajustes → Tokens.

En el resto de llamadas: `Authorization: Bearer <token>`.

## Convenciones
- Respuestas: `{"data": ...}` (+ `cursor`, `has_more`, `server_time` en listas/sync).
- Errores: `{"error": {"code", "message"}}` con HTTP 4xx/5xx (`401` sin token, `404`
  `module_disabled` si el módulo está apagado).
- Fechas ISO8601. **Importante**: al pasar `since`/`cursor` en la query, **URL-encodea** el valor
  (el `+` del offset si no se codifica llega como espacio).

## Sincronización (lo importante)
```
GET /api/v1/sync?since=<iso>&cursor=<c>&limit=200
→ {"data": {"articles": [...], "feeds": [...], "categories": [...], "tags": [...]},
   "cursor": "...", "has_more": false, "server_time": "<iso>"}
```
- Sin `since`: sync completa. Con `since=<server_time anterior>`: **solo lo cambiado** (estado o
  contenido) desde entonces, **con el contenido** (`body`, `summary`, `enclosure_url`, `image_url`…)
  → el cliente nunca vuelve a la fuente.
- Pagina con `cursor`/`has_more` (orden estable por `updated_at,id`).
- Cursor de delta: `Article.updated_at` (cambia con cualquier modificación, también desde la web).

## Meta
- `GET /api/v1/me` → usuario, **módulos activos** (`rss`/`podcasts`/`curation`), contadores.
- `GET /api/v1/modules`.

## Lector RSS
- `GET /api/v1/feeds` · `GET /api/v1/categories` · `GET /api/v1/tags`.
- `GET /api/v1/articles?feed=&category=&tag=&unread=1&saved=1&q=&since=&cursor=&limit=`.
- `GET /api/v1/articles/<id>` (incluye full_text, contexto, claims, traducción…).
- `POST /api/v1/articles/<id>/state` `{read?, saved?}`.
- `POST /api/v1/articles/state` `{ids|feed|category, older_than?, read?, saved?}` (bloque).
- `POST|DELETE /api/v1/articles/<id>/tags` `{name}`.

## Podcasts (módulo `podcasts`)
- `GET /api/v1/podcasts` · `GET /api/v1/podcasts/<id>` (+episodios) · `GET /api/v1/episodes?feed=&in_progress=1`.
- Cola: `GET/POST /api/v1/queue` `{episode_id, position?}` · `DELETE /api/v1/queue/<episode_id>` ·
  `POST /api/v1/queue/reorder` `{ids}`.
- Reproducción: `POST /api/v1/episodes/<id>/progress` `{position, duration}` ·
  `POST /api/v1/episodes/<id>/played`.
- `PATCH /api/v1/podcasts/<id>/settings` `{playback_speed, skip_intro, skip_outro}`.

## Curación IA (módulo `curation`)
- `GET /api/v1/stories?filter=recent|blindspot` · `GET /api/v1/stories/<id>` (perspectivas,
  síntesis, sesgo, **fuentes con credibilidad**).
- `GET /api/v1/trending?country=ES` · `GET /api/v1/trending/<id>` · `GET /api/v1/trending/countries`.
- `GET/POST /api/v1/aifeeds` · `GET/PATCH/DELETE /api/v1/aifeeds/<id>` (+candidatos) ·
  `POST /api/v1/aifeeds/<id>/search` · `POST /api/v1/aifeeds/candidates/<id>` `{decision:accept|reject}`.
- `GET/POST /api/v1/topics` · `DELETE /api/v1/topics/<id>`.
- `GET /api/v1/articles/<id>/related`.

## Gestión + IA on-demand
- `POST /api/v1/subscribe` `{url|feed_url, category_id?, kind?}` · `PATCH|DELETE /api/v1/feeds/<id>`.
- `GET/POST /api/v1/manage/categories` · `PATCH|DELETE /api/v1/manage/categories/<id>`.
- `POST /api/v1/opml/import` (OPML crudo o `{opml, kind}`) · `GET /api/v1/opml/export`.
- `POST /api/v1/articles/<id>/summarize|translate|context|chat` (reutiliza la IA del lector).

## Ejemplos
```bash
TOKEN=$(curl -s -XPOST $H/api/v1/auth/token -d '{"username":"u","password":"p"}' | jq -r .data.token)
curl -s $H/api/v1/me -H "Authorization: Bearer $TOKEN"
curl -s "$H/api/v1/sync" -H "Authorization: Bearer $TOKEN"      # sync completa
curl -s "$H/api/v1/sync?since=2026-06-26T10%3A00%3A00%2B00%3A00" -H "Authorization: Bearer $TOKEN"
```
