from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.pipeline.contracts import ContractError, ManifestError
from apps.pipeline.services import import_window_package
from apps.pipeline.services.window_import import WindowImportError


class Command(BaseCommand):
    help = "Valida, importa e publica atomicamente uma janela histórica preparada."

    def add_arguments(self, parser) -> None:
        parser.add_argument("manifest", type=Path)
        parser.add_argument(
            "--allow-revision",
            action="store_true",
            help="Autoriza substituir atomicamente competências com hash diferente.",
        )

    def handle(self, *args, **options) -> None:
        try:
            result = import_window_package(
                options["manifest"],
                allow_revision=options["allow_revision"],
            )
        except (ContractError, ManifestError, WindowImportError, OSError) as exc:
            raise CommandError(str(exc)) from exc

        if result.revised_competences:
            action = f"revisada ({', '.join(result.revised_competences)})"
        else:
            action = "publicada" if result.imported else "já estava publicada; no-op"
        self.stdout.write(
            self.style.SUCCESS(
                f"Janela {result.window.code} {action}; "
                f"competências={result.competence_count}; eventos={result.event_count}; "
                f"alertas={result.warning_count}; batch={result.batch_id}."
            )
        )
