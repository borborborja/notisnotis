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


class PodcastUITests(TestCase):
    def setUp(self):
        self.u = get_user_model().objects.create_user("pu", "", "pw-pod-67890")
        self.client.login(username="pu", password="pw-pod-67890")
        src = Source.objects.create(name="P2", domain="p2.com")
        self.feed = Feed.objects.create(user=self.u, source=src, url="http://p2/rss", kind="podcast",
                                        title="Mi Pod", image_url="http://p2/cover.jpg")
        self.ep = Article.objects.create(feed=self.feed, source=src, guid="x1", title="Ep X",
                                         enclosure_url="http://p2/x1.mp3", enclosure_type="audio/mpeg",
                                         duration=1800, play_position=300)

    def test_home_and_detail_render(self):
        self.assertEqual(self.client.get("/podcasts/").status_code, 200)
        self.assertContains(self.client.get(f"/podcasts/{self.feed.pk}/"), "Ep X")
        self.assertEqual(self.client.get("/podcasts/list/in_progress/").status_code, 200)

    def test_queue_add_and_up_next(self):
        from podcasts.models import QueueItem
        self.client.post(f"/podcasts/ep/{self.ep.pk}/queue/")
        self.assertEqual(QueueItem.objects.filter(user=self.u).count(), 1)
        self.assertContains(self.client.get("/podcasts/up-next/"), "Ep X")
        self.client.post(f"/podcasts/ep/{self.ep.pk}/unqueue/")
        self.assertEqual(QueueItem.objects.filter(user=self.u).count(), 0)


class AntennaPodImportTests(TestCase):
    def _make_db(self, path):
        import sqlite3
        con = sqlite3.connect(path)
        con.executescript(
            "CREATE TABLE Feeds(id INTEGER PRIMARY KEY, title TEXT, custom_title TEXT, download_url TEXT,"
            " link TEXT, description TEXT, image_url TEXT, feed_playback_speed REAL, feed_skip_intro INTEGER,"
            " feed_skip_ending INTEGER, feed_tags TEXT);"
            "CREATE TABLE FeedItems(id INTEGER PRIMARY KEY, title TEXT, pubDate INTEGER, read INTEGER,"
            " link TEXT, description TEXT, media INTEGER, feed INTEGER, item_identifier TEXT, image_url TEXT);"
            "CREATE TABLE FeedMedia(id INTEGER PRIMARY KEY, duration INTEGER, download_url TEXT, position INTEGER,"
            " played_duration INTEGER, last_played_time INTEGER, downloaded INTEGER, mime_type TEXT, feeditem INTEGER);"
            "CREATE TABLE Queue(id INTEGER PRIMARY KEY, feeditem INTEGER, feed INTEGER);"
            "CREATE TABLE Favorites(id INTEGER PRIMARY KEY, feeditem INTEGER, feed INTEGER);"
            "CREATE TABLE SimpleChapters(id INTEGER PRIMARY KEY, title TEXT, start INTEGER, feeditem INTEGER, link TEXT, image_url TEXT);"
        )
        con.execute("INSERT INTO Feeds VALUES(1,'Pod A','',?,?,?,?,1.5,30,20,'Tech')",
                    ("https://a.com/rss", "https://a.com", "Desc A", "https://a.com/cover.jpg"))
        con.execute("INSERT INTO FeedItems VALUES(10,'Ep 1',1700000000000,1,?,?,100,1,'guid-1','')",
                    ("https://a.com/1", "body 1"))
        con.execute("INSERT INTO FeedItems VALUES(11,'Ep 2',1700000100000,0,?,?,101,1,'guid-2','')",
                    ("https://a.com/2", "body 2"))
        con.execute("INSERT INTO FeedMedia VALUES(100,1800000,?,600000,0,1700000050000,1,'audio/mpeg',10)",
                    ("https://a.com/1.mp3",))
        con.execute("INSERT INTO FeedMedia VALUES(101,1200000,?,0,0,0,0,'audio/mpeg',11)",
                    ("https://a.com/2.mp3",))
        con.execute("INSERT INTO Favorites VALUES(1,11,1)")
        con.execute("INSERT INTO Queue VALUES(1,11,1)")
        con.execute("INSERT INTO SimpleChapters VALUES(1,'Intro',0,10,'','')")
        con.commit(); con.close()

    def test_import_maps_everything(self):
        import os, tempfile
        from articles.models import Article
        from feeds.models import Feed
        from podcasts.antennapod import import_backup
        from podcasts.models import QueueItem

        u = get_user_model().objects.create_user("ap", "", "pw-ap-12345")
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False); tmp.close()
        try:
            self._make_db(tmp.name)
            counts = import_backup(u, tmp.name)
        finally:
            os.unlink(tmp.name)

        feed = Feed.objects.get(user=u, url="https://a.com/rss")
        self.assertEqual(feed.kind, "podcast")
        self.assertEqual(feed.playback_speed, 1.5)
        self.assertEqual(feed.skip_intro, 30)
        self.assertEqual(feed.image_url, "https://a.com/cover.jpg")
        ep1 = Article.objects.get(feed=feed, guid="guid-1")
        self.assertTrue(ep1.is_read)               # read==PLAYED
        self.assertEqual(ep1.play_position, 600)   # 600000ms → 600s
        self.assertEqual(ep1.duration, 1800)       # 1800000ms → 1800s
        self.assertEqual(ep1.chapters[0]["title"], "Intro")
        ep2 = Article.objects.get(feed=feed, guid="guid-2")
        self.assertTrue(ep2.is_saved)              # favorito
        self.assertEqual(QueueItem.objects.filter(user=u).count(), 1)
        self.assertEqual(counts["feeds"], 1)
        self.assertEqual(counts["episodes"], 2)
        self.assertEqual(counts["played"], 1)
        self.assertEqual(counts["favorites"], 1)
