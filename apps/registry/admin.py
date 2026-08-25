from django.contrib import admin

from .models import (
    Company,
    CompanySnapshot,
    Establishment,
    EstablishmentSnapshot,
    PartnerParticipation,
    PartnerSnapshot,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("cnpj_basic", "created_at")
    search_fields = ("cnpj_basic",)


@admin.register(Establishment)
class EstablishmentAdmin(admin.ModelAdmin):
    list_display = ("cnpj", "company", "created_at")
    search_fields = ("cnpj", "company__cnpj_basic")


@admin.register(PartnerParticipation)
class PartnerParticipationAdmin(admin.ModelAdmin):
    list_display = ("company", "partner_type", "partner_key", "created_at")
    list_filter = ("partner_type",)
    search_fields = ("company__cnpj_basic", "partner_key")


@admin.register(CompanySnapshot)
class CompanySnapshotAdmin(admin.ModelAdmin):
    list_display = ("company", "legal_name", "revision", "share_capital")
    search_fields = ("company__cnpj_basic", "legal_name", "legal_name_search")
    list_filter = ("company_size_code", "simples_optant", "mei_optant")


@admin.register(EstablishmentSnapshot)
class EstablishmentSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "establishment",
        "trade_name",
        "revision",
        "municipality",
        "registration_status_code",
        "is_in_region",
    )
    search_fields = ("establishment__cnpj", "trade_name", "trade_name_search")
    list_filter = ("is_in_region", "state_code", "registration_status_code")


@admin.register(PartnerSnapshot)
class PartnerSnapshotAdmin(admin.ModelAdmin):
    list_display = ("display_name", "participation", "revision", "qualification_code")
    search_fields = ("display_name", "participation__company__cnpj_basic")
