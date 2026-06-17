# Sistema de funciones (feature flags · tiers · beta · por-usuario)

Permite, **sin tocar el código de cada función**: asignar tiers de pago, encender/apagar
funciones por usuario y gestionar betas. Implementado en `features/`.

## Cómo funciona
- Cada función se **declara una vez** en `features/registry.py` (`FEATURES`):
  `Feature(key, label, min_tier, beta, category)`.
- Tiers ordenados en `TIERS = ["free", "pro", "max"]` (rango = índice). Una función exige
  un `min_tier`.
- El acceso por usuario vive en `features.UserEntitlements` (Admin de Django):
  `tier`, `beta_access`, `grants` (keys concedidas pese al tier), `denies` (keys vetadas),
  `tier_expires` (al expirar baja a `free`).
- **Resolución** (`has_feature(user, key)`):
  1. función no declarada → permitida; desactivada globalmente (`FEATURES_DISABLED`) → no.
  2. superusuario → todo.
  3. **`FEATURES_ENFORCED=0` (def.) → todo activo** (sistema *dormido*: no cambia nada hoy).
  4. enforced: `denies` veta; `grants` concede; beta exige `beta_access`; si no,
     `rango(tier_usuario) >= rango(min_tier)`.

## Estados (operador)
| `.env` | Efecto |
|---|---|
| `FEATURES_ENFORCED=0` | Todo encendido para todos (estado actual). |
| `FEATURES_ENFORCED=1` | Se aplican tiers/beta/overrides por usuario. |
| `FEATURES_DEFAULT_TIER=free\|pro\|max` | Tier de quien no tiene fila de entitlements. |
| `FEATURES_DISABLED=chat,webpush` | Apaga funciones globalmente (kill-switch). |

Gestión por usuario: **Admin → Funciones/tiers → User entitlements** (tier, beta,
grants, denies, expiración). El día que haya pago, el webhook del proveedor solo tiene que
escribir `tier`/`tier_expires` en esa fila.

## Cómo se usa en el código (gating)
- **Vistas:** `@feature_required("chat")` (devuelve 403 si no hay acceso). Ej.:
  `articles/views.py` (translate/summarize/chat).
- **Plantillas:** el context processor expone `features` (set de keys activas):
  `{% if 'chat' in features %} … {% endif %}`. Ej.: `templates/articles/_reading_pane.html`,
  `templates/partials/sidebar.html`.
- **Python:** `from features import has_feature; has_feature(user, "translate")`.

## Cómo AÑADIR una función nueva (gateable)
1. Declara su `Feature(...)` en `features/registry.py` con su `min_tier`/`beta`.
2. Gatea dónde corresponda: `@feature_required("key")` en la vista y/o `{% if 'key' in
   features %}` en la plantilla.
3. (Opcional) Si tiene **configuración** (API key, SMTP…), usa además el patrón cascade de
   `notisnotis/optconfig.py` (ver CLAUDE.md §6). Feature = *acceso*; Capability = *config*.
4. Documenta y añade test en `features/tests.py`.

## Relación con otros sistemas
- **optconfig (cascade)** decide *cómo se configura* una opción (operador/usuario). 
- **features (este)** decide *quién puede usarla* (tier/beta/override).
  Son ortogonales y se combinan (p.ej. `webpush` es feature `max`+beta **y** capability VAPID).
