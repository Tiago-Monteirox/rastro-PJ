from django.conf import settings
from django.db import models

from apps.registry.models import Company


class Watchlist(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="company_watchlist"
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="watchers")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "portal_watchlist"
        verbose_name = "empresa monitorada"
        verbose_name_plural = "empresas monitoradas"
        constraints = [
            models.UniqueConstraint(fields=("user", "company"), name="portal_watchlist_uniq")
        ]

    def __str__(self) -> str:
        return f"{self.user}: {self.company}"
