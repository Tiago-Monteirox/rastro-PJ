from __future__ import annotations

import re
from calendar import monthrange
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.db.models import Count, Min, Q, QuerySet
from django.urls import reverse

from apps.cartography.models import (
    AddressResolution,
    CartographicObservation,
    CartographicProjection,
    CnaeSubclass,
    MunicipalityBoundary,
    MunicipalityPopulation,
)
from apps.changes.models import ChangeEvent
from apps.pipeline.models import CompetenceRevision
from apps.registry.models import CompanySnapshot, EstablishmentSnapshot

COMPETENCE_PATTERN = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")
CNAE_PATTERN = re.compile(r"^[0-9]{7}$")
IBGE_PATTERN = re.compile(r"^[0-9]{7}$")
DETAIL_LIMIT = 5_000
DETAIL_PAGE_SIZE = 25
BRANCH_LABELS = {"1": "Matriz", "2": "Filial"}
SIZE_LABELS = {
    "00": "Não informado",
    "01": "Microempresa",
    "03": "Empresa de pequeno porte",
    "05": "Demais",
}
PRECISION_LABELS = dict(AddressResolution.Method.choices)
TAX_LABELS = dict(CartographicObservation.TaxProfile.choices)
OPENING_PERIODS = {
    "1": "Na competência selecionada",
    "3": "Últimos 3 meses",
    "6": "Últimos 6 meses",
    "12": "Últimos 12 meses",
}
ANALYSIS_MODES = {
    "stock": "Concentração atual",
    "dynamics": "Dinâmica territorial (experimental)",
}
MAP_METRICS = {
    "absolute": "Volume absoluto",
    "per_1000": "Por mil habitantes (Censo 2022)",
}


class MapQueryError(Exception):
    pass


@dataclass(frozen=True)
class MapSelection:
    projection: CartographicProjection
    revision: CompetenceRevision
    competence: str
    municipality: str = ""
    cnae: str = ""
    branch_type: str = ""
    company_size: str = ""
    tax_profile: str = ""
    precision: str = ""
    opening_period: str = ""
    analysis_mode: str = "stock"
    map_metric: str = "absolute"

    def as_dict(self) -> dict[str, str]:
        return {
            "competence": self.competence,
            "municipality": self.municipality,
            "cnae": self.cnae,
            "branch_type": self.branch_type,
            "company_size": self.company_size,
            "tax_profile": self.tax_profile,
            "precision": self.precision,
            "opening_period": self.opening_period,
            "analysis_mode": self.analysis_mode,
            "map_metric": self.map_metric,
        }


def published_projection() -> CartographicProjection | None:
    return (
        CartographicProjection.objects.filter(status=CartographicProjection.Status.PUBLISHED)
        .select_related("historical_window", "boundary_source", "cnefe_source")
        .order_by("-published_at")
        .first()
    )


def map_page_context() -> dict:
    projection = published_projection()
    if projection is None:
        return {
            "projection": None,
            "revision_options": [],
            "municipalities": [],
            "cnae_options": [],
            "size_options": [],
            "tax_options": CartographicObservation.TaxProfile.choices,
            "precision_options": AddressResolution.Method.choices,
            "branch_options": (("1", "Matriz"), ("2", "Filial")),
            "opening_options": OPENING_PERIODS.items(),
            "analysis_mode_options": ANALYSIS_MODES.items(),
            "map_metric_options": MAP_METRICS.items(),
        }

    revisions = _projection_revisions(projection)
    latest = revisions[-1] if revisions else None
    municipalities = list(
        projection.historical_window.geographic_scope.scope_municipalities.select_related(
            "municipality"
        )
        .order_by("municipality__name")
        .values_list(
            "municipality__ibge_code",
            "municipality__name",
            "municipality__uf",
        )
    )
    cnae_options = []
    size_codes = []
    if latest:
        observations = CartographicObservation.objects.filter(
            projection=projection, revision=latest
        )
        cnae_codes = list(
            observations.exclude(main_cnae_code="")
            .order_by("main_cnae_code")
            .values_list("main_cnae_code", flat=True)
            .distinct()
        )
        cnae_descriptions = _cnae_descriptions(cnae_codes)
        cnae_options = [
            (code, _cnae_label(code, cnae_descriptions.get(code, ""))) for code in cnae_codes
        ]
        size_codes = list(
            observations.exclude(company_size_code="")
            .order_by("company_size_code")
            .values_list("company_size_code", flat=True)
            .distinct()
        )
    return {
        "projection": projection,
        "revision_options": revisions,
        "municipalities": municipalities,
        "cnae_options": cnae_options,
        "size_options": [(code, SIZE_LABELS.get(code, code)) for code in size_codes],
        "tax_options": CartographicObservation.TaxProfile.choices,
        "precision_options": AddressResolution.Method.choices,
        "branch_options": (("1", "Matriz"), ("2", "Filial")),
        "opening_options": OPENING_PERIODS.items(),
        "analysis_mode_options": ANALYSIS_MODES.items(),
        "map_metric_options": MAP_METRICS.items(),
    }


