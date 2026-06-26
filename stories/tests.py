from django.test import TestCase

from stories.analysis import compute_bias_distribution, detect_blindspot
from stories.similarity import cosine, mean_vector


class _FakeSource:
    def __init__(self, bias):
        self.bias = bias


class _FakeArticle:
    def __init__(self, bias):
        self.source = _FakeSource(bias)


class SimilarityTests(TestCase):
    def test_cosine_identical(self):
        self.assertAlmostEqual(cosine([1, 0, 0], [1, 0, 0]), 1.0)

    def test_cosine_orthogonal(self):
        self.assertAlmostEqual(cosine([1, 0], [0, 1]), 0.0)

    def test_cosine_mismatched_or_empty(self):
        self.assertEqual(cosine([1, 2], [1]), 0.0)
        self.assertEqual(cosine([], [1]), 0.0)

    def test_mean_vector(self):
        self.assertEqual(mean_vector([[0, 0], [2, 4]]), [1.0, 2.0])
        self.assertIsNone(mean_vector([]))


class BlindspotTests(TestCase):
    def test_distribution_counts(self):
        arts = [_FakeArticle("left"), _FakeArticle("left"), _FakeArticle("center")]
        dist = compute_bias_distribution(arts)
        self.assertEqual(dist["left"], 2)
        self.assertEqual(dist["center"], 1)

    def test_blindspot_when_one_side_dominates(self):
        dist = {"left": 5, "lean_left": 3, "center": 0, "lean_right": 0, "right": 0}
        is_blind, side = detect_blindspot(dist)
        self.assertTrue(is_blind)
        self.assertEqual(side, "right")

    def test_no_blindspot_when_balanced(self):
        dist = {"left": 3, "lean_left": 0, "center": 1, "lean_right": 0, "right": 3}
        is_blind, _ = detect_blindspot(dist)
        self.assertFalse(is_blind)

    def test_no_blindspot_below_minimum_coverage(self):
        dist = {"left": 2, "lean_left": 0, "center": 0, "lean_right": 0, "right": 0}
        is_blind, _ = detect_blindspot(dist)
        self.assertFalse(is_blind)


class PhaseCTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from feeds.models import Feed, Source
        from articles.models import Article
        from django.utils import timezone

        self.user = get_user_model().objects.create_user("c", "", "pw")
        self.client.login(username="c", password="pw")
        self.H = {"HTTP_HOST": "localhost"}
        self.left = Source.objects.create(name="Izq", domain="izq.com", bias="left")
        self.right = Source.objects.create(name="Der", domain="der.com", bias="right")
        fl = Feed.objects.create(user=self.user, source=self.left, url="http://izq/rss")
        fr = Feed.objects.create(user=self.user, source=self.right, url="http://der/rss")
        now = timezone.now()
        for i in range(3):
            Article.objects.create(feed=fl, source=self.left, guid=f"l{i}", title=f"Clima {i}",
                                   is_read=True, read_at=now)
        Article.objects.create(feed=fr, source=self.right, guid="r0", title="Deportes", is_read=True, read_at=now)

    def test_bias_diet_counts_read(self):
        r = self.client.get("/diet/?days=30", **self.H)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["total"], 4)

    def test_topic_create_and_filter(self):
        from stories.models import Topic

        self.client.post("/topics/", {"name": "Clima", "keywords": "clima"}, **self.H)
        topic = Topic.objects.get(user=self.user, name="Clima")
        r = self.client.get(f"/articles/?topic={topic.id}", **self.H)
        titles = [a.title for a in r.context["page"]]
        self.assertTrue(all("Clima" in t for t in titles))
        self.assertEqual(len(titles), 3)

    def test_trending_ok(self):
        self.assertEqual(self.client.get("/trending/", **self.H).status_code, 200)

    def test_topic_matcher(self):
        from stories.models import Topic
        from stories.topics import article_matches, topic_terms

        t = Topic.objects.create(user=self.user, name="x", keywords="clima, energía")
        terms = topic_terms(t)
        self.assertTrue(article_matches(terms, type("A", (), {"title": "El CLIMA hoy", "summary": ""})))
        self.assertFalse(article_matches(terms, type("A", (), {"title": "Deportes", "summary": ""})))


