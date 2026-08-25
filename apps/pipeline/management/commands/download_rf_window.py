from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.pipeline.services.rf_sources import ReceitaSourceError, download_competence


class Command(BaseCommand):
    help = "Baixa, em sequência e com retomada, as fontes de várias competências."

    def add_arguments(self, parser) -> None:
        parser.add_argument("destination", type=Path)
        parser.add_argument("--competence", action="append", required=True)
        parser.add_argument("--reserve-gib", type=int, default=20)
        parser.add_argument("--workers", type=int, default=4)

    def handle(self, *args, **options) -> None:
        competences = options["competence"]
        if len(competences) != len(set(competences)):
            raise CommandError("Não repita competências na mesma janela de download.")

        total_bytes = 0
        total_files = 0
        for position, competence in enumerate(competences, start=1):
            self.stdout.write(
                f"[{position}/{len(competences)}] Verificando competência {competence}..."
            )
            try:
                downloaded = download_competence(
                    competence,
                    destination_root=options["destination"],
                    reserve_bytes=options["reserve_gib"] * 1024**3,
                    workers=options["workers"],
                )
            except ReceitaSourceError as exc:
                raise CommandError(f"Competência {competence}: {exc}") from exc
            competence_bytes = sum(item.remote.size_bytes for item in downloaded)
            total_bytes += competence_bytes
            total_files += len(downloaded)
            self.stdout.write(
                self.style.SUCCESS(
                    f"[{position}/{len(competences)}] {competence}: "
                    f"arquivos={len(downloaded)}; bytes={competence_bytes}."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Janela verificada: competências={len(competences)}; "
                f"arquivos={total_files}; bytes={total_bytes}."
            )
        )
