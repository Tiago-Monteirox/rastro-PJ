import uuid

from django.db import models
from django.db.models import Q, Value

from apps.geography.models import GeographicScope


class HistoricalWindow(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        PREPARING = "PREPARING", "Em preparação"
        VALIDATED = "VALIDATED", "Validada"
        ACTIVE = "ACTIVE", "Ativa"
        SUPERSEDED = "SUPERSEDED", "Substituída"
        FAILED = "FAILED", "Falhou"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geographic_scope = models.ForeignKey(
        GeographicScope, on_delete=models.PROTECT, related_name="historical_windows"
    )
    code = models.CharField(max_length=80, unique=True)
    start_competence = models.DateField()
    end_competence = models.DateField()
    contract_version = models.CharField(max_length=20)
    cohort_hash = models.CharField(max_length=64, null=True, blank=True)
    manifest_hash = models.CharField(max_length=64, null=True, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "pipeline_historical_window"
        verbose_name = "janela histórica"
        verbose_name_plural = "janelas históricas"
        ordering = ("-start_competence",)
        constraints = [
            models.CheckConstraint(
                condition=Q(start_competence__lte=models.F("end_competence")),
                name="pipe_window_start_lte_end",
            ),
            models.UniqueConstraint(
                Value(1), condition=Q(status="ACTIVE"), name="pipe_one_active_window"
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status__in=("VALIDATED", "ACTIVE", "SUPERSEDED"))
                    | (
                        Q(cohort_hash__isnull=False)
                        & Q(manifest_hash__isnull=False)
                        & Q(cohort_hash__regex=r"^[0-9a-f]{64}$")
                        & Q(manifest_hash__regex=r"^[0-9a-f]{64}$")
                    )
                ),
                name="pipe_window_published_hashes",
            ),
        ]

    def __str__(self) -> str:
        return self.code


class WindowCompetence(models.Model):
    historical_window = models.ForeignKey(
        HistoricalWindow, on_delete=models.PROTECT, related_name="competences"
    )
    competence = models.DateField()
    position = models.PositiveSmallIntegerField()

    class Meta:
        db_table = "pipeline_window_competence"
        verbose_name = "competência da janela"
        verbose_name_plural = "competências da janela"
        ordering = ("historical_window", "position")
        constraints = [
            models.UniqueConstraint(
                fields=("historical_window", "competence"),
                name="pipe_window_competence_uniq",
            ),
            models.UniqueConstraint(
                fields=("historical_window", "position"), name="pipe_window_position_uniq"
            ),
        ]

    def __str__(self) -> str:
        return self.competence.strftime("%Y-%m")


