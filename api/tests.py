import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import ApiToken
from articles.models import Article
from feeds.models import Feed, Source


class ApiBaseTests(TestCase):
    def setUp(self):
        self.U = get_user_model()
        self.user = self.U.objects.create_user("apiu", "", "pw-api-12345")
        self.token = ApiToken.objects.create(user=self.user, name="t").token
        self.src = Source.objects.create(name="S", domain="s.com")
        self.feed = Feed.objects.create(user=self.user, url="http://s.com/f", source=self.src, title="F")
        self.a = Article.objects.create(feed=self.feed, source=self.src, guid="g1", title="Hola",
                                        summary="cuerpo", body="cuerpo largo")

    def _auth(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    # --- auth ---
    def test_login_returns_token(self):
        r = self.client.post("/api/v1/auth/token", data=json.dumps(
            {"username": "apiu", "password": "pw-api-12345"}), content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["data"]["token"])

    def test_login_bad_credentials(self):
        r = self.client.post("/api/v1/auth/token", data=json.dumps(
            {"username": "apiu", "password": "nope"}), content_type="application/json")
        self.assertEqual(r.status_code, 401)

    def test_bearer_required(self):
        self.assertEqual(self.client.get("/api/v1/me").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/me", HTTP_AUTHORIZATION="Bearer x").status_code, 401)

    def test_me_reports_modules_and_counts(self):
        r = self.client.get("/api/v1/me", **self._auth())
        self.assertEqual(r.status_code, 200)
        d = r.json()["data"]
        self.assertTrue(d["modules"]["rss"])
        self.assertEqual(d["counts"]["unread"], 1)

    # --- delta-sync ---
    def test_sync_returns_content_and_state(self):
        r = self.client.get("/api/v1/sync", **self._auth())
        d = r.json()["data"]
        self.assertEqual(len(d["articles"]), 1)
        art = d["articles"][0]
        self.assertEqual(art["title"], "Hola")
        self.assertTrue(art["body"])           # contenido servido (sin re-fetch)
        self.assertIn("is_read", art)

    def test_sync_delta_only_changed(self):
        # marca un punto en el tiempo, luego cambia el artículo
        t0 = timezone.now().isoformat()
        self.a.is_read = True
        self.a.save()
        r = self.client.get(f"/api/v1/sync?since={t0}", **self._auth())
        d = r.json()["data"]
        self.assertEqual([x["id"] for x in d["articles"]], [self.a.id])
        # un segundo punto posterior no trae nada
        t1 = r.json()["server_time"]
        r2 = self.client.get(f"/api/v1/sync?since={t1}", **self._auth())
        self.assertEqual(r2.json()["data"]["articles"], [])


class ApiReaderTests(TestCase):
    def setUp(self):
        self.U = get_user_model()
        self.user = self.U.objects.create_user("ru", "", "pw")
        self.token = ApiToken.objects.create(user=self.user).token
        self.src = Source.objects.create(name="S", domain="s.com")
        self.feed = Feed.objects.create(user=self.user, url="http://s/f", source=self.src, title="F")
        self.a = Article.objects.create(feed=self.feed, source=self.src, guid="g", title="t", body="b")
        self.H = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def test_feeds_with_unread(self):
        r = self.client.get("/api/v1/feeds", **self.H).json()["data"]
        self.assertEqual(r[0]["unread"], 1)

    def test_articles_list_and_state(self):
        r = self.client.get("/api/v1/articles", **self.H).json()["data"]
        self.assertEqual(len(r), 1)
        import json
        r2 = self.client.post(f"/api/v1/articles/{self.a.id}/state",
                              data=json.dumps({"read": True, "saved": True}),
                              content_type="application/json", **self.H)
        d = r2.json()["data"]
        self.assertTrue(d["is_read"] and d["is_saved"])
        self.a.refresh_from_db()
        self.assertTrue(self.a.is_read and self.a.is_saved)

    def test_tags_add_bumps_updated(self):
        import json
        before = self.a.updated_at
        self.client.post(f"/api/v1/articles/{self.a.id}/tags",
                         data=json.dumps({"name": "x"}), content_type="application/json", **self.H)
        self.a.refresh_from_db()
        self.assertGreater(self.a.updated_at, before)
        self.assertIn("x", [t.name for t in self.a.tags.all()])


class ApiModuleGatingTests(TestCase):
    def setUp(self):
        from accounts.models import UserConfig
        self.U = get_user_model()
        self.user = self.U.objects.create_user("gu", "", "pw")
        # Desactiva podcasts y curación para este usuario
        UserConfig.objects.create(user=self.user, data={"module_podcasts": "0", "module_curation": "0"})
        self.token = ApiToken.objects.create(user=self.user).token
        self.H = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def test_me_reports_disabled(self):
        d = self.client.get("/api/v1/me", **self.H).json()["data"]
        self.assertFalse(d["modules"]["podcasts"])
        self.assertFalse(d["modules"]["curation"])

    def test_podcasts_404_when_off(self):
        self.assertEqual(self.client.get("/api/v1/podcasts", **self.H).status_code, 404)

    def test_curation_404_when_off(self):
        self.assertEqual(self.client.get("/api/v1/stories", **self.H).status_code, 404)
