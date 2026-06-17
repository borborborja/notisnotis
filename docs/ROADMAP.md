# Roadmap y estado

Tablero de qué está hecho y qué falta. Marca aquí cuando completes algo.
Diseño detallado e histórico: `~/.claude/plans/quiero-programar-una-app-peaceful-origami.md`.

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
### Fase B (resto)
- [ ] **Web push**: `WEBPUSH_ENABLED` + VAPID (cascade), modelo `PushSubscription`,
  service worker, `pywebpush`. Necesita HTTPS + dispositivo real para verificar.

### Fase C — diferenciadores del agregador
- [ ] **Dieta informativa**: dashboard del sesgo de lo que el usuario *lee*
  (`Article.is_read` × `Source.bias`), reusa `stories.views._bias_bars`.
- [ ] **Seguir temas + alertas** (keyword o embedding).
- [ ] **Tendencias / comparar fuentes / línea temporal** de una historia.

### Fase D — plataforma
- [ ] **PWA + offline** (`manifest.json` + service worker).
- [ ] **Gestión de cuenta** (cambiar password/email, borrar cuenta, 2FA), panel admin.
- [ ] **Salud de feeds** (panel de errores; ya hay `Feed.fail_count`/`last_error`).
- [ ] **pgvector** — sustituir el coseno en Python por VectorField + ANN. Ver CLAUDE.md §5.
- [ ] **Backup/restore** (export JSON) + import Pocket/Instapaper.

## Reglas al avanzar
- Implementa **fase a fase**, con tests + verificación al cerrar cada una.
- Mantén el provider `mock` operativo (todo probable sin claves).
- Cualquier opción nueva → patrón cascade (CLAUDE.md §6).
