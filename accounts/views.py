from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from aiproviders.config import editable_fields, locked_fields
from feeds.models import Feed

from .models import ApiToken, UserConfig

TABS = [
    ("general", "General"),
    ("ai", "Análisis con IA"),
    ("updates", "Actualización"),
    ("filters", "Filtros"),
    ("notifications", "Notificaciones"),
    ("tokens", "API / MCP"),
    ("account", "Cuenta"),
]
FONTS = [("sans", "Sans-serif"), ("serif", "Serif")]
SIZES = [("s", "Pequeña"), ("m", "Mediana"), ("l", "Grande")]
WIDTHS = [("narrow", "Estrecho"), ("normal", "Normal"), ("wide", "Ancho")]
DEDUPE = [("off", "Desactivado"), ("url", "Por URL"), ("title", "Por título")]
CADENCE_CHOICES = [
    (15, "cada 15 min"),
    (30, "cada 30 min"),
    (60, "cada hora"),
    (180, "cada 3 horas"),
    (360, "cada 6 horas"),
    (720, "cada 12 horas"),
    (1440, "cada día"),
]


def register(request):
    if request.user.is_authenticated:
        return redirect("stories:home")
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("feeds:upload_opml")
    else:
        form = UserCreationForm()
    return render(request, "accounts/register.html", {"form": form})


