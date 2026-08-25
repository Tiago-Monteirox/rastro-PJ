from pathlib import Path

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.geography.models import GeographicScope
from apps.pipeline.services.synthetic_window import generate_synthetic_window


class Command(BaseCommand):
    help = "Gera a janela sintética G2 com dois pacotes tipados e sem dados pessoais."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("output_directory", type=Path)
        parser.add_argument("--scope-code", default="triangulo-mineiro-35")
        parser.add_argument("--scope-version", type=int, default=1)

    def handle(self, *args, **options):
        try:
            scope = GeographicScope.objects.get(
                code=options["scope_code"], version=options["scope_version"]
            )
        except GeographicScope.DoesNotExist as exc:
            raise CommandError("Recorte geográfico não carregado.") from exc

        manifest_path = generate_synthetic_window(
            output_directory=options["output_directory"],
            scope_code=scope.code,
            scope_version=scope.version,
            scope_hash=scope.scope_hash,
        )
        self.stdout.write(self.style.SUCCESS(f"Janela sintética gerada: {manifest_path}"))
