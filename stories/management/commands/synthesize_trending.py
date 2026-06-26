from django.core.management.base import BaseCommand
from django.db.models import Count


class Command(BaseCommand):
    help = "Redacta la noticia contrastada de las historias de tendencia multi-fuente (acotado)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=8, help="máx. síntesis por pasada")

    def handle(self, *args, **opts):
        from stories.models import Story
        from stories.synthesis import generate_synthesis
        from stories.trending import COUNTRIES, trending_user

        users = [trending_user(c[0]) for c in COUNTRIES]
        qs = (Story.objects.filter(user__in=users, synthesized_at__isnull=True)
              .annotate(n=Count("story_articles")).filter(n__gte=2)
              .order_by("-n", "-last_updated")[: opts["limit"]])
        done = 0
        for story in qs:
            try:
                generate_synthesis(story)
                done += 1
            except Exception as exc:  # noqa: BLE001 - una que falle no aborta el resto
                self.stderr.write(f"[error] {story.pk}: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Síntesis de tendencias: {done}"))
