from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable

from django.db import transaction
from django.utils import timezone

from apps.cartography.models import CnaeSubclass

IBGE_CNAE_SUBCLASSES_URL = "https://servicodados.ibge.gov.br/api/v2/cnae/subclasses"
MINIMUM_CATALOG_SIZE = 1_000
CODE_PATTERN = re.compile(r"^[0-9]{7}$")


class CnaeCatalogError(Exception):
    pass


def fetch_cnae_catalog(
    *,
    opener: Callable | None = None,
    minimum_size: int = MINIMUM_CATALOG_SIZE,
) -> dict[str, str]:
    request = urllib.request.Request(
        IBGE_CNAE_SUBCLASSES_URL,
        headers={"Accept": "application/json", "User-Agent": "rastro-pj/1.0"},
    )
    open_url = opener or urllib.request.urlopen
    try:
        with open_url(request, timeout=60) as response:
            payload = json.load(response)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise CnaeCatalogError(f"Não foi possível obter o catálogo CNAE do IBGE: {exc}") from exc

    if not isinstance(payload, list):
        raise CnaeCatalogError("O catálogo CNAE do IBGE não retornou uma lista.")
    catalog: dict[str, str] = {}
    for item in payload:
        code = str(item.get("id", "")).strip() if isinstance(item, dict) else ""
        description = (
            " ".join(str(item.get("descricao", "")).split()) if isinstance(item, dict) else ""
        )
        if not CODE_PATTERN.fullmatch(code) or not description:
            raise CnaeCatalogError("O catálogo CNAE do IBGE contém uma subclasse inválida.")
        catalog[code] = description
    if len(catalog) < minimum_size:
        raise CnaeCatalogError(
            f"O catálogo CNAE retornou somente {len(catalog)} subclasses; "
            f"eram esperadas ao menos {minimum_size}."
        )
    return catalog


@transaction.atomic
def replace_cnae_catalog(catalog: dict[str, str]) -> int:
    synchronized_at = timezone.now()
    CnaeSubclass.objects.bulk_create(
        [
            CnaeSubclass(
                code=code,
                description=description,
                source="IBGE CNAE API v2",
                synced_at=synchronized_at,
            )
            for code, description in sorted(catalog.items())
        ],
        batch_size=500,
        update_conflicts=True,
        update_fields=("description", "source", "synced_at"),
        unique_fields=("code",),
    )
    CnaeSubclass.objects.exclude(code__in=catalog).delete()
    return len(catalog)


def sync_cnae_catalog() -> int:
    return replace_cnae_catalog(fetch_cnae_catalog())
