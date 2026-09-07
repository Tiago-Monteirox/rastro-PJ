from django.core.management.base import BaseCommand, CommandError

from apps.cartography.services.cnae_catalog import CnaeCatalogError, sync_cnae_catalog


class Command(BaseCommand):
    help = "Sincroniza localmente as descrições oficiais das subclasses CNAE do IBGE."

    def handle(self, *args, **options):
        try:
            total = sync_cnae_catalog()
        except CnaeCatalogError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Catálogo CNAE sincronizado: {total:,} subclasses."))
