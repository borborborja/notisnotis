# Referencias de implementación e inspiración

Cuando tengas dudas de **cómo implementar** algo, mira primero estos proyectos. Cuando
la duda sea **cómo debería comportarse** (productos cerrados), mira las descripciones de
comportamiento. Mapea siempre la feature de NotisNotis a su referencia antes de inventar.

> Nota: NotisNotis es Django/Python + htmx. Las referencias en Go/PHP/JS valen por su
> **diseño y comportamiento**, no para copiar código literal.

---

## A. Código abierto que SÍ puedes leer

### miniflux/v2 — https://github.com/miniflux/v2 (Go) — referencia principal
Lector RSS minimalista, muy bien diseñado. Es nuestra brújula para el backend.
- **APIs de sincronización**: `internal/fever/` (Fever API) e `internal/googlereader/`
  (Google Reader API) → cómo mapear feeds/categorías/estados, formato de respuestas,
  `edit-tag`, `stream/items/ids`, `ClientLogin`. *Nuestro equivalente:* `syncapi/`.
- **Fetch / conditional GET**: cómo usa ETag/Last-Modified y maneja 304, gzip, errores y
  backoff. *Nuestro equivalente:* `feeds/management/commands/fetch_feeds.py`.
- **Reglas**: `block_filter_entry_rules` / `keep_filter_entry_rules` (regex sobre
  título/url/autor/contenido) y `rewrite`/`scraper` rules (selectores CSS). *Nuestro:*
  `feeds/filters.py` + `feeds/rules.py` (las rewrite/scraper aún no están).
- **OPML, integraciones (Wallabag, etc.), feed discovery, favicons**.

### electh/ReactFlux — https://github.com/electh/ReactFlux (React) — referencia de UX
Frontend alternativo para miniflux. Mira aquí para **interacción y lector**:
atajos de teclado, modos de vista, filtros por estado, marcar-leído-al-scroll, ajustes de
tipografía/ancho, gestos. *Nuestro equivalente:* `static/js/app.js`, `templates/articles/`.

### FreshRSS/FreshRSS — https://github.com/FreshRSS/FreshRSS (PHP)
Otra implementación madura de la **Google Reader API** (útil para contrastar dudas de
compatibilidad con clientes) + sistema de etiquetas, temas y WebSub. Buena segunda opinión.

### NewsBlur/NewsBlur — https://github.com/samuelclay/NewsBlur (Python/**Django**)
La referencia más cercana a nuestro stack. Útil para: estructura Django a escala, dedupe
de historias, "intelligence trainer" (clasificador por feed/autor/tag — inspira reglas/
recomendaciones), y manejo de muchos feeds.

### nextcloud/news — https://github.com/nextcloud/news (PHP) + su API REST
Otra API de lector (la "Nextcloud News API") por si algún cliente la pide; modelo de datos
folder/feed/item claro.

