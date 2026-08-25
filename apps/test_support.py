from datetime import date

from apps.geography.models import GeographicScope, Municipality
from apps.pipeline.models import (
    CompetenceRevision,
    HistoricalWindow,
    ImportBatch,
    WindowCompetence,
)
from apps.registry.models import Company, Establishment


def create_scope(*, code: str = "triangulo-mineiro-35", hash_char: str = "a"):
    return GeographicScope.objects.create(
        code=code,
        name="Triângulo Mineiro — 35 municípios",
        version=1,
        scope_hash=hash_char * 64,
    )


def create_municipality():
    return Municipality.objects.create(
        ibge_code="3170206", tom_code="5403", name="Uberlândia", uf="MG"
    )


def create_window(*, scope, code: str = "tm-2025-08-2026-08", status="DRAFT"):
    published = status in {
        HistoricalWindow.Status.VALIDATED,
        HistoricalWindow.Status.ACTIVE,
        HistoricalWindow.Status.SUPERSEDED,
    }
    return HistoricalWindow.objects.create(
        geographic_scope=scope,
        code=code,
        start_competence=date(2025, 8, 1),
        end_competence=date(2026, 8, 1),
        contract_version="1.0.0",
        cohort_hash="b" * 64 if published else None,
        manifest_hash="c" * 64 if published else None,
        status=status,
    )


def create_revision(
    *,
    window,
    competence: date = date(2025, 8, 1),
    position: int = 0,
    revision_number: int = 1,
    status: str = CompetenceRevision.Status.STAGING,
    hash_char: str = "d",
):
    window_competence = WindowCompetence.objects.create(
        historical_window=window, competence=competence, position=position
    )
    revision = CompetenceRevision.objects.create(
        window_competence=window_competence,
        revision_number=revision_number,
        package_hash=hash_char * 64,
        contract_version="1.0.0",
        status=status,
    )
    return window_competence, revision


def create_company_with_establishment():
    company = Company.objects.create(cnpj_basic="12345678")
    establishment = Establishment.objects.create(company=company, cnpj="12345678000190")
    return company, establishment


def create_import_batch(*, revision):
    return ImportBatch.objects.create(
        competence_revision=revision,
        operation=ImportBatch.Operation.IMPORT,
        status=ImportBatch.Status.LOADING,
    )
