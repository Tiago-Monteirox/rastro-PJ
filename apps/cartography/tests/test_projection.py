from datetime import date

from django.test import TestCase

from apps.cartography.models import AddressResolution, GeographicSource
from apps.cartography.services.matching import (
    CnefeCandidate,
    address_lookup_key,
)
from apps.cartography.services.projection import (
    CnefeIndexes,
    _materialize_address_resolutions,
)
from apps.geography.models import ScopeMunicipality
from apps.pipeline.models import CompetenceRevision, HistoricalWindow
from apps.registry.models import Company, Establishment, EstablishmentSnapshot
from apps.test_support import create_municipality, create_revision, create_scope, create_window


class ProjectionMaterializationTests(TestCase):
    def test_equivalent_normalized_addresses_are_upserted_once(self):
        scope = create_scope()
        municipality = create_municipality()
        ScopeMunicipality.objects.create(scope=scope, municipality=municipality)
        window = create_window(scope=scope, status=HistoricalWindow.Status.ACTIVE)
        _, revision = create_revision(
            window=window,
            competence=date(2026, 8, 1),
            status=CompetenceRevision.Status.PUBLISHED,
        )
        first_company = Company.objects.create(cnpj_basic="11111111")
        second_company = Company.objects.create(cnpj_basic="22222222")
        first = Establishment.objects.create(
            company=first_company,
            cnpj="11111111000191",
        )
        second = Establishment.objects.create(
            company=second_company,
            cnpj="22222222000191",
        )
        common = {
            "revision": revision,
            "branch_type": "1",
            "registration_status_code": "02",
            "main_cnae_code": "4711302",
            "postal_code": "38400130",
            "state_code": "MG",
            "municipality": municipality,
            "municipality_tom_code": municipality.tom_code,
            "is_in_region": True,
        }
        EstablishmentSnapshot.objects.create(
            **common,
            establishment=first,
            street_name="Afonso Pena",
            street_number="0745",
            record_hash="a" * 64,
        )
        EstablishmentSnapshot.objects.create(
            **common,
            establishment=second,
            street_name="AFONSO-PENA",
            street_number="745",
            record_hash="b" * 64,
        )
        source = GeographicSource.objects.create(
            kind=GeographicSource.Kind.CNEFE,
            version="2022",
            content_hash="c" * 64,
        )
        candidate = CnefeCandidate("100", -18.9, -48.2, 1)
        key = address_lookup_key("3170206", "38400130", "AFONSO PENA", "745")
        indexes = CnefeIndexes(
            by_address={key: [candidate]},
            by_postal_code={("3170206", "38400130"): [candidate]},
            row_count=1,
        )

        _materialize_address_resolutions(
            source=source,
            algorithm_version="1.0.0",
            revisions=[revision],
            indexes=indexes,
            progress=lambda _: None,
        )

        resolution = AddressResolution.objects.get(source=source)
        self.assertEqual(resolution.method, AddressResolution.Method.ADDRESS)
        self.assertEqual(resolution.normalized_street, "AFONSO PENA")
        self.assertEqual(resolution.normalized_number, "745")