### Clientes (para saber qué ESPERA un lector de nuestras APIs)
- **Reeder / NetNewsWire** (Ranchero/NetNewsWire, Swift, https://github.com/Ranchero-Software/NetNewsWire):
  ver cómo un cliente llama a Google Reader (orden: subscription/list → unread ids →
  contents → edit-tag). Si algo no sincroniza, contrasta el flujo con su código.
- **yang991178/fluent-reader** (Electron) — cliente multi-backend.

### Extracción de texto completo (paywall / readability)
- **mozilla/readability** (JS, algoritmo de referencia) y **adbar/trafilatura** o
  **goose3** (Python). *Nuestro equivalente:* `articles/fulltext.py` (heurística propia con
  BeautifulSoup). Si la extracción falla mucho, mira la heurística de readability.

### Embeddings / escala
- **pgvector/pgvector** — https://github.com/pgvector/pgvector y `pgvector-python`.
  Referencia para la meta futura de sustituir el coseno en Python (`stories/similarity.py`).

### Web push (meta futura)
- **web-push-libs/pywebpush** y la spec VAPID. Mira ejemplos de service worker + suscripción.

---

## B. Productos cerrados — cómo se COMPORTAN (no hay código)

### Feedly — el modelo de UX del lector
- Layout de 3 paneles (categorías/feeds | lista | artículo); **vistas** Title-only / Magazine
  / Cards; contadores de no leídos por feed/categoría; "Mark as read" (todo / por encima);
  **boards** (guardar/etiquetar); búsqueda; lectura cómoda (tipografía/tema).
- Comportamiento clave a emular: marcar leído al abrir/scroll, organización por carpetas,
  densidad alta, navegación con teclado. *Nuestro:* shell Feedly ya implementado.

### Ground News — el modelo del AGREGADOR (nuestro valor diferencial)
- Agrupa la **misma noticia** cubierta por muchas fuentes en una "Story".
- **Bias bar**: distribución Left/Center/Right de la cobertura; etiqueta cada fuente.
- **Blindspot**: historias muy cubiertas por un lado e ignoradas por el otro ("Blindspot
  for the left/right").
- **Factuality** y propiedad del medio; resúmenes y comparación de cómo lo enmarca cada lado.
- "**Bias check / My News Bias**": panel que muestra el sesgo de lo que TÚ lees (→ nuestra
  meta de "dieta informativa", roadmap Fase C).
- *Nuestro equivalente:* `stories/` (clustering + `analysis.py` con sesgo/blindspot/
  perspectivas). La metodología de sesgo la hace el LLM, no una base curada.

### Inoreader — power features de lector
- Reglas/automatización (si título contiene X → marcar/etiquetar/notificar), monitorización
  de keywords, "Active Search", digests por email, OPML. *Inspira:* `feeds/rules.py`, digest.

### Readwise Reader / Pocket / Wallabag — read-it-later
- Guardar para después, resaltar, "send to". *Nuestro:* tags + webhook "Enviar a"; Wallabag
  es el destino self-hosted típico del usuario.

---

## C. Estándares y especificaciones (la fuente de la verdad)
- **Fever API**: https://feedafever.com/api — formato exacto de `groups/feeds/items` y `mark`.
- **Google Reader API** (no oficial, documentada por la comunidad): buscar
  "Google Reader API reference" / la doc de FreshRSS y miniflux; rutas `/reader/api/0/...`.
- **RSS 2.0** y **Atom (RFC 4287)**; **OPML 2.0** (subscripciones con carpetas anidadas).
- **JSON Feed** (https://jsonfeed.org) — formato moderno alternativo a RSS.
- **WebSub / PubSubHubbub** — entrega push de feeds (meta futura para tiempo real).
- **VAPID / Web Push** (RFC 8030/8292) — para notificaciones push.
- **Media bias** (metodología, contexto): AllSides y Media Bias/Fact Check — útil como
  marco conceptual del sesgo aunque aquí lo estime el LLM.

---

## D. Mapa rápido: feature de NotisNotis → dónde mirar
| Feature | Mira |
|---|---|
| Fever / Google Reader API | miniflux `internal/fever`, `internal/googlereader`; spec Fever; FreshRSS |
| Fetch eficiente / 304 / backoff | miniflux fetcher |
| Reglas, block/keep, rewrite/scraper | miniflux filter rules; Inoreader (comportamiento) |
| Lector / atajos / vistas / tipografía | ReactFlux; Feedly (comportamiento) |
| Texto completo (paywall) | mozilla/readability, trafilatura |
| Agregador: sesgo / blindspot / perspectivas | Ground News (comportamiento) |
| Dieta informativa (Fase C) | Ground News "My News Bias" |
| Escala embeddings (pgvector) | pgvector + pgvector-python |
| Web push (Fase B) | pywebpush + spec VAPID |
| Dedupe / clasificación | NewsBlur |
