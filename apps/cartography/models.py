import uuid

from django.db import models
from django.db.models import Q

from apps.geography.models import Municipality
from apps.pipeline.models import CompetenceRevision, HistoricalWindow
from apps.registry.models import Company, Establishment


class GeographicSource(models.Model):
    class Kind(models.TextChoices):
        CNEFE = "CNEFE", "CNEFE"
        MUNICIPAL_BOUNDARIES = "MUNICIPAL_BOUNDARIES", "Malha municipal"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=32, choices=Kind.choices)
    version = models.CharField(max_length=40)
    content_hash = models.CharField(max_length=64)
    manifest = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cartography_geographic_source"
        verbose_name = "fonte geográfica"
        verbose_name_plural = "fontes geográficas"
        ordering = ("kind", "-created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("kind", "version", "content_hash"),
                name="cart_source_kind_ver_hash_uniq",
            ),
            models.CheckConstraint(
                condition=Q(content_hash__regex=r"^[0-9a-f]{64}$"),
                name="cart_source_hash_sha256",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.version}"


class MunicipalityBoundary(models.Model):
    source = models.ForeignKey(
        GeographicSource, on_delete=models.PROTECT, related_name="municipality_boundaries"
    )
    municipality = models.ForeignKey(
        Municipality, on_delete=models.PROTECT, related_name="cartographic_boundaries"
    )
    geometry = models.JSONField()
    bbox = models.JSONField(default=list)
    center_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    center_longitude = models.DecimalField(max_digits=10, decimal_places=6)

    class Meta:
        db_table = "cartography_municipality_boundary"
        verbose_name = "limite municipal"
        verbose_name_plural = "limites municipais"
        ordering = ("municipality__name",)
        constraints = [
            models.UniqueConstraint(
                fields=("source", "municipality"), name="cart_boundary_source_city_uniq"
            ),
            models.CheckConstraint(
                condition=Q(center_latitude__gte=-90) & Q(center_latitude__lte=90),
                name="cart_boundary_lat_range",
            ),
            models.CheckConstraint(
                condition=Q(center_longitude__gte=-180) & Q(center_longitude__lte=180),
                name="cart_boundary_lng_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.municipality} — {self.source.version}"


class AddressResolution(models.Model):
    class Method(models.TextChoices):
        ADDRESS = "ADDRESS", "Endereço CNEFE"
        POSTAL_CODE = "POSTAL_CODE", "Aproximação por CEP"
        UNLOCATED = "UNLOCATED", "Não localizado"

    source = models.ForeignKey(
        GeographicSource, on_delete=models.PROTECT, related_name="address_resolutions"
    )
    municipality = models.ForeignKey(
        Municipality, on_delete=models.PROTECT, related_name="address_resolutions"
    )
    algorithm_version = models.CharField(max_length=20, default="1.0.0")
    fingerprint = models.CharField(max_length=64)
    postal_code = models.CharField(max_length=8, blank=True)
    normalized_street = models.CharField(max_length=300, blank=True)
    normalized_number = models.CharField(max_length=40, blank=True)
    method = models.CharField(max_length=16, choices=Method.choices)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    cnefe_level = models.PositiveSmallIntegerField(null=True, blank=True)
    cnefe_address_code = models.CharField(max_length=40, blank=True)
    candidate_count = models.PositiveIntegerField(default=0)
    dispersion_meters = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    reason = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cartography_address_resolution"
        verbose_name = "resolução de endereço"
        verbose_name_plural = "resoluções de endereço"
        constraints = [
            models.UniqueConstraint(
                fields=("source", "municipality", "algorithm_version", "fingerprint"),
                name="cart_resolution_source_city_fp_uniq",
            ),
            models.CheckConstraint(
                condition=Q(fingerprint__regex=r"^[0-9a-f]{64}$"),
                name="cart_resolution_fp_sha256",
            ),
            models.CheckConstraint(
                condition=(Q(latitude__isnull=True) & Q(longitude__isnull=True))
                | (Q(latitude__isnull=False) & Q(longitude__isnull=False)),
                name="cart_resolution_coord_pair",
            ),
            models.CheckConstraint(
                condition=Q(latitude__isnull=True) | (Q(latitude__gte=-90) & Q(latitude__lte=90)),
                name="cart_resolution_lat_range",
            ),
            models.CheckConstraint(
                condition=Q(longitude__isnull=True)
                | (Q(longitude__gte=-180) & Q(longitude__lte=180)),
                name="cart_resolution_lng_range",
            ),
            models.CheckConstraint(
                condition=Q(cnefe_level__isnull=True)
                | (Q(cnefe_level__gte=1) & Q(cnefe_level__lte=6)),
                name="cart_resolution_level_range",
            ),
        ]
        indexes = [
            models.Index(
                fields=("source", "algorithm_version", "municipality", "postal_code"),
                name="cart_res_src_city_cep",
            ),
            models.Index(fields=("source", "method"), name="cart_res_source_method"),
        ]

    def __str__(self) -> str:
        identity = f"{self.municipality.ibge_code}:{self.fingerprint[:10]}"
        return f"{identity} — {self.get_method_display()}"


class CartographicProjection(models.Model):
    class Status(models.TextChoices):
        PREPARING = "PREPARING", "Em preparação"
        PUBLISHED = "PUBLISHED", "Publicada"
        SUPERSEDED = "SUPERSEDED", "Substituída"
        FAILED_QUALITY_GATE = "FAILED_QUALITY_GATE", "Reprovada na qualidade"
        FAILED = "FAILED", "Falhou"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    historical_window = models.ForeignKey(
        HistoricalWindow, on_delete=models.PROTECT, related_name="cartographic_projections"
    )
    cnefe_source = models.ForeignKey(
        GeographicSource, on_delete=models.PROTECT, related_name="cnefe_projections"
    )
    boundary_source = models.ForeignKey(
        GeographicSource, on_delete=models.PROTECT, related_name="boundary_projections"
    )
    registry_manifest_hash = models.CharField(max_length=64)
    algorithm_version = models.CharField(max_length=20, default="1.0.0")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PREPARING)
    quality_report = models.JSONField(default=dict)
    eligible_count = models.PositiveBigIntegerField(default=0)
    located_count = models.PositiveBigIntegerField(default=0)
    address_count = models.PositiveBigIntegerField(default=0)
    postal_code_count = models.PositiveBigIntegerField(default=0)
    unlocated_count = models.PositiveBigIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "cartography_projection"
        verbose_name = "projeção cartográfica"
        verbose_name_plural = "projeções cartográficas"
        ordering = ("-started_at",)
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "historical_window",
                    "cnefe_source",
                    "boundary_source",
                    "registry_manifest_hash",
                    "algorithm_version",
                ),
                name="cart_projection_inputs_uniq",
            ),
            models.UniqueConstraint(
                fields=("historical_window",),
                condition=Q(status="PUBLISHED"),
                name="cart_one_published_projection",
            ),
            models.CheckConstraint(
                condition=Q(registry_manifest_hash__regex=r"^[0-9a-f]{64}$"),
                name="cart_projection_registry_sha256",
            ),
            models.CheckConstraint(
                condition=Q(located_count__lte=models.F("eligible_count")),
                name="cart_projection_located_lte_all",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.historical_window.code} — {self.get_status_display()}"


