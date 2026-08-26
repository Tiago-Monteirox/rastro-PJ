from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.geography.models import GeographicScope
from apps.pipeline.models import CompetenceRevision, HistoricalWindow
from apps.pipeline.services import import_window_package
from apps.pipeline.services.synthetic_window import generate_synthetic_window
from apps.registry.models import EstablishmentSnapshot

from .models import Watchlist


class PortalSmokeTests(TestCase):
    def test_home_renders_empty_foundation(self):
        response = self.client.get(reverse("portal:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aguardando dados")
        self.assertContains(response, "Ainda não importada")

    def test_health_checks_database(self):
        response = self.client.get(reverse("portal:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})


class PortalPublishedWindowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        reference = Path(__file__).parents[2] / "data/reference/triangulo_mineiro_35_municipios.csv"
        call_command("load_geographic_scope", reference, no_color=True, verbosity=0)
        scope = GeographicScope.objects.get(code="triangulo-mineiro-35", version=1)
        with TemporaryDirectory() as temporary_directory:
            manifest = generate_synthetic_window(
                output_directory=Path(temporary_directory),
                scope_code=scope.code,
                scope_version=scope.version,
                scope_hash=scope.scope_hash,
            )
            import_window_package(manifest)

    def test_dashboard_uses_published_metrics_and_events(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Eventos no intervalo")
        self.assertContains(response, ">10<")
        self.assertContains(response, "Aberturas e baixas por competência")
        self.assertContains(response, "CNAEs com maior crescimento")
        self.assertEqual(len(response.context["establishment_trend"]), 2)
        self.assertEqual(len(response.context["opening_closing_series"]), 2)
        self.assertTrue(response.context["status_distribution"])
        self.assertTrue(response.context["size_distribution"])
        self.assertContains(response, "Maiores aumentos de capital social")
        self.assertContains(response, "Empresas que mais ampliaram o quadro societário")

    def test_dashboard_ranks_growth_in_a_temporal_and_municipal_cut(self):
        response = self.client.get(
            "/",
            {
                "start_competence": "2026-07",
                "end_competence": "2026-08",
                "municipality": "3170206",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filters"]["start_competence"], "2026-07")
        self.assertEqual(response.context["filters"]["end_competence"], "2026-08")
        self.assertEqual(response.context["capital_growth"][0]["cnpj_basic"], "11111111")
        self.assertEqual(response.context["capital_growth"][0]["delta_display"], "R$ 50.000,00")
        self.assertEqual(response.context["partner_growth"][0]["cnpj_basic"], "11111111")
        self.assertEqual(response.context["partner_growth"][0]["previous"], 1)
        self.assertEqual(response.context["partner_growth"][0]["current"], 2)
        self.assertEqual(response.context["partner_growth"][0]["delta"], 1)

    def test_dashboard_filters_published_snapshot_by_competence_municipality_and_cnae(self):
        window = HistoricalWindow.objects.get(status=HistoricalWindow.Status.ACTIVE)
        revision = CompetenceRevision.objects.get(
            window_competence__historical_window=window,
            window_competence__competence="2026-08-01",
            status__in=CompetenceRevision.ACTIVE_STATUSES,
        )
        regional = EstablishmentSnapshot.objects.filter(
            revision=revision,
            is_in_region=True,
            municipality__ibge_code="3170206",
            main_cnae_code="4711302",
        )

        response = self.client.get(
            "/",
            {"competence": "2026-08", "municipality": "3170206", "cnae": "4711302"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_revision"], revision)
        self.assertEqual(response.context["establishments"], regional.count())
        self.assertEqual(
            response.context["companies"],
            regional.values("establishment__company_id").distinct().count(),
        )
        self.assertEqual(response.context["filters"]["municipality"], "3170206")
        self.assertEqual(response.context["filters"]["cnae"], "4711302")
        self.assertEqual(response.context["event_total"], 2)
        self.assertEqual(response.context["opened"], 1)
        self.assertEqual(response.context["closed"], 0)
        self.assertEqual(
            {item["event_type"] for item in response.context["event_counts"]},
            {"ESTABLISHMENT_OPENED", "REGISTRATION_STATUS_CHANGED"},
        )
        self.assertEqual(
            sum(item["total"] for item in response.context["status_distribution"]),
            regional.count(),
        )
        self.assertEqual(
            sum(item["total"] for item in response.context["size_distribution"]),
            regional.values("establishment__company_id").distinct().count(),
        )
        self.assertContains(response, "Todos os 35 municípios")

    def test_dashboard_rejects_filters_outside_the_active_scope_and_metrics(self):
        response = self.client.get(
            "/",
            {"competence": "1999-01", "municipality": "3550308", "cnae": "9999999"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filters"]["competence"], "2026-08")
        self.assertEqual(response.context["filters"]["municipality"], "")
        self.assertEqual(response.context["filters"]["cnae"], "")

    def test_search_and_company_detail_are_connected(self):
        response = self.client.get("/empresas/", {"q": "Alfa"})

        self.assertContains(response, "Alfa Comércio Ltda")
        detail = self.client.get("/empresas/11111111/")
        self.assertContains(detail, "Aumento de capital social")
        self.assertContains(detail, "Mudança de endereço")
        self.assertContains(detail, "Entrada de sócio")
        self.assertContains(detail, "R$ 100.000,00")
        self.assertContains(detail, "R$ 150.000,00")
        self.assertContains(detail, "Holding Exemplo")
        self.assertNotContains(detail, "SHARE_CAPITAL_CHANGED")
        self.assertNotContains(detail, "partner_key")
        self.assertNotContains(detail, "***")

    def test_search_supports_formatted_cnpj_and_text_inside_legal_name(self):
        formatted_cnpj = self.client.get("/empresas/", {"q": "11.111.111/0001-91"})
        inner_legal_name = self.client.get("/empresas/", {"q": "Comércio"})

        self.assertContains(formatted_cnpj, "Alfa Comércio Ltda")
        self.assertContains(inner_legal_name, "Alfa Comércio Ltda")

    def test_search_filters_by_regional_municipality_status_and_cnae(self):
        response = self.client.get(
            "/empresas/",
            {"municipality": "3170206", "status": "03", "cnae": "4711302"},
        )

        self.assertContains(response, "Zeta Consultoria Ltda")
        self.assertNotContains(response, "Alfa Comércio Ltda")
        self.assertEqual(response.context["filters"]["municipality"], "3170206")
        self.assertEqual(response.context["filters"]["status"], "03")
        self.assertEqual(response.context["filters"]["cnae"], "4711302")

    def test_search_combines_text_and_regional_filters(self):
        matching = self.client.get(
            "/empresas/",
            {"q": "Alfa", "municipality": "3170206", "cnae": "4751201"},
        )
        excluded = self.client.get(
            "/empresas/",
            {"q": "Alfa", "municipality": "3170206", "cnae": "4711302"},
        )

        self.assertContains(matching, "Alfa Comércio Ltda")
        self.assertContains(excluded, "Nenhuma empresa encontrada")

    def test_event_filters_return_expected_type(self):
        response = self.client.get("/eventos/", {"event_type": "ESTABLISHMENT_CLOSED"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Baixa de estabelecimento")
        self.assertEqual(
            {item["record"].event_type for item in response.context["events"]},
            {"ESTABLISHMENT_CLOSED"},
        )

    def test_event_filters_accept_basic_cnpj_and_reject_invalid_values(self):
        company_events = self.client.get("/eventos/", {"cnpj": "11111111"})
        establishment_events = self.client.get("/eventos/", {"cnpj": "11.111.111/0001-91"})
        invalid = self.client.get(
            "/eventos/",
            {
                "event_type": "INVALID",
                "entity_type": "INVALID",
                "competence": "invalida",
                "cnpj": "123",
            },
        )

        self.assertEqual(company_events.status_code, 200)
        self.assertIn(
            "ADDRESS_CHANGED",
            {item["record"].event_type for item in company_events.context["events"]},
        )
        self.assertEqual(establishment_events.status_code, 200)
        self.assertIn(
            "ADDRESS_CHANGED",
            {item["record"].event_type for item in establishment_events.context["events"]},
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertEqual(
            invalid.context["filters"],
            {"event_type": "", "entity_type": "", "competence": "", "cnpj": ""},
        )

    def test_import_screen_lists_revisions_and_persisted_provenance(self):
        anonymous = self.client.get("/importacoes/")
        self.assertRedirects(anonymous, "/conta/login/?next=/importacoes/")

        user = get_user_model().objects.create_user(username="auditoria")
        self.client.force_login(user)
        response = self.client.get("/importacoes/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Revisões por competência")
        self.assertContains(response, "08/2026")
        self.assertContains(response, "r1")
        self.assertContains(response, "4 artefato(s)")

    def test_authenticated_user_can_add_and_remove_watchlist_company(self):
        user = get_user_model().objects.create_user(username="tiago", password="teste-local")
        self.client.force_login(user)

        added = self.client.post("/monitoradas/11111111/", {"action": "add"})
        self.assertEqual(added.status_code, 302)
        self.assertTrue(Watchlist.objects.filter(user=user).exists())
        listing = self.client.get("/monitoradas/")
        self.assertContains(listing, "Alfa Comércio Ltda")
        self.assertContains(listing, "alteração(ões)")
        self.assertContains(listing, "no último intervalo")

        removed = self.client.post("/monitoradas/11111111/", {"action": "remove"})
        self.assertEqual(removed.status_code, 302)
        self.assertFalse(Watchlist.objects.filter(user=user).exists())

    def test_watchlist_change_rejects_get(self):
        user = get_user_model().objects.create_user(username="gabriel")
        self.client.force_login(user)

        response = self.client.get("/monitoradas/11111111/")

        self.assertEqual(response.status_code, 405)
