from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from notifications.config import DIGEST
from notifications.digest import send_digest_to


class Command(BaseCommand):
    help = "Envía el digest por email a los usuarios suscritos (operador lo programa por cron)."

    def add_arguments(self, parser):
        parser.add_argument("--frequency", choices=["daily", "weekly"], default="daily")
        parser.add_argument("--user", help="limitar a un username")
        parser.add_argument("--dry-run", action="store_true", help="no envía; solo cuenta")

    def handle(self, *args, **opts):
        if not DIGEST.enabled():
            self.stdout.write(self.style.WARNING("DIGEST_ENABLED está desactivado en .env."))
            return
        users = get_user_model().objects.all()
        if opts.get("user"):
            users = users.filter(username=opts["user"])
        sent, skipped = 0, {}
        for user in users:
            result = send_digest_to(user, opts["frequency"], dry_run=opts["dry_run"])
            if result == "sent":
                sent += 1
            else:
                skipped[result] = skipped.get(result, 0) + 1
        self.stdout.write(self.style.SUCCESS(f"Enviados: {sent} | omitidos: {skipped}"))
