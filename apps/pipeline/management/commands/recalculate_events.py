from django.core.management.base import BaseCommand, CommandError

from apps.pipeline.models import HistoricalWindow
from apps.pipeline.services import recalculate_window_events


class Command(BaseCommand):
    help = "Recalcula deterministicamente os eventos da janela histórica ativa."

    def handle(self, *args, **options) -> None:
        window = HistoricalWindow.objects.filter(status=HistoricalWindow.Status.ACTIVE).first()
        if not window:
            raise CommandError("Não há janela ativa.")
        count = recalculate_window_events(window)
        self.stdout.write(self.style.SUCCESS(f"Eventos recalculados: {count}."))
