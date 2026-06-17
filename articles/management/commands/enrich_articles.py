from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from aiproviders.client import get_chat_client
from aiproviders.config import effective_config
from articles.enrich import enrich_article
from articles.models import Article


class Command(BaseCommand):
    help = "Enriquece artículos no enriquecidos (solo usuarios con enrich_mode=batch)."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="limitar a un username")
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--force", action="store_true", help="ignorar el modo on_demand")

    def handle(self, *args, **opts):
        User = get_user_model()
        users = User.objects.all()
        if opts.get("user"):
            users = users.filter(username=opts["user"])

        done = 0
        for user in users:
            if not opts["force"] and effective_config(user)["enrich_mode"] != "batch":
                continue
            qs = (
                Article.objects.filter(feed__user=user, enriched_at__isnull=True)
                .select_related("source")
                .order_by("-fetched_at")
            )
            if opts["limit"]:
                qs = qs[: opts["limit"]]
            client = get_chat_client(user)
            for article in qs:
                try:
                    enrich_article(article, client=client)
                    done += 1
                except Exception as exc:  # noqa: BLE001
                    self.stderr.write(f"[error] {article.id}: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Artículos enriquecidos: {done}"))