@login_required
def settings_view(request, tab="general"):
    if tab not in dict(TABS):
        tab = "general"

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "new_token":
            ApiToken.objects.create(user=request.user, name=request.POST.get("name", "default")[:100])
        elif action == "delete_token":
            ApiToken.objects.filter(user=request.user, pk=request.POST.get("token_id")).delete()
        elif action == "gen_sync_password":
            from syncapi.models import SyncCredential

            SyncCredential.get_or_create_for(request.user).regenerate()
            messages.success(request, "Credencial de sincronización regenerada.")
        elif action == "save_config":
            _save_ai_config(request)
            messages.success(request, "Configuración de IA guardada.")
        elif action == "save_updates":
            _save_updates(request)
            messages.success(request, "Preferencias de actualización guardadas.")
        elif action == "save_ai_updates":
            config, _ = UserConfig.objects.get_or_create(user=request.user)
            try:
                config.data["ai_search_minutes"] = max(15, int(request.POST.get("ai_search_minutes", 720)))
            except ValueError:
                config.data["ai_search_minutes"] = 720
            try:
                config.data["ai_min_score"] = max(0, min(10, int(request.POST.get("ai_min_score", 6))))
            except ValueError:
                config.data["ai_min_score"] = 6
            config.save(update_fields=["data"])
            messages.success(request, "Ajustes de fuentes IA guardados.")
            return redirect("account_settings_tab", tab="updates")
        elif action == "save_audio":
            from aiproviders.config import transcribe_fields
            from notisnotis import optconfig

            optconfig.save_user_fields(request.user, transcribe_fields(), request.POST)
            cfg, _ = UserConfig.objects.get_or_create(user=request.user)
            cfg.data["auto_transcribe"] = "1" if request.POST.get("auto_transcribe") == "1" else "0"
            cfg.save(update_fields=["data"])
            messages.success(request, "Ajustes de fuentes audio guardados.")
            return redirect("account_settings_tab", tab="updates")
        elif action == "save_reading":
            _save_reading(request)
            messages.success(request, "Preferencias de lectura guardadas.")
        elif action == "save_modules":
            from features.modules import MODULE_FIELDS
            from notisnotis import optconfig

            cfg, _ = UserConfig.objects.get_or_create(user=request.user)
            for field in MODULE_FIELDS:
                if optconfig.is_locked(field):
                    continue  # lo fijó el operador en .env
                cfg.data[field[optconfig.KEY]] = "1" if request.POST.get(field[optconfig.KEY]) == "1" else "0"
            cfg.save(update_fields=["data"])
            messages.success(request, "Módulos actualizados.")
        elif action == "save_filters":
            _save_filters(request)
            messages.success(request, "Filtros guardados.")
        elif action == "save_digest":
            from notifications.config import save_digest_prefs

            save_digest_prefs(request.user, request.POST)
            messages.success(request, "Preferencias de notificaciones guardadas.")
        elif action == "reembed":
            from articles.embedding_admin import reset_user_embeddings

            n = reset_user_embeddings(request.user)
            messages.success(request,
                             f"{n} artículos marcados: se recalcularán los embeddings en la "
                             "próxima actualización (el scheduler corre cada pocos minutos).")
            return redirect("account_settings_tab", tab="ai")
        elif action == "reindex":
            from articles.embedding_admin import reindex_user_articles

            n = reindex_user_articles(request.user)
            messages.success(request,
                             f"{n} artículos marcados para reprocesar: se recalcularán embeddings, "
                             "agrupación y análisis con el modelo actual en la próxima actualización. "
                             "El enriquecimiento del lector se rehace al abrir cada artículo.")
            return redirect("account_settings_tab", tab="ai")
        elif action == "set_embed_dim":
            if not request.user.is_superuser:
                messages.error(request, "Solo el operador puede cambiar la dimensión.")
                return redirect("account_settings_tab", tab="ai")
            from articles.embedding_admin import reset_all_embeddings, set_pgvector_dim

            try:
                n = int(request.POST.get("embed_dim_new", "0"))
            except ValueError:
                n = 0
            if not 8 <= n <= 4096:
                messages.error(request, "Dimensión no válida (8–4096).")
                return redirect("account_settings_tab", tab="ai")
            reset_all_embeddings()
            applied = set_pgvector_dim(n)
            cfg, _ = UserConfig.objects.get_or_create(user=request.user)
            cfg.data["embed_dim"] = str(n)
            cfg.save(update_fields=["data"])
            extra = "" if applied else " (SQLite: solo se guardó el valor; la columna pgvector es de Postgres)"
            messages.success(request,
                             f"Dimensión ajustada a {n}. Se han invalidado todos los embeddings y "
                             f"se recalcularán.{extra} Pon también AI_EMBED_DIM={n} en tu .env.")
            return redirect("account_settings_tab", tab="ai")
        elif action == "save_sync":
            cfg, _ = UserConfig.objects.get_or_create(user=request.user)
            cfg.data["sync_curation"] = "1" if request.POST.get("sync_curation") == "1" else "0"
            cfg.data["sync_aifeeds"] = "1" if request.POST.get("sync_aifeeds") == "1" else "0"
            cfg.data["sync_transcription"] = "1" if request.POST.get("sync_transcription") == "1" else "0"
            cfg.save(update_fields=["data"])
            messages.success(request, "Preferencia de sincronización guardada.")
            return redirect("account_settings_tab", tab="tokens")
        elif action == "save_email":
            request.user.email = request.POST.get("email", "").strip()
            request.user.save(update_fields=["email"])
            messages.success(request, "Email actualizado.")
        elif action == "save_password":
            return _change_password(request, tab)
        elif action == "delete_account":
            from django.contrib.auth import logout

            if request.POST.get("confirm") == request.user.get_username():
                user = request.user
                logout(request)
                user.delete()
                messages.success(request, "Cuenta eliminada.")
                return redirect("login")
            messages.error(request, "La confirmación no coincide; cuenta NO eliminada.")
        return redirect("account_settings_tab", tab=tab)

    ctx = {"tabs": TABS, "active_tab": tab}
    if tab == "general":
        from articles.ai_actions import LANGS, reading_prefs
        from features.modules import modules_state

        ctx["langs"] = LANGS
        ctx["reading"] = reading_prefs(request.user)
        ctx["fonts"], ctx["sizes"], ctx["widths"] = FONTS, SIZES, WIDTHS
        ctx["modules_state"] = modules_state(request.user)
    if tab == "filters":
        cfg = getattr(request.user, "config", None)
        data = cfg.data if cfg else {}
        ctx["block_rules"] = data.get("block_rules", "")
        ctx["keep_rules"] = data.get("keep_rules", "")
        ctx["dedupe"] = data.get("dedupe", "off")
        ctx["dedupe_choices"] = DEDUPE
    if tab == "notifications":
        from notifications.config import DIGEST, FREQUENCIES, digest_prefs

        ctx["digest_enabled"] = DIGEST.enabled()
        ctx["needs_user_smtp"] = DIGEST.needs_user_config(request.user)
        ctx["smtp_editable"] = DIGEST.editable_fields(request.user)
        ctx["smtp_locked"] = DIGEST.locked_fields()
        ctx["digest"] = digest_prefs(request.user)
        ctx["frequencies"] = FREQUENCIES
        from notifications.config import WEBPUSH

        ctx["webpush_enabled"] = WEBPUSH.enabled() and bool(WEBPUSH.resolve(request.user)["vapid_public"])
    if tab == "ai":
        from aiproviders.config import fields_state

        st = fields_state(request.user)
        ctx["chat"] = _ai_section(st, "chat", "chat_provider", "chat_model")
        ctx["embed"] = _ai_section(st, "embed", "embed_provider", "embed_model")
        ctx["ai_options"] = [st[k] for k in
                             ("enrich_mode", "cluster_threshold", "cluster_window_days",
                              "embed_dim", "fulltext_enabled")]
        # Estado de embeddings: detecta si hay que recalcular tras cambiar de modelo.
        from articles.embedding_admin import pgvector_column_dim, sample_embedding_dim

        configured = st["embed_dim"]["effective"]
        sample = sample_embedding_dim(request.user)
        ctx["emb_configured_dim"] = configured
        ctx["emb_sample_dim"] = sample
        ctx["emb_column_dim"] = pgvector_column_dim()
        ctx["emb_provider"] = st["embed_provider"]["effective"]
        ctx["emb_model"] = st["embed_model"]["effective"]
        ctx["emb_mismatch"] = bool(sample) and str(sample) != str(configured)
    elif tab == "updates":
        cfg = getattr(request.user, "config", None)
        data = cfg.data if cfg else {}
        ctx["cadence_choices"] = CADENCE_CHOICES
        ctx["smart_mode"] = data.get("smart_mode", "1") == "1"
        ctx["default_minutes"] = int(data.get("fetch_default_minutes", 60))
        ctx["crawl_new_feeds"] = data.get("crawl_new_feeds", "0") == "1"
        ctx["fulltext_enabled"] = settings.FULLTEXT_ENABLED
        ctx["ai_search_minutes"] = int(data.get("ai_search_minutes", 720))
        ctx["ai_min_score"] = int(data.get("ai_min_score", 6))
        ctx["ai_feeds"] = request.user.ai_feeds.all()
        from aiproviders.config import TRANSCRIBE_KEYS, fields_state

        st = fields_state(request.user)
        ctx["transcribe_fields"] = [st[k] for k in TRANSCRIBE_KEYS]
        ctx["auto_transcribe"] = data.get("auto_transcribe", "0") == "1"
        ctx["feeds"] = Feed.objects.filter(user=request.user).select_related("source").order_by(
            "fetch_interval_minutes"
        )
    elif tab == "tokens":
        from syncapi.models import SyncCredential

        ctx["tokens"] = request.user.api_tokens.all()
        ctx["sync"] = SyncCredential.get_or_create_for(request.user)
        ctx["fever_url"] = request.build_absolute_uri("/api/fever/")
        ctx["greader_url"] = request.build_absolute_uri("/api/greader/")
        cfg = getattr(request.user, "config", None)
        ctx["sync_curation"] = bool(cfg and cfg.data.get("sync_curation") == "1")
        ctx["sync_aifeeds"] = not (cfg and cfg.data.get("sync_aifeeds") == "0")
        ctx["sync_transcription"] = not (cfg and cfg.data.get("sync_transcription") == "0")
    elif tab == "account":
        from django_otp.plugins.otp_totp.models import TOTPDevice

        ctx["twofa_enabled"] = TOTPDevice.objects.filter(user=request.user, confirmed=True).exists()
    return render(request, f"settings/{tab}.html", ctx)


