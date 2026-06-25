from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from aiproviders.client import get_embed_client
from articles.models import Article


class Command(BaseCommand):
    help = "Genera embeddings para los artículos sin embedding (cliente por usuario)."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="limitar a un username")
        parser.add_argument("--batch", type=int, default=32)
        parser.add_argument("--all", action="store_true",
                            help="re-embebe TODOS los artículos, no solo los que no tienen embedding")

    def handle(self, *args, **opts):
        User = get_user_model()
        users = User.objects.all()
        if opts.get("user"):
            users = users.filter(username=opts["user"])

        done = 0
        for user in users:
            qs = Article.objects.filter(feed__user=user)
            if not opts.get("all"):
                qs = qs.filter(embedding__isnull=True)
            pending = list(qs.order_by("id"))
            if not pending:
                continue
            client = get_embed_client(user)
            # En Postgres poblamos además la columna pgvector (ANN); en SQLite no.
            use_vec = connection.vendor == "postgresql"
            fields = ["embedding", "embedded_at"] + (["embedding_vec"] if use_vec else [])
            for i in range(0, len(pending), opts["batch"]):
                chunk = pending[i : i + opts["batch"]]
                texts = [f"{a.title}\n\n{(a.summary or a.body)[:1000]}" for a in chunk]
                try:
                    vectors = client.embed(texts)
                except Exception as exc:  # noqa: BLE001
                    self.stderr.write(f"[error] embeddings de {user}: {exc}")
                    break
                now = timezone.now()
                for article, vec in zip(chunk, vectors):
                    article.embedding = vec
                    article.embedded_at = now
                    if use_vec:
                        article.embedding_vec = vec
                Article.objects.bulk_update(chunk, fields)
                done += len(chunk)
        self.stdout.write(self.style.SUCCESS(f"Embeddings generados: {done}"))
