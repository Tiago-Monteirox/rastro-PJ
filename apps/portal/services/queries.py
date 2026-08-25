from __future__ import annotations

import re

from django.db.models import Count, F, Q, Sum
from django.shortcuts import get_object_or_404

from apps.changes.models import ChangeEvent, RegionalMonthlyMetric
from apps.pipeline.models import (
    CompetenceRevision,
    DataQualityIssue,
    HistoricalWindow,
    ImportBatch,
)
from apps.pipeline.services.normalization import normalize_search_text
from apps.registry.models import (
    Company,
    CompanySnapshot,
    Establishment,
    EstablishmentSnapshot,
    PartnerSnapshot,
)

from ..models import Watchlist

SEARCH_STATUS_OPTIONS = (
    ("01", "Nula"),
    ("02", "Ativa"),
    ("03", "Suspensa"),
    ("04", "Inapta"),
    ("08", "Baixada"),
)
COMPANY_SIZE_LABELS = {
    "00": "Não informado",
    "01": "Microempresa",
    "03": "Empresa de pequeno porte",
    "05": "Demais",
    None: "Não informado",
    "": "Não informado",
}


def dashboard_context(filters: dict[str, str] | None = None) -> dict:
    filters = filters or {}
    window = _active_window()
    revisions = list(_active_revisions(window))
    latest = revisions[-1] if revisions else None
    selected_competence = filters.get("competence", "").strip()
    selected_revision = next(
        (
            revision
            for revision in revisions
            if revision.window_competence.competence.strftime("%Y-%m") == selected_competence
        ),
        latest,
    )
    selected_index = revisions.index(selected_revision) if selected_revision else -1
    previous_revision = revisions[selected_index - 1] if selected_index > 0 else None

    municipalities = []
    if window:
        municipalities = [
            membership.municipality
            for membership in window.geographic_scope.scope_municipalities.select_related(
                "municipality"
            ).order_by("municipality__name")
        ]
    municipality_codes = {municipality.ibge_code for municipality in municipalities}
    selected_municipality = filters.get("municipality", "").strip()
    if selected_municipality not in municipality_codes:
        selected_municipality = ""

    cnae_options = []
    if selected_revision:
        cnae_options = list(
            RegionalMonthlyMetric.objects.filter(
                revision=selected_revision,
                metric_type="REGIONAL_ESTABLISHMENTS_BY_CNAE",
            )
            .exclude(cnae_code__isnull=True)
            .exclude(cnae_code="")
            .values_list("cnae_code", flat=True)
            .order_by("cnae_code")
        )
    selected_cnae = re.sub(r"\D", "", filters.get("cnae", ""))
    if selected_cnae not in set(cnae_options):
        selected_cnae = ""

    metric_values = {}
    regional_establishments = EstablishmentSnapshot.objects.none()
    if selected_revision:
        metric_values = dict(
            RegionalMonthlyMetric.objects.filter(
                revision=selected_revision,
                metric_type__in=(
                    "REGIONAL_COMPANIES_TOTAL",
                    "REGIONAL_ESTABLISHMENTS_TOTAL",
                ),
            ).values_list("metric_type", "value")
        )
        regional_establishments = EstablishmentSnapshot.objects.filter(
            revision=selected_revision,
            is_in_region=True,
        )
        if selected_municipality:
            regional_establishments = regional_establishments.filter(
                municipality__ibge_code=selected_municipality
            )
        if selected_cnae:
            regional_establishments = regional_establishments.filter(main_cnae_code=selected_cnae)

    if selected_municipality or selected_cnae:
        companies = regional_establishments.values("establishment__company_id").distinct().count()
        establishments = regional_establishments.count()
    else:
        companies = metric_values.get("REGIONAL_COMPANIES_TOTAL", 0)
        establishments = metric_values.get("REGIONAL_ESTABLISHMENTS_TOTAL", 0)

    eligible_company_ids = regional_establishments.values("establishment__company_id")
    eligible_establishment_ids = regional_establishments.values("establishment_id")
    interval_events = ChangeEvent.objects.none()
    event_counts = []
    if window and selected_revision:
        interval_events = ChangeEvent.objects.filter(
            historical_window=window,
            to_revision=selected_revision,
        )
        if selected_municipality or selected_cnae:
            interval_events = interval_events.filter(
                Q(company_id__in=eligible_company_ids)
                | Q(establishment_id__in=eligible_establishment_ids)
                | Q(participation__company_id__in=eligible_company_ids)
            )
        event_counts = list(
            interval_events.values("event_type")
            .annotate(total=Count("id"))
            .order_by("-total", "event_type")
        )

    event_totals = {item["event_type"]: item["total"] for item in event_counts}

    status_distribution = []
    size_distribution = []
    if selected_revision:
        if not selected_municipality and not selected_cnae:
            status_rows = RegionalMonthlyMetric.objects.filter(
                revision=selected_revision,
                metric_type="REGIONAL_ESTABLISHMENTS_BY_STATUS",
            ).values("registration_status_code", "value")
            size_rows = RegionalMonthlyMetric.objects.filter(
                revision=selected_revision,
                metric_type="REGIONAL_COMPANIES_BY_SIZE",
            ).values("company_size_code", "value")
        else:
            status_rows = regional_establishments.values("registration_status_code").annotate(
                value=Count("id")
            )
            size_rows = (
                CompanySnapshot.objects.filter(
                    revision=selected_revision,
                    company_id__in=eligible_company_ids,
                )
                .values("company_size_code")
                .annotate(value=Count("id"))
            )
        status_labels = dict(SEARCH_STATUS_OPTIONS)
        status_distribution = sorted(
            (
                {
                    "code": row["registration_status_code"] or "—",
                    "label": status_labels.get(row["registration_status_code"], "Não informada"),
                    "total": row["value"],
                }
                for row in status_rows
            ),
            key=lambda item: (-item["total"], item["code"]),
        )
        size_distribution = sorted(
            (
                {
                    "code": row["company_size_code"] or "—",
                    "label": COMPANY_SIZE_LABELS.get(
                        row["company_size_code"], row["company_size_code"] or "Não informado"
                    ),
                    "total": row["value"],
                }
                for row in size_rows
            ),
            key=lambda item: (-item["total"], item["code"]),
        )

    trend_by_competence = {}
    if revisions:
        if not selected_municipality and not selected_cnae:
            trend_rows = RegionalMonthlyMetric.objects.filter(
                revision__in=revisions,
                metric_type="REGIONAL_ESTABLISHMENTS_TOTAL",
            ).values("revision_id", "value")
        elif selected_municipality and not selected_cnae:
            trend_rows = RegionalMonthlyMetric.objects.filter(
                revision__in=revisions,
                metric_type="REGIONAL_ESTABLISHMENTS_BY_MUNICIPALITY",
                municipality__ibge_code=selected_municipality,
            ).values("revision_id", "value")
        elif selected_cnae and not selected_municipality:
            trend_rows = RegionalMonthlyMetric.objects.filter(
                revision__in=revisions,
                metric_type="REGIONAL_ESTABLISHMENTS_BY_CNAE",
                cnae_code=selected_cnae,
            ).values("revision_id", "value")
        else:
            trend_rows = (
                EstablishmentSnapshot.objects.filter(
                    revision__in=revisions,
                    is_in_region=True,
                    municipality__ibge_code=selected_municipality,
                    main_cnae_code=selected_cnae,
                )
                .values("revision_id")
                .annotate(value=Count("id"))
            )
        trend_by_competence = {row["revision_id"]: row["value"] for row in trend_rows}
    establishment_trend = [
        {
            "competence": revision.window_competence.competence,
            "total": trend_by_competence.get(revision.pk, 0),
        }
        for revision in revisions
    ]

    opening_closing_rows = []
    if window:
        opening_closing_events = ChangeEvent.objects.filter(
            historical_window=window,
            event_type__in=("ESTABLISHMENT_OPENED", "ESTABLISHMENT_CLOSED"),
        )
        if selected_municipality or selected_cnae:
            opening_closing_events = opening_closing_events.filter(
                establishment__snapshots__revision=F("to_revision"),
                establishment__snapshots__is_in_region=True,
            )
            if selected_municipality:
                opening_closing_events = opening_closing_events.filter(
                    establishment__snapshots__municipality__ibge_code=selected_municipality
                )
            if selected_cnae:
                opening_closing_events = opening_closing_events.filter(
                    establishment__snapshots__main_cnae_code=selected_cnae
                )
        opening_closing_rows = list(
            opening_closing_events.values(
                "to_revision_id",
                "event_type",
            ).annotate(total=Count("id"))
        )
    opening_closing_totals = {
        (row["to_revision_id"], row["event_type"]): row["total"] for row in opening_closing_rows
    }
    opening_closing_series = [
        {
            "competence": revision.window_competence.competence,
            "opened": opening_closing_totals.get((revision.pk, "ESTABLISHMENT_OPENED"), 0),
            "closed": opening_closing_totals.get((revision.pk, "ESTABLISHMENT_CLOSED"), 0),
        }
        for revision in revisions
    ]

    def cnae_counts(revision):
        if not revision:
            return {}
        if not selected_municipality:
            rows = RegionalMonthlyMetric.objects.filter(
                revision=revision,
                metric_type="REGIONAL_ESTABLISHMENTS_BY_CNAE",
            )
            if selected_cnae:
                rows = rows.filter(cnae_code=selected_cnae)
            return dict(rows.values_list("cnae_code", "value"))
        rows = EstablishmentSnapshot.objects.filter(
            revision=revision,
            is_in_region=True,
            municipality__ibge_code=selected_municipality,
        )
        if selected_cnae:
            rows = rows.filter(main_cnae_code=selected_cnae)
        return dict(
            rows.values("main_cnae_code")
            .annotate(total=Count("id"))
            .values_list("main_cnae_code", "total")
        )

    current_cnaes = cnae_counts(selected_revision)
    previous_cnaes = cnae_counts(previous_revision)
    cnae_changes = [
        {
            "code": code or "—",
            "current": current_cnaes.get(code, 0),
            "previous": previous_cnaes.get(code, 0),
            "delta": current_cnaes.get(code, 0) - previous_cnaes.get(code, 0),
        }
        for code in current_cnaes.keys() | previous_cnaes.keys()
    ]
    cnae_growth = sorted(
        (item for item in cnae_changes if item["delta"] > 0),
        key=lambda item: (-item["delta"], item["code"]),
    )[:5]
    cnae_reduction = sorted(
        (item for item in cnae_changes if item["delta"] < 0),
        key=lambda item: (item["delta"], item["code"]),
    )[:5]

    recent_companies = []
    if selected_revision:
        seen_company_ids = set()
        recent_events = interval_events.select_related(
            "company",
            "establishment__company",
            "participation__company",
        ).order_by("-detected_at", "-id")[:200]
        for event in recent_events:
            company = event.company
            if not company and event.establishment:
                company = event.establishment.company
            if not company and event.participation:
                company = event.participation.company
            if not company or company.pk in seen_company_ids:
                continue
            seen_company_ids.add(company.pk)
            recent_companies.append({"company": company, "event": event})
            if len(recent_companies) == 8:
                break

    return {
        "active_window": window,
        "published_competences": len(revisions),
        "companies": companies,
        "establishments": establishments,
        "event_total": sum(item["total"] for item in event_counts),
        "event_counts": event_counts[:10],
        "opened": event_totals.get("ESTABLISHMENT_OPENED", 0),
        "closed": event_totals.get("ESTABLISHMENT_CLOSED", 0),
        "status_distribution": status_distribution,
        "size_distribution": size_distribution,
        "establishment_trend": establishment_trend,
        "opening_closing_series": opening_closing_series,
        "cnae_growth": cnae_growth,
        "cnae_reduction": cnae_reduction,
        "recent_companies": recent_companies,
        "latest_revision": latest,
        "selected_revision": selected_revision,
        "revision_options": revisions,
        "municipalities": municipalities,
        "cnae_options": cnae_options,
        "filters": {
            "competence": (
                selected_revision.window_competence.competence.strftime("%Y-%m")
                if selected_revision
                else ""
            ),
            "municipality": selected_municipality,
            "cnae": selected_cnae,
        },
        "latest_batches": ImportBatch.objects.order_by("-started_at")[:5],
    }