class CompetenceRevision(models.Model):
    class Status(models.TextChoices):
        STAGING = "STAGING", "Em staging"
        PUBLISHED = "PUBLISHED", "Publicada"
        PUBLISHED_WITH_WARNINGS = "PUBLISHED_WITH_WARNINGS", "Publicada com alertas"
        SUPERSEDED = "SUPERSEDED", "Substituída"
        FAILED_QUALITY_GATE = "FAILED_QUALITY_GATE", "Reprovada na qualidade"
        FAILED = "FAILED", "Falhou"

    ACTIVE_STATUSES = (Status.PUBLISHED, Status.PUBLISHED_WITH_WARNINGS)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    window_competence = models.ForeignKey(
        WindowCompetence, on_delete=models.PROTECT, related_name="revisions"
    )
    revision_number = models.PositiveSmallIntegerField()
    package_hash = models.CharField(max_length=64)
    contract_version = models.CharField(max_length=20)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.STAGING)
    warning_count = models.PositiveIntegerField(default=0)
    row_counts = models.JSONField(default=dict)
    manifest = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "pipeline_competence_revision"
        verbose_name = "revisão de competência"
        verbose_name_plural = "revisões de competência"
        ordering = ("window_competence", "revision_number")
        constraints = [
            models.CheckConstraint(
                condition=Q(revision_number__gt=0), name="pipe_revision_number_gt_0"
            ),
            models.CheckConstraint(
                condition=Q(package_hash__regex=r"^[0-9a-f]{64}$"),
                name="pipe_revision_hash_sha256",
            ),
            models.UniqueConstraint(
                fields=("window_competence", "revision_number"),
                name="pipe_revision_number_uniq",
            ),
            models.UniqueConstraint(
                fields=("window_competence", "package_hash"),
                name="pipe_revision_package_uniq",
            ),
            models.UniqueConstraint(
                fields=("window_competence",),
                condition=Q(status__in=("PUBLISHED", "PUBLISHED_WITH_WARNINGS")),
                name="pipe_one_active_revision",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.window_competence} r{self.revision_number}"


class ImportBatch(models.Model):
    class Operation(models.TextChoices):
        PREPARE = "PREPARE", "Preparação"
        IMPORT = "IMPORT", "Importação"
        RECALCULATE = "RECALCULATE", "Recálculo"
        CLEANUP = "CLEANUP", "Limpeza"

    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "Recebido"
        VALIDATING = "VALIDATING", "Validando"
        LOADING = "LOADING", "Carregando"
        PUBLISHING = "PUBLISHING", "Publicando"
        COMPLETED = "COMPLETED", "Concluído"
        FAILED = "FAILED", "Falhou"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    competence_revision = models.ForeignKey(
        CompetenceRevision,
        on_delete=models.PROTECT,
        related_name="import_batches",
        null=True,
        blank=True,
    )
    operation = models.CharField(max_length=20, choices=Operation.choices)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.RECEIVED)
    phase = models.CharField(max_length=50, null=True, blank=True)
    counters = models.JSONField(default=dict)
    sanitized_options = models.JSONField(default=dict)
    error_code = models.CharField(max_length=80, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "pipeline_import_batch"
        verbose_name = "lote de processamento"
        verbose_name_plural = "lotes de processamento"
        ordering = ("-started_at",)
        indexes = [models.Index(fields=("status", "started_at"), name="pipe_batch_status_started")]

    def __str__(self) -> str:
        return f"{self.operation} {self.id}"


class SourceArtifact(models.Model):
    competence_revision = models.ForeignKey(
        CompetenceRevision, on_delete=models.PROTECT, related_name="source_artifacts"
    )
    source_type = models.CharField(max_length=40)
    source_url = models.URLField(max_length=1000)
    file_name = models.CharField(max_length=255)
    competence = models.DateField()
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    acquired_at = models.DateTimeField()

    class Meta:
        db_table = "pipeline_source_artifact"
        verbose_name = "artefato-fonte"
        verbose_name_plural = "artefatos-fonte"
        constraints = [
            models.UniqueConstraint(
                fields=("competence_revision", "source_type", "file_name"),
                name="pipe_source_artifact_uniq",
            ),
            models.CheckConstraint(
                condition=Q(sha256__regex=r"^[0-9a-f]{64}$"),
                name="pipe_source_hash_sha256",
            ),
        ]


class PackageArtifact(models.Model):
    class ArtifactType(models.TextChoices):
        MANIFEST = "MANIFEST", "Manifesto"
        COMPANIES = "COMPANIES", "Empresas"
        ESTABLISHMENTS = "ESTABLISHMENTS", "Estabelecimentos"
        PARTNERS = "PARTNERS", "Sócios"

    competence_revision = models.ForeignKey(
        CompetenceRevision, on_delete=models.PROTECT, related_name="package_artifacts"
    )
    artifact_type = models.CharField(max_length=20, choices=ArtifactType.choices)
    relative_path = models.CharField(max_length=500)
    sha256 = models.CharField(max_length=64)
    size_bytes = models.PositiveBigIntegerField()
    row_count = models.PositiveBigIntegerField()
    schema = models.JSONField(default=dict)

    class Meta:
        db_table = "pipeline_package_artifact"
        verbose_name = "artefato de pacote"
        verbose_name_plural = "artefatos de pacote"
        constraints = [
            models.UniqueConstraint(
                fields=("competence_revision", "artifact_type"),
                name="pipe_package_artifact_uniq",
            ),
            models.CheckConstraint(
                condition=Q(sha256__regex=r"^[0-9a-f]{64}$"),
                name="pipe_package_hash_sha256",
            ),
        ]


class DataQualityIssue(models.Model):
    class Severity(models.TextChoices):
        FATAL = "FATAL", "Fatal"
        WARNING = "WARNING", "Alerta"

    import_batch = models.ForeignKey(
        ImportBatch, on_delete=models.PROTECT, related_name="quality_issues"
    )
    competence_revision = models.ForeignKey(
        CompetenceRevision,
        on_delete=models.PROTECT,
        related_name="quality_issues",
        null=True,
        blank=True,
    )
    rule_code = models.CharField(max_length=80)
    severity = models.CharField(max_length=16, choices=Severity.choices)
    entity_type = models.CharField(max_length=24, null=True, blank=True)
    entity_key = models.CharField(max_length=80, null=True, blank=True)
    eligible_rows = models.BigIntegerField()
    affected_rows = models.BigIntegerField()
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pipeline_data_quality_issue"
        verbose_name = "ocorrência de qualidade"
        verbose_name_plural = "ocorrências de qualidade"
        indexes = [
            models.Index(
                fields=("import_batch", "severity", "rule_code"),
                name="pipe_dqi_batch_severity_rule",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(eligible_rows__gte=0), name="pipe_dqi_eligible_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(affected_rows__gte=0), name="pipe_dqi_affected_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(affected_rows__lte=models.F("eligible_rows")),
                name="pipe_dqi_affected_lte_eligible",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.severity}: {self.rule_code}"
