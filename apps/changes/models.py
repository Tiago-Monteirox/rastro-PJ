import uuid

from django.db import models
from django.db.models import F, Q

from apps.geography.models import Municipality
from apps.pipeline.models import CompetenceRevision, HistoricalWindow, ImportBatch
from apps.registry.models import Company, Establishment, PartnerParticipation


class ChangeEvent(models.Model):
    class EntityType(models.TextChoices):
        COMPANY = "COMPANY", "Empresa"
        ESTABLISHMENT = "ESTABLISHMENT", "Estabelecimento"
        PARTICIPATION = "PARTICIPATION", "Participação societária"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_key = models.CharField(max_length=64, unique=True)
    historical_window = models.ForeignKey(
        HistoricalWindow, on_delete=models.PROTECT, related_name="change_events"
    )
    from_revision = models.ForeignKey(
        CompetenceRevision, on_delete=models.PROTECT, related_name="outgoing_change_events"
    )
    to_revision = models.ForeignKey(
        CompetenceRevision, on_delete=models.PROTECT, related_name="incoming_change_events"
    )
    entity_type = models.CharField(max_length=24, choices=EntityType.choices)
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="change_events", null=True, blank=True
    )
    establishment = models.ForeignKey(
        Establishment,
        on_delete=models.PROTECT,
        related_name="change_events",
        null=True,
        blank=True,
    )
    participation = models.ForeignKey(
        PartnerParticipation,
        on_delete=models.PROTECT,
        related_name="change_events",
        null=True,
        blank=True,
    )
    dimension = models.CharField(max_length=40)
    event_type = models.CharField(max_length=60)
    previous_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    source_effective_date = models.DateField(null=True, blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)
    import_batch = models.ForeignKey(
        ImportBatch, on_delete=models.PROTECT, related_name="change_events"
    )

    class Meta:
        db_table = "changes_change_event"
        verbose_name = "evento de mudança"
        verbose_name_plural = "eventos de mudança"
        ordering = ("-detected_at",)
        constraints = [
            models.CheckConstraint(
                condition=Q(event_key__regex=r"^[0-9a-f]{64}$"),
                name="chg_event_key_sha256",
            ),
            models.CheckConstraint(
                condition=(
                    Q(company__isnull=False, establishment__isnull=True, participation__isnull=True)
                    | Q(
                        company__isnull=True,
                        establishment__isnull=False,
                        participation__isnull=True,
                    )
                    | Q(
                        company__isnull=True,
                        establishment__isnull=True,
                        participation__isnull=False,
                    )
                ),
                name="chg_event_exactly_one_target",
            ),
            models.CheckConstraint(
                condition=~Q(from_revision=F("to_revision")),
                name="chg_event_distinct_revisions",
            ),
        ]
        indexes = [
            models.Index(fields=("to_revision", "event_type"), name="chg_event_to_type"),
            models.Index(fields=("from_revision",), name="chg_event_from_revision"),
            models.Index(fields=("company",), name="chg_event_company"),
            models.Index(fields=("establishment",), name="chg_event_establishment"),
            models.Index(fields=("participation",), name="chg_event_participation"),
        ]

    def __str__(self) -> str:
        return f"{self.event_type}: {self.event_key[:12]}"


class RegionalMonthlyMetric(models.Model):
    class EntityType(models.TextChoices):
        COMPANY = "COMPANY", "Empresa"
        ESTABLISHMENT = "ESTABLISHMENT", "Estabelecimento"

    metric_key = models.CharField(max_length=64, unique=True)
    revision = models.ForeignKey(
        CompetenceRevision, on_delete=models.PROTECT, related_name="regional_metrics"
    )
    metric_type = models.CharField(max_length=60)
    entity_type = models.CharField(max_length=24, choices=EntityType.choices)
    municipality = models.ForeignKey(
        Municipality,
        on_delete=models.PROTECT,
        related_name="regional_metrics",
        null=True,
        blank=True,
    )
    cnae_code = models.CharField(max_length=7, null=True, blank=True)
    registration_status_code = models.CharField(max_length=2, null=True, blank=True)
    company_size_code = models.CharField(max_length=2, null=True, blank=True)
    extra_dimensions = models.JSONField(default=dict)
    value = models.BigIntegerField()

    class Meta:
        db_table = "changes_regional_monthly_metric"
        verbose_name = "métrica regional mensal"
        verbose_name_plural = "métricas regionais mensais"
        constraints = [
            models.CheckConstraint(
                condition=Q(metric_key__regex=r"^[0-9a-f]{64}$"),
                name="chg_metric_key_sha256",
            ),
            models.CheckConstraint(condition=Q(value__gte=0), name="chg_metric_nonnegative"),
        ]
        indexes = [
            models.Index(fields=("revision", "metric_type"), name="chg_metric_revision_type")
        ]

    def __str__(self) -> str:
        return f"{self.metric_type}: {self.value}"
