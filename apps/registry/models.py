from django.db import models
from django.db.models import Q

from apps.geography.models import Municipality
from apps.pipeline.models import CompetenceRevision


class Company(models.Model):
    cnpj_basic = models.CharField(max_length=8, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "registry_company"
        verbose_name = "empresa"
        verbose_name_plural = "empresas"
        constraints = [
            models.CheckConstraint(
                condition=Q(cnpj_basic__regex=r"^[0-9]{8}$"), name="reg_company_cnpj_basic_8d"
            )
        ]

    def __str__(self) -> str:
        return self.cnpj_basic


class Establishment(models.Model):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="establishments")
    cnpj = models.CharField(max_length=14, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "registry_establishment"
        verbose_name = "estabelecimento"
        verbose_name_plural = "estabelecimentos"
        constraints = [
            models.CheckConstraint(
                condition=Q(cnpj__regex=r"^[0-9]{14}$"), name="reg_establishment_cnpj_14d"
            )
        ]

    def __str__(self) -> str:
        return self.cnpj


class PartnerParticipation(models.Model):
    class PartnerType(models.TextChoices):
        PERSON = "PF", "Pessoa física"
        COMPANY = "PJ", "Pessoa jurídica"
        FOREIGN = "FOREIGN", "Estrangeiro"

    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="partner_participations"
    )
    partner_key = models.CharField(max_length=64)
    partner_type = models.CharField(max_length=12, choices=PartnerType.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "registry_partner_participation"
        verbose_name = "participação societária"
        verbose_name_plural = "participações societárias"
        constraints = [
            models.UniqueConstraint(
                fields=("company", "partner_key"), name="reg_company_partner_key_uniq"
            )
        ]

    def __str__(self) -> str:
        return f"{self.company} / {self.partner_type} / {self.partner_key[:12]}"


class CompanySnapshot(models.Model):
    revision = models.ForeignKey(
        CompetenceRevision, on_delete=models.PROTECT, related_name="company_snapshots"
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="snapshots")
    legal_name = models.CharField(max_length=255)
    legal_name_search = models.CharField(max_length=255, db_index=True)
    legal_nature_code = models.CharField(max_length=4, null=True, blank=True)
    share_capital = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    company_size_code = models.CharField(max_length=2, null=True, blank=True)
    simples_optant = models.BooleanField(null=True, blank=True)
    simples_option_date = models.DateField(null=True, blank=True)
    simples_exclusion_date = models.DateField(null=True, blank=True)
    mei_optant = models.BooleanField(null=True, blank=True)
    mei_option_date = models.DateField(null=True, blank=True)
    mei_exclusion_date = models.DateField(null=True, blank=True)
    record_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "registry_company_snapshot"
        verbose_name = "fotografia de empresa"
        verbose_name_plural = "fotografias de empresa"
        constraints = [
            models.UniqueConstraint(
                fields=("revision", "company"), name="reg_company_snapshot_uniq"
            ),
            models.CheckConstraint(
                condition=Q(share_capital__isnull=True) | Q(share_capital__gte=0),
                name="reg_company_capital_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(record_hash__regex=r"^[0-9a-f]{64}$"),
                name="reg_company_snapshot_hash_sha256",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.legal_name} — {self.revision}"


class EstablishmentSnapshot(models.Model):
    revision = models.ForeignKey(
        CompetenceRevision, on_delete=models.PROTECT, related_name="establishment_snapshots"
    )
    establishment = models.ForeignKey(
        Establishment, on_delete=models.PROTECT, related_name="snapshots"
    )
    branch_type = models.CharField(max_length=2)
    trade_name = models.CharField(max_length=255, blank=True)
    trade_name_search = models.CharField(max_length=255, blank=True, db_index=True)
    registration_status_code = models.CharField(max_length=2)
    registration_status_date = models.DateField(null=True, blank=True)
    registration_status_reason_code = models.CharField(max_length=2, null=True, blank=True)
    activity_start_date = models.DateField(null=True, blank=True)
    main_cnae_code = models.CharField(max_length=7, null=True, blank=True)
    street_type = models.CharField(max_length=40, blank=True)
    street_name = models.CharField(max_length=255, blank=True)
    street_number = models.CharField(max_length=20, blank=True)
    address_complement = models.CharField(max_length=255, blank=True)
    neighborhood = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=8, blank=True)
    state_code = models.CharField(max_length=2)
    municipality = models.ForeignKey(
        Municipality, on_delete=models.PROTECT, related_name="establishment_snapshots"
    )
    municipality_tom_code = models.CharField(max_length=4)
    is_in_region = models.BooleanField()
    record_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "registry_establishment_snapshot"
        verbose_name = "fotografia de estabelecimento"
        verbose_name_plural = "fotografias de estabelecimento"
        constraints = [
            models.UniqueConstraint(
                fields=("revision", "establishment"), name="reg_establishment_snapshot_uniq"
            ),
            models.CheckConstraint(
                condition=Q(municipality_tom_code__regex=r"^[0-9]{4}$"),
                name="reg_est_snapshot_tom_4d",
            ),
            models.CheckConstraint(
                condition=Q(state_code__regex=r"^[A-Z]{2}$"), name="reg_est_snapshot_uf_2letters"
            ),
            models.CheckConstraint(
                condition=Q(postal_code="") | Q(postal_code__regex=r"^[0-9]{8}$"),
                name="reg_est_snapshot_postal_8d",
            ),
            models.CheckConstraint(
                condition=Q(main_cnae_code__isnull=True)
                | Q(main_cnae_code="")
                | Q(main_cnae_code__regex=r"^[0-9]{7}$"),
                name="reg_est_snapshot_cnae_7d",
            ),
            models.CheckConstraint(
                condition=Q(record_hash__regex=r"^[0-9a-f]{64}$"),
                name="reg_est_snapshot_hash_sha256",
            ),
        ]
        indexes = [
            models.Index(
                fields=("revision", "municipality", "is_in_region"),
                name="reg_est_rev_city_region",
            ),
            models.Index(
                fields=("revision", "main_cnae_code", "is_in_region"),
                name="reg_est_rev_cnae_region",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.establishment} — {self.revision}"


class PartnerSnapshot(models.Model):
    revision = models.ForeignKey(
        CompetenceRevision, on_delete=models.PROTECT, related_name="partner_snapshots"
    )
    participation = models.ForeignKey(
        PartnerParticipation, on_delete=models.PROTECT, related_name="snapshots"
    )
    display_name = models.CharField(max_length=255)
    partner_cnpj_basic = models.CharField(max_length=8, null=True, blank=True)
    country_code = models.CharField(max_length=3, null=True, blank=True)
    qualification_code = models.CharField(max_length=2, null=True, blank=True)
    entry_date = models.DateField(null=True, blank=True)
    record_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "registry_partner_snapshot"
        verbose_name = "fotografia de participação societária"
        verbose_name_plural = "fotografias de participação societária"
        constraints = [
            models.UniqueConstraint(
                fields=("revision", "participation"), name="reg_partner_snapshot_uniq"
            ),
            models.CheckConstraint(
                condition=Q(partner_cnpj_basic__isnull=True)
                | Q(partner_cnpj_basic="")
                | Q(partner_cnpj_basic__regex=r"^[0-9]{8}$"),
                name="reg_partner_snapshot_cnpj_basic_8d",
            ),
            models.CheckConstraint(
                condition=Q(record_hash__regex=r"^[0-9a-f]{64}$"),
                name="reg_partner_snapshot_hash_sha256",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.display_name} — {self.revision}"
