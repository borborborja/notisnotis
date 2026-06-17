import base64

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.management.base import BaseCommand

from feeds.models import Source

MAX_BYTES = 30000


class Command(BaseCommand):
    help = "Descarga y cachea el favicon de cada fuente como data URI."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="re-descargar también las que ya tienen")
        parser.add_argument("--limit", type=int, default=0, help="máx. fuentes por ejecución (0 = todas)")

    def handle(self, *args, **opts):
        qs = Source.objects.all() if opts["all"] else Source.objects.filter(favicon="")
        if opts["limit"]:
            qs = qs[: opts["limit"]]
        done = 0
        for source in qs:
            data_uri = self._fetch(source.domain)
            if data_uri:
                source.favicon = data_uri
                source.save(update_fields=["favicon"])
                done += 1
        self.stdout.write(self.style.SUCCESS(f"Favicons obtenidos: {done}"))

    def _fetch(self, domain):
        headers = {"User-Agent": settings.RSS_USER_AGENT}
        base = f"https://{domain}"
        icon_url = None
        # 1) busca <link rel="icon"> en la home
        try:
            html = requests.get(base, headers=headers, timeout=15).text
            soup = BeautifulSoup(html, "html.parser")
            link = soup.find("link", rel=lambda v: v and "icon" in v.lower())
            if link and link.get("href"):
                href = link["href"]
                if href.startswith("//"):
                    href = "https:" + href
                elif href.startswith("/"):
                    href = base + href
                elif not href.startswith("http"):
                    href = base + "/" + href
                icon_url = href
        except Exception:  # noqa: BLE001
            pass
        # 2) fallback /favicon.ico
        for candidate in filter(None, [icon_url, f"{base}/favicon.ico"]):
            try:
                resp = requests.get(candidate, headers=headers, timeout=15)
                if resp.status_code == 200 and resp.content and len(resp.content) <= MAX_BYTES:
                    ctype = resp.headers.get("Content-Type", "image/x-icon").split(";")[0]
                    if "image" not in ctype:
                        ctype = "image/x-icon"
                    b64 = base64.b64encode(resp.content).decode()
                    return f"data:{ctype};base64,{b64}"
            except Exception:  # noqa: BLE001
                continue
        return None
