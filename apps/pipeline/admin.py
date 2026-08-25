from django.contrib import admin

from .models import (
    CompetenceRevision,
    DataQualityIssue,
    HistoricalWindow,
    ImportBatch,
    PackageArtifact,
    SourceArtifact,
    WindowCompetence,
)


@admin.register(HistoricalWindow)
class HistoricalWindowAdmin(admin.ModelAdmin):
    list_display = ("code", "start_competence", "end_competence", "status", "created_at")
    list_filter = ("status", "contract_version")
    search_fields = ("code", "cohort_hash", "manifest_hash")


@admin.register(WindowCompetence)
class WindowCompetenceAdmin(admin.ModelAdmin):
    list_display = ("historical_window", "competence", "position")
    list_filter = ("historical_window",)


@admin.register(CompetenceRevision)
class CompetenceRevisionAdmin(admin.ModelAdmin):
    list_display = (
        "window_competence",
        "revision_number",
        "status",
        "warning_count",
        "published_at",
    )
    list_filter = ("status", "contract_version")
    search_fields = ("package_hash",)


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "operation", "status", "phase", "started_at", "finished_at")
    list_filter = ("operation", "status")
    readonly_fields = ("started_at",)


@admin.register(DataQualityIssue)
class DataQualityIssueAdmin(admin.ModelAdmin):
    list_display = ("rule_code", "severity", "affected_rows", "eligible_rows", "created_at")
    list_filter = ("severity", "rule_code")
    search_fields = ("entity_key",)


admin.site.register(SourceArtifact)
admin.site.register(PackageArtifact)