def parse_selection(filters: Mapping[str, str]) -> MapSelection:
    projection = published_projection()
    if projection is None:
        raise MapQueryError("A projeção cartográfica ainda não foi preparada.")
    revisions = _projection_revisions(projection)
    if not revisions:
        raise MapQueryError("A projeção publicada não possui competências consultáveis.")
    by_competence = {
        revision.window_competence.competence.strftime("%Y-%m"): revision for revision in revisions
    }
    competence = str(filters.get("competence", "")).strip() or next(reversed(by_competence))
    if not COMPETENCE_PATTERN.fullmatch(competence) or competence not in by_competence:
        raise MapQueryError("Competência inválida ou fora da projeção publicada.")

    municipality = str(filters.get("municipality", "")).strip()
    memberships = projection.historical_window.geographic_scope.scope_municipalities.select_related(
        "municipality"
    )
    allowed_municipalities = {membership.municipality.ibge_code for membership in memberships}
    if municipality and (
        not IBGE_PATTERN.fullmatch(municipality) or municipality not in allowed_municipalities
    ):
        raise MapQueryError("Município inválido ou fora do recorte cartográfico.")

    cnae = str(filters.get("cnae", "")).strip()
    if cnae and not CNAE_PATTERN.fullmatch(cnae):
        raise MapQueryError("CNAE principal deve possuir sete dígitos.")
    branch_type = str(filters.get("branch_type", "")).strip()
    if branch_type and branch_type not in BRANCH_LABELS:
        raise MapQueryError("Tipo de estabelecimento inválido.")
    company_size = str(filters.get("company_size", "")).strip()
    if company_size and company_size not in SIZE_LABELS:
        raise MapQueryError("Porte empresarial inválido.")
    tax_profile = str(filters.get("tax_profile", "")).strip()
    if tax_profile and tax_profile not in TAX_LABELS:
        raise MapQueryError("Perfil tributário inválido.")
    precision = str(filters.get("precision", "")).strip()
    if precision and precision not in PRECISION_LABELS:
        raise MapQueryError("Precisão espacial inválida.")
    opening_period = str(filters.get("opening_period", "")).strip()
    if opening_period and opening_period not in OPENING_PERIODS:
        raise MapQueryError("Período de abertura inválido.")
    analysis_mode = str(filters.get("analysis_mode", "stock")).strip() or "stock"
    if analysis_mode not in ANALYSIS_MODES:
        raise MapQueryError("Modo de análise inválido.")
    if analysis_mode == "dynamics" and opening_period:
        raise MapQueryError(
            "O período de abertura não pode ser combinado com a dinâmica territorial."
        )
    map_metric = str(filters.get("map_metric", "absolute")).strip() or "absolute"
    if map_metric not in MAP_METRICS:
        raise MapQueryError("Métrica municipal inválida.")
    if analysis_mode == "dynamics" and map_metric != "absolute":
        raise MapQueryError(
            "A métrica por mil habitantes não pode ser combinada com a dinâmica territorial."
        )

    return MapSelection(
        projection=projection,
        revision=by_competence[competence],
        competence=competence,
        municipality=municipality,
        cnae=cnae,
        branch_type=branch_type,
        company_size=company_size,
        tax_profile=tax_profile,
        precision=precision,
        opening_period=opening_period,
        analysis_mode=analysis_mode,
        map_metric=map_metric,
    )


