from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Transcribe episodios de audio/YouTube en segundo plano (trickle; lento en CPU)."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="limitar a un username")
        parser.add_argument("--limit", type=int, default=3, help="máx. por pasada (trickle)")

    def handle(self, *args, **opts):
        from articles.models import Article
        from articles.transcribe import is_transcribable, transcribe_episode

        users = get_user_model().objects.all()
        if opts.get("user"):
            users = users.filter(username=opts["user"])
        limit = opts.get("limit", 3)

        done = 0
        for user in users:
            cfg = getattr(user, "config", None)
            auto = bool(cfg and cfg.data.get("auto_transcribe") == "1")
            base = (Article.objects.filter(feed__user=user, feed__kind__in=["podcast", "youtube"])
                    .exclude(fulltext_source="transcript").select_related("feed"))
            qs = base if auto else base.filter(transcribe_requested=True)
            # Los pedidos explícitamente, primero.
            for art in qs.order_by("-transcribe_requested", "-published_at")[:limit]:
                if not is_transcribable(art):
                    continue
                try:
                    transcribe_episode(art)
                    done += 1
                except Exception as exc:  # noqa: BLE001 - un episodio que falle no aborta el lote
                    self.stderr.write(f"[error] {art.id}: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Episodios transcritos: {done}"))