def search_company_context(query: str, filters: dict[str, str] | None = None) -> dict:
    query = query.strip()
    filters = filters or {}
    window = _active_window()
    revision = _active_revisions(window).last() if window else None

    municipalities = []
    if window:
        municipalities = [
            membership.municipality
            for membership in window.geographic_scope.scope_municipalities.select_related(
                "municipality"
            ).order_by("municipality__name")
        ]
    municipality_codes = {municipality.ibge_code for municipality in municipalities}
    selected_municipality = filters.get("municipality", "").strip()
    if selected_municipality not in municipality_codes:
        selected_municipality = ""

    status_codes = {code for code, _label in SEARCH_STATUS_OPTIONS}
    selected_status = filters.get("status", "").strip()
    if selected_status not in status_codes:
        selected_status = ""

    selected_cnae = re.sub(r"\D", "", filters.get("cnae", ""))
    if len(selected_cnae) != 7:
        selected_cnae = ""

    selected_filters = {
        "municipality": selected_municipality,
        "status": selected_status,
        "cnae": selected_cnae,
    }
    has_search = bool(query or any(selected_filters.values()))
    base_context = {
        "query": query,
        "results": [],
        "active_window": window,
        "revision": revision,
        "municipalities": municipalities,
        "status_options": SEARCH_STATUS_OPTIONS,
        "filters": selected_filters,
        "has_search": has_search,
    }
    if not has_search or not revision:
        return base_context

    company_ids = set()
    digits = re.sub(r"\D", "", query)
    is_cnpj_query = bool(re.fullmatch(r"[\d\s./-]+", query)) and len(digits) in (8, 14)
    if is_cnpj_query and len(digits) == 8:
        company_ids.update(Company.objects.filter(cnpj_basic=digits).values_list("id", flat=True))
    elif is_cnpj_query and len(digits) == 14:
        company_ids.update(
            Establishment.objects.filter(cnpj=digits).values_list("company_id", flat=True)
        )
    if len(query) >= 2 and not is_cnpj_query:
        normalized = normalize_search_text(query)
        prefix_ids = set(
            CompanySnapshot.objects.filter(
                revision=revision, legal_name_search__startswith=normalized
            ).values_list("company_id", flat=True)[:50]
        )
        prefix_ids.update(
            EstablishmentSnapshot.objects.filter(
                revision=revision, trade_name_search__startswith=normalized
            ).values_list("establishment__company_id", flat=True)[:50]
        )
        company_ids.update(prefix_ids)
        if not prefix_ids:
            company_ids.update(
                CompanySnapshot.objects.filter(
                    revision=revision, legal_name_search__icontains=normalized
                ).values_list("company_id", flat=True)[:50]
            )
            company_ids.update(
                EstablishmentSnapshot.objects.filter(
                    revision=revision, trade_name_search__icontains=normalized
                ).values_list("establishment__company_id", flat=True)[:50]
            )
    snapshots_query = CompanySnapshot.objects.filter(revision=revision).select_related("company")
    if query:
        snapshots_query = snapshots_query.filter(company_id__in=company_ids)

    regional_filter = EstablishmentSnapshot.objects.filter(revision=revision, is_in_region=True)
    if selected_municipality:
        regional_filter = regional_filter.filter(municipality__ibge_code=selected_municipality)
    if selected_status:
        regional_filter = regional_filter.filter(registration_status_code=selected_status)
    if selected_cnae:
        regional_filter = regional_filter.filter(main_cnae_code=selected_cnae)
    if any(selected_filters.values()):
        snapshots_query = snapshots_query.filter(
            company_id__in=regional_filter.values("establishment__company_id")
        )

    selected_snapshots = list(snapshots_query.order_by("legal_name")[:50])
    result_company_ids = [snapshot.company_id for snapshot in selected_snapshots]
    regional_counts = dict(
        EstablishmentSnapshot.objects.filter(
            revision=revision,
            establishment__company_id__in=result_company_ids,
            is_in_region=True,
        )
        .values("establishment__company_id")
        .annotate(total=Count("id"))
        .values_list("establishment__company_id", "total")
    )
    base_context["results"] = [
        {
            "company": snapshot.company,
            "snapshot": snapshot,
            "regional_establishments": regional_counts.get(snapshot.company_id, 0),
        }
        for snapshot in selected_snapshots
    ]
    return base_context


