from django.contrib.auth import get_user_model
from django.test import TestCase

from articles.models import Article
from feeds.models import Feed, Source

H = {"HTTP_HOST": "localhost"}


class SearchTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user("u", "", "pw")
        self.client.login(username="u", password="pw")
        self.src = Source.objects.create(name="BBC", domain="bbc.com")
        self.feed = Feed.objects.create(user_id=1, source=self.src, url="http://bbc/rss")
        Article.objects.create(feed=self.feed, source=self.src, guid="1", title="Clima y energía", body="cuerpo sobre clima", is_read=False)
        Article.objects.create(feed=self.feed, source=self.src, guid="2", title="Deportes", body="futbol", is_read=True, is_saved=True)
        Article.objects.create(feed=self.feed, source=self.src, guid="3", title="Economía", summary="mercados", is_read=False)

    def _titles(self, q):
        r = self.client.get(f"/articles/?q={q}", **H)
        return [a.title for a in r.context["page"]]

    def test_text_search_in_body(self):
        self.assertEqual(self._titles("clima"), ["Clima y energía"])

    def test_is_unread_operator(self):
        titles = self._titles("is:unread")
        self.assertIn("Clima y energía", titles)
        self.assertNotIn("Deportes", titles)

    def test_is_saved_operator(self):
        self.assertEqual(self._titles("is:saved"), ["Deportes"])


class TagTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user("t", "", "pw")
        self.client.login(username="t", password="pw")
        self.src = Source.objects.create(name="BBC", domain="bbc.com")
        self.feed = Feed.objects.create(user_id=1, source=self.src, url="http://bbc/rss")
        self.art = Article.objects.create(feed=self.feed, source=self.src, guid="1", title="Hola", body="x")

    def test_tag_add_remove_and_filter(self):
        from articles.models import Tag

        self.client.post(f"/articles/{self.art.pk}/tag/", {"name": "fav"}, **H)
        tag = Tag.objects.get(user_id=1, name="fav")
        self.assertIn(tag, self.art.tags.all())
        r = self.client.get(f"/articles/?tag={tag.id}", **H)
        self.assertIn(self.art, list(r.context["page"]))
        self.client.post(f"/articles/{self.art.pk}/untag/", {"tag_id": tag.id}, **H)
        self.assertEqual(self.art.tags.count(), 0)

    def test_export_markdown(self):
        r = self.client.get(f"/articles/{self.art.pk}/export.md", **H)
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/markdown", r["Content-Type"])
        self.assertIn(b"# Hola", r.content)
