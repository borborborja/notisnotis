import base64
import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from articles.models import Article
from feeds.models import Feed, Source
from syncapi.models import SyncCredential


class GpodderApiTests(TestCase):
    def setUp(self):
        self.u = get_user_model().objects.create_user("gp", "", "pw-gp-12345")
        self.cred = SyncCredential.get_or_create_for(self.u)
        self.cred.save()
        src = Source.objects.create(name="P", domain="p.com")
        self.feed = Feed.objects.create(user=self.u, source=src, url="http://p/rss", kind="podcast")
        self.ep = Article.objects.create(feed=self.feed, source=src, guid="e1", title="E1",
                                         enclosure_url="http://p/e1.mp3", enclosure_type="audio/mpeg")

    def _auth(self):
        raw = base64.b64encode(f"gp:{self.cred.password}".encode()).decode()
        return {"HTTP_AUTHORIZATION": "Basic " + raw}

    def test_login_requires_auth(self):
        self.assertEqual(self.client.post("/api/2/auth/gp/login.json").status_code, 401)
        self.assertEqual(self.client.post("/api/2/auth/gp/login.json", **self._auth()).status_code, 200)

    def test_subscriptions_get_lists_podcasts(self):
        r = self.client.get("/api/2/subscriptions/gp/dev1.json?since=0", **self._auth())
        self.assertEqual(r.status_code, 200)
        self.assertIn("http://p/rss", json.loads(r.content)["add"])

    def test_subscriptions_post_adds_and_removes(self):
        body = json.dumps({"add": ["http://p/new.rss"], "remove": ["http://p/rss"]})
        r = self.client.post("/api/2/subscriptions/gp/dev1.json", body,
                             content_type="application/json", **self._auth())
        self.assertEqual(r.status_code, 200)
        self.assertTrue(Feed.objects.filter(user=self.u, url="http://p/new.rss").exists())
        self.assertFalse(Feed.objects.filter(user=self.u, url="http://p/rss").exists())

    def test_episode_play_action_updates_position(self):
        body = json.dumps([{"podcast": "http://p/rss", "episode": "http://p/e1.mp3",
                            "action": "play", "position": 350, "total": 1800}])
        r = self.client.post("/api/2/episodes/gp.json", body,
                             content_type="application/json", **self._auth())
        self.assertEqual(r.status_code, 200)
        self.ep.refresh_from_db()
        self.assertEqual(self.ep.play_position, 350)
        self.assertEqual(self.ep.duration, 1800)

    def test_episode_get_returns_actions(self):
        self.ep.play_position = 100
        from django.utils import timezone
        self.ep.play_updated_at = timezone.now()
        self.ep.save()
        r = self.client.get("/api/2/episodes/gp.json?since=0", **self._auth())
        self.assertEqual(r.status_code, 200)
        acts = json.loads(r.content)["actions"]
        self.assertEqual(acts[0]["episode"], "http://p/e1.mp3")
        self.assertEqual(acts[0]["position"], 100)