def bootstrap_payload(filters: Mapping[str, str]) -> dict:
    selection = parse_selection(filters)
    observations = filtered_observations(selection)
    totals = observations.aggregate(
        establishments=Count("id"),
        companies=Count("company_id", distinct=True),
        municipalities=Count("municipality_id", distinct=True),
        headquarters=Count("id", filter=Q(branch_type="1")),
        branches=Count("id", filter=Q(branch_type="2")),
        address=Count("id", filter=Q(location_method=AddressResolution.Method.ADDRESS)),
        postal_code=Count("id", filter=Q(location_method=AddressResolution.Method.POSTAL_CODE)),
        unlocated=Count("id", filter=Q(location_method=AddressResolution.Method.UNLOCATED)),
        mei=Count("id", filter=Q(tax_profile=CartographicObservation.TaxProfile.MEI)),
        simples=Count("id", filter=Q(tax_profile=CartographicObservation.TaxProfile.SIMPLES)),
        regular=Count("id", filter=Q(tax_profile=CartographicObservation.TaxProfile.REGULAR)),
        unknown=Count("id", filter=Q(tax_profile=CartographicObservation.TaxProfile.UNKNOWN)),
    )
    located = totals["address"] + totals["postal_code"]
    coverage = located / totals["establishments"] if totals["establishments"] else 0.0
    municipality_rows = list(
        observations.values("municipality_id", "municipality__ibge_code", "municipality__name")
        .annotate(
            total=Count("id"),
            companies=Count("company_id", distinct=True),
            located=Count("id", filter=~Q(location_method=AddressResolution.Method.UNLOCATED)),
        )
        .order_by("-total", "municipality__name")
    )
    municipality_counts = {row["municipality_id"]: row for row in municipality_rows}
    population_by_municipality, population_reference = _population_reference(
        selection,
        totals=totals,
        municipality_counts=municipality_counts,
    )
    if selection.map_metric == "per_1000" and not population_reference["available"]:
        raise MapQueryError(
            "A referência demográfica ainda não foi sincronizada para todos os municípios."
        )
    dynamics_analysis = None
    if selection.analysis_mode == "dynamics":
        dynamics_analysis = _dynamics_analysis(
            selection,
            current_observations=observations,
            current_municipality_rows=municipality_rows,
        )
        rankings = dynamics_analysis["rankings"]
        municipality_dynamics = dynamics_analysis["municipalities"]
    else:
        rankings = _stock_rankings(
            observations,
            municipality_rows,
            population_by_municipality=population_by_municipality,
            map_metric=selection.map_metric,
        )
        municipality_dynamics = None
    return {
        "selection": selection.as_dict(),
        "projection": {
            "id": str(selection.projection.pk),
            "published_at": (
                selection.projection.published_at.isoformat()
                if selection.projection.published_at
                else None
            ),
            "algorithm_version": selection.projection.algorithm_version,
        },
        "indicators": {
            "establishments": totals["establishments"],
            "companies": totals["companies"],
            "municipalities": totals["municipalities"],
            "branches": {
                "headquarters": totals["headquarters"],
                "branches": totals["branches"],
            },
            "tax_profile": {
                "mei": totals["mei"],
                "simples": totals["simples"],
                "regular": totals["regular"],
                "unknown": totals["unknown"],
            },
            "geographic_coverage": {
                "located": located,
                "address": totals["address"],
                "postal_code": totals["postal_code"],
                "unlocated": totals["unlocated"],
                "percentage": round(coverage * 100, 2),
            },
        },
        "dynamics": dynamics_analysis["summary"] if dynamics_analysis else None,
        "population_reference": population_reference,
        "rankings": rankings,
        "municipalities": _municipality_feature_collection(
            selection,
            municipality_counts,
            dynamics=municipality_dynamics,
            population_by_municipality=population_by_municipality,
        ),
    }


def locations_payload(filters: Mapping[str, str]) -> dict:
    selection = parse_selection(filters)
    if selection.analysis_mode == "dynamics":
        return {
            "selection": selection.as_dict(),
            "level": "municipality",
            "requested_level": "municipality",
            "aggregation_reason": (
                "A dinâmica territorial experimental compara municípios; "
                "os pontos pertencem ao modo de concentração atual."
            ),
            "locations": {"type": "FeatureCollection", "features": []},
        }
    west, south, east, north = _parse_bounds(filters)
    zoom = _parse_float(filters.get("zoom"), "Zoom", minimum=0, maximum=24)
    observations = filtered_observations(selection).filter(
        latitude__isnull=False,
        longitude__isnull=False,
        longitude__gte=west,
        longitude__lte=east,
        latitude__gte=south,
        latitude__lte=north,
    )

    if zoom < 9:
        return {
            "selection": selection.as_dict(),
            "level": "municipality",
            "requested_level": "municipality",
            "aggregation_reason": "",
            "locations": _municipality_points(selection, observations),
        }
    if zoom < 12:
        return _postal_or_municipality_payload(
            selection, observations, requested_level="postal_code"
        )

    exact_rows = _limited_rows(
        observations.values("latitude", "longitude", "location_method", "cnefe_level")
        .annotate(total=Count("id"), companies=Count("company_id", distinct=True))
        .order_by("-total", "latitude", "longitude"),
        DETAIL_LIMIT,
    )
    if exact_rows is not None:
        return {
            "selection": selection.as_dict(),
            "level": "location",
            "requested_level": "location",
            "aggregation_reason": "",
            "locations": _point_collection(
                exact_rows,
                kind="location",
                latitude_key="latitude",
                longitude_key="longitude",
            ),
        }
    return _postal_or_municipality_payload(
        selection,
        observations,
        requested_level="location",
        reason="Mais de 5.000 localizações; agregação ampliada para preservar o conjunto completo.",
    )


