from django.core.management.base import BaseCommand, CommandError

from apps.pipeline.services.rf_sources import ReceitaSourceError, inventory_competence


class Command(BaseCommand):
    help = "Inventaria os ZIPs oficiais necessários para uma competência da Receita Federal."

    def add_arguments(self, parser) -> None:
        parser.add_argument("competence")

    def handle(self, *args, **options) -> None:
        try:
            files = inventory_competence(options["competence"])
        except ReceitaSourceError as exc:
            raise CommandError(str(exc)) from exc
        total = sum(item.size_bytes for item in files)
        self.stdout.write(
            self.style.SUCCESS(
                f"Inventário válido: competência={options['competence']}; "
                f"arquivos={len(files)}; bytes={total}."
            )
        )
        if options["verbosity"] >= 2:
            for item in files:
                self.stdout.write(f"{item.file_name}\t{item.size_bytes}")
