from django.contrib.auth import get_user_model
from django.test import TestCase

from articles.models import Article
from feeds.models import Feed, Source


class PlayerEndpointTests(TestCase):
    def setUp(self):
        self.u = get_user_model().objects.create_user("pp", "", "pw-pod-12345")
        self.client.login(username="pp", password="pw-pod-12345")
        src = Source.objects.create(name="Pod", domain="pod.com")
        self.feed = Feed.objects.create(user=self.u, source=src, url="http://pod/rss", kind="podcast")
        self.ep = Article.objects.create(feed=self.feed, source=src, guid="e1", title="Ep 1",
                                         enclosure_url="http://pod/ep1.mp3", enclosure_type="audio/mpeg")

    def test_progress_saves_position_and_duration(self):
        r = self.client.post(f"/podcasts/ep/{self.ep.pk}/progress/",
                             {"position": "120", "duration": "1800"})
        self.assertEqual(r.status_code, 200)
        self.ep.refresh_from_db()
        self.assertEqual(self.ep.play_position, 120)
        self.assertEqual(self.ep.duration, 1800)
        self.assertFalse(self.ep.is_read)

    def test_progress_near_end_marks_played(self):
        self.client.post(f"/podcasts/ep/{self.ep.pk}/progress/",
                         {"position": "1790", "duration": "1800"})
        self.ep.refresh_from_db()
        self.assertTrue(self.ep.is_read)
        self.assertEqual(self.ep.play_position, 0)

    def test_played_toggle(self):
        self.client.post(f"/podcasts/ep/{self.ep.pk}/played/")
        self.ep.refresh_from_db()
        self.assertTrue(self.ep.is_read)
        self.client.post(f"/podcasts/ep/{self.ep.pk}/played/")
        self.ep.refresh_from_db()
        self.assertFalse(self.ep.is_read)

    def test_gated_by_module(self):
        from accounts.models import UserConfig
        UserConfig.objects.create(user=self.u, data={"module_podcasts": "0"})
        self.u.refresh_from_db()
        r = self.client.post(f"/podcasts/ep/{self.ep.pk}/played/")
        self.assertEqual(r.status_code, 302)  # módulo off → redirige
