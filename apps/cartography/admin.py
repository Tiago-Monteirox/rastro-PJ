from django.contrib import admin

from .models import (
    AddressResolution,
    CartographicObservation,
    CartographicProjection,
    CnaeSubclass,
    GeographicSource,
    MunicipalityBoundary,
    MunicipalityPopulation,
)


@admin.register(CnaeSubclass)
class CnaeSubclassAdmin(admin.ModelAdmin):
    list_display = ("code", "description", "source", "synced_at")
    search_fields = ("code", "description")


@admin.register(GeographicSource)
class GeographicSourceAdmin(admin.ModelAdmin):
    list_display = ("kind", "version", "content_hash", "created_at")
    list_filter = ("kind", "version")
    search_fields = ("content_hash",)


@admin.register(MunicipalityBoundary)
class MunicipalityBoundaryAdmin(admin.ModelAdmin):
    list_display = ("municipality", "source", "center_latitude", "center_longitude")
    search_fields = ("municipality__name", "municipality__ibge_code")


@admin.register(MunicipalityPopulation)
class MunicipalityPopulationAdmin(admin.ModelAdmin):
    list_display = ("municipality", "population", "reference_year", "source", "synced_at")
    list_filter = ("reference_year", "source")
    search_fields = ("municipality__name", "municipality__ibge_code")


@admin.register(AddressResolution)
class AddressResolutionAdmin(admin.ModelAdmin):
    list_display = ("municipality", "postal_code", "method", "cnefe_level", "candidate_count")
    list_filter = ("method", "cnefe_level", "municipality")
    search_fields = ("fingerprint", "postal_code", "normalized_street")


@admin.register(CartographicProjection)
class CartographicProjectionAdmin(admin.ModelAdmin):
    list_display = (
        "historical_window",
        "algorithm_version",
        "status",
        "eligible_count",
        "located_count",
        "published_at",
    )
    list_filter = ("status", "algorithm_version")


@admin.register(CartographicObservation)
class CartographicObservationAdmin(admin.ModelAdmin):
    list_display = (
        "establishment",
        "revision",
        "municipality",
        "location_method",
        "main_cnae_code",
        "activity_start_date",
    )
    list_filter = ("location_method", "branch_type", "tax_profile")
    search_fields = ("establishment__cnpj", "company__cnpj_basic", "postal_code")
