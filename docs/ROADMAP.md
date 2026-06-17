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
- [ ] **B1 · Web push** — VAPID + `PushSubscription` + service worker (`pywebpush`).

### Fase C — diferenciadores del agregador
- [ ] **C1 · Dieta informativa** — sesgo de lo que el usuario *lee*.
- [ ] **C2 · Seguir temas + alertas** (keyword o embedding).
- [ ] **C3 · Tendencias / comparar fuentes / línea temporal**.

### Fase D — plataforma
- [ ] **D1 · PWA + offline**.
- [ ] **D2 · Gestión de cuenta** (password/email, borrar, 2FA).
- [ ] **D3 · Salud de feeds** (panel de errores + reactivar).
- [ ] **D4 · pgvector** — sustituir coseno en Python por VectorField + ANN.
- [ ] **D5 · Backup/restore** + import Pocket/Instapaper.

## Reglas al avanzar
- Implementa **fase a fase**, con tests + verificación al cerrar cada una.
- Mantén el provider `mock` operativo (todo probable sin claves).
- Cualquier opción nueva → patrón cascade (CLAUDE.md §6).
