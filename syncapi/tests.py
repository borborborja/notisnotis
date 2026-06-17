import hashlib

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from articles.models import Article
from feeds.models import Feed, Source
from syncapi.googlereader import parse_item_id
from syncapi.models import SyncCredential

H = {"HTTP_HOST": "localhost"}


class SyncBase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("demo", "", "x")
        self.cred = SyncCredential.get_or_create_for(self.user)
        self.src = Source.objects.create(name="BBC", domain="bbc.com")
        self.feed = Feed.objects.create(user=self.user, source=self.src, url="http://bbc.com/rss")
        self.art = Article.objects.create(feed=self.feed, source=self.src, guid="g1", url="http://x/1", title="Hola")


class FeverTests(SyncBase):
    def test_hash_and_auth(self):
        expected = hashlib.md5(f"demo:{self.cred.password}".encode()).hexdigest()
        self.assertEqual(self.cred.fever_hash, expected)
        c = Client()
        r = c.post("/api/fever/?api&feeds", {"api_key": expected}, **H)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["auth"], 1)
        self.assertTrue(any(f["id"] == self.feed.id for f in r.json()["feeds"]))

    def test_bad_auth(self):
        r = Client().post("/api/fever/?api&feeds", {"api_key": "nope"}, **H)
        self.assertEqual(r.json()["auth"], 0)

    def test_mark_item_read(self):
        c = Client()
        c.post("/api/fever/?api", {"api_key": self.cred.fever_hash, "mark": "item", "as": "read", "id": self.art.id}, **H)
        self.art.refresh_from_db()
        self.assertTrue(self.art.is_read)


class GReaderTests(SyncBase):
    def test_parse_item_id(self):
        self.assertEqual(parse_item_id("42"), 42)
        self.assertEqual(parse_item_id("tag:google.com,2005:reader/item/000000000000002a"), 42)

    def test_client_login_and_edit_tag(self):
        c = Client()
        r = c.post("/api/greader/accounts/ClientLogin", {"Email": "demo", "Passwd": self.cred.password}, **H)
        self.assertIn("Auth=", r.content.decode())
        auth = {"HTTP_AUTHORIZATION": f"GoogleLogin auth={self.cred.token}", **H}
        r2 = c.post("/api/greader/reader/api/0/edit-tag",
                    {"i": str(self.art.id), "a": "user/-/state/com.google/read"}, **auth)
        self.assertEqual(r2.status_code, 200)
        self.art.refresh_from_db()
        self.assertTrue(self.art.is_read)

    def test_subscription_list_requires_auth(self):
        self.assertEqual(Client().get("/api/greader/reader/api/0/subscription/list", **H).status_code, 403)

    def test_edit_tag_label_adds_user_tag(self):
        from articles.models import Tag

        c = Client()
        auth = {"HTTP_AUTHORIZATION": f"GoogleLogin auth={self.cred.token}", **H}
        c.post("/api/greader/reader/api/0/edit-tag",
               {"i": str(self.art.id), "a": "user/-/label/lectura"}, **auth)
        self.assertTrue(Tag.objects.filter(user=self.user, name="lectura").exists())
        self.assertIn("lectura", [t.name for t in self.art.tags.all()])
