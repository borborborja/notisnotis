# Módulos / sectores

facet.news se divide en tres **sectores** que se pueden encender o apagar enteros:

| Módulo | Qué incluye | Se puede apagar |
|---|---|---|
| `rss` (core) | Lector RSS, búsqueda, tags, guardados, feeds+categorías+reglas, OPML, **resúmenes IA por artículo** (resumir/traducir/chat), digest, sync, MCP, 2FA, reproductor multimedia | No (siempre activo) |
| `curation` | Agregador: historias, blindspots, dieta, tendencias, comparar, temas, **feeds con IA** (búsqueda web), síntesis, y el **contexto/afirmaciones/"otras fuentes"** del lector | Sí |
| `podcasts` | Feeds de podcasts y canales de YouTube, buscador de podcasts, **transcripciones** | Sí |

## Cómo se resuelve (cascada)

Igual que `optconfig`: **`.env` del operador > ajuste del usuario > default**. Implementado en
`features/modules.py` (`MODULE_FIELDS` con `MODULE_CURATION` / `MODULE_PODCASTS`, default `1`).

- Operador fija `MODULE_CURATION=0` en `.env` → curación **desactivada para todos** y bloqueada
  (los usuarios la ven en solo lectura en Ajustes → General).
- Operador no lo fija → cada usuario lo activa/desactiva en **Ajustes → General → Módulos**.
- Nadie lo define → **activado** (no cambia el comportamiento por defecto).

Perfiles: `curation=0 podcasts=0` → lector RSS simple con IA; `curation=0 podcasts=1` → RSS +
podcasts; ambos `=1` → todo.

## Cómo se gatea en el código

- **Vistas:** `@module_required("curation"|"podcasts")` (`features/decorators.py`) → si off,
  redirige al lector.
- **Plantillas:** context processor `features.context_processors.modules` expone `modules`
  (set). Uso: `{% if 'curation' in modules %}` / `{% if 'podcasts' in modules %}`.
- **Pipeline:** `run_pipeline` salta los pasos del sector si el operador/default lo tiene off;
  además los comandos por-usuario (`cluster_stories`, `run_aifeeds`, `transcribe_episodes`,
  `analyze_stories`) saltan a los usuarios que lo tengan off.
- **Helpers:** `module_enabled(user, key)`, `enabled_modules(user)`, `modules_state(user)`.

## No confundir con

- **Feature** (`features/registry.py`): acceso por **tier/plan** (quién), dormido por defecto.
- **Capability** (`optconfig`): **configuración** (cómo: SMTP, claves…).
- **Módulo** (esto): **sector on/off** (operador + usuario). Un módulo off oculta su sector
  pase lo que pase con features/capabilities.
