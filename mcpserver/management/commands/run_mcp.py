import sys

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Arranca el servidor MCP de facet.news (requiere Python >= 3.10 y el paquete mcp)."

    def add_arguments(self, parser):
        parser.add_argument("--http", action="store_true", help="transporte HTTP/SSE en vez de stdio")
        parser.add_argument("--host", default="0.0.0.0")
        parser.add_argument("--port", type=int, default=8765)

    def handle(self, *args, **opts):
        if sys.version_info < (3, 10):
            raise CommandError(
                "El servidor MCP requiere Python >= 3.10 (usa la imagen Docker). "
                f"Versión actual: {sys.version.split()[0]}."
            )
        try:
            from mcpserver.server import build_server
        except ImportError as exc:
            raise CommandError(f"Falta el paquete 'mcp': pip install mcp ({exc}).") from exc

        server = build_server()
        if opts["http"]:
            server.settings.host = opts["host"]
            server.settings.port = opts["port"]
            self.stdout.write(self.style.SUCCESS(f"MCP HTTP en {opts['host']}:{opts['port']}"))
            server.run(transport="sse")
        else:
            self.stderr.write("MCP en stdio. Conéctalo desde tu cliente (Claude Desktop).\n")
            server.run(transport="stdio")