class NNBackendTests(TestCase):
    """Backend de vecinos: en SQLite usa el fallback coseno en Python (pgvector solo PG)."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from feeds.models import Feed, Source
        from articles.models import Article

        self.user = get_user_model().objects.create_user("nn", "", "pw")
        src = Source.objects.create(name="S", domain="s.com", bias="center")
        feed = Feed.objects.create(user=self.user, source=src, url="http://s/rss")
        # Embeddings 3D sencillos: a y b alineados con la consulta, c ortogonal.
        Article.objects.create(feed=feed, source=src, guid="a", title="A", embedding=[1.0, 0.0, 0.0])
        Article.objects.create(feed=feed, source=src, guid="b", title="B", embedding=[0.9, 0.1, 0.0])
        Article.objects.create(feed=feed, source=src, guid="c", title="C", embedding=[0.0, 0.0, 1.0])

    def test_top_k_ranks_by_similarity(self):
        from stories.nn import top_k_articles

        results = top_k_articles(self.user, [1.0, 0.0, 0.0], k=2)
        self.assertEqual(len(results), 2)
        titles = [a.title for _, a in results]
        # Los dos más cercanos a la consulta son A y B (no C, ortogonal).
        self.assertEqual(set(titles), {"A", "B"})
        # Devuelve (score, Article) ordenado de mayor a menor score.
        self.assertGreaterEqual(results[0][0], results[1][0])

    def test_empty_vector_returns_empty(self):
        from stories.nn import top_k_articles

        self.assertEqual(top_k_articles(self.user, [], k=5), [])


class ClusteringSourceTests(TestCase):
    def test_same_topic_clusters_even_same_source(self):
        from django.contrib.auth import get_user_model
        from feeds.models import Feed, Source
        from articles.models import Article
        from stories.models import Story
        from django.core.management import call_command

        u = get_user_model().objects.create_user("cl", "", "pw")
        src = Source.objects.create(name="Blog", domain="blog.com")
        feed = Feed.objects.create(user=u, source=src, url="http://blog/rss")
        # Mismo tema (embeddings idénticos), misma fuente: deben ir en UNA historia
        # (timeline de evolución del tema, aunque sea el mismo medio).
        Article.objects.create(feed=feed, source=src, guid="c1", title="SpaceX posible salida", embedding=[1.0, 0.0])
        Article.objects.create(feed=feed, source=src, guid="c2", title="SpaceX sale a bolsa", embedding=[1.0, 0.0])
        call_command("cluster_stories", "--user", "cl")
        self.assertEqual(Story.objects.filter(user=u).count(), 1)

    def test_different_sources_cluster(self):
        from django.contrib.auth import get_user_model
        from feeds.models import Feed, Source
        from articles.models import Article
        from stories.models import Story
        from django.core.management import call_command

        u = get_user_model().objects.create_user("cl2", "", "pw")
        s1 = Source.objects.create(name="A", domain="a.com")
        s2 = Source.objects.create(name="B", domain="b.com")
        f1 = Feed.objects.create(user=u, source=s1, url="http://a/rss")
        f2 = Feed.objects.create(user=u, source=s2, url="http://b/rss")
        Article.objects.create(feed=f1, source=s1, guid="x1", title="Evento", embedding=[1.0, 0.0])
        Article.objects.create(feed=f2, source=s2, guid="x2", title="Evento", embedding=[1.0, 0.0])
        call_command("cluster_stories", "--user", "cl2")
        # Dos fuentes distintas, mismo suceso → una sola historia con 2 fuentes.
        self.assertEqual(Story.objects.filter(user=u).count(), 1)


class SynthesisTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from feeds.models import Feed, Source
        from articles.models import Article
        from stories.models import Story, StoryArticle

        self.U = get_user_model()
        self.U.objects.create_user("sy", "", "pw-initial-1")
        self.client.login(username="sy", password="pw-initial-1")
        u = self.U.objects.get(username="sy")
        s1 = Source.objects.create(name="A", domain="a.com", bias="left")
        s2 = Source.objects.create(name="B", domain="b.com", bias="right")
        f1 = Feed.objects.create(user=u, source=s1, url="http://a/rss")
        f2 = Feed.objects.create(user=u, source=s2, url="http://b/rss")
        a1 = Article.objects.create(feed=f1, source=s1, guid="a1", title="X según A", body="cuerpo A")
        a2 = Article.objects.create(feed=f2, source=s2, guid="a2", title="X según B", body="cuerpo B")
        self.story = Story.objects.create(user=u, headline="X")
        StoryArticle.objects.create(story=self.story, article=a1, similarity=1.0)
        StoryArticle.objects.create(story=self.story, article=a2, similarity=0.9)

    def test_synthesize_multi_source(self):
        from stories.models import Story

        r = self.client.post(f"/story/{self.story.pk}/synthesize/", **self.H if hasattr(self, 'H') else {"HTTP_HOST": "localhost"})
        self.assertEqual(r.status_code, 200)
        self.story.refresh_from_db()
        self.assertTrue(self.story.synthesis)            # el mock devuelve texto
        self.assertIsNotNone(self.story.synthesized_at)

    def test_render_markdown_escapes_and_formats(self):
        from stories.synthesis import render_markdown

        out = render_markdown("## Título\n\nIdea **clave** y <script>")
        self.assertIn("<h3>Título</h3>", out)
        self.assertIn("<strong>clave</strong>", out)
        self.assertIn("&lt;script&gt;", out)            # HTML escapado (seguro)


class TrendingTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.U = get_user_model()
        self.user = self.U.objects.create_user("tu_real", "", "pw-tr-12345")
        self.client.login(username="tu_real", password="pw-tr-12345")

    def test_top_headlines_cleans_source_suffix(self):
        from unittest import mock
        from stories import trending

        class _P:
            entries = [{"title": "Gran noticia - El País"}, {"title": "Otra cosa - RTVE"},
                       {"title": "Gran noticia - El País"}]  # duplicado
        with mock.patch("stories.trending.feedparser.parse", return_value=_P()):
            heads = trending.top_headlines("ES", limit=10)
        self.assertEqual(heads, ["Gran noticia", "Otra cosa"])

    def test_fetch_trending_creates_articles_for_system_user(self):
        from unittest import mock
        from django.core.management import call_command
        from articles.models import Article
        from stories.trending import trending_user

        results = [{"url": "https://a.com/1", "title": "T1", "snippet": "s"},
                   {"url": "https://b.com/2", "title": "T2", "snippet": "s"}]
        with mock.patch("stories.trending.top_headlines", return_value=["Titular"]), \
             mock.patch("aifeeds.search.web_search", return_value=results):
            call_command("fetch_trending", "--country", "ES", "--force")
        tu = trending_user("ES")
        self.assertEqual(Article.objects.filter(feed__user=tu).count(), 2)
        # No aparecen en el lector del usuario real.
        self.assertEqual(Article.objects.filter(feed__user=self.user).count(), 0)

    def _trend_story(self, cc="ES", headline="Suceso"):
        from stories.models import Story, StoryArticle
        from stories.trending import trending_user, trending_feed
        from feeds.models import Source
        from articles.models import Article
        tu = trending_user(cc); feed = trending_feed(cc)
        st = Story.objects.create(user=tu, headline=headline,
                                  bias_distribution={"left": 1, "center": 1})
        for i, dom in enumerate(["l.com", "c.com"]):
            src, _ = Source.objects.get_or_create(domain=dom, defaults={"name": dom, "bias": "left" if i == 0 else "center"})
            a = Article.objects.create(feed=feed, source=src, guid=f"{cc}{i}", title=f"a{i}",
                                       url=f"https://{dom}/{i}")
            StoryArticle.objects.create(story=st, article=a, similarity=0.9)
        return st

    def test_trending_view_shows_country_only(self):
        es = self._trend_story("ES", "Noticia ES")
        self._trend_story("US", "News US")
        r = self.client.get("/trending/")  # país por defecto ES
        self.assertContains(r, "Noticia ES")
        self.assertNotContains(r, "News US")

    def test_trending_detail_rejects_user_story(self):
        from stories.models import Story
        mine = Story.objects.create(user=self.user, headline="Mía")
        self.assertEqual(self.client.get(f"/trending/{mine.pk}/").status_code, 404)
        es = self._trend_story("ES")
        self.assertEqual(self.client.get(f"/trending/{es.pk}/").status_code, 200)

    def test_set_country_saves_pref(self):
        from accounts.models import UserConfig
        self.client.post("/trending/country/", {"country": "US"})
        self.assertEqual(UserConfig.objects.get(user=self.user).data["trending_country"], "US")


class CredibilityTests(TestCase):
    def test_press_freedom_tiers(self):
        from feeds.press_freedom import tier
        self.assertEqual(tier("ES"), "free")
        self.assertEqual(tier("VE"), "not_free")
        self.assertEqual(tier("ZZ"), "unknown")

    def test_signal_local_free_boost_and_state_censored_discount(self):
        from stories.credibility import source_signal
        class S:
            def __init__(self, **k): self.__dict__.update(k)
        # Local en país libre, alta fiabilidad → peso alto + flag local
        s1 = S(factuality="high", country="ES", ownership="independent")
        r1 = source_signal(s1, "ES")
        self.assertIn("local", r1["flags"]); self.assertGreaterEqual(r1["weight"], 1.0)
        # Estatal en país sin libertad de prensa → fuerte recorte + flags
        s2 = S(factuality="high", country="VE", ownership="state")
        r2 = source_signal(s2, "VE")
        self.assertIn("estatal", r2["flags"]); self.assertIn("baja libertad de prensa", r2["flags"])
        self.assertLess(r2["weight"], r1["weight"])

    def test_context_label(self):
        from stories.credibility import context_label
        class S:
            def __init__(self, **k): self.__dict__.update(k)
        lbl = context_label(S(country="VE", ownership="state", factuality="mixed"), "VE")
        self.assertIn("local", lbl); self.assertIn("estatal", lbl); self.assertIn("libertad", lbl)
