from django.core.management.base import BaseCommand, CommandError

from apps.cartography.services.population_reference import (
    IBGE_POPULATION_REFERENCE_YEAR,
    PopulationReferenceError,
    sync_population_reference,
)
from apps.geography.models import GeographicScope


class Command(BaseCommand):
    help = "Sincroniza a população residente municipal do Censo 2022 pela API SIDRA do IBGE."

    def add_arguments(self, parser):
        parser.add_argument("--scope", default="triangulo-mineiro-35")

    def handle(self, *args, **options):
        try:
            scope = (
                GeographicScope.objects.filter(code=options["scope"]).order_by("-version").first()
            )
            if scope is None:
                raise CommandError(f"Recorte geográfico inexistente: {options['scope']}.")
            municipalities = [
                membership.municipality
                for membership in scope.scope_municipalities.select_related("municipality")
            ]
            source, total = sync_population_reference(municipalities)
        except PopulationReferenceError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"População IBGE {IBGE_POPULATION_REFERENCE_YEAR} sincronizada: "
                f"{total} municípios; fonte {source.content_hash[:12]}."
            )
        )
