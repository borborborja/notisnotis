from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Busca por internet y propone noticias para los feeds con IA (incremental)."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="limitar a un username")
        parser.add_argument("--feed", type=int, help="id de un AIFeed concreto")
        parser.add_argument("--force", action="store_true", help="ignorar la cadencia (busca ya)")

    def handle(self, *args, **opts):
        from datetime import timedelta

        from django.utils import timezone

        from aifeeds.models import AIFeed
        from aifeeds.services import run_search

        qs = AIFeed.objects.filter(enabled=True).select_related("user", "user__config")
        if opts.get("user"):
            qs = qs.filter(user__username=opts["user"])
        if opts.get("feed"):
            qs = qs.filter(pk=opts["feed"])

        from features.modules import module_enabled

        gated = not (opts.get("force") or opts.get("feed"))
        now = timezone.now()
        total = 0
        for ai in qs:
            if not module_enabled(ai.user, "curation"):
                continue
            if gated and ai.last_run:
                cfg = getattr(ai.user, "config", None)
                minutes = int(cfg.data.get("ai_search_minutes", 720)) if cfg else 720
                if ai.last_run > now - timedelta(minutes=minutes):
                    continue  # aún no toca según la cadencia del usuario
            try:
                n = run_search(ai)
            except Exception as exc:  # noqa: BLE001 - un feed que falle no aborta el resto
                self.stderr.write(f"[error] {ai.name}: {exc}")
                continue
            total += n
            self.stdout.write(f"{ai.name}: {n} propuestas nuevas")
        self.stdout.write(self.style.SUCCESS(f"Propuestas creadas: {total}"))
