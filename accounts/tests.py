from django.contrib.auth import get_user_model
from django.test import TestCase

H = {"HTTP_HOST": "localhost"}


class AccountMgmtTests(TestCase):
    def setUp(self):
        self.U = get_user_model()
        self.U.objects.create_user("a", "a@x.com", "pw-initial-1")
        self.client.login(username="a", password="pw-initial-1")

    def test_change_email(self):
        self.client.post("/accounts/settings/account/", {"action": "save_email", "email": "n@x.com"}, **H)
        self.assertEqual(self.U.objects.get(username="a").email, "n@x.com")

    def test_change_password(self):
        self.client.post("/accounts/settings/account/", {
            "action": "save_password", "old_password": "pw-initial-1",
            "new_password1": "Str0ngPass99", "new_password2": "Str0ngPass99"}, **H)
        self.client.logout()
        self.assertTrue(self.client.login(username="a", password="Str0ngPass99"))

    def test_delete_account(self):
        r = self.client.post("/accounts/settings/account/",
                             {"action": "delete_account", "confirm": "a"}, **H)
        self.assertEqual(r.status_code, 302)
        self.assertFalse(self.U.objects.filter(username="a").exists())

    def test_export(self):
        r = self.client.get("/accounts/export.json", **H)
        self.assertEqual(r.status_code, 200)
        self.assertIn("feeds", r.json())


class DataTransferTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("d", "", "pw")

    def test_import_pocket(self):
        from accounts.datatransfer import import_pocket
        from articles.models import Article

        html = '<ul><li><a href="https://ej.com/1" tags="x">Título 1</a></li>' \
               '<li><a href="https://ej.com/2">Título 2</a></li></ul>'
        res = import_pocket(self.user, html)
        self.assertEqual(res["saved"], 2)
        self.assertEqual(Article.objects.filter(feed__user=self.user, is_saved=True).count(), 2)

    def test_export_import_roundtrip(self):
        from accounts.datatransfer import export_user_data, import_user_data
        from feeds.models import Category, Feed, Source

        src = Source.objects.create(name="BBC", domain="bbc.com")
        cat = Category.objects.create(user=self.user, name="News")
        Feed.objects.create(user=self.user, source=src, url="http://bbc/rss", title="BBC", category=cat)
        data = export_user_data(self.user)

        other = get_user_model().objects.create_user("d2", "", "pw")
        import_user_data(other, data)
        self.assertTrue(Feed.objects.filter(user=other, url="http://bbc/rss").exists())
        self.assertTrue(Category.objects.filter(user=other, name="News").exists())


class PwaTests(TestCase):
    def test_service_worker_served_at_root(self):
        r = self.client.get("/sw.js", **H)
        self.assertEqual(r.status_code, 200)
        self.assertIn("javascript", r["Content-Type"])
        self.assertIn(b"notisnotis", r.content)


def _current_totp(device, step_offset=0):
    """Token TOTP para un dispositivo (igual que hace verify_token).

    `step_offset` permite un código de un paso futuro: necesario tras confirmar el
    alta, porque TOTP no acepta reutilizar el mismo código (anti-replay).
    """
    import time

    from django_otp.oath import TOTP

    totp = TOTP(device.bin_key, device.step, device.t0, device.digits, device.drift)
    totp.time = time.time() + step_offset * device.step
    return totp.token()


class TwoFactorTests(TestCase):
    def setUp(self):
        self.U = get_user_model()
        self.U.objects.create_user("t", "t@x.com", "pw-initial-1")
        self.client.login(username="t", password="pw-initial-1")

    def _enroll(self):
        from django_otp.plugins.otp_totp.models import TOTPDevice

        # GET crea el dispositivo sin confirmar y muestra el QR.
        r = self.client.get("/accounts/2fa/setup/", **H)
        self.assertEqual(r.status_code, 200)
        device = TOTPDevice.objects.get(user__username="t", confirmed=False)
        # POST con un código válido lo confirma y muestra los códigos de recuperación.
        r = self.client.post("/accounts/2fa/setup/", {"token": _current_totp(device)}, **H)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context["codes"]), 10)
        device.refresh_from_db()
        self.assertTrue(device.confirmed)
        return device

    def test_enroll_creates_device_and_recovery_codes(self):
        from django_otp.plugins.otp_static.models import StaticDevice

        self._enroll()
        sd = StaticDevice.objects.get(user__username="t")
        self.assertEqual(sd.token_set.count(), 10)

    def test_enroll_rejects_bad_code(self):
        self.client.get("/accounts/2fa/setup/", **H)
        r = self.client.post("/accounts/2fa/setup/", {"token": "000000"}, **H)
        # Sin confirmar: sigue mostrando el QR de alta.
        self.assertIn("qr_svg", r.context)

    def test_unverified_user_is_forced_to_challenge(self):
        device = self._enroll()
        self.client.logout()
        self.client.login(username="t", password="pw-initial-1")
        # Con dispositivo confirmado pero sin pasar el reto: la app redirige a verify.
        r = self.client.get("/articles/", **H)
        self.assertRedirects(r, "/accounts/2fa/verify/", fetch_redirect_response=False)
        # Verificar con un TOTP válido (paso siguiente, no reutilizado) desbloquea.
        device.refresh_from_db()
        r = self.client.post("/accounts/2fa/verify/", {"token": _current_totp(device, step_offset=1)}, **H)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get("/articles/", **H).status_code, 200)

    def test_recovery_code_passes_challenge(self):
        from django_otp.plugins.otp_static.models import StaticDevice

        self._enroll()
        code = StaticDevice.objects.get(user__username="t").token_set.first().token
        self.client.logout()
        self.client.login(username="t", password="pw-initial-1")
        r = self.client.post("/accounts/2fa/verify/", {"token": code}, **H)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get("/articles/", **H).status_code, 200)

    def test_disable_removes_2fa(self):
        from django_otp.plugins.otp_totp.models import TOTPDevice

        self._enroll()
        self.client.post("/accounts/2fa/disable/", **H)
        self.assertFalse(TOTPDevice.objects.filter(user__username="t").exists())

    def test_user_without_2fa_is_unaffected(self):
        # Sin dispositivo, el middleware no interfiere.
        self.assertEqual(self.client.get("/articles/", **H).status_code, 200)


class SettingsTabsRenderTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user("tabs", "t@x.com", "pw-initial-1")
        self.client.login(username="tabs", password="pw-initial-1")

    def test_all_tabs_render(self):
        for tab in ("general", "ai", "updates", "filters", "notifications", "tokens", "account"):
            r = self.client.get(f"/accounts/settings/{tab}/", **H)
            self.assertEqual(r.status_code, 200, f"tab {tab} no renderiza")


class AiSettingsUiTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user("ai", "ai@x.com", "pw-initial-1")
        self.client.login(username="ai", password="pw-initial-1")

    def test_ai_tab_renders_provider_ui(self):
        r = self.client.get("/accounts/settings/ai/", **H)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Recuperar modelos")
        self.assertContains(r, 'data-ai-provider="chat"')
        self.assertContains(r, 'data-ai-provider="embed"')

    def test_fetch_models_endpoint_mock(self):
        # Proveedor mock por defecto: el endpoint devuelve los modelos en un <select>.
        r = self.client.post("/accounts/settings/ai/models/",
                             {"kind": "chat", "chat_provider": "mock", "current": ""}, **H)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "mock-small")
        self.assertContains(r, '<select name="chat_model"')

    def test_fetch_models_endpoint_error_is_graceful(self):
        # openai sin clave válida → error capturado, no excepción (sin red: requests mockeado).
        from unittest import mock

        class _Resp:
            status_code = 401
            text = "Unauthorized"

        with mock.patch("aiproviders.providers.openai.requests.get", return_value=_Resp()):
            r = self.client.post("/accounts/settings/ai/models/",
                                 {"kind": "embed", "embed_provider": "openai",
                                  "openai_api_key": "x", "current": ""}, **H)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "No se pudieron recuperar los modelos")


class S3StorageConfigTests(TestCase):
    """Selección del backend de media según el entorno (patrón de operador)."""

    def test_disabled_without_bucket(self):
        from django.conf import settings
        from notisnotis import storagecfg

        # Sin bucket: S3 desactivado y el default sigue en disco local.
        self.assertFalse(storagecfg.s3_enabled({}))
        self.assertEqual(
            settings.STORAGES["default"]["BACKEND"],
            "django.core.files.storage.FileSystemStorage",
        )

    def test_enabled_with_bucket(self):
        from notisnotis import storagecfg

        env = {"AWS_STORAGE_BUCKET_NAME": "mi-bucket"}
        self.assertTrue(storagecfg.s3_enabled(env))
        self.assertFalse(storagecfg.static_to_s3(env))  # estáticos siguen en whitenoise
        self.assertTrue(storagecfg.static_to_s3({**env, "AWS_S3_STATIC": "1"}))
        aws = storagecfg.aws_settings(env)
        self.assertEqual(aws["AWS_STORAGE_BUCKET_NAME"], "mi-bucket")
        self.assertIsNone(aws["AWS_S3_ENDPOINT_URL"])  # AWS real por defecto
        self.assertTrue(aws["AWS_QUERYSTRING_AUTH"])   # bucket privado por defecto

    def test_compatible_endpoint(self):
        from notisnotis import storagecfg

        aws = storagecfg.aws_settings({
            "AWS_STORAGE_BUCKET_NAME": "b",
            "AWS_S3_ENDPOINT_URL": "https://minio.local:9000",
        })
        self.assertEqual(aws["AWS_S3_ENDPOINT_URL"], "https://minio.local:9000")