class CartographicObservation(models.Model):
    class TaxProfile(models.TextChoices):
        MEI = "MEI", "MEI"
        SIMPLES = "SIMPLES", "Simples Nacional"
        REGULAR = "REGULAR", "Não optante"
        UNKNOWN = "UNKNOWN", "Não informado"

    projection = models.ForeignKey(
        CartographicProjection, on_delete=models.CASCADE, related_name="observations"
    )
    revision = models.ForeignKey(
        CompetenceRevision, on_delete=models.PROTECT, related_name="cartographic_observations"
    )
    establishment = models.ForeignKey(
        Establishment, on_delete=models.PROTECT, related_name="cartographic_observations"
    )
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="cartographic_observations"
    )
    municipality = models.ForeignKey(
        Municipality, on_delete=models.PROTECT, related_name="cartographic_observations"
    )
    address_resolution = models.ForeignKey(
        AddressResolution,
        on_delete=models.PROTECT,
        related_name="observations",
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    location_method = models.CharField(max_length=16, choices=AddressResolution.Method.choices)
    cnefe_level = models.PositiveSmallIntegerField(null=True, blank=True)
    postal_code = models.CharField(max_length=8, blank=True)
    main_cnae_code = models.CharField(max_length=7, blank=True)
    branch_type = models.CharField(max_length=2)
    company_size_code = models.CharField(max_length=2, blank=True)
    tax_profile = models.CharField(max_length=12, choices=TaxProfile.choices)

    class Meta:
        db_table = "cartography_observation"
        verbose_name = "observação cartográfica"
        verbose_name_plural = "observações cartográficas"
        constraints = [
            models.UniqueConstraint(
                fields=("projection", "revision", "establishment"),
                name="cart_observation_projection_uniq",
            ),
            models.CheckConstraint(
                condition=(Q(latitude__isnull=True) & Q(longitude__isnull=True))
                | (Q(latitude__isnull=False) & Q(longitude__isnull=False)),
                name="cart_observation_coord_pair",
            ),
            models.CheckConstraint(
                condition=Q(latitude__isnull=True) | (Q(latitude__gte=-90) & Q(latitude__lte=90)),
                name="cart_observation_lat_range",
            ),
            models.CheckConstraint(
                condition=Q(longitude__isnull=True)
                | (Q(longitude__gte=-180) & Q(longitude__lte=180)),
                name="cart_observation_lng_range",
            ),
            models.CheckConstraint(
                condition=Q(cnefe_level__isnull=True)
                | (Q(cnefe_level__gte=1) & Q(cnefe_level__lte=6)),
                name="cart_observation_level_range",
            ),
        ]
        indexes = [
            models.Index(
                fields=("projection", "revision", "municipality"),
                name="cart_obs_proj_rev_city",
            ),
            models.Index(
                fields=("projection", "revision", "main_cnae_code"),
                name="cart_obs_proj_rev_cnae",
            ),
            models.Index(
                fields=("projection", "revision", "latitude", "longitude"),
                name="cart_obs_proj_rev_coord",
            ),
            models.Index(
                fields=("projection", "revision", "branch_type"),
                name="cart_obs_proj_rev_branch",
            ),
            models.Index(
                fields=("projection", "revision", "company_size_code"),
                name="cart_obs_proj_rev_size",
            ),
            models.Index(
                fields=("projection", "revision", "tax_profile"),
                name="cart_obs_proj_rev_tax",
            ),
            models.Index(
                fields=("projection", "revision", "location_method"),
                name="cart_obs_proj_rev_method",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.establishment} — {self.revision}"
