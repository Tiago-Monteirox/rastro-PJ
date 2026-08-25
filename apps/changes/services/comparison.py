from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class EventCandidate:
    entity_type: str
    entity_key: str | tuple[str, str]
    dimension: str
    event_type: str
    previous_value: Any
    new_value: Any
    source_effective_date: date | None = None


@dataclass(frozen=True)
class QualityCandidate:
    rule_code: str
    entity_type: str
    entity_key: str
    details: dict[str, Any]
    affected_rows: int = 1


def compare_snapshots(
    *,
    previous_competence: date,
    current_competence: date,
    previous_companies: dict[str, dict],
    current_companies: dict[str, dict],
    previous_establishments: dict[str, dict],
    current_establishments: dict[str, dict],
    previous_partners: dict[tuple[str, str], dict],
    current_partners: dict[tuple[str, str], dict],
) -> tuple[list[EventCandidate], list[QualityCandidate]]:
    events: list[EventCandidate] = []
    issues: list[QualityCandidate] = []

    _compare_companies(previous_companies, current_companies, events, issues)
    _compare_establishments(
        previous_competence,
        current_competence,
        previous_establishments,
        current_establishments,
        events,
        issues,
    )
    _compare_partners(
        previous_companies,
        current_companies,
        previous_partners,
        current_partners,
        events,
    )
    return events, issues


def _compare_companies(previous: dict, current: dict, events: list, issues: list) -> None:
    for cnpj_basic in sorted(previous.keys() - current.keys()):
        issues.append(
            QualityCandidate(
                rule_code="COMPANY_MISSING_IN_CURRENT",
                entity_type="COMPANY",
                entity_key=cnpj_basic,
                details={"comparison_suspended": True},
            )
        )
    for cnpj_basic in sorted(previous.keys() & current.keys()):
        before = previous[cnpj_basic]
        after = current[cnpj_basic]
        if before["share_capital"] != after["share_capital"]:
            events.append(
                EventCandidate(
                    entity_type="COMPANY",
                    entity_key=cnpj_basic,
                    dimension="share_capital",
                    event_type="SHARE_CAPITAL_CHANGED",
                    previous_value={"share_capital": str(before["share_capital"])},
                    new_value={"share_capital": str(after["share_capital"])},
                )
            )
        _compare_company_p1(cnpj_basic, before, after, events)


def _compare_establishments(
    previous_competence: date,
    current_competence: date,
    previous: dict,
    current: dict,
    events: list,
    issues: list,
) -> None:
    for cnpj in sorted(previous.keys() - current.keys()):
        issues.append(
            QualityCandidate(
                rule_code="ESTABLISHMENT_MISSING_IN_CURRENT",
                entity_type="ESTABLISHMENT",
                entity_key=cnpj,
                details={"comparison_suspended": True},
            )
        )

    for cnpj in sorted(current.keys() - previous.keys()):
        snapshot = current[cnpj]
        started = snapshot["activity_start_date"]
        if started and previous_competence < started <= current_competence:
            events.append(
                EventCandidate(
                    entity_type="ESTABLISHMENT",
                    entity_key=cnpj,
                    dimension="lifecycle",
                    event_type="ESTABLISHMENT_OPENED",
                    previous_value=None,
                    new_value={"registration_status_code": snapshot["registration_status_code"]},
                    source_effective_date=started,
                )
            )
        else:
            issues.append(
                QualityCandidate(
                    rule_code="LATE_FIRST_SEEN",
                    entity_type="ESTABLISHMENT",
                    entity_key=cnpj,
                    details={
                        "activity_start_date": started.isoformat() if started else None,
                        "comparison_suspended": True,
                    },
                )
            )

    for cnpj in sorted(previous.keys() & current.keys()):
        before = previous[cnpj]
        after = current[cnpj]
        _compare_registration(cnpj, before, after, events)
        _compare_location(cnpj, before, after, events)
        if before["main_cnae_code"] != after["main_cnae_code"]:
            events.append(
                EventCandidate(
                    entity_type="ESTABLISHMENT",
                    entity_key=cnpj,
                    dimension="main_cnae",
                    event_type="MAIN_CNAE_CHANGED",
                    previous_value={"main_cnae_code": before["main_cnae_code"]},
                    new_value={"main_cnae_code": after["main_cnae_code"]},
                )
            )


def _compare_registration(cnpj: str, before: dict, after: dict, events: list) -> None:
    old_status = before["registration_status_code"]
    new_status = after["registration_status_code"]
    if old_status == new_status:
        return
    closed = new_status == "08" and old_status != "08"
    events.append(
        EventCandidate(
            entity_type="ESTABLISHMENT",
            entity_key=cnpj,
            dimension="registration_status",
            event_type="ESTABLISHMENT_CLOSED" if closed else "REGISTRATION_STATUS_CHANGED",
            previous_value={"registration_status_code": old_status},
            new_value={"registration_status_code": new_status},
            source_effective_date=(after["registration_status_date"] if closed else None),
        )
    )


