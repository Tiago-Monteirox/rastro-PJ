import uuid

from django.db import models
from django.db.models import Q


class GeographicScope(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=120)
    version = models.PositiveSmallIntegerField()
    scope_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "geography_geographic_scope"
        verbose_name = "recorte geográfico"
        verbose_name_plural = "recortes geográficos"
        constraints = [
            models.UniqueConstraint(fields=("code", "version"), name="geo_scope_code_version_uniq"),
            models.CheckConstraint(condition=Q(version__gt=0), name="geo_scope_version_gt_0"),
            models.CheckConstraint(
                condition=Q(scope_hash__regex=r"^[0-9a-f]{64}$"),
                name="geo_scope_hash_sha256",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} (v{self.version})"


class Municipality(models.Model):
    ibge_code = models.CharField(max_length=7, unique=True)
    tom_code = models.CharField(max_length=4, unique=True)
    name = models.CharField(max_length=120)
    uf = models.CharField(max_length=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "geography_municipality"
        verbose_name = "município"
        verbose_name_plural = "municípios"
        ordering = ("uf", "name")
        constraints = [
            models.CheckConstraint(
                condition=Q(ibge_code__regex=r"^[0-9]{7}$"), name="geo_municipality_ibge_7d"
            ),
            models.CheckConstraint(
                condition=Q(tom_code__regex=r"^[0-9]{4}$"), name="geo_municipality_tom_4d"
            ),
            models.CheckConstraint(
                condition=Q(uf__regex=r"^[A-Z]{2}$"), name="geo_municipality_uf_2letters"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name}/{self.uf} ({self.ibge_code})"


class ScopeMunicipality(models.Model):
    scope = models.ForeignKey(
        GeographicScope, on_delete=models.PROTECT, related_name="scope_municipalities"
    )
    municipality = models.ForeignKey(
        Municipality, on_delete=models.PROTECT, related_name="scope_memberships"
    )

    class Meta:
        db_table = "geography_scope_municipality"
        verbose_name = "município do recorte"
        verbose_name_plural = "municípios do recorte"
        constraints = [
            models.UniqueConstraint(
                fields=("scope", "municipality"), name="geo_scope_municipality_uniq"
            )
        ]

    def __str__(self) -> str:
        return f"{self.scope}: {self.municipality}"
