from django.contrib import admin

from .models import ChangeEvent, RegionalMonthlyMetric


@admin.register(ChangeEvent)
class ChangeEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "entity_type", "from_revision", "to_revision", "detected_at")
    list_filter = ("entity_type", "event_type", "dimension")
    search_fields = ("event_key", "company__cnpj_basic", "establishment__cnpj")


@admin.register(RegionalMonthlyMetric)
class RegionalMonthlyMetricAdmin(admin.ModelAdmin):
    list_display = ("metric_type", "entity_type", "revision", "municipality", "value")
    list_filter = ("metric_type", "entity_type")
    search_fields = ("metric_key", "cnae_code")
