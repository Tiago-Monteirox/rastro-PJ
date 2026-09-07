from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.cartography.services.projection import (
    ProjectionPreparationError,
    prepare_cartographic_projection,
)
from apps.cartography.services.sources import CartographicSourceError


class Command(BaseCommand):
    help = "Prepara, valida e publica a projeção cartográfica da janela histórica ativa."

    def add_arguments(self, parser):
        parser.add_argument("cnefe_directory", type=Path)
        parser.add_argument(
            "--boundary-directory",
            type=Path,
            default=settings.BASE_DIR / "var/data/cartography/ibge-boundaries-2022",
        )
        parser.add_argument("--window", default="")
        parser.add_argument("--cnefe-version", default="2022")
        parser.add_argument("--boundary-version", default="2022-minima")
        parser.add_argument("--download-missing-boundaries", action="store_true")
        parser.add_argument("--approve-coverage-drop", action="store_true")

    def handle(self, *args, **options):
        try:
            result = prepare_cartographic_projection(
                cnefe_directory=options["cnefe_directory"],
                boundary_directory=options["boundary_directory"],
                window_code=options["window"],
                cnefe_version=options["cnefe_version"],
                boundary_version=options["boundary_version"],
                download_missing_boundaries=options["download_missing_boundaries"],
                approve_coverage_drop=options["approve_coverage_drop"],
                progress=self.stdout.write,
            )
        except (ProjectionPreparationError, CartographicSourceError) as exc:
            raise CommandError(str(exc)) from exc

        projection = result.projection
        if result.already_published:
            self.stdout.write(
                self.style.WARNING(
                    f"Projeção {projection.pk} já estava publicada; nenhuma escrita necessária."
                )
            )
            return
        coverage = projection.quality_report["totals"]["coverage"] * 100
        self.stdout.write(
            self.style.SUCCESS(
                f"Projeção {projection.pk} publicada: {projection.eligible_count:,} ocorrências; "
                f"cobertura={coverage:.2f}%."
            )
        )