def _compare_location(cnpj: str, before: dict, after: dict, events: list) -> None:
    old_region = before["is_in_region"]
    new_region = after["is_in_region"]
    old_address = _address_value(before)
    new_address = _address_value(after)
    if old_region != new_region:
        events.append(
            EventCandidate(
                entity_type="ESTABLISHMENT",
                entity_key=cnpj,
                dimension="location",
                event_type="ENTERED_REGION" if new_region else "LEFT_REGION",
                previous_value=old_address,
                new_value=new_address,
            )
        )
    elif old_address != new_address:
        events.append(
            EventCandidate(
                entity_type="ESTABLISHMENT",
                entity_key=cnpj,
                dimension="location",
                event_type="ADDRESS_CHANGED",
                previous_value=old_address,
                new_value=new_address,
            )
        )


def _compare_partners(
    previous_companies: dict,
    current_companies: dict,
    previous: dict,
    current: dict,
    events: list,
) -> None:
    comparable_companies = previous_companies.keys() & current_companies.keys()
    for key in sorted(current.keys() - previous.keys()):
        if key[0] in comparable_companies:
            events.append(_partner_event("PARTNER_ADDED", key, None, current[key]))
    for key in sorted(previous.keys() - current.keys()):
        if key[0] in comparable_companies:
            events.append(_partner_event("PARTNER_REMOVED", key, previous[key], None))
    for key in sorted(previous.keys() & current.keys()):
        if (
            key[0] in comparable_companies
            and previous[key]["qualification_code"] != current[key]["qualification_code"]
        ):
            events.append(
                EventCandidate(
                    entity_type="PARTICIPATION",
                    entity_key=key,
                    dimension="partner_qualification",
                    event_type="PARTNER_QUALIFICATION_CHANGED",
                    previous_value={"qualification_code": previous[key]["qualification_code"]},
                    new_value={"qualification_code": current[key]["qualification_code"]},
                )
            )


def _compare_company_p1(cnpj_basic: str, before: dict, after: dict, events: list) -> None:
    simple_fields = (
        ("legal_nature_code", "legal_nature", "LEGAL_NATURE_CHANGED"),
        ("company_size_code", "company_size", "COMPANY_SIZE_CHANGED"),
    )
    for field, dimension, event_type in simple_fields:
        if before[field] != after[field]:
            events.append(
                EventCandidate(
                    entity_type="COMPANY",
                    entity_key=cnpj_basic,
                    dimension=dimension,
                    event_type=event_type,
                    previous_value={field: before[field]},
                    new_value={field: after[field]},
                )
            )
    for prefix, event_type in (
        ("simples", "SIMPLES_STATUS_CHANGED"),
        ("mei", "MEI_STATUS_CHANGED"),
    ):
        fields = (
            f"{prefix}_optant",
            f"{prefix}_option_date",
            f"{prefix}_exclusion_date",
        )
        old_value = {field: _json_value(before[field]) for field in fields}
        new_value = {field: _json_value(after[field]) for field in fields}
        if old_value != new_value:
            events.append(
                EventCandidate(
                    entity_type="COMPANY",
                    entity_key=cnpj_basic,
                    dimension=f"{prefix}_status",
                    event_type=event_type,
                    previous_value=old_value,
                    new_value=new_value,
                )
            )


def _partner_event(event_type: str, key: tuple[str, str], before, after) -> EventCandidate:
    return EventCandidate(
        entity_type="PARTICIPATION",
        entity_key=key,
        dimension="partnership",
        event_type=event_type,
        previous_value=_partner_value(before),
        new_value=_partner_value(after),
        source_effective_date=after["entry_date"]
        if after and event_type == "PARTNER_ADDED"
        else None,
    )


def _address_value(snapshot: dict) -> dict[str, Any]:
    fields = (
        "street_type",
        "street_name",
        "street_number",
        "address_complement",
        "neighborhood",
        "postal_code",
        "state_code",
        "municipality_ibge_code",
    )
    return {field: snapshot[field] for field in fields}


def _partner_value(snapshot: dict | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        "partner_type": snapshot["partner_type"],
        "display_name": snapshot["display_name"],
        "partner_cnpj_basic": snapshot["partner_cnpj_basic"],
        "qualification_code": snapshot["qualification_code"],
    }


def _json_value(value: Any) -> Any:
    return value.isoformat() if isinstance(value, date) else value
