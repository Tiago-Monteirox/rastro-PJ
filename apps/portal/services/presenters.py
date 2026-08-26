from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

EVENT_TYPE_LABELS = {
    "ADDRESS_CHANGED": "Mudança de endereço",
    "COMPANY_SIZE_CHANGED": "Mudança de porte",
    "ENTERED_REGION": "Entrada na região",
    "ESTABLISHMENT_CLOSED": "Baixa de estabelecimento",
    "ESTABLISHMENT_OPENED": "Abertura de estabelecimento",
    "LEGAL_NATURE_CHANGED": "Mudança de natureza jurídica",
    "LEFT_REGION": "Saída da região",
    "MAIN_CNAE_CHANGED": "Mudança de atividade principal",
    "MEI_STATUS_CHANGED": "Mudança no MEI",
    "PARTNER_ADDED": "Entrada de sócio",
    "PARTNER_QUALIFICATION_CHANGED": "Mudança de qualificação societária",
    "PARTNER_REMOVED": "Saída de sócio",
    "REGISTRATION_STATUS_CHANGED": "Mudança de situação cadastral",
    "SHARE_CAPITAL_CHANGED": "Alteração de capital social",
    "SIMPLES_STATUS_CHANGED": "Mudança no Simples Nacional",
}

DIMENSION_LABELS = {
    "company_size": "Porte da empresa",
    "legal_nature": "Natureza jurídica",
    "lifecycle": "Ciclo cadastral",
    "location": "Localização",
    "main_cnae": "Atividade principal",
    "mei_status": "MEI",
    "partner_qualification": "Qualificação do sócio",
    "partnership": "Quadro societário",
    "registration_status": "Situação cadastral",
    "share_capital": "Capital social",
    "simples_status": "Simples Nacional",
}

REGISTRATION_STATUS_LABELS = {
    "01": "Nula",
    "02": "Ativa",
    "03": "Suspensa",
    "04": "Inapta",
    "08": "Baixada",
}

COMPANY_SIZE_LABELS = {
    "00": "Não informado",
    "01": "Microempresa",
    "03": "Empresa de pequeno porte",
    "05": "Demais",
    None: "Não informado",
    "": "Não informado",
}

FIELD_LABELS = {
    "address_complement": "Complemento",
    "company_size_code": "Porte",
    "country_code": "País",
    "display_name": "Sócio",
    "entry_date": "Entrada",
    "legal_nature_code": "Natureza jurídica",
    "main_cnae_code": "CNAE principal",
    "mei_exclusion_date": "Exclusão",
    "mei_optant": "Situação",
    "mei_option_date": "Opção",
    "municipality_ibge_code": "Município IBGE",
    "neighborhood": "Bairro",
    "partner_cnpj_basic": "CNPJ básico do sócio",
    "partner_type": "Tipo",
    "postal_code": "CEP",
    "qualification_code": "Qualificação",
    "registration_status_code": "Situação cadastral",
    "share_capital": "Capital social",
    "simples_exclusion_date": "Exclusão",
    "simples_optant": "Situação",
    "simples_option_date": "Opção",
    "state_code": "UF",
    "street_name": "Logradouro",
    "street_number": "Número",
    "street_type": "Tipo de logradouro",
}


def event_type_label(event_type: str) -> str:
    return EVENT_TYPE_LABELS.get(event_type, event_type.replace("_", " ").capitalize())


def format_brl_currency(value: Any) -> str:
    decimal_value = _decimal(value)
    if decimal_value is None:
        return "Não informado"
    formatted = f"{decimal_value:,.2f}"
    return f"R$ {formatted.replace(',', '#').replace('.', ',').replace('#', '.')}"


def present_event(event) -> dict[str, Any]:
    return {
        "record": event,
        "label": _specific_event_label(event),
        "dimension_label": DIMENSION_LABELS.get(event.dimension, "Alteração cadastral"),
        "previous": _format_event_value(event.event_type, event.previous_value, before=True),
        "current": _format_event_value(event.event_type, event.new_value, before=False),
    }


def present_events(events) -> list[dict[str, Any]]:
    return [present_event(event) for event in events]


def present_event_counts(rows: list[dict]) -> list[dict]:
    return [{**row, "label": event_type_label(row["event_type"])} for row in rows]


def event_type_options(event_types: list[str]) -> list[dict[str, str]]:
    options = [
        {"value": event_type, "label": event_type_label(event_type)} for event_type in event_types
    ]
    return sorted(options, key=lambda option: option["label"])


def _specific_event_label(event) -> str:
    if event.event_type != "SHARE_CAPITAL_CHANGED":
        return event_type_label(event.event_type)
    previous = _decimal((event.previous_value or {}).get("share_capital"))
    current = _decimal((event.new_value or {}).get("share_capital"))
    if previous is not None and current is not None:
        if current > previous:
            return "Aumento de capital social"
        if current < previous:
            return "Redução de capital social"
    return event_type_label(event.event_type)


