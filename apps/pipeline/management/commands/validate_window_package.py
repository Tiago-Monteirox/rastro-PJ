from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.pipeline.contracts import ContractError, ManifestError
from apps.pipeline.services import validate_window_package


class Command(BaseCommand):
    help = "Valida uma janela preparada, seus manifestos e artefatos Parquet."

    def add_arguments(self, parser) -> None:
        parser.add_argument("manifest", type=Path)

    def handle(self, *args, **options) -> None:
        try:
            validated = validate_window_package(options["manifest"])
        except (ContractError, ManifestError, OSError) as exc:
            raise CommandError(str(exc)) from exc

        row_counts = {name: 0 for name in ("companies", "establishments", "partners")}
        for package in validated.packages:
            for name, artifact in package.artifacts.items():
                row_counts[name] += artifact.validation.row_count
        self.stdout.write(
            self.style.SUCCESS(
                f"Janela válida: {validated.manifest.window_code}; "
                f"{len(validated.packages)} competência(s); linhas={row_counts}."
            )
        )