def company_detail_context(cnpj_basic: str, user=None) -> dict:
    company = get_object_or_404(Company, cnpj_basic=cnpj_basic)
    window = _active_window()
    revisions = _active_revisions(window)
    latest = revisions.last() if window else None
    company_snapshot = None
    establishments = EstablishmentSnapshot.objects.none()
    partners = PartnerSnapshot.objects.none()
    if latest:
        company_snapshot = CompanySnapshot.objects.filter(revision=latest, company=company).first()
        establishments = (
            EstablishmentSnapshot.objects.filter(revision=latest, establishment__company=company)
            .select_related("establishment", "municipality")
            .order_by("-is_in_region", "establishment__cnpj")
        )
        partners = (
            PartnerSnapshot.objects.filter(revision=latest, participation__company=company)
            .select_related("participation")
            .order_by("display_name")
        )
    events = ChangeEvent.objects.none()
    if window:
        establishment_ids = list(company.establishments.values_list("id", flat=True))
        participation_ids = list(company.partner_participations.values_list("id", flat=True))
        target_filter = Q(company_id=company.id)
        if establishment_ids:
            target_filter |= Q(establishment_id__in=establishment_ids)
        if participation_ids:
            target_filter |= Q(participation_id__in=participation_ids)
        events = (
            ChangeEvent.objects.filter(historical_window=window)
            .filter(target_filter)
            .select_related(
                "from_revision__window_competence",
                "to_revision__window_competence",
                "establishment",
                "participation",
            )
            .order_by("-to_revision__window_competence__competence", "event_type")
        )
    return {
        "active_window": window,
        "company": company,
        "snapshot": company_snapshot,
        "establishments": establishments,
        "partners": partners,
        "events": events,
        "latest_revision": latest,
        "is_watched": bool(
            user
            and user.is_authenticated
            and Watchlist.objects.filter(user=user, company=company).exists()
        ),
    }


