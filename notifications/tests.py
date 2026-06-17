import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import UserConfig
from articles.models import Article
from feeds.models import Feed, Source
from notifications.config import DIGEST
from notifications.digest import send_digest_to


class CapabilityStateTests(TestCase):
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DIGEST_ENABLED", None)
            self.assertFalse(DIGEST.enabled())

    def test_global_when_smtp_in_env(self):
        with patch.dict(os.environ, {"DIGEST_ENABLED": "1", "SMTP_HOST": "smtp.x.com", "SMTP_FROM": "a@x.com"}):
            self.assertTrue(DIGEST.enabled())
            self.assertTrue(DIGEST.required_all_in_env())
            self.assertFalse(DIGEST.needs_user_config(None))

    def test_user_config_when_smtp_absent(self):
        with patch.dict(os.environ, {"DIGEST_ENABLED": "1"}):
            os.environ.pop("SMTP_HOST", None)
            os.environ.pop("SMTP_FROM", None)
            self.assertTrue(DIGEST.needs_user_config(None))


class PushTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user("p", "", "pw")
        self.client.login(username="p", password="pw")

    def test_subscribe_creates_record(self):
        import json as _json

        from notifications.models import PushSubscription
        body = _json.dumps({"endpoint": "https://push/abc", "keys": {"p256dh": "k", "auth": "a"}})
        r = self.client.post("/notifications/push/subscribe/", data=body,
                             content_type="application/json", HTTP_HOST="localhost")
        self.assertEqual(r.status_code, 204)
        self.assertTrue(PushSubscription.objects.filter(endpoint="https://push/abc").exists())

    def test_key_disabled(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WEBPUSH_ENABLED", None)
            r = self.client.get("/notifications/push/key/", HTTP_HOST="localhost")
            self.assertFalse(r.json()["enabled"])

    def test_send_push_disabled_returns_zero(self):
        from notifications.push import send_push
        with patch.dict(os.environ, {"WEBPUSH_ENABLED": "0"}):
            self.assertEqual(send_push(get_user_model().objects.get(username="p"), "t", "b"), 0)


class SendDigestTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("u", "u@x.com", "pw")
        src = Source.objects.create(name="BBC", domain="bbc.com")
        feed = Feed.objects.create(user=self.user, source=src, url="http://bbc/rss")
        Article.objects.create(feed=feed, source=src, guid="1", title="Hola", url="http://x/1", is_read=False)

    def _optin(self, smtp=True):
        cfg, _ = UserConfig.objects.get_or_create(user=self.user)
        cfg.data.update({"digest_optin": "1", "digest_frequency": "daily", "digest_email": "u@x.com"})
        if smtp:
            cfg.data.update({"smtp_host": "smtp.x.com", "smtp_from": "a@x.com"})
        cfg.save()

    def test_skips_when_disabled(self):
        with patch.dict(os.environ, {"DIGEST_ENABLED": "0"}):
            self.assertEqual(send_digest_to(self.user, "daily", dry_run=True), "skipped:disabled")

    def test_sent_with_user_smtp(self):
        self._optin(smtp=True)
        with patch.dict(os.environ, {"DIGEST_ENABLED": "1"}):
            os.environ.pop("SMTP_HOST", None); os.environ.pop("SMTP_FROM", None)
            self.assertEqual(send_digest_to(self.user, "daily", dry_run=True), "sent")

    def test_skip_no_smtp(self):
        self._optin(smtp=False)
        with patch.dict(os.environ, {"DIGEST_ENABLED": "1"}):
            os.environ.pop("SMTP_HOST", None); os.environ.pop("SMTP_FROM", None)
            self.assertEqual(send_digest_to(self.user, "daily", dry_run=True), "skipped:no_smtp")

    def test_skip_not_optin(self):
        with patch.dict(os.environ, {"DIGEST_ENABLED": "1", "SMTP_HOST": "s", "SMTP_FROM": "a@x.com"}):
            self.assertEqual(send_digest_to(self.user, "daily", dry_run=True), "skipped:not_optin")