def location_details_payload(filters: Mapping[str, str]) -> dict:
    selection = parse_selection(filters)
    if selection.analysis_mode == "dynamics":
        raise MapQueryError(
            "Detalhes de estabelecimentos estão disponíveis no modo de concentração atual."
        )
    latitude = _parse_decimal(filters.get("latitude"), "Latitude", -90, 90)
    longitude = _parse_decimal(filters.get("longitude"), "Longitude", -180, 180)
    location_method = str(filters.get("location_method", "")).strip()
    if location_method and location_method not in PRECISION_LABELS:
        raise MapQueryError("Método de localização inválido.")
    cnefe_level_text = str(filters.get("cnefe_level", "")).strip()
    cnefe_level = None
    if cnefe_level_text:
        try:
            cnefe_level = int(cnefe_level_text)
        except ValueError as exc:
            raise MapQueryError("Nível CNEFE inválido.") from exc
        if not 1 <= cnefe_level <= 6:
            raise MapQueryError("Nível CNEFE inválido.")
    try:
        page_number = max(1, int(str(filters.get("page", "1"))))
    except ValueError as exc:
        raise MapQueryError("Página inválida.") from exc

    observations = filtered_observations(selection).filter(
        latitude=latitude,
        longitude=longitude,
    )
    if location_method:
        observations = observations.filter(location_method=location_method)
    if cnefe_level is not None:
        observations = observations.filter(cnefe_level=cnefe_level)
    observations = observations.select_related("establishment", "company", "municipality").order_by(
        "establishment__cnpj"
    )
    paginator = Paginator(observations, DETAIL_PAGE_SIZE)
    page = paginator.get_page(page_number)
    establishment_ids = [item.establishment_id for item in page.object_list]
    company_ids = [item.company_id for item in page.object_list]
    establishment_snapshots = {
        item.establishment_id: item
        for item in EstablishmentSnapshot.objects.filter(
            revision=selection.revision,
            establishment_id__in=establishment_ids,
        )
    }
    company_snapshots = {
        item.company_id: item
        for item in CompanySnapshot.objects.filter(
            revision=selection.revision,
            company_id__in=company_ids,
        )
    }
    cnae_descriptions = _cnae_descriptions(
        [observation.main_cnae_code for observation in page.object_list]
    )
    items = []
    for observation in page.object_list:
        establishment_snapshot = establishment_snapshots.get(observation.establishment_id)
        company_snapshot = company_snapshots.get(observation.company_id)
        legal_name = company_snapshot.legal_name if company_snapshot else ""
        trade_name = establishment_snapshot.trade_name if establishment_snapshot else ""
        items.append(
            {
                "cnpj": observation.establishment.cnpj,
                "cnpj_basic": observation.company.cnpj_basic,
                "legal_name": legal_name,
                "trade_name": trade_name,
                "municipality": observation.municipality.name,
                "main_cnae_code": observation.main_cnae_code,
                "main_cnae_label": _cnae_label(
                    observation.main_cnae_code,
                    cnae_descriptions.get(observation.main_cnae_code, ""),
                ),
                "branch_type": BRANCH_LABELS.get(observation.branch_type, observation.branch_type),
                "precision": PRECISION_LABELS.get(
                    observation.location_method, observation.location_method
                ),
                "cnefe_level": observation.cnefe_level,
                "company_url": reverse(
                    "portal:company-detail",
                    kwargs={"cnpj_basic": observation.company.cnpj_basic},
                ),
            }
        )
    return {
        "selection": selection.as_dict(),
        "coordinate": {"latitude": float(latitude), "longitude": float(longitude)},
        "items": items,
        "pagination": {
            "page": page.number,
            "pages": paginator.num_pages,
            "total": paginator.count,
            "has_previous": page.has_previous(),
            "has_next": page.has_next(),
        },
    }


def filtered_observations(
    selection: MapSelection,
    *,
    revision: CompetenceRevision | None = None,
) -> QuerySet:
    queryset = CartographicObservation.objects.filter(
        projection=selection.projection,
        revision=revision or selection.revision,
    )
    if selection.municipality:
        queryset = queryset.filter(municipality__ibge_code=selection.municipality)
    if selection.cnae:
        queryset = queryset.filter(main_cnae_code=selection.cnae)
    if selection.branch_type:
        queryset = queryset.filter(branch_type=selection.branch_type)
    if selection.company_size:
        queryset = queryset.filter(company_size_code=selection.company_size)
    if selection.tax_profile:
        queryset = queryset.filter(tax_profile=selection.tax_profile)
    if selection.precision:
        queryset = queryset.filter(location_method=selection.precision)
    if selection.opening_period:
        start, end = _opening_date_range(selection)
        queryset = queryset.filter(activity_start_date__range=(start, end))
    return queryset