def _event_target_filter(cnpj_digits: str) -> Q:
    if len(cnpj_digits) == 8:
        company = Company.objects.filter(cnpj_basic=cnpj_digits).first()
        if not company:
            return Q(pk__in=())
        establishment_ids = list(company.establishments.values_list("id", flat=True))
        participation_ids = list(company.partner_participations.values_list("id", flat=True))
        target_filter = Q(company_id=company.id)
        if establishment_ids:
            target_filter |= Q(establishment_id__in=establishment_ids)
        if participation_ids:
            target_filter |= Q(participation_id__in=participation_ids)
        return target_filter

    establishment = Establishment.objects.select_related("company").filter(cnpj=cnpj_digits).first()
    if not establishment:
        return Q(pk__in=())
    participation_ids = list(
        establishment.company.partner_participations.values_list("id", flat=True)
    )
    target_filter = Q(company_id=establishment.company_id) | Q(establishment_id=establishment.id)
    if participation_ids:
        target_filter |= Q(participation_id__in=participation_ids)
    return target_filter


def event_list_context(filters: dict[str, str]) -> dict:
    window = _active_window()
    event_types = list(
        ChangeEvent.objects.filter(historical_window=window)
        .values_list("event_type", flat=True)
        .distinct()
        .order_by("event_type")
        if window
        else []
    )
    competence_options = [
        revision.window_competence.competence.strftime("%Y-%m")
        for revision in _active_revisions(window)
    ]
    selected_filters = {
        "event_type": (
            filters.get("event_type", "") if filters.get("event_type", "") in event_types else ""
        ),
        "entity_type": (
            filters.get("entity_type", "")
            if filters.get("entity_type", "") in {"COMPANY", "ESTABLISHMENT", "PARTICIPATION"}
            else ""
        ),
        "competence": (
            filters.get("competence", "")
            if filters.get("competence", "") in competence_options
            else ""
        ),
        "cnpj": "",
    }
    cnpj_digits = re.sub(r"\D", "", filters.get("cnpj", ""))
    if len(cnpj_digits) in (8, 14):
        selected_filters["cnpj"] = cnpj_digits

    events = ChangeEvent.objects.none()
    if window:
        events = ChangeEvent.objects.filter(historical_window=window).select_related(
            "company",
            "establishment__company",
            "participation__company",
            "from_revision__window_competence",
            "to_revision__window_competence",
        )
        if selected_filters["event_type"]:
            events = events.filter(event_type=selected_filters["event_type"])
        if selected_filters["entity_type"]:
            events = events.filter(entity_type=selected_filters["entity_type"])
        if selected_filters["competence"]:
            events = events.filter(
                to_revision__window_competence__competence=(f"{selected_filters['competence']}-01")
            )
        if selected_filters["cnpj"]:
            digits = selected_filters["cnpj"]
            events = events.filter(_event_target_filter(digits))
    return {
        "active_window": window,
        "events": events.order_by("-to_revision__window_competence__competence")[:200],
        "event_types": event_types,
        "filters": selected_filters,
    }


