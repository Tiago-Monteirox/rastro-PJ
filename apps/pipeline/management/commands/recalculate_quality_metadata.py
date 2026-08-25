from django.core.management.base import BaseCommand, CommandError

from apps.pipeline.models import HistoricalWindow
from apps.pipeline.services import recalculate_quality_metadata


class Command(BaseCommand):
    help = "Recalcula elegibilidade, volume afetado e limite dos alertas da janela ativa."

    def handle(self, *args, **options) -> None:
        window = HistoricalWindow.objects.filter(status=HistoricalWindow.Status.ACTIVE).first()
        if not window:
            raise CommandError("Não há janela ativa.")
        count, batch_id = recalculate_quality_metadata(window)
        self.stdout.write(
            self.style.SUCCESS(
                f"Metadados de qualidade recalculados: ocorrências={count}; batch={batch_id}."
            )
        )