def _stock_rankings(
    observations: QuerySet,
    municipality_rows: list[dict],
    *,
    population_by_municipality: dict[int, int],
    map_metric: str,
) -> dict:
    cnae_ranking = list(
        observations.exclude(main_cnae_code="")
        .values("main_cnae_code")
        .annotate(total=Count("id"), companies=Count("company_id", distinct=True))
        .order_by("-total", "main_cnae_code")[:10]
    )
    cnae_descriptions = _cnae_descriptions([row["main_cnae_code"] for row in cnae_ranking])
    municipality_ranking = []
    for row in municipality_rows:
        population = population_by_municipality.get(row["municipality_id"])
        municipality_ranking.append(
            {
                "ibge_code": row["municipality__ibge_code"],
                "name": row["municipality__name"],
                "establishments": row["total"],
                "companies": row["companies"],
                "population": population,
                "establishments_per_1000": _per_1000(row["total"], population),
                "companies_per_1000": _per_1000(row["companies"], population),
                "coverage_percentage": round(
                    (row["located"] / row["total"] * 100) if row["total"] else 0,
                    2,
                ),
            }
        )
    if map_metric == "per_1000":
        municipality_ranking.sort(
            key=lambda row: (
                -(row["establishments_per_1000"] or 0),
                -row["establishments"],
                row["name"],
            )
        )
    return {
        "municipalities": municipality_ranking[:10],
        "cnaes": [
            {
                "code": row["main_cnae_code"],
                "formatted_code": _format_cnae_code(row["main_cnae_code"]),
                "description": cnae_descriptions.get(row["main_cnae_code"], ""),
                "label": _cnae_label(
                    row["main_cnae_code"],
                    cnae_descriptions.get(row["main_cnae_code"], ""),
                ),
                "establishments": row["total"],
                "companies": row["companies"],
            }
            for row in cnae_ranking
        ],
    }


def _dynamics_analysis(
    selection: MapSelection,
    *,
    current_observations: QuerySet,
    current_municipality_rows: list[dict],
) -> dict:
    previous_revision = _previous_revision(selection)
    previous_observations = filtered_observations(selection, revision=previous_revision)
    previous_municipality_rows = list(
        previous_observations.values(
            "municipality_id",
            "municipality__ibge_code",
            "municipality__name",
        )
        .annotate(total=Count("id"))
        .order_by()
    )
    comparison_events = ChangeEvent.objects.filter(
        historical_window=selection.projection.historical_window,
        from_revision=previous_revision,
        to_revision=selection.revision,
        establishment_id__isnull=False,
    )
    opening_events = comparison_events.filter(event_type="ESTABLISHMENT_OPENED")
    closing_events = comparison_events.filter(event_type="ESTABLISHMENT_CLOSED")
    opened_observations = current_observations.filter(
        establishment_id__in=opening_events.values("establishment_id")
    )
    closed_observations = previous_observations.filter(
        establishment_id__in=closing_events.values("establishment_id")
    )

    current_by_municipality = {row["municipality_id"]: row for row in current_municipality_rows}
    previous_by_municipality = {row["municipality_id"]: row for row in previous_municipality_rows}
    openings_by_municipality = _counts_by(opened_observations, "municipality_id")
    closures_by_municipality = _counts_by(closed_observations, "municipality_id")
    municipality_ids = (
        set(current_by_municipality)
        | set(previous_by_municipality)
        | set(openings_by_municipality)
        | set(closures_by_municipality)
    )
    municipality_dynamics = {}
    municipality_ranking = []
    for municipality_id in municipality_ids:
        current = current_by_municipality.get(municipality_id, {})
        previous = previous_by_municipality.get(municipality_id, {})
        current_total = current.get("total", 0)
        previous_total = previous.get("total", 0)
        openings = openings_by_municipality.get(municipality_id, 0)
        closures = closures_by_municipality.get(municipality_id, 0)
        stock_change = current_total - previous_total
        lifecycle_balance = openings - closures
        row = {
            "ibge_code": current.get("municipality__ibge_code")
            or previous.get("municipality__ibge_code"),
            "name": current.get("municipality__name") or previous.get("municipality__name"),
            "previous_establishments": previous_total,
            "establishments": current_total,
            "stock_change": stock_change,
            "change_percentage": _percentage_change(previous_total, stock_change),
            "openings": openings,
            "closures": closures,
            "lifecycle_balance": lifecycle_balance,
            "other_effects": stock_change - lifecycle_balance,
        }
        municipality_dynamics[municipality_id] = row
        if stock_change or openings or closures:
            municipality_ranking.append(row)
    municipality_ranking.sort(
        key=lambda row: (-abs(row["stock_change"]), -row["stock_change"], row["name"])
    )

    cnae_dynamics = _cnae_dynamics(
        current_observations=current_observations,
        previous_observations=previous_observations,
        opened_observations=opened_observations,
        closed_observations=closed_observations,
    )
    current_total = sum(row["total"] for row in current_municipality_rows)
    previous_total = sum(row["total"] for row in previous_municipality_rows)
    openings = sum(openings_by_municipality.values())
    closures = sum(closures_by_municipality.values())
    stock_change = current_total - previous_total
    lifecycle_balance = openings - closures
    scale_max = max(
        [abs(row["stock_change"]) for row in municipality_dynamics.values()],
        default=1,
    )
    return {
        "summary": {
            "experimental": True,
            "from_competence": previous_revision.window_competence.competence.strftime("%Y-%m"),
            "to_competence": selection.competence,
            "previous_establishments": previous_total,
            "current_establishments": current_total,
            "stock_change": stock_change,
            "change_percentage": _percentage_change(previous_total, stock_change),
            "openings": openings,
            "closures": closures,
            "lifecycle_balance": lifecycle_balance,
            "other_effects": stock_change - lifecycle_balance,
            "scale_max": max(scale_max, 1),
        },
        "municipalities": municipality_dynamics,
        "rankings": {
            "municipalities": municipality_ranking[:10],
            "cnaes": cnae_dynamics[:10],
        },
    }


