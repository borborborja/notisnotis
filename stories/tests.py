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
    def test_same_source_not_clustered(self):
        from django.contrib.auth import get_user_model
        from feeds.models import Feed, Source
        from articles.models import Article
        from stories.models import Story
        from django.core.management import call_command

        u = get_user_model().objects.create_user("cl", "", "pw")
        src = Source.objects.create(name="Blog", domain="blog.com")
        feed = Feed.objects.create(user=u, source=src, url="http://blog/rss")
        # Dos entradas de la MISMA fuente con embeddings idénticos (títulos casi iguales).
        Article.objects.create(feed=feed, source=src, guid="c1", title="Cap 73", embedding=[1.0, 0.0])
        Article.objects.create(feed=feed, source=src, guid="c2", title="Cap 75", embedding=[1.0, 0.0])
        call_command("cluster_stories", "--user", "cl")
        # No deben acabar en la misma historia (cada fuente aporta una sola perspectiva).
        self.assertEqual(Story.objects.filter(user=u).count(), 2)

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
