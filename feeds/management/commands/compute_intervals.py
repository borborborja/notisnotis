from django.core.management.base import BaseCommand

from feeds.intervals import update_auto_intervals
from feeds.models import Feed


class Command(BaseCommand):
    help = "Recalcula la cadencia de los feeds en modo inteligente según su frecuencia de publicación."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="limitar a un username")

    def handle(self, *args, **opts):
        feeds = Feed.objects.filter(enabled=True, auto_interval=True)
        if opts.get("user"):
            feeds = feeds.filter(user__username=opts["user"])
        updated = update_auto_intervals(feeds)
        self.stdout.write(self.style.SUCCESS(f"Cadencias actualizadas: {updated}"))
