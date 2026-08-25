from django.contrib import admin

from .models import Watchlist


@admin.register(Watchlist)
class WatchlistAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "created_at")
    search_fields = ("user__username", "company__cnpj_basic")