def _format_event_value(event_type: str, payload: Any, *, before: bool) -> str:
    if payload is None:
        return _absent_value(event_type, before=before)
    if not isinstance(payload, dict):
        return _format_scalar(payload)
    if event_type == "SHARE_CAPITAL_CHANGED":
        return format_brl_currency(payload.get("share_capital"))
    if event_type in {"ADDRESS_CHANGED", "ENTERED_REGION", "LEFT_REGION"}:
        return _format_address(payload)
    if event_type in {"PARTNER_ADDED", "PARTNER_REMOVED"}:
        return _format_partner(payload)
    if event_type in {
        "REGISTRATION_STATUS_CHANGED",
        "ESTABLISHMENT_CLOSED",
        "ESTABLISHMENT_OPENED",
    }:
        return _format_registration_status(payload.get("registration_status_code"))
    if event_type == "MAIN_CNAE_CHANGED":
        code = payload.get("main_cnae_code")
        return f"CNAE {code}" if code else "CNAE não informado"
    if event_type == "COMPANY_SIZE_CHANGED":
        code = payload.get("company_size_code")
        return COMPANY_SIZE_LABELS.get(code, f"Código {code}")
    if event_type == "LEGAL_NATURE_CHANGED":
        code = payload.get("legal_nature_code")
        return f"Código {code}" if code else "Não informada"
    if event_type in {"SIMPLES_STATUS_CHANGED", "MEI_STATUS_CHANGED"}:
        prefix = "simples" if event_type.startswith("SIMPLES") else "mei"
        return _format_tax_status(payload, prefix)
    if event_type == "PARTNER_QUALIFICATION_CHANGED":
        code = payload.get("qualification_code")
        return f"Qualificação {code}" if code else "Não informada"
    return _format_mapping(payload)


def _absent_value(event_type: str, *, before: bool) -> str:
    if event_type == "ESTABLISHMENT_OPENED" and before:
        return "Não constava na competência anterior"
    if event_type == "PARTNER_ADDED" and before:
        return "Participação ainda não registrada"
    if event_type == "PARTNER_REMOVED" and not before:
        return "Participação não consta mais"
    return "Não se aplica"


def _format_address(payload: dict[str, Any]) -> str:
    street = " ".join(
        str(value).strip()
        for value in (payload.get("street_type"), payload.get("street_name"))
        if value
    )
    if payload.get("street_number"):
        street = (
            f"{street}, {payload['street_number']}" if street else str(payload["street_number"])
        )
    locality = " — ".join(
        str(value).strip()
        for value in (payload.get("neighborhood"), payload.get("state_code"))
        if value
    )
    parts = [part for part in (street, payload.get("address_complement"), locality) if part]
    if payload.get("postal_code"):
        parts.append(f"CEP {payload['postal_code']}")
    if payload.get("municipality_ibge_code"):
        parts.append(f"IBGE {payload['municipality_ibge_code']}")
    return " · ".join(parts) or "Endereço não informado"


def _format_partner(payload: dict[str, Any]) -> str:
    partner_type = {"PF": "Pessoa física", "PJ": "Pessoa jurídica", "EX": "Estrangeiro"}.get(
        payload.get("partner_type"), payload.get("partner_type") or "Tipo não informado"
    )
    parts = [payload.get("display_name") or "Nome não informado", partner_type]
    if payload.get("partner_cnpj_basic"):
        parts.append(f"CNPJ básico {payload['partner_cnpj_basic']}")
    if payload.get("qualification_code"):
        parts.append(f"qualificação {payload['qualification_code']}")
    return " · ".join(parts)


def _format_registration_status(code: Any) -> str:
    if not code:
        return "Situação não informada"
    label = REGISTRATION_STATUS_LABELS.get(str(code), "Código desconhecido")
    return f"{label} ({code})"


def _format_tax_status(payload: dict[str, Any], prefix: str) -> str:
    optant = payload.get(f"{prefix}_optant")
    if optant is True:
        status = "Optante"
    elif optant is False:
        status = "Não optante"
    else:
        status = "Situação não informada"
    details = [status]
    option_date = payload.get(f"{prefix}_option_date")
    exclusion_date = payload.get(f"{prefix}_exclusion_date")
    if option_date:
        details.append(f"opção em {_format_date(option_date)}")
    if exclusion_date:
        details.append(f"exclusão em {_format_date(exclusion_date)}")
    return " · ".join(details)


def _format_mapping(payload: dict[str, Any]) -> str:
    parts = []
    for key, value in payload.items():
        if value in (None, ""):
            continue
        label = FIELD_LABELS.get(key, key.replace("_", " ").capitalize())
        parts.append(f"{label}: {_format_scalar(value)}")
    return " · ".join(parts) or "Sem informação"


def _format_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "Sim" if value else "Não"
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value)


def _format_date(value: Any) -> str:
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    try:
        return date.fromisoformat(str(value)).strftime("%d/%m/%Y")
    except ValueError:
        return str(value)


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
