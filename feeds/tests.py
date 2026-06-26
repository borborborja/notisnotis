from django.contrib.auth import get_user_model
from django.test import TestCase

from feeds.models import Bias, Feed, Source
from feeds.opml import import_opml_for_user

OPML = """<?xml version="1.0"?>
<opml version="2.0"><body>
  <outline title="BBC" type="rss" xmlUrl="http://feeds.bbci.co.uk/news/rss.xml" htmlUrl="https://www.bbc.com"/>
  <outline title="NPR" type="rss" xmlUrl="https://feeds.npr.org/1001/rss.xml" htmlUrl="https://www.npr.org"/>
  <outline title="Carpeta sin feed"/>
</body></opml>"""


class OpmlImportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("u", "", "x")

    def test_import_creates_sources_and_feeds(self):
        created, skipped = import_opml_for_user(self.user, OPML)
        self.assertEqual(created, 2)
        self.assertEqual(skipped, 0)
        self.assertEqual(Feed.objects.filter(user=self.user).count(), 2)
        self.assertTrue(Source.objects.filter(domain="bbc.com").exists())

    def test_reimport_is_idempotent(self):
        import_opml_for_user(self.user, OPML)
        created, skipped = import_opml_for_user(self.user, OPML)
        self.assertEqual(created, 0)
        self.assertEqual(skipped, 2)

    def test_domain_strips_www(self):
        import_opml_for_user(self.user, OPML)
        self.assertFalse(Source.objects.filter(domain__startswith="www.").exists())


NESTED_OPML = """<?xml version="1.0"?>
<opml version="2.0"><body>
  <outline title="Noticias">
    <outline title="BBC" type="rss" xmlUrl="http://feeds.bbci.co.uk/news/rss.xml" htmlUrl="https://www.bbc.com"/>
    <outline title="NPR" type="rss" xmlUrl="https://feeds.npr.org/1001/rss.xml" htmlUrl="https://www.npr.org"/>
  </outline>
  <outline title="Suelto" type="rss" xmlUrl="https://example.com/rss" htmlUrl="https://example.com"/>
</body></opml>"""


class FilterRuleTests(TestCase):
    def test_block_matches(self):
        from feeds.filters import compile_rules, is_blocked

        block = compile_rules("publicidad\n(?i)patrocinado")
        self.assertTrue(is_blocked("Post PATROCINADO", "", block, []))
        self.assertFalse(is_blocked("Noticia normal", "", block, []))

    def test_keep_only(self):
        from feeds.filters import compile_rules, is_blocked

        keep = compile_rules("clima")
        self.assertFalse(is_blocked("El clima hoy", "", [], keep))
        self.assertTrue(is_blocked("Deportes", "", [], keep))

    def test_invalid_regex_ignored(self):
        from feeds.filters import compile_rules

        self.assertEqual(len(compile_rules("[unclosed\nvalido")), 1)


class CategoryMgmtTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user("u", "", "pw")
        self.c = self.client
        self.c.login(username="u", password="pw")
        self.H = {"HTTP_HOST": "localhost"}

    def test_create_rename_delete(self):
        from feeds.models import Category

        self.c.post("/feeds/categories/create/", {"name": "Tecno"}, **self.H)
        cat = Category.objects.get(name="Tecno")
        self.c.post(f"/feeds/categories/{cat.pk}/rename/", {"name": "Tech"}, **self.H)
        cat.refresh_from_db()
        self.assertEqual(cat.name, "Tech")
        self.c.post(f"/feeds/categories/{cat.pk}/delete/", **self.H)
        self.assertFalse(Category.objects.filter(pk=cat.pk).exists())


class SubscribeHelperTests(TestCase):
    def test_create_feed(self):
        from feeds.views import _create_feed

        user = get_user_model().objects.create_user("s", "", "pw")
        feed, created = _create_feed(user, "https://www.bbc.com/news/rss.xml", "BBC")
        self.assertTrue(created)
        self.assertEqual(feed.source.domain, "bbc.com")
        # idempotente
        _, created2 = _create_feed(user, "https://www.bbc.com/news/rss.xml", "BBC")
        self.assertFalse(created2)


class FeedHealthTests(TestCase):
    def test_reactivate(self):
        from feeds.models import Source

        u = get_user_model().objects.create_user("h", "", "pw")
        self.client.login(username="h", password="pw")
        src = Source.objects.create(name="S", domain="s.com")
        feed = Feed.objects.create(user=u, source=src, url="http://s/rss", enabled=False, fail_count=12,
                                  last_error="boom")
        self.client.post(f"/feeds/{feed.pk}/reactivate/", HTTP_HOST="localhost")
        feed.refresh_from_db()
        self.assertTrue(feed.enabled)
        self.assertEqual(feed.fail_count, 0)
        self.assertEqual(feed.last_error, "")


