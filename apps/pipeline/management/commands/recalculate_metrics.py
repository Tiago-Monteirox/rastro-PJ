from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.changes.models import RegionalMonthlyMetric
from apps.pipeline.models import CompetenceRevision, HistoricalWindow
from apps.pipeline.services import persist_revision_metrics


class Command(BaseCommand):
    help = "Recalcula as métricas derivadas da janela histórica ativa."

    def handle(self, *args, **options) -> None:
        window = HistoricalWindow.objects.filter(status=HistoricalWindow.Status.ACTIVE).first()
        if not window:
            raise CommandError("Não há janela ativa.")
        revisions = list(
            CompetenceRevision.objects.filter(
                window_competence__historical_window=window,
                status__in=CompetenceRevision.ACTIVE_STATUSES,
            ).order_by("window_competence__competence")
        )
        with transaction.atomic():
            RegionalMonthlyMetric.objects.filter(revision__in=revisions).delete()
            for revision in revisions:
                persist_revision_metrics(revision)
        self.stdout.write(
            self.style.SUCCESS(
                f"Métricas recalculadas: competências={len(revisions)}; "
                f"linhas={RegionalMonthlyMetric.objects.filter(revision__in=revisions).count()}."
            )
        )