# Campos de conexión por proveedor (para mostrar solo los del proveedor elegido).
_PROVIDER_CONN = {
    "mock": [],
    "ollama": ["ollama_base_url"],
    "ollama_cloud": ["ollama_cloud_api_key", "ollama_cloud_base_url"],
    "openai": ["openai_api_key", "openai_base_url"],
    "openrouter": ["openrouter_api_key", "openrouter_base_url"],
    "jina": ["jina_api_key", "jina_base_url"],
}
_CONN_KEYS = sorted({k for ks in _PROVIDER_CONN.values() for k in ks})


def _ai_section(st, kind, prov_key, model_key):
    """Datos para pintar una sección (chat o embeddings) agrupada por proveedor."""
    pf = st[prov_key]
    conn = [
        {"provider": prov, "fields": [st[k] for k in keys]}
        for prov, keys in _PROVIDER_CONN.items() if prov in (pf["choices"] or [])
    ]
    return {
        "kind": kind,
        "provider_field": pf,
        "current_provider": pf["effective"] or pf["default"],
        "model_field": st[model_key],
        "current_model": st[model_key]["effective"] or st[model_key]["default"],
        "conn": conn,
    }


@login_required
@require_POST
def ai_models(request):
    """htmx: recupera los modelos del proveedor (con la config del formulario sin guardar)."""
    from aiproviders.client import build_chat_client, build_embed_client
    from aiproviders.config import effective_config

    kind = request.POST.get("kind", "chat")
    cfg = dict(effective_config(request.user))
    prov_key = "chat_provider" if kind == "chat" else "embed_provider"
    submitted_provider = request.POST.get(prov_key, "").strip()
    if submitted_provider:
        cfg[prov_key] = submitted_provider
    for k in _CONN_KEYS:
        v = request.POST.get(k, "").strip()
        if v:
            cfg[k] = v
    models, error = [], ""
    try:
        client = build_chat_client(cfg) if kind == "chat" else build_embed_client(cfg)
        models = client.list_models()
    except Exception as exc:  # noqa: BLE001
        error = str(exc)[:200]
    name = "chat_model" if kind == "chat" else "embed_model"
    return render(request, "settings/_model_options.html",
                  {"name": name, "models": models, "current": request.POST.get("current", ""), "error": error})