def _cnae_dynamics(
    *,
    current_observations: QuerySet,
    previous_observations: QuerySet,
    opened_observations: QuerySet,
    closed_observations: QuerySet,
) -> list[dict]:
    current = _counts_by(current_observations.exclude(main_cnae_code=""), "main_cnae_code")
    previous = _counts_by(previous_observations.exclude(main_cnae_code=""), "main_cnae_code")
    openings = _counts_by(opened_observations.exclude(main_cnae_code=""), "main_cnae_code")
    closures = _counts_by(closed_observations.exclude(main_cnae_code=""), "main_cnae_code")
    codes = set(current) | set(previous) | set(openings) | set(closures)
    descriptions = _cnae_descriptions(list(codes))
    rows = []
    for code in codes:
        current_total = current.get(code, 0)
        previous_total = previous.get(code, 0)
        stock_change = current_total - previous_total
        opened = openings.get(code, 0)
        closed = closures.get(code, 0)
        if not (stock_change or opened or closed):
            continue
        lifecycle_balance = opened - closed
        rows.append(
            {
                "code": code,
                "formatted_code": _format_cnae_code(code),
                "description": descriptions.get(code, ""),
                "label": _cnae_label(code, descriptions.get(code, "")),
                "previous_establishments": previous_total,
                "establishments": current_total,
                "stock_change": stock_change,
                "change_percentage": _percentage_change(previous_total, stock_change),
                "openings": opened,
                "closures": closed,
                "other_effects": stock_change - lifecycle_balance,
            }
        )
    rows.sort(key=lambda row: (-abs(row["stock_change"]), -row["stock_change"], row["code"]))
    return rows


def _counts_by(queryset: QuerySet, field: str) -> dict:
    return {
        row[field]: row["total"]
        for row in queryset.values(field).annotate(total=Count("id")).order_by()
    }


def _percentage_change(previous: int, change: int) -> float | None:
    return round(change / previous * 100, 2) if previous else None


def _per_1000(value: int, population: int | None) -> float | None:
    return round(value / population * 1000, 2) if population else None


def _population_reference(
    selection: MapSelection,
    *,
    totals: dict,
    municipality_counts: dict[int, dict],
) -> tuple[dict[int, int], dict]:
    memberships = list(
        selection.projection.historical_window.geographic_scope.scope_municipalities.select_related(
            "municipality"
        )
    )
    scope_municipality_ids = [membership.municipality_id for membership in memberships]
    expected = len(scope_municipality_ids)
    latest_complete_reference = (
        MunicipalityPopulation.objects.filter(municipality_id__in=scope_municipality_ids)
        .values("reference_year", "source_id")
        .annotate(total=Count("municipality_id", distinct=True))
        .filter(total=expected)
        .order_by("-reference_year", "-source__created_at")
        .first()
    )
    if latest_complete_reference is None:
        return {}, {
            "available": False,
            "reference_year": None,
            "source": "",
            "source_url": "",
            "population": None,
            "establishments_per_1000": None,
            "companies_per_1000": None,
            "municipalities_with_population": 0,
            "expected_municipalities": expected,
            "scale_max": None,
        }

    rows = list(
        MunicipalityPopulation.objects.filter(
            municipality_id__in=scope_municipality_ids,
            reference_year=latest_complete_reference["reference_year"],
            source_id=latest_complete_reference["source_id"],
        ).select_related("source")
    )
    population_by_municipality = {row.municipality_id: row.population for row in rows}
    selected_municipality_ids = scope_municipality_ids
    if selection.municipality:
        selected_municipality_ids = [
            membership.municipality_id
            for membership in memberships
            if membership.municipality.ibge_code == selection.municipality
        ]
    selected_population = sum(
        population_by_municipality[municipality_id] for municipality_id in selected_municipality_ids
    )
    municipal_ratios = [
        _per_1000(
            municipality_counts.get(municipality_id, {"total": 0})["total"],
            population_by_municipality[municipality_id],
        )
        or 0
        for municipality_id in scope_municipality_ids
    ]
    source = rows[0].source
    return population_by_municipality, {
        "available": True,
        "reference_year": latest_complete_reference["reference_year"],
        "source": source.version,
        "source_url": source.manifest.get("url", ""),
        "population": selected_population,
        "establishments_per_1000": _per_1000(totals["establishments"], selected_population),
        "companies_per_1000": _per_1000(totals["companies"], selected_population),
        "municipalities_with_population": len(population_by_municipality),
        "expected_municipalities": expected,
        "scale_max": max(municipal_ratios, default=0),
    }


