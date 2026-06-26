from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from aifeeds.models import AIFeed, AIFeedCandidate, AIFeedExample

H = {"HTTP_HOST": "localhost"}

FAKE_RESULTS = [
    {"url": "https://ej.com/llm-local", "title": "Nuevo LLM que corre en local", "snippet": "..."},
    {"url": "https://ej.com/otro", "title": "Otra noticia", "snippet": "..."},
]


class AIFeedFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("ai", "", "pw-initial-1")
        self.client.login(username="ai", password="pw-initial-1")
        self.ai = AIFeed.objects.create(user=self.user, name="IA local", description="LLM local")

    def test_run_search_creates_candidates(self):
        # web_search mockeado (sin red); provider mock por defecto.
        with mock.patch("aifeeds.services.web_search", return_value=FAKE_RESULTS):
            from aifeeds.services import run_search
            res = run_search(self.ai)
        self.assertEqual(res["proposed"], 2)
        self.assertEqual(AIFeedCandidate.objects.filter(ai_feed=self.ai, status="pending").count(), 2)

    def test_run_search_dedupes(self):
        with mock.patch("aifeeds.services.web_search", return_value=FAKE_RESULTS):
            from aifeeds.services import run_search
            run_search(self.ai)
            res2 = run_search(self.ai)  # segunda vez: mismas URLs → 0 nuevas
        self.assertEqual(res2["proposed"], 0)

    def test_accept_creates_article_and_positive_example(self):
        from aifeeds.services import accept_candidate
        from articles.models import Article

        cand = AIFeedCandidate.objects.create(
            ai_feed=self.ai, url="https://ej.com/x", title="Titular", snippet="s", score=8)
        article = accept_candidate(cand)
        cand.refresh_from_db()
        self.assertEqual(cand.status, "accepted")
        self.assertEqual(cand.article_id, article.id)
        # Artículo en el feed sintético, con fuente por dominio real (no aifeed.local).
        self.assertEqual(article.feed, self.ai.feed)
        self.assertEqual(article.source.domain, "ej.com")
        self.assertTrue(AIFeedExample.objects.filter(ai_feed=self.ai, relevant=True).exists())

    def test_reject_creates_negative_example(self):
        from aifeeds.services import reject_candidate

        cand = AIFeedCandidate.objects.create(
            ai_feed=self.ai, url="https://ej.com/y", title="No", snippet="s", score=7)
        reject_candidate(cand)
        cand.refresh_from_db()
        self.assertEqual(cand.status, "rejected")
        self.assertTrue(AIFeedExample.objects.filter(ai_feed=self.ai, relevant=False).exists())

    def test_views_list_and_decide(self):
        r = self.client.get("/aifeeds/", **H)
        self.assertEqual(r.status_code, 200)
        cand = AIFeedCandidate.objects.create(
            ai_feed=self.ai, url="https://ej.com/z", title="Z", snippet="s", score=9)
        r = self.client.post(f"/aifeeds/candidate/{cand.pk}/decide/", {"decision": "accept"}, **H)
        self.assertEqual(r.status_code, 200)
        cand.refresh_from_db()
        self.assertEqual(cand.status, "accepted")


class AutoAcceptTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from accounts.models import UserConfig
        self.u = get_user_model().objects.create_user("aa", "", "pw-aa-12345")
        UserConfig.objects.create(user=self.u, data={"chat_provider": "mock"})

    def _feed(self, **kw):
        from aifeeds.models import AIFeed
        return AIFeed.objects.create(user=self.u, name="T", description="tema", **kw)

    def test_untrained_only_proposes(self):
        from unittest import mock
        from aifeeds import services
        from aifeeds.models import AIFeedCandidate
        ai = self._feed(min_score=5, auto_accept_score=8)
        results = [{"url": "https://x/1", "title": "N1", "snippet": "s"}]
        with mock.patch("aifeeds.services.web_search", return_value=results), \
             mock.patch("aifeeds.services.score_candidates", return_value={"https://x/1": {"score": 10, "reason": ""}}), \
             mock.patch("aifeeds.services.generate_queries", return_value=["q"]):
            res = services.run_search(ai)
        self.assertEqual(res, {"proposed": 1, "auto": 0})  # sin entrenar → solo propone
        self.assertEqual(AIFeedCandidate.objects.filter(ai_feed=ai, status="pending").count(), 1)

    def test_trained_auto_accepts_high_score(self):
        from unittest import mock
        from aifeeds import services
        from aifeeds.models import AIFeedCandidate, AIFeedExample
        from articles.models import Article
        ai = self._feed(min_score=5, auto_accept_score=8)
        for i in range(services.TRAIN_MIN):  # entrenar
            AIFeedExample.objects.create(ai_feed=ai, title=f"ok{i}", relevant=True)
        results = [{"url": "https://x/hi", "title": "Alta", "snippet": "s"},
                   {"url": "https://x/lo", "title": "Media", "snippet": "s"}]
        scores = {"https://x/hi": {"score": 9, "reason": "", "llm": True},
                  "https://x/lo": {"score": 6, "reason": "", "llm": True}}
        with mock.patch("aifeeds.services.web_search", side_effect=lambda q, k=12: results), \
             mock.patch("aifeeds.services.score_candidates", return_value=scores), \
             mock.patch("aifeeds.services.generate_queries", return_value=["q"]):
            res = services.run_search(ai)
        self.assertEqual(res["auto"], 1)       # la de 9 se auto-añade
        self.assertEqual(res["proposed"], 1)   # la de 6 queda por revisar
        self.assertTrue(Article.objects.filter(feed=ai.feed, title="Alta").exists())
        self.assertEqual(AIFeedCandidate.objects.filter(ai_feed=ai, status="accepted").count(), 1)

    def test_unscored_never_auto_accepts(self):
        """Un candidato que el LLM NO puntuó (llm=False) no se auto-acepta aunque min>=auto."""
        from unittest import mock
        from aifeeds import services
        from aifeeds.models import AIFeedCandidate, AIFeedExample
        ai = self._feed(min_score=8, auto_accept_score=8)  # config alcanzable por el usuario
        for i in range(services.TRAIN_MIN):
            AIFeedExample.objects.create(ai_feed=ai, title=f"ok{i}", relevant=True)
        results = [{"url": "https://x/u", "title": "SinPuntuar", "snippet": "s"}]
        # score_candidates real con LLM que no devuelve nada → fallback llm=False, score=min_score
        with mock.patch("aifeeds.services.web_search", side_effect=lambda q, k=12: results), \
             mock.patch("aifeeds.services.score_candidates",
                        return_value={"https://x/u": {"score": 8, "reason": "", "llm": False}}), \
             mock.patch("aifeeds.services.generate_queries", return_value=["q"]):
            res = services.run_search(ai)
        self.assertEqual(res["auto"], 0)       # NO se auto-acepta sin score real
        self.assertEqual(res["proposed"], 1)   # queda como propuesta
