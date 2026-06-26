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
            n = run_search(self.ai)
        self.assertEqual(n, 2)
        self.assertEqual(AIFeedCandidate.objects.filter(ai_feed=self.ai, status="pending").count(), 2)

    def test_run_search_dedupes(self):
        with mock.patch("aifeeds.services.web_search", return_value=FAKE_RESULTS):
            from aifeeds.services import run_search
            run_search(self.ai)
            n2 = run_search(self.ai)  # segunda vez: mismas URLs → 0 nuevas
        self.assertEqual(n2, 0)

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
