from django.core.management.base import BaseCommand

from aiproviders.client import get_chat_client
from stories.analysis import analyze_story
from stories.models import Story


class Command(BaseCommand):
    help = "Analiza historias 'dirty' (sesgo, blindspot, resúmenes) con el cliente del propietario."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="re-analizar todas, no solo dirty")
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **opts):
        qs = Story.objects.all() if opts["all"] else Story.objects.filter(dirty=True)
        qs = qs.select_related("user").order_by("-last_updated")
        if opts["limit"]:
            qs = qs[: opts["limit"]]
        from features.modules import module_enabled

        clients = {}
        done = 0
        for story in qs:
            if not module_enabled(story.user, "curation"):
                continue
            client = clients.get(story.user_id)
            if client is None:
                client = clients[story.user_id] = get_chat_client(story.user)
            try:
                analyze_story(story, client=client)
                done += 1
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f"[error] historia {story.id}: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Historias analizadas: {done}"))