def import_list_context() -> dict:
    window = _active_window()
    batches = list(
        ImportBatch.objects.annotate(quality_issue_count=Count("quality_issues")).order_by(
            "-started_at"
        )[:100]
    )
    summaries = {}
    if batches:
        for row in (
            DataQualityIssue.objects.filter(import_batch_id__in=[batch.pk for batch in batches])
            .values("import_batch_id", "severity", "rule_code")
            .annotate(total=Count("id"), affected=Sum("affected_rows"))
            .order_by("rule_code")
        ):
            summaries.setdefault(row["import_batch_id"], []).append(row)
    for batch in batches:
        batch.quality_summary = summaries.get(batch.pk, [])

    revisions = CompetenceRevision.objects.none()
    if window:
        revisions = (
            CompetenceRevision.objects.filter(window_competence__historical_window=window)
            .select_related("window_competence")
            .annotate(
                source_count=Count("source_artifacts", distinct=True),
                package_count=Count("package_artifacts", distinct=True),
            )
            .order_by("window_competence__position", "-revision_number")
        )
    return {
        "active_window": window,
        "revisions": revisions,
        "batches": batches,
    }


def watchlist_context(user) -> dict:
    window = _active_window()
    latest = _active_revisions(window).last() if window else None
    items = list(Watchlist.objects.filter(user=user).select_related("company"))
    company_ids = [item.company_id for item in items]
    snapshots = {}
    recent_event_counts = {}
    if latest:
        snapshots = {
            item.company_id: item
            for item in CompanySnapshot.objects.filter(
                revision=latest,
                company_id__in=company_ids,
            )
        }
        events = ChangeEvent.objects.filter(
            historical_window=window,
            to_revision=latest,
        )
        for relation in (
            "company_id",
            "establishment__company_id",
            "participation__company_id",
        ):
            for row in (
                events.filter(**{f"{relation}__in": company_ids})
                .values(relation)
                .annotate(total=Count("id"))
            ):
                company_id = row[relation]
                recent_event_counts[company_id] = (
                    recent_event_counts.get(company_id, 0) + row["total"]
                )
    return {
        "active_window": window,
        "watchlist_items": [
            {
                "watchlist": item,
                "snapshot": snapshots.get(item.company_id),
                "recent_event_count": recent_event_counts.get(item.company_id, 0),
            }
            for item in items
        ],
        "latest_revision": latest,
    }


def _active_window():
    return HistoricalWindow.objects.filter(status=HistoricalWindow.Status.ACTIVE).first()


def _active_revisions(window):
    if not window:
        return CompetenceRevision.objects.none()
    return (
        CompetenceRevision.objects.filter(
            window_competence__historical_window=window,
            status__in=CompetenceRevision.ACTIVE_STATUSES,
        )
        .select_related("window_competence")
        .order_by("window_competence__competence")
    )
