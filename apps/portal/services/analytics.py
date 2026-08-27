from __future__ import annotations

from decimal import Decimal, InvalidOperation
from math import ceil

from django.db.models import Count, F, IntegerField, Q
from django.db.models.expressions import ExpressionWrapper

from apps.registry.models import CompanySnapshot, PartnerSnapshot

from .presenters import format_brl_currency

CAPITAL_GROWTH_PAGE_SIZE = 10


def capital_growth_ranking(
    interval_events,
    end_revision,
    *,
    page: int = 1,
    per_page: int = CAPITAL_GROWTH_PAGE_SIZE,
) -> dict:
    """Ranqueia aumentos de capital social do intervalo e devolve uma página do ranking."""
    if not end_revision:
        return _empty_ranking_page(per_page)
    companies: dict[int, dict] = {}
    rows = (
        interval_events.filter(event_type="SHARE_CAPITAL_CHANGED", company__isnull=False)
        .values(
            "company_id",
            "company__cnpj_basic",
            "previous_value",
            "new_value",
        )
        .order_by("company_id", "to_revision__window_competence__position")
    )
    for row in rows.iterator(chunk_size=2000):
        previous = _capital_value(row["previous_value"])
        current = _capital_value(row["new_value"])
        if previous is None or current is None:
            continue
        company = companies.setdefault(
            row["company_id"],
            {
                "company_id": row["company_id"],
                "cnpj_basic": row["company__cnpj_basic"],
                "previous": previous,
                "current": current,
            },
        )
        company["current"] = current

    ranking = []
    for company in companies.values():
        company["delta"] = company["current"] - company["previous"]
        if company["delta"] > 0:
            ranking.append(company)
    ranking.sort(key=lambda item: (-item["delta"], item["cnpj_basic"]))

    total = len(ranking)
    pages = max(1, ceil(total / per_page))
    page = min(max(page, 1), pages)
    offset = (page - 1) * per_page
    items = ranking[offset : offset + per_page]
    _attach_company_names(items, end_revision)
    for item in items:
        item["previous_display"] = format_brl_currency(item["previous"])
        item["current_display"] = format_brl_currency(item["current"])
        item["delta_display"] = format_brl_currency(item["delta"])
    return {
        "items": items,
        "total": total,
        "page": page,
        "pages": pages,
        "per_page": per_page,
        "has_previous": page > 1,
        "has_next": page < pages,
        "previous_page": page - 1,
        "next_page": page + 1,
        "start_index": offset + 1 if items else 0,
        "end_index": offset + len(items),
    }


def _empty_ranking_page(per_page: int) -> dict:
    return {
        "items": [],
        "total": 0,
        "page": 1,
        "pages": 1,
        "per_page": per_page,
        "has_previous": False,
        "has_next": False,
        "previous_page": 1,
        "next_page": 1,
        "start_index": 0,
        "end_index": 0,
    }


def partner_growth_ranking(interval_events, start_revision, end_revision, *, limit: int = 8):
    if not start_revision or not end_revision:
        return []
    delta_expression = ExpressionWrapper(F("added") - F("removed"), output_field=IntegerField())
    rows = list(
        interval_events.filter(
            event_type__in=("PARTNER_ADDED", "PARTNER_REMOVED"),
            participation__isnull=False,
        )
        .values("participation__company_id", "participation__company__cnpj_basic")
        .annotate(
            added=Count("id", filter=Q(event_type="PARTNER_ADDED")),
            removed=Count("id", filter=Q(event_type="PARTNER_REMOVED")),
        )
        .annotate(delta=delta_expression)
        .filter(delta__gt=0)
        .order_by("-delta", "participation__company__cnpj_basic")[:limit]
    )
    ranking = [
        {
            **row,
            "company_id": row["participation__company_id"],
            "cnpj_basic": row["participation__company__cnpj_basic"],
        }
        for row in rows
    ]
    company_ids = [item["company_id"] for item in ranking]
    previous_counts = _partner_counts(start_revision, company_ids)
    current_counts = _partner_counts(end_revision, company_ids)
    _attach_company_names(ranking, end_revision)
    for item in ranking:
        item["previous"] = previous_counts.get(item["company_id"], 0)
        item["current"] = current_counts.get(item["company_id"], 0)
    return ranking


def _attach_company_names(ranking: list[dict], revision) -> None:
    if not ranking:
        return
    names = dict(
        CompanySnapshot.objects.filter(
            revision=revision,
            company_id__in=[item["company_id"] for item in ranking],
        ).values_list("company_id", "legal_name")
    )
    for item in ranking:
        item["legal_name"] = names.get(item["company_id"], "Empresa sem nome na competência")


def _partner_counts(revision, company_ids: list[int]) -> dict[int, int]:
    if not company_ids:
        return {}
    return {
        row["participation__company_id"]: row["total"]
        for row in PartnerSnapshot.objects.filter(
            revision=revision,
            participation__company_id__in=company_ids,
        )
        .values("participation__company_id")
        .annotate(total=Count("id"))
    }


def _capital_value(payload) -> Decimal | None:
    if not isinstance(payload, dict):
        return None
    try:
        return Decimal(str(payload.get("share_capital")))
    except (InvalidOperation, TypeError, ValueError):
        return None