def _previous_revision(selection: MapSelection) -> CompetenceRevision:
    revisions = _projection_revisions(selection.projection)
    revision_ids = [revision.pk for revision in revisions]
    try:
        current_index = revision_ids.index(selection.revision.pk)
    except ValueError as exc:
        raise MapQueryError("A competência selecionada não pertence à projeção publicada.") from exc
    if current_index == 0:
        raise MapQueryError(
            "A primeira competência é o baseline e não possui comparação territorial anterior."
        )
    return revisions[current_index - 1]


def _opening_date_range(selection: MapSelection) -> tuple[date, date]:
    competence = selection.revision.window_competence.competence
    months = int(selection.opening_period)
    start_index = competence.year * 12 + competence.month - months
    start = date(start_index // 12, start_index % 12 + 1, 1)
    end = date(competence.year, competence.month, monthrange(competence.year, competence.month)[1])
    return start, end


def _cnae_descriptions(codes: list[str]) -> dict[str, str]:
    clean_codes = {code for code in codes if code}
    return dict(
        CnaeSubclass.objects.filter(code__in=clean_codes).values_list("code", "description")
    )


def _format_cnae_code(code: str) -> str:
    if not CNAE_PATTERN.fullmatch(code):
        return code
    return f"{code[:4]}-{code[4]}/{code[5:]}"


def _cnae_label(code: str, description: str) -> str:
    formatted = _format_cnae_code(code)
    return f"{formatted} — {description}" if description else formatted


def _postal_or_municipality_payload(
    selection: MapSelection,
    observations: QuerySet,
    *,
    requested_level: str,
    reason: str = "",
) -> dict:
    postal_rows = _limited_rows(
        observations.exclude(postal_code="")
        .values("municipality_id", "postal_code")
        .annotate(
            representative_resolution_id=Min("address_resolution_id"),
            total=Count("id"),
            companies=Count("company_id", distinct=True),
        )
        .order_by("-total", "postal_code"),
        DETAIL_LIMIT,
    )
    if postal_rows is not None:
        _attach_resolution_coordinates(postal_rows)
        fallback_reason = reason
        if requested_level == "postal_code":
            fallback_reason = ""
        return {
            "selection": selection.as_dict(),
            "level": "postal_code",
            "requested_level": requested_level,
            "aggregation_reason": fallback_reason,
            "locations": _point_collection(
                postal_rows,
                kind="postal_code",
                latitude_key="latitude",
                longitude_key="longitude",
            ),
        }
    return {
        "selection": selection.as_dict(),
        "level": "municipality",
        "requested_level": requested_level,
        "aggregation_reason": (
            "Mais de 5.000 agregados por CEP; agregação ampliada para municípios."
        ),
        "locations": _municipality_points(selection, observations),
    }


def _attach_resolution_coordinates(rows: list[dict]) -> None:
    resolutions = AddressResolution.objects.in_bulk(
        row["representative_resolution_id"] for row in rows
    )
    for row in rows:
        resolution = resolutions[row.pop("representative_resolution_id")]
        row["latitude"] = resolution.latitude
        row["longitude"] = resolution.longitude


def _municipality_points(selection: MapSelection, observations: QuerySet) -> dict:
    counts = {
        row["municipality_id"]: row
        for row in observations.values("municipality_id")
        .annotate(total=Count("id"), companies=Count("company_id", distinct=True))
        .order_by()
    }
    features = []
    for boundary in MunicipalityBoundary.objects.filter(
        source=selection.projection.boundary_source,
        municipality_id__in=counts,
    ).select_related("municipality"):
        row = counts[boundary.municipality_id]
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        float(boundary.center_longitude),
                        float(boundary.center_latitude),
                    ],
                },
                "properties": {
                    "kind": "municipality",
                    "ibge_code": boundary.municipality.ibge_code,
                    "name": boundary.municipality.name,
                    "total": row["total"],
                    "companies": row["companies"],
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _municipality_feature_collection(
    selection: MapSelection,
    municipality_counts: dict[int, dict],
    *,
    dynamics: dict[int, dict] | None = None,
    population_by_municipality: dict[int, int] | None = None,
) -> dict:
    features = []
    boundaries = MunicipalityBoundary.objects.filter(
        source=selection.projection.boundary_source
    ).select_related("municipality")
    for boundary in boundaries:
        row = municipality_counts.get(
            boundary.municipality_id,
            {"total": 0, "companies": 0, "located": 0},
        )
        coverage = row["located"] / row["total"] * 100 if row["total"] else 0
        dynamic_values = (dynamics or {}).get(
            boundary.municipality_id,
            {
                "previous_establishments": 0,
                "stock_change": 0,
                "change_percentage": None,
                "openings": 0,
                "closures": 0,
                "lifecycle_balance": 0,
                "other_effects": 0,
            },
        )
        population = (population_by_municipality or {}).get(boundary.municipality_id)
        features.append(
            {
                "type": "Feature",
                "id": boundary.municipality.ibge_code,
                "geometry": boundary.geometry,
                "properties": {
                    "ibge_code": boundary.municipality.ibge_code,
                    "name": boundary.municipality.name,
                    "bbox": boundary.bbox,
                    "establishments": row["total"],
                    "companies": row["companies"],
                    "coverage_percentage": round(coverage, 2),
                    "population": population,
                    "establishments_per_1000": _per_1000(row["total"], population),
                    "companies_per_1000": _per_1000(row["companies"], population),
                    **{
                        key: dynamic_values[key]
                        for key in (
                            "previous_establishments",
                            "stock_change",
                            "change_percentage",
                            "openings",
                            "closures",
                            "lifecycle_balance",
                            "other_effects",
                        )
                    },
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _point_collection(
    rows: list[dict],
    *,
    kind: str,
    latitude_key: str,
    longitude_key: str,
) -> dict:
    features = []
    for row in rows:
        properties = {
            key: value
            for key, value in row.items()
            if key not in {latitude_key, longitude_key, "municipality_id"}
        }
        properties["kind"] = kind
        # Mapbox quantizes coordinates exposed by rendered-feature click events.
        # Preserve the database coordinates as properties so the detail lookup
        # can use the exact six-decimal identity of the selected location.
        properties["detail_latitude"] = float(row[latitude_key])
        properties["detail_longitude"] = float(row[longitude_key])
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        float(row[longitude_key]),
                        float(row[latitude_key]),
                    ],
                },
                "properties": properties,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _projection_revisions(
    projection: CartographicProjection,
) -> list[CompetenceRevision]:
    return list(
        CompetenceRevision.objects.filter(
            window_competence__historical_window=projection.historical_window,
            status__in=CompetenceRevision.ACTIVE_STATUSES,
        )
        .select_related("window_competence")
        .order_by("window_competence__competence")
    )


def _parse_bounds(filters: Mapping[str, str]) -> tuple[float, float, float, float]:
    west = _parse_float(filters.get("west"), "Limite oeste", -180, 180)
    south = _parse_float(filters.get("south"), "Limite sul", -90, 90)
    east = _parse_float(filters.get("east"), "Limite leste", -180, 180)
    north = _parse_float(filters.get("north"), "Limite norte", -90, 90)
    if west >= east or south >= north:
        raise MapQueryError("A caixa visível possui limites invertidos ou vazios.")
    return west, south, east, north


def _parse_float(
    value: object,
    label: str,
    minimum: float,
    maximum: float,
) -> float:
    try:
        parsed = float(str(value))
    except (TypeError, ValueError) as exc:
        raise MapQueryError(f"{label} inválido.") from exc
    if not minimum <= parsed <= maximum:
        raise MapQueryError(f"{label} fora do intervalo permitido.")
    return parsed


def _parse_decimal(
    value: object,
    label: str,
    minimum: int,
    maximum: int,
) -> Decimal:
    try:
        parsed = Decimal(str(value)).quantize(Decimal("0.000001"))
    except (InvalidOperation, TypeError) as exc:
        raise MapQueryError(f"{label} inválida.") from exc
    if not minimum <= parsed <= maximum:
        raise MapQueryError(f"{label} fora do intervalo permitido.")
    return parsed


def _limited_rows(queryset: QuerySet, limit: int) -> list[dict] | None:
    rows = list(queryset[: limit + 1])
    return rows if len(rows) <= limit else None
