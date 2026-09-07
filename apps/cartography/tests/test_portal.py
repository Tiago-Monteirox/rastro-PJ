from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.cartography.models import (
    AddressResolution,
    CartographicObservation,
    CartographicProjection,
    CnaeSubclass,
    GeographicSource,
    MunicipalityBoundary,
)
from apps.geography.models import ScopeMunicipality
from apps.pipeline.models import CompetenceRevision, HistoricalWindow
from apps.registry.models import (
    Company,
    CompanySnapshot,
    Establishment,
    EstablishmentSnapshot,
)
from apps.test_support import (
    create_company_with_establishment,
    create_municipality,
    create_revision,
    create_scope,
    create_window,
)


@override_settings(MAPBOX_PUBLIC_TOKEN="pk.test-public-token")
class CartographicPortalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.scope = create_scope()
        cls.municipality = create_municipality()
        ScopeMunicipality.objects.create(scope=cls.scope, municipality=cls.municipality)
        cls.window = create_window(scope=cls.scope, status=HistoricalWindow.Status.ACTIVE)
        _, cls.revision = create_revision(
            window=cls.window,
            competence=date(2026, 8, 1),
            status=CompetenceRevision.Status.PUBLISHED,
        )
        cls.cnefe_source = GeographicSource.objects.create(
            kind=GeographicSource.Kind.CNEFE,
            version="2022",
            content_hash="5" * 64,
        )
        cls.boundary_source = GeographicSource.objects.create(
            kind=GeographicSource.Kind.MUNICIPAL_BOUNDARIES,
            version="2022-minima",
            content_hash="6" * 64,
        )
        MunicipalityBoundary.objects.create(
            source=cls.boundary_source,
            municipality=cls.municipality,
            geometry={
                "type": "Polygon",
                "coordinates": [
                    [
                        [-48.3, -19.0],
                        [-48.1, -19.0],
                        [-48.1, -18.8],
                        [-48.3, -19.0],
                    ]
                ],
            },
            bbox=[-48.3, -19.0, -48.1, -18.8],
            center_latitude=Decimal("-18.900000"),
            center_longitude=Decimal("-48.200000"),
        )
        cls.projection = CartographicProjection.objects.create(
            historical_window=cls.window,
            cnefe_source=cls.cnefe_source,
            boundary_source=cls.boundary_source,
            registry_manifest_hash=cls.window.manifest_hash,
            status=CartographicProjection.Status.PUBLISHED,
            eligible_count=1,
            located_count=1,
            address_count=1,
        )
        CnaeSubclass.objects.create(
            code="4711302",
            description=(
                "COMÉRCIO VAREJISTA DE MERCADORIAS EM GERAL, COM PREDOMINÂNCIA DE ALIMENTOS"
            ),
        )
        cls.company, cls.establishment = create_company_with_establishment()
        CompanySnapshot.objects.create(
            revision=cls.revision,
            company=cls.company,
            legal_name="Empresa Cartográfica Ltda",
            legal_name_search="EMPRESA CARTOGRAFICA LTDA",
            company_size_code="01",
            simples_optant=True,
            mei_optant=False,
            record_hash="7" * 64,
        )
        EstablishmentSnapshot.objects.create(
            revision=cls.revision,
            establishment=cls.establishment,
            branch_type=EstablishmentSnapshot.BRANCH_TYPE_HEADQUARTERS,
            trade_name="Ponto no mapa",
            trade_name_search="PONTO NO MAPA",
            registration_status_code="02",
            activity_start_date=date(2026, 4, 10),
            main_cnae_code="4711302",
            street_type="AVENIDA",
            street_name="AFONSO PENA",
            street_number="745",
            neighborhood="CENTRO",
            postal_code="38400130",
            state_code="MG",
            municipality=cls.municipality,
            municipality_tom_code=cls.municipality.tom_code,
            is_in_region=True,
            record_hash="8" * 64,
        )
        cls.resolution = AddressResolution.objects.create(
            source=cls.cnefe_source,
            municipality=cls.municipality,
            fingerprint="9" * 64,
            postal_code="38400130",
            normalized_street="AFONSO PENA",
            normalized_number="745",
            method=AddressResolution.Method.ADDRESS,
            latitude=Decimal("-18.900000"),
            longitude=Decimal("-48.200000"),
            cnefe_level=1,
            cnefe_address_code="100",
            candidate_count=1,
            dispersion_meters=Decimal("0"),
            reason="address_match",
        )
        CartographicObservation.objects.create(
            projection=cls.projection,
            revision=cls.revision,
            establishment=cls.establishment,
            company=cls.company,
            municipality=cls.municipality,
            address_resolution=cls.resolution,
            latitude=cls.resolution.latitude,
            longitude=cls.resolution.longitude,
            location_method=cls.resolution.method,
            cnefe_level=1,
            postal_code="38400130",
            main_cnae_code="4711302",
            activity_start_date=date(2026, 4, 10),
            branch_type="1",
            company_size_code="01",
            tax_profile=CartographicObservation.TaxProfile.SIMPLES,
        )
        cls.user = get_user_model().objects.create_user(username="mapa", password="senha-local")

    def setUp(self):
        self.client.force_login(self.user)

    def test_page_and_every_api_require_authentication(self):
        self.client.logout()

        for path in (
            "/mapa/",
            "/mapa/api/resumo/",
            "/mapa/api/localizacoes/",
            "/mapa/api/estabelecimentos/",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/conta/login/", response.url)

    def test_map_page_exposes_fallback_table_and_public_token(self):
        response = self.client.get("/mapa/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rastro PJ")
        self.assertContains(response, "Mapa analítico regional")
        self.assertContains(response, "Alternativa acessível ao mapa")
        self.assertContains(response, "Uberlândia")
        self.assertContains(response, "pk.test-public-token")
        self.assertContains(response, "Verde claro indica menos estabelecimentos")
        self.assertContains(response, "Agrupamento por CEP")
        self.assertContains(
            response,
            "4711-3/02 — COMÉRCIO VAREJISTA DE MERCADORIAS EM GERAL",
        )

    @override_settings(MAPBOX_PUBLIC_TOKEN="sk.secret-must-not-reach-browser")
    def test_secret_mapbox_token_is_rejected_and_never_rendered(self):
        response = self.client.get("/mapa/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "somente tokens públicos")
        self.assertNotContains(response, "sk.secret-must-not-reach-browser")

    def test_bootstrap_uses_one_competence_and_all_eight_filters(self):
        response = self.client.get(
            "/mapa/api/resumo/",
            {
                "competence": "2026-08",
                "municipality": "3170206",
                "cnae": "4711302",
                "branch_type": "1",
                "company_size": "01",
                "tax_profile": "SIMPLES",
                "precision": "ADDRESS",
                "opening_period": "6",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["indicators"]["establishments"], 1)
        self.assertEqual(payload["indicators"]["companies"], 1)
        self.assertEqual(payload["indicators"]["geographic_coverage"]["percentage"], 100.0)
        self.assertEqual(payload["selection"]["competence"], "2026-08")
        self.assertEqual(payload["selection"]["opening_period"], "6")
        self.assertEqual(len(payload["municipalities"]["features"]), 1)
        self.assertEqual(
            payload["municipalities"]["features"][0]["properties"]["bbox"],
            [-48.3, -19.0, -48.1, -18.8],
        )

    def test_opening_period_is_relative_to_the_selected_competence(self):
        current_month = self.client.get(
            "/mapa/api/resumo/",
            {"competence": "2026-08", "opening_period": "1"},
        )
        last_six_months = self.client.get(
            "/mapa/api/resumo/",
            {"competence": "2026-08", "opening_period": "6"},
        )

        self.assertEqual(current_month.json()["indicators"]["establishments"], 0)
        self.assertEqual(last_six_months.json()["indicators"]["establishments"], 1)

    def test_page_preserves_filters_from_the_url(self):
        response = self.client.get(
            "/mapa/",
            {
                "competence": "2026-08",
                "municipality": "3170206",
                "cnae": "4711302",
                "opening_period": "6",
            },
        )

        self.assertContains(response, 'option value="3170206" selected')
        self.assertContains(response, 'value="4711302" list="map-cnae-options"')
        self.assertContains(response, 'option value="6" selected')

    def test_unknown_opening_period_is_rejected(self):
        response = self.client.get(
            "/mapa/api/resumo/",
            {"competence": "2026-08", "opening_period": "24"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Período de abertura inválido", response.json()["error"])

    def test_invalid_filter_is_rejected_instead_of_silently_ignored(self):
        response = self.client.get(
            "/mapa/api/resumo/",
            {"competence": "2026-08", "municipality": "3550308"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("fora do recorte", response.json()["error"])

    def test_unknown_company_size_is_rejected(self):
        response = self.client.get(
            "/mapa/api/resumo/",
            {"competence": "2026-08", "company_size": "ZZ"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Porte empresarial inválido", response.json()["error"])

    def test_location_endpoint_returns_complete_exact_group(self):
        response = self.client.get(
            "/mapa/api/localizacoes/",
            {
                "competence": "2026-08",
                "west": "-49",
                "south": "-20",
                "east": "-47",
                "north": "-18",
                "zoom": "13",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["level"], "location")
        self.assertEqual(len(payload["locations"]["features"]), 1)
        self.assertEqual(
            payload["locations"]["features"][0]["properties"]["location_method"],
            "ADDRESS",
        )
        self.assertEqual(
            payload["locations"]["features"][0]["properties"]["detail_latitude"],
            -18.9,
        )
        self.assertEqual(
            payload["locations"]["features"][0]["properties"]["detail_longitude"],
            -48.2,
        )

    def test_excess_detail_is_aggregated_without_silent_truncation(self):
        company = Company.objects.create(cnpj_basic="87654321")
        establishment = Establishment.objects.create(
            company=company,
            cnpj="87654321000198",
        )
        resolution = AddressResolution.objects.create(
            source=self.cnefe_source,
            municipality=self.municipality,
            fingerprint="d" * 64,
            postal_code="38400130",
            normalized_street="OUTRA RUA",
            normalized_number="10",
            method=AddressResolution.Method.ADDRESS,
            latitude=Decimal("-18.910000"),
            longitude=Decimal("-48.210000"),
            cnefe_level=1,
            cnefe_address_code="200",
            candidate_count=1,
            dispersion_meters=Decimal("0"),
            reason="address_match",
        )
        CartographicObservation.objects.create(
            projection=self.projection,
            revision=self.revision,
            establishment=establishment,
            company=company,
            municipality=self.municipality,
            address_resolution=resolution,
            latitude=resolution.latitude,
            longitude=resolution.longitude,
            location_method=resolution.method,
            cnefe_level=1,
            postal_code="38400130",
            main_cnae_code="4711302",
            branch_type="2",
            company_size_code="01",
            tax_profile=CartographicObservation.TaxProfile.SIMPLES,
        )

        with patch("apps.cartography.services.queries.DETAIL_LIMIT", 1):
            response = self.client.get(
                "/mapa/api/localizacoes/",
                {
                    "competence": "2026-08",
                    "west": "-49",
                    "south": "-20",
                    "east": "-47",
                    "north": "-18",
                    "zoom": "13",
                },
            )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["requested_level"], "location")
        self.assertEqual(payload["level"], "postal_code")
        self.assertTrue(payload["aggregation_reason"])
        self.assertEqual(len(payload["locations"]["features"]), 1)
        self.assertIn(
            payload["locations"]["features"][0]["geometry"]["coordinates"],
            ([-48.2, -18.9], [-48.21, -18.91]),
        )

    def test_legitimate_empty_filter_returns_an_empty_analysis(self):
        response = self.client.get(
            "/mapa/api/resumo/",
            {"competence": "2026-08", "cnae": "9999999"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["indicators"]["establishments"], 0)
        self.assertEqual(payload["indicators"]["companies"], 0)
        self.assertEqual(payload["indicators"]["geographic_coverage"]["percentage"], 0.0)
        self.assertEqual(payload["rankings"]["municipalities"], [])

    def test_location_details_are_paginated_and_contain_no_personal_data(self):
        response = self.client.get(
            "/mapa/api/estabelecimentos/",
            {
                "competence": "2026-08",
                "latitude": "-18.900000",
                "longitude": "-48.200000",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["pagination"]["total"], 1)
        self.assertEqual(payload["items"][0]["legal_name"], "Empresa Cartográfica Ltda")
        self.assertEqual(payload["items"][0]["company_url"], "/empresas/12345678/")
        self.assertIn("COMÉRCIO VAREJISTA", payload["items"][0]["main_cnae_label"])
        self.assertNotIn("cpf", response.content.decode().lower())
        self.assertNotIn("partner", response.content.decode().lower())

    def test_location_details_preserve_the_clicked_precision_group(self):
        company = Company.objects.create(cnpj_basic="87654321")
        establishment = Establishment.objects.create(
            company=company,
            cnpj="87654321000198",
        )
        CompanySnapshot.objects.create(
            revision=self.revision,
            company=company,
            legal_name="Empresa no mesmo ponto",
            legal_name_search="EMPRESA NO MESMO PONTO",
            company_size_code="01",
            simples_optant=True,
            mei_optant=False,
            record_hash="d" * 64,
        )
        EstablishmentSnapshot.objects.create(
            revision=self.revision,
            establishment=establishment,
            branch_type=EstablishmentSnapshot.BRANCH_TYPE_BRANCH,
            trade_name="Aproximação por CEP",
            trade_name_search="APROXIMACAO POR CEP",
            registration_status_code="02",
            main_cnae_code="4711302",
            street_type="RUA",
            street_name="OUTRO ENDERECO",
            street_number="10",
            neighborhood="CENTRO",
            postal_code="38400130",
            state_code="MG",
            municipality=self.municipality,
            municipality_tom_code=self.municipality.tom_code,
            is_in_region=True,
            record_hash="e" * 64,
        )
        resolution = AddressResolution.objects.create(
            source=self.cnefe_source,
            municipality=self.municipality,
            fingerprint="f" * 64,
            postal_code="38400130",
            method=AddressResolution.Method.POSTAL_CODE,
            latitude=Decimal("-18.900000"),
            longitude=Decimal("-48.200000"),
            cnefe_level=5,
            cnefe_address_code="300",
            candidate_count=3,
            dispersion_meters=Decimal("25"),
            reason="postal_code_fallback",
        )
        CartographicObservation.objects.create(
            projection=self.projection,
            revision=self.revision,
            establishment=establishment,
            company=company,
            municipality=self.municipality,
            address_resolution=resolution,
            latitude=resolution.latitude,
            longitude=resolution.longitude,
            location_method=resolution.method,
            cnefe_level=5,
            postal_code="38400130",
            main_cnae_code="4711302",
            branch_type="2",
            company_size_code="01",
            tax_profile=CartographicObservation.TaxProfile.SIMPLES,
        )

        response = self.client.get(
            "/mapa/api/estabelecimentos/",
            {
                "competence": "2026-08",
                "latitude": "-18.900000",
                "longitude": "-48.200000",
                "location_method": "ADDRESS",
                "cnefe_level": "1",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["pagination"]["total"], 1)
        self.assertEqual(payload["items"][0]["precision"], "Endereço CNEFE")

    def test_absent_projection_has_distinct_page_and_api_states(self):
        self.projection.status = CartographicProjection.Status.FAILED
        self.projection.save(update_fields=("status",))

        page = self.client.get("/mapa/")
        api = self.client.get("/mapa/api/resumo/")

        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "projeção cartográfica ainda não foi publicada")
        self.assertEqual(api.status_code, 503)
        self.assertIn("ainda não foi preparada", api.json()["error"])
