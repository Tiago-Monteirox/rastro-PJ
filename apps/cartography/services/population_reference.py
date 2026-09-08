from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable

from django.db import transaction
from django.utils import timezone

from apps.cartography.models import GeographicSource, MunicipalityPopulation
from apps.geography.models import Municipality

IBGE_SIDRA_TABLE = "4709"
IBGE_POPULATION_VARIABLE = "93"
IBGE_POPULATION_REFERENCE_YEAR = 2022
IBGE_POPULATION_SOURCE_VERSION = "Censo 2022"
IBGE_SIDRA_BASE_URL = "https://apisidra.ibge.gov.br/values"
IBGE_CODE_PATTERN = re.compile(r"^[0-9]{7}$")


class PopulationReferenceError(Exception):
    pass


def population_reference_url(ibge_codes: Iterable[str]) -> str:
    codes = _validated_codes(ibge_codes)
    joined_codes = ",".join(codes)
    return (
        f"{IBGE_SIDRA_BASE_URL}/t/{IBGE_SIDRA_TABLE}/n6/{joined_codes}"
        f"/v/{IBGE_POPULATION_VARIABLE}/p/{IBGE_POPULATION_REFERENCE_YEAR}?formato=json"
    )


def fetch_population_reference(
    ibge_codes: Iterable[str],
    *,
    opener: Callable | None = None,
) -> dict[str, int]:
    expected_codes = _validated_codes(ibge_codes)
    request = urllib.request.Request(
        population_reference_url(expected_codes),
        headers={"Accept": "application/json", "User-Agent": "rastro-pj/1.0"},
    )
    open_url = opener or urllib.request.urlopen
    try:
        with open_url(request, timeout=60) as response:
            payload = json.load(response)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise PopulationReferenceError(
            f"Não foi possível obter a população municipal do IBGE: {exc}"
        ) from exc

    if not isinstance(payload, list):
        raise PopulationReferenceError("A API SIDRA do IBGE não retornou uma lista.")

    expected = set(expected_codes)
    population_by_code: dict[str, int] = {}
    for item in payload:
        if not isinstance(item, dict):
            raise PopulationReferenceError("A API SIDRA retornou uma linha inválida.")
        code = str(item.get("D1C", "")).strip()
        if code == "Município (Código)":
            continue
        value = str(item.get("V", "")).strip()
        if (
            code not in expected
            or str(item.get("D2C", "")).strip() != IBGE_POPULATION_VARIABLE
            or str(item.get("D3C", "")).strip() != str(IBGE_POPULATION_REFERENCE_YEAR)
            or not value.isdigit()
            or int(value) <= 0
            or code in population_by_code
        ):
            raise PopulationReferenceError(
                "A API SIDRA retornou código, período ou população municipal inválidos."
            )
        population_by_code[code] = int(value)

    missing = expected - set(population_by_code)
    if missing:
        raise PopulationReferenceError(
            "A API SIDRA não retornou todos os municípios solicitados: "
            + ", ".join(sorted(missing))
        )
    return population_by_code


@transaction.atomic
def replace_population_reference(
    population_by_code: dict[str, int],
) -> tuple[GeographicSource, int]:
    codes = _validated_codes(population_by_code)
    municipalities = {
        municipality.ibge_code: municipality
        for municipality in Municipality.objects.filter(ibge_code__in=codes)
    }
    missing = set(codes) - set(municipalities)
    if missing:
        raise PopulationReferenceError(
            "Municípios ainda não cadastrados no Rastro PJ: " + ", ".join(sorted(missing))
        )
    if any(
        not isinstance(population_by_code[code], int) or population_by_code[code] <= 0
        for code in codes
    ):
        raise PopulationReferenceError("A população municipal deve ser um inteiro positivo.")

    values = [{"ibge_code": code, "population": population_by_code[code]} for code in codes]
    canonical = json.dumps(
        {
            "table": IBGE_SIDRA_TABLE,
            "variable": IBGE_POPULATION_VARIABLE,
            "reference_year": IBGE_POPULATION_REFERENCE_YEAR,
            "values": values,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    content_hash = hashlib.sha256(canonical).hexdigest()
    source, _ = GeographicSource.objects.get_or_create(
        kind=GeographicSource.Kind.MUNICIPAL_POPULATION,
        version=IBGE_POPULATION_SOURCE_VERSION,
        content_hash=content_hash,
        defaults={
            "manifest": {
                "provider": "IBGE",
                "survey": "Censo Demográfico 2022",
                "table": IBGE_SIDRA_TABLE,
                "variable": IBGE_POPULATION_VARIABLE,
                "reference_year": IBGE_POPULATION_REFERENCE_YEAR,
                "unit": "Pessoas",
                "url": population_reference_url(codes),
                "municipality_count": len(codes),
                "values": values,
            }
        },
    )
    synchronized_at = timezone.now()
    MunicipalityPopulation.objects.bulk_create(
        [
            MunicipalityPopulation(
                source=source,
                municipality=municipalities[code],
                reference_year=IBGE_POPULATION_REFERENCE_YEAR,
                population=population_by_code[code],
                synced_at=synchronized_at,
            )
            for code in codes
        ],
        batch_size=100,
        update_conflicts=True,
        update_fields=("source", "population", "synced_at"),
        unique_fields=("municipality", "reference_year"),
    )
    return source, len(codes)


def sync_population_reference(
    municipalities: Iterable[Municipality],
) -> tuple[GeographicSource, int]:
    municipality_list = list(municipalities)
    population_by_code = fetch_population_reference(
        municipality.ibge_code for municipality in municipality_list
    )
    return replace_population_reference(population_by_code)


def _validated_codes(ibge_codes: Iterable[str]) -> list[str]:
    codes = sorted(set(ibge_codes))
    if not codes or any(not IBGE_CODE_PATTERN.fullmatch(code) for code in codes):
        raise PopulationReferenceError("Os códigos IBGE devem possuir sete dígitos.")
    return codes
