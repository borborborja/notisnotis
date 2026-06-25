# Roadmap y estado

Tablero de qué está hecho y qué falta. Marca aquí cuando completes algo.
**Specs ejecutables y autocontenidas de lo pendiente:** [`docs/PHASES.md`](PHASES.md)
(objetivo, modelos, endpoints, ficheros, aceptación y verificación de cada tarea).

## Hecho ✅
- **Agregador**: clustering por embeddings (coseno en Python), barra de sesgo, blindspot,
  resúmenes por perspectiva (`stories/`).
- **Lector enriquecido**: contexto + afirmaciones (LLM), traducir, resumir, chat con
  contexto de artículos relacionados (`articles/ai_actions.py`).
- **Texto completo / paywall** en cascada + crawler por feed (`articles/fulltext.py`).
- **UI Feedly**: shell 3 paneles, sidebar con categorías/tags/contadores, modos de vista
  (títulos/tarjetas/revista), columnas redimensionables, dark mode, iconos SVG, tipografía
  inline, atajos de teclado, gestos táctiles, tiempo de lectura, favicons.
- **Fetch eficiente**: concurrente (ThreadPool, red) + conditional GET (ETag/Last-Modified)
  + backoff/auto-desactivar; cadencia inteligente por fuente.
- **Búsqueda**: full-text (SearchVector en Postgres, fallback SQLite) + operadores
  `is:unread|read|saved`, `feed:`.
- **Suscripción por URL + autodescubrimiento**; **gestión de categorías** en UI.
- **Filtros** block/keep (regex) + dedupe; **motor de reglas** (auto leído/★/tag).
- **Tags** múltiples + mapeo a labels de Google Reader.
- **APIs de sincronización**: Fever + Google Reader (`syncapi/`).
- **MCP server** (`mcpserver/`).
- **Digest email** (capacidad sobre optconfig: flag + SMTP global/usuario) + webhook "enviar a".
- **Patrón de configuración en cascada** (`notisnotis/optconfig.py`) — convención global.

## Pendiente ⏳
Detalle de cada ítem en [`docs/PHASES.md`](PHASES.md).

### Fase B (resto)
- [x] **B1 · Web push** — VAPID (cascade) + `PushSubscription` + service worker + `pywebpush`;
  disparo en blindspots nuevos y temas con alerta. *Falta verificación real con HTTPS+VAPID.*

### Fase C — diferenciadores del agregador
- [x] **C1 · Dieta informativa** — `/diet/` (sesgo de lo leído).
- [x] **C2 · Seguir temas + alertas** — `stories.Topic`, filtro `?topic=`, push en `fetch_feeds`.
- [x] **C3 · Tendencias / comparar fuentes** — `/trending/`, `/compare/`. (Línea temporal de
  historia: pendiente menor en `_story_reading.html`.)

### Fase D — plataforma
- [x] **D1 · PWA + offline** — `manifest.webmanifest`, SW en `/sw.js` (caché shell + push),
  icono, registro en `app.js`. *Instalación real: verificar en despliegue HTTPS.*
- [x] **D2 · Gestión de cuenta** — cambiar email/contraseña, borrar cuenta (pestaña Cuenta).
  **2FA TOTP** activo: alta con QR + códigos de recuperación + reto en login
  (`accounts/twofa.py`, `accounts/middleware.py`, gateado por la función `twofa`).
- [x] **D3 · Salud de feeds** — estado/fallos en Feeds + reactivar.
- [x] **D4 · pgvector** — NN desacoplado en `stories/nn.py` con rama ANN en Postgres
  (`Article.embedding_vec` VectorField + índice HNSW; extensión por migración guardada).
  En SQLite/dev sigue el fallback coseno en Python. Imagen `pgvector/pgvector:pg16`.
- [x] **D5 · Backup/restore** — export/import JSON + import Pocket/Instapaper (pestaña Cuenta).

## Reglas al avanzar
- Implementa **fase a fase**, con tests + verificación al cerrar cada una.
- Mantén el provider `mock` operativo (todo probable sin claves).
- Cualquier opción nueva → patrón cascade (CLAUDE.md §6).