class RuleEngineTests(TestCase):
    def setUp(self):
        from articles.models import Article, Tag
        from feeds.models import Source

        self.user = get_user_model().objects.create_user("r", "", "pw")
        src = Source.objects.create(name="S", domain="s.com")
        self.feed = Feed.objects.create(user=self.user, source=src, url="http://s/rss")
        self.match = Article.objects.create(feed=self.feed, source=src, guid="1", title="Oferta especial hoy")
        self.nomatch = Article.objects.create(feed=self.feed, source=src, guid="2", title="Noticia normal")
        self.tag = Tag.objects.create(user=self.user, name="promos")

    def test_rule_applies_actions_on_match(self):
        from feeds.models import Rule
        from feeds.rules import apply_rules, load_rules

        Rule.objects.create(user=self.user, name="promos", pattern="(?i)oferta",
                            action_mark_read=True, action_star=True, action_tag=self.tag)
        rules = load_rules(self.user)
        apply_rules(self.match, rules)
        apply_rules(self.nomatch, rules)
        self.match.refresh_from_db(); self.nomatch.refresh_from_db()
        self.assertTrue(self.match.is_read)
        self.assertTrue(self.match.is_saved)
        self.assertIn(self.tag, self.match.tags.all())
        self.assertFalse(self.nomatch.is_read)


class NestedOpmlTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("n", "", "x")

    def test_folders_become_categories(self):
        from feeds.models import Category

        import_opml_for_user(self.user, NESTED_OPML)
        cat = Category.objects.get(user=self.user, name="Noticias")
        self.assertEqual(cat.feeds.count(), 2)
        # El feed fuera de carpeta queda sin categoría.
        self.assertEqual(Feed.objects.filter(user=self.user, category__isnull=True).count(), 1)


class CrawlNewFeedsTests(TestCase):
    def test_opml_import_sets_crawler_when_pref_on(self):
        from accounts.models import UserConfig
        from feeds.models import Feed
        from feeds.opml import import_opml_for_user

        user = get_user_model().objects.create_user("cr", "", "pw")
        UserConfig.objects.create(user=user, data={"crawl_new_feeds": "1"})
        opml = '<?xml version="1.0"?><opml><body>' \
               '<outline type="rss" text="X" xmlUrl="http://x.com/rss"/></body></opml>'
        import_opml_for_user(user, opml)
        self.assertTrue(Feed.objects.get(user=user, url="http://x.com/rss").crawler)

    def test_opml_import_no_crawler_by_default(self):
        from feeds.models import Feed
        from feeds.opml import import_opml_for_user

        user = get_user_model().objects.create_user("cr2", "", "pw")
        opml = '<?xml version="1.0"?><opml><body>' \
               '<outline type="rss" text="Y" xmlUrl="http://y.com/rss"/></body></opml>'
        import_opml_for_user(user, opml)
        self.assertFalse(Feed.objects.get(user=user, url="http://y.com/rss").crawler)


class OpmlKindTests(TestCase):
    def test_opml_marks_youtube_kind(self):
        from django.contrib.auth import get_user_model
        from feeds.models import Feed
        from feeds.opml import import_opml_for_user

        u = get_user_model().objects.create_user("yt", "", "pw")
        opml = ('<?xml version="1.0"?><opml><body>'
                '<outline type="rss" text="Canal" xmlUrl="https://www.youtube.com/feeds/videos.xml?channel_id=UC123"/>'
                '<outline type="rss" text="Blog" xmlUrl="https://blog.com/rss"/></body></opml>')
        import_opml_for_user(u, opml)
        self.assertEqual(Feed.objects.get(user=u, url__contains="youtube").kind, "youtube")
        self.assertEqual(Feed.objects.get(user=u, url="https://blog.com/rss").kind, "rss")


class FeedsManagerTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.U = get_user_model()
        self.u = self.U.objects.create_user("mg", "", "pw-mgr-12345")
        self.client.login(username="mg", password="pw-mgr-12345")

    def test_opml_import_as_podcast(self):
        from feeds.models import Feed
        from feeds.opml import import_opml_for_user
        opml = ('<?xml version="1.0"?><opml><body>'
                '<outline type="rss" text="Pod" xmlUrl="https://pod.com/rss"/>'
                '<outline type="rss" text="Yt" xmlUrl="https://www.youtube.com/feeds/videos.xml?channel_id=UC1"/>'
                '</body></opml>')
        import_opml_for_user(self.u, opml, kind="podcast")
        self.assertEqual(Feed.objects.get(user=self.u, url="https://pod.com/rss").kind, "podcast")
        # YouTube siempre se detecta como youtube aunque importes como podcast.
        self.assertEqual(Feed.objects.get(user=self.u, url__contains="youtube").kind, "youtube")

    def test_reimport_as_podcast_promotes_existing_rss(self):
        from feeds.models import Feed
        opml = ('<?xml version="1.0"?><opml><body>'
                '<outline type="rss" text="P" xmlUrl="https://p.com/rss"/></body></opml>')
        import_opml_for_user(self.u, opml, kind="rss")
        self.assertEqual(Feed.objects.get(user=self.u, url="https://p.com/rss").kind, "rss")
        # Reimportar como Podcasts promueve el feed existente (no se quedan como RSS).
        created, skipped = import_opml_for_user(self.u, opml, kind="podcast")
        self.assertEqual((created, skipped), (0, 1))
        self.assertEqual(Feed.objects.get(user=self.u, url="https://p.com/rss").kind, "podcast")

    def test_search_podcasts_parses_itunes(self):
        from unittest import mock
        from feeds.podcastsearch import search_podcasts

        class _Resp:
            def raise_for_status(self): pass
            def json(self):
                return {"results": [
                    {"collectionName": "Mi Pod", "feedUrl": "https://x/rss", "artistName": "Autor",
                     "artworkUrl100": "https://x/art.jpg"},
                    {"collectionName": "Sin feed"},  # se descarta
                ]}
        with mock.patch("feeds.podcastsearch.requests.get", return_value=_Resp()):
            out = search_podcasts("test")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["feed_url"], "https://x/rss")
        self.assertEqual(out[0]["title"], "Mi Pod")

    def test_podcast_search_view(self):
        from unittest import mock
        with mock.patch("feeds.views.search_podcasts" if False else "feeds.podcastsearch.requests.get") as g:
            g.return_value.raise_for_status = lambda: None
            g.return_value.json = lambda: {"results": []}
            r = self.client.get("/feeds/podcasts/search/?q=algo")
        self.assertEqual(r.status_code, 200)

    def test_feed_list_tabs_split_by_kind(self):
        from feeds.models import Feed, Source
        s = Source.objects.create(name="S", domain="s.com")
        Feed.objects.create(user=self.u, source=s, url="http://s/rss", kind="rss")
        Feed.objects.create(user=self.u, source=s, url="http://s/pod", kind="podcast")
        r = self.client.get("/feeds/?tab=podcasts")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["active"], "podcasts")
        self.assertEqual(len(r.context["rss_feeds"]), 1)
        self.assertEqual(len(r.context["podcast_feeds"]), 1)


class SidebarPerfTests(TestCase):
    def test_sidebar_skipped_on_htmx(self):
        from django.contrib.auth import get_user_model
        from feeds.context_processors import sidebar

        class _Req:
            def __init__(self, htmx):
                self.user = u
                self.headers = {"HX-Request": "true"} if htmx else {}
        u = get_user_model().objects.create_user("sp", "", "pw-sp-123")
        self.assertEqual(sidebar(_Req(True)), {})         # htmx → vacío (sin queries)
        self.assertIn("sidebar_categories", sidebar(_Req(False)))  # full → datos


class ImageExtractionTests(TestCase):
    def test_img_field_sources_and_https(self):
        from feeds.management.commands.fetch_feeds import _img_field, _entry_image
        self.assertEqual(_img_field({"image": {"href": "http://x/a.jpg"}}), "https://x/a.jpg")
        self.assertEqual(_img_field({"itunes_image": "http://x/b.jpg"}), "https://x/b.jpg")
        self.assertEqual(_img_field({"media_thumbnail": [{"url": "https://x/c.jpg"}]}), "https://x/c.jpg")
        self.assertEqual(_entry_image({}), "")

    def test_backfill_from_episode(self):
        from django.contrib.auth import get_user_model
        from django.core.management import call_command
        from feeds.models import Feed, Source
        from articles.models import Article
        u = get_user_model().objects.create_user("bf", "", "pw-bf-123")
        src = Source.objects.create(name="B", domain="b.com")
        feed = Feed.objects.create(user=u, source=src, url="http://b/rss", kind="podcast")
        Article.objects.create(feed=feed, source=src, guid="b1", title="E",
                               image_url="https://b/ep.jpg")
        call_command("backfill_podcast_images", "--user", "bf")
        feed.refresh_from_db()
        self.assertEqual(feed.image_url, "https://b/ep.jpg")
