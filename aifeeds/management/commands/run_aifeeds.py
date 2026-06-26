from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Busca por internet y propone noticias para los feeds con IA (incremental)."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="limitar a un username")
        parser.add_argument("--feed", type=int, help="id de un AIFeed concreto")

    def handle(self, *args, **opts):
        from aifeeds.models import AIFeed
        from aifeeds.services import run_search

        qs = AIFeed.objects.filter(enabled=True).select_related("user")
        if opts.get("user"):
            qs = qs.filter(user__username=opts["user"])
        if opts.get("feed"):
            qs = qs.filter(pk=opts["feed"])

        total = 0
        for ai in qs:
            try:
                n = run_search(ai)
            except Exception as exc:  # noqa: BLE001 - un feed que falle no aborta el resto
                self.stderr.write(f"[error] {ai.name}: {exc}")
                continue
            total += n
            self.stdout.write(f"{ai.name}: {n} propuestas nuevas")
        self.stdout.write(self.style.SUCCESS(f"Propuestas creadas: {total}"))
