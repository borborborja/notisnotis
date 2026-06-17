from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from aiproviders.client import get_chat_client
from feeds.models import Bias, Source

VALID_BIAS = {b.value for b in Bias}

PROMPT = (
    "Eres un analista de medios. Estima la orientación política editorial y la "
    "fiabilidad factual del medio indicado. Responde SOLO con JSON: "
    '{{"bias": "left|lean_left|center|lean_right|right", '
    '"factuality": "high|mixed|low", "reasoning": "una frase"}}.\n\n'
    "Medio: {name}\nDominio: {domain}"
)


class Command(BaseCommand):
    help = (
        "Estima el sesgo de fuentes sin valorar. La fuente es global; se valora con el "
        "cliente del primer usuario que la tenga en sus feeds (su API key)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="re-evaluar las valoradas por LLM")

    def _rate(self, source, client):
        messages = [
            {"role": "system", "content": "Devuelve únicamente JSON válido."},
            {"role": "user", "content": PROMPT.format(name=source.name, domain=source.domain)},
        ]
        data = client.chat(messages, json=True)
        bias = data.get("bias", "unknown")
        source.bias = bias if bias in VALID_BIAS else Bias.UNKNOWN
        source.factuality = (data.get("factuality") or "")[:64]
        source.bias_reasoning = (data.get("reasoning") or "")[:1000]
        source.bias_source = "llm"
        source.save(update_fields=["bias", "factuality", "bias_reasoning", "bias_source"])

    def handle(self, *args, **opts):
        User = get_user_model()
        rated = 0
        # Recorre usuarios para usar la API key de cada uno sobre las fuentes de sus feeds.
        for user in User.objects.all():
            sources = Source.objects.filter(feeds__user=user).distinct()
            if not opts["all"]:
                sources = sources.filter(bias=Bias.UNKNOWN)
            else:
                sources = sources.exclude(bias_source="manual")
            if not sources:
                continue
            client = get_chat_client(user)
            for source in sources:
                # Re-comprueba por si otro usuario ya la valoró en esta misma pasada.
                source.refresh_from_db()
                if not opts["all"] and source.bias != Bias.UNKNOWN:
                    continue
                if source.bias_source == "manual":
                    continue
                try:
                    self._rate(source, client)
                    rated += 1
                except Exception as exc:  # noqa: BLE001
                    self.stderr.write(f"[error] {source.domain}: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Fuentes valoradas: {rated}"))
