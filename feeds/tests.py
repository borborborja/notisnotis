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
