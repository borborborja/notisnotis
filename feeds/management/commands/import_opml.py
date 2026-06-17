from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from feeds.opml import import_opml_for_user


class Command(BaseCommand):
    help = "Importa un archivo OPML para un usuario."

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True, help="username del propietario")
        parser.add_argument("--file", required=True, help="ruta al .opml")

    def handle(self, *args, **opts):
        User = get_user_model()
        try:
            user = User.objects.get(username=opts["user"])
        except User.DoesNotExist as exc:
            raise CommandError(f"Usuario '{opts['user']}' no existe.") from exc
        with open(opts["file"], "r", encoding="utf-8") as fh:
            content = fh.read()
        created, skipped = import_opml_for_user(user, content)
        self.stdout.write(self.style.SUCCESS(f"{created} feeds nuevos, {skipped} existentes."))
