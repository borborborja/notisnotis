import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Importa un backup de AntennaPod (export de base de datos .db) para un usuario."

    def add_arguments(self, parser):
        parser.add_argument("db_path", help="ruta al fichero .db de AntennaPod")
        parser.add_argument("--user", required=True, help="username destino")

    def handle(self, *args, **opts):
        from podcasts.antennapod import import_backup

        path = opts["db_path"]
        if not os.path.exists(path):
            raise CommandError(f"No existe el fichero: {path}")
        try:
            user = get_user_model().objects.get(username=opts["user"])
        except get_user_model().DoesNotExist:
            raise CommandError(f"Usuario desconocido: {opts['user']}")

        self.stdout.write(f"Importando {path} para {user.username}…")
        counts = import_backup(user, path)
        self.stdout.write(self.style.SUCCESS(
            "Importado: " + ", ".join(f"{k}={v}" for k, v in counts.items())
        ))
