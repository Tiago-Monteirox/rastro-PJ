from django.contrib import admin

from .models import GeographicScope, Municipality, ScopeMunicipality


class ScopeMunicipalityInline(admin.TabularInline):
    model = ScopeMunicipality
    extra = 0


@admin.register(GeographicScope)
class GeographicScopeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "version", "created_at")
    search_fields = ("code", "name", "scope_hash")
    inlines = (ScopeMunicipalityInline,)


@admin.register(Municipality)
class MunicipalityAdmin(admin.ModelAdmin):
    list_display = ("ibge_code", "tom_code", "name", "uf")
    list_filter = ("uf",)
    search_fields = ("ibge_code", "tom_code", "name")
