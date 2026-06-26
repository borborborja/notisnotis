from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Orquesta el pipeline completo: fetch → embed → (enrich) → cluster → rate → analyze."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="limitar a un username donde aplique")
        parser.add_argument("--skip-fetch", action="store_true")

    def handle(self, *args, **opts):
        from features.modules import module_enabled

        user = opts.get("user")
        user_args = {"user": user} if user else {}
        # Módulos a nivel operador/default (los comandos por-usuario afinan por usuario).
        curation = module_enabled(None, "curation")
        podcasts = module_enabled(None, "podcasts")

        def run(cmd, **kw):
            self.stdout.write(self.style.MIGRATE_HEADING(f"→ {cmd}"))
            call_command(cmd, **kw)

        if not opts["skip_fetch"]:
            run("compute_intervals", **user_args)  # modo inteligente: ajusta cadencias
            run("fetch_feeds", **user_args)         # solo descarga feeds vencidos
            if curation:
                try:
                    run("run_aifeeds", **user_args)  # busca por web y propone (feeds con IA)
                except Exception as exc:  # noqa: BLE001 - el buscador no debe tumbar el pipeline
                    self.stderr.write(f"[aifeeds] {exc}")
        if curation:
            run("embed_articles", **user_args)
            run("enrich_articles", **user_args)  # solo enriquece usuarios en modo batch
            run("cluster_stories", **user_args)
            run("rate_sources")
        if podcasts:
            try:
                run("transcribe_episodes", limit=3)  # trickle: transcribir es lento
            except Exception as exc:  # noqa: BLE001 - no debe tumbar el pipeline
                self.stderr.write(f"[transcribe] {exc}")
        run("fetch_favicons", limit=25)  # trickle: evita bloquear el pipeline
        if curation:
            run("analyze_stories")
        self.stdout.write(self.style.SUCCESS("Pipeline completado."))