def _save_ai_config(request):
    config, _ = UserConfig.objects.get_or_create(user=request.user)
    data = dict(config.data)
    for field in editable_fields(request.user):
        key = field["key"]
        submitted = request.POST.get(key, "")
        if field["secret"]:
            if submitted.strip() == "":
                continue
            if submitted == "__CLEAR__":
                data.pop(key, None)
                continue
        data[key] = submitted.strip()
    config.data = data
    config.save(update_fields=["data"])


def _save_updates(request):
    config, _ = UserConfig.objects.get_or_create(user=request.user)
    smart = request.POST.get("smart_mode") == "1"
    try:
        minutes = int(request.POST.get("default_minutes", 60))
    except ValueError:
        minutes = 60
    config.data["smart_mode"] = "1" if smart else "0"
    config.data["fetch_default_minutes"] = minutes
    config.data["crawl_new_feeds"] = "1" if request.POST.get("crawl_new_feeds") == "1" else "0"
    config.save(update_fields=["data"])

    feeds = Feed.objects.filter(user=request.user)
    if smart:
        feeds.update(auto_interval=True)
        from feeds.intervals import update_auto_intervals

        update_auto_intervals(feeds)
    else:
        feeds.update(auto_interval=False, fetch_interval_minutes=minutes)


def _save_reading(request):
    config, _ = UserConfig.objects.get_or_create(user=request.user)
    config.data["translate_lang"] = request.POST.get("translate_lang", "es")
    config.data["auto_translate"] = "1" if request.POST.get("auto_translate") == "1" else "0"
    config.data["auto_summarize"] = "1" if request.POST.get("auto_summarize") == "1" else "0"
    config.data["auto_mark_scroll"] = "1" if request.POST.get("auto_mark_scroll") == "1" else "0"
    config.data["read_font"] = request.POST.get("read_font", "sans")
    config.data["read_size"] = request.POST.get("read_size", "m")
    config.data["read_width"] = request.POST.get("read_width", "normal")
    config.save(update_fields=["data"])


@login_required
def export_data(request):
    from django.http import JsonResponse

    from .datatransfer import export_user_data

    resp = JsonResponse(export_user_data(request.user))
    resp["Content-Disposition"] = 'attachment; filename="notisnotis-export.json"'
    return resp


@login_required
def import_data(request):
    if request.method == "POST" and request.FILES.get("file"):
        from .datatransfer import detect_and_import

        f = request.FILES["file"]
        try:
            kind, result = detect_and_import(request.user, f.name, f.read())
            messages.success(request, f"Importado ({kind}): {result}")
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"No se pudo importar: {exc}")
    return redirect("account_settings_tab", tab="account")


def _change_password(request, tab):
    from django.contrib.auth import update_session_auth_hash
    from django.contrib.auth.forms import PasswordChangeForm

    form = PasswordChangeForm(request.user, request.POST)
    if form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)  # no cerrar sesión
        messages.success(request, "Contraseña cambiada.")
    else:
        messages.error(request, "; ".join(f"{k}: {v[0]}" for k, v in form.errors.items()))
    return redirect("account_settings_tab", tab=tab)


def _save_filters(request):
    config, _ = UserConfig.objects.get_or_create(user=request.user)
    config.data["block_rules"] = request.POST.get("block_rules", "").strip()
    config.data["keep_rules"] = request.POST.get("keep_rules", "").strip()
    config.data["dedupe"] = request.POST.get("dedupe", "off")
    config.save(update_fields=["data"])
