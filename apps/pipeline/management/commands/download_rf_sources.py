from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.pipeline.services.rf_sources import ReceitaSourceError, download_competence


class Command(BaseCommand):
    help = "Baixa com retomada os ZIPs oficiais necessários para uma competência."

    def add_arguments(self, parser) -> None:
        parser.add_argument("competence")
        parser.add_argument("destination", type=Path)
        parser.add_argument("--reserve-gib", type=int, default=20)
        parser.add_argument("--workers", type=int, default=4)

    def handle(self, *args, **options) -> None:
        try:
            downloaded = download_competence(
                options["competence"],
                destination_root=options["destination"],
                reserve_bytes=options["reserve_gib"] * 1024**3,
                workers=options["workers"],
            )
        except ReceitaSourceError as exc:
            raise CommandError(str(exc)) from exc
        total = sum(item.remote.size_bytes for item in downloaded)
        self.stdout.write(
            self.style.SUCCESS(
                f"Fontes verificadas: competência={options['competence']}; "
                f"arquivos={len(downloaded)}; bytes={total}."
            )
        )
