from pathlib import Path

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.geography.services import GeographicReferenceError, load_geographic_scope


class Command(BaseCommand):
    help = "Valida e carrega uma versão imutável do recorte geográfico."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("reference", type=Path, help="CSV com município, IBGE, TOM e UF.")
        parser.add_argument("--code", default="triangulo-mineiro-35")
        parser.add_argument("--name", default="Triângulo Mineiro — 35 municípios")
        parser.add_argument("--scope-version", type=int, default=1)
        parser.add_argument("--expected-count", type=int, default=35)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        try:
            result = load_geographic_scope(
                reference_path=options["reference"],
                code=options["code"],
                name=options["name"],
                version=options["scope_version"],
                expected_count=options["expected_count"],
                dry_run=options["dry_run"],
            )
        except GeographicReferenceError as exc:
            raise CommandError(str(exc)) from exc

        action = "validada" if result.dry_run else ("criada" if result.created else "confirmada")
        self.stdout.write(
            self.style.SUCCESS(
                f"Referência {action}: {result.municipality_count} municípios; "
                f"scope_hash={result.scope_hash}."
            )
        )
