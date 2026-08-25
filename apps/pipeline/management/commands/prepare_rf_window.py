from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.geography.models import GeographicScope, ScopeMunicipality
from apps.pipeline.services.municipality_catalog import MunicipalityCatalogError
from apps.pipeline.services.rf_prepare import ReceitaPreparationError, prepare_rf_window


class Command(BaseCommand):
    help = "Descobre a coorte regional e prepara pacotes Parquet de uma janela real."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--competence", action="append", required=True, dest="competences")
        parser.add_argument("--sources-root", type=Path, required=True)
        parser.add_argument("--output", type=Path, required=True)
        parser.add_argument("--work-root", type=Path, required=True)
        parser.add_argument("--scope-code", default="triangulo-mineiro-35")
        parser.add_argument("--scope-version", type=int, default=1)
        parser.add_argument("--window-code")
        parser.add_argument(
            "--resume",
            action="store_true",
            help="Retoma coorte e pacotes somente quando entradas e hashes ainda conferem.",
        )
        parser.add_argument(
            "--ibge-cache",
            type=Path,
            default=Path("var/data/reference/ibge-municipalities.json"),
        )

    def handle(self, *args, **options) -> None:
        try:
            scope = GeographicScope.objects.get(
                code=options["scope_code"], version=options["scope_version"]
            )
            tom_codes = set(
                ScopeMunicipality.objects.filter(scope=scope).values_list(
                    "municipality__tom_code", flat=True
                )
            )
            manifest = prepare_rf_window(
                competences=options["competences"],
                sources_root=options["sources_root"],
                output_root=options["output"],
                work_root=options["work_root"],
                scope_code=scope.code,
                scope_version=scope.version,
                scope_hash=scope.scope_hash,
                scope_tom_codes=tom_codes,
                partner_hmac_secret=settings.RF_PARTNER_HMAC_SECRET,
                ibge_cache_path=options["ibge_cache"],
                window_code=options["window_code"],
                progress=self.stdout.write,
                resume=options["resume"],
            )
        except (
            GeographicScope.DoesNotExist,
            MunicipalityCatalogError,
            ReceitaPreparationError,
        ) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Janela preparada: {manifest}."))
