from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q


class Command(BaseCommand):
    help = "Rellena la portada (image_url) de podcasts vacíos usando el arte de sus episodios."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="limitar a un username")

    def handle(self, *args, **opts):
        from feeds.models import Feed

        feeds = Feed.objects.filter(kind__in=["podcast", "youtube"]).filter(
            Q(image_url="") | Q(image_url__isnull=True))
        if opts.get("user"):
            feeds = feeds.filter(user__username=opts["user"])

        done = 0
        for feed in feeds:
            art = (feed.articles.exclude(image_url="").order_by("-published_at")
                   .values_list("image_url", flat=True).first())
            if art:
                feed.image_url = art[:1000]
                feed.save(update_fields=["image_url"])
                done += 1
        self.stdout.write(self.style.SUCCESS(f"Portadas rellenadas: {done}"))
