from __future__ import annotations

import gzip
import json
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..contracts import SourceManifest, file_sha256, write_json_atomic
from .normalization import normalize_search_text

IBGE_MUNICIPALITIES_URL = (
    "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?orderBy=nome"
)

# A Receita ainda publica alguns nomes históricos ou grafias diferentes das usadas no
# catálogo atual do IBGE. As chaves incluem a UF para que a compatibilidade nunca torne
# a resolução ambígua. "EXTERIOR" não recebe alias: não é município e não possui código IBGE.
RF_MUNICIPALITY_NAME_ALIASES = {
    ("sao luiz", "MA"): "sao luis",
    ("fortaleza do tabocao", "TO"): "tabocao",
    ("eldorado dos carajas", "PA"): "eldorado do carajas",
    ("santa isabel do para", "PA"): "santa izabel do para",
    ("ares", "RN"): "arez",
    ("boa saude", "RN"): "januario cicco",
    ("muquem de sao francisco", "BA"): "muquem do sao francisco",
    ("amparo de sao francisco", "SE"): "amparo do sao francisco",
    ("amparo da serra", "MG"): "amparo do serra",
    ("brasopolis", "MG"): "brazopolis",
    ("parati", "RJ"): "paraty",
    ("balneario de picarras", "SC"): "balneario picarras",
    ("santana do livramento", "RS"): "sant ana do livramento",
    ("santo antonio do leverger", "MT"): "santo antonio de leverger",
    ("couto de magalhaes", "TO"): "couto magalhaes",
    ("sao valerio da natividade", "TO"): "sao valerio",
}


class MunicipalityCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class MunicipalityIdentity:
    ibge_code: str
    tom_code: str
    name: str
    uf: str


@dataclass(frozen=True)
class IbgeCatalog:
    path: Path
    sha256: str
    entries: dict[tuple[str, str], tuple[str, str]]

    def to_source_manifest(self) -> SourceManifest:
        return SourceManifest(
            source_type="ibge_municipalities",
            url=IBGE_MUNICIPALITIES_URL,
            file_name=self.path.name,
            size_bytes=self.path.stat().st_size,
            sha256=self.sha256,
        )


class MunicipalityResolver:
    def __init__(self, *, tom_names: dict[str, str], ibge_catalog: IbgeCatalog):
        self.tom_names = tom_names
        self.ibge_catalog = ibge_catalog

    def resolve(self, tom_code: str, uf: str) -> MunicipalityIdentity:
        try:
            rf_name = self.tom_names[tom_code]
        except KeyError as exc:
            raise MunicipalityCatalogError(f"TOM desconhecido: {tom_code}.") from exc
        source_key = (normalize_search_text(rf_name), uf)
        key = (RF_MUNICIPALITY_NAME_ALIASES.get(source_key, source_key[0]), uf)
        try:
            ibge_code, ibge_name = self.ibge_catalog.entries[key]
        except KeyError as exc:
            raise MunicipalityCatalogError(
                f"Não foi possível mapear TOM {tom_code} ({rf_name}/{uf}) para IBGE."
            ) from exc
        return MunicipalityIdentity(
            ibge_code=ibge_code,
            tom_code=tom_code,
            name=ibge_name,
            uf=uf,
        )


def fetch_ibge_catalog(
    cache_path: Path,
    *,
    opener: Callable = urllib.request.urlopen,
) -> IbgeCatalog:
    cache_path = Path(cache_path)
    if not cache_path.is_file():
        request = urllib.request.Request(
            IBGE_MUNICIPALITIES_URL,
            headers={"Accept": "application/json", "User-Agent": "projeto-integrador/1.0"},
        )
        try:
            with opener(request, timeout=120) as response:
                raw_payload = response.read()
                if raw_payload.startswith(b"\x1f\x8b"):
                    raw_payload = gzip.decompress(raw_payload)
                payload = json.loads(raw_payload)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise MunicipalityCatalogError("Falha ao obter catálogo do IBGE.") from exc
        write_json_atomic(cache_path, payload)
    else:
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MunicipalityCatalogError("Cache do IBGE inválido.") from exc
    entries = _parse_ibge_entries(payload)
    return IbgeCatalog(path=cache_path, sha256=file_sha256(cache_path), entries=entries)


def load_rf_municipality_names(zip_path: Path) -> dict[str, str]:
    zip_path = Path(zip_path)
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            if len(members) != 1:
                raise MunicipalityCatalogError("Municipios.zip deve conter um arquivo.")
            with archive.open(members[0]) as source:
                lines = source.read().decode("cp1252").splitlines()
    except (OSError, zipfile.BadZipFile, UnicodeDecodeError) as exc:
        raise MunicipalityCatalogError("Municipios.zip inválido.") from exc
    result = {}
    for line in lines:
        parts = line.split(";")
        if len(parts) != 2:
            raise MunicipalityCatalogError("Linha inválida em Municipios.zip.")
        tom_code, name = (part.strip('"') for part in parts)
        if len(tom_code) != 4 or not tom_code.isdigit() or not name:
            raise MunicipalityCatalogError("Referência TOM inválida.")
        result[tom_code] = name
    if len(result) < 5_000:
        raise MunicipalityCatalogError("Catálogo TOM nacional incompleto.")
    return result


def _parse_ibge_entries(payload: list[dict]) -> dict[tuple[str, str], tuple[str, str]]:
    if not isinstance(payload, list):
        raise MunicipalityCatalogError("Catálogo do IBGE deveria ser uma lista.")
    entries = {}
    for item in payload:
        try:
            ibge_code = str(item["id"])
            name = item["nome"]
            uf = _extract_uf(item)
        except (KeyError, TypeError) as exc:
            raise MunicipalityCatalogError("Município inválido no catálogo do IBGE.") from exc
        key = (normalize_search_text(name), uf)
        if key in entries:
            raise MunicipalityCatalogError(f"Município IBGE ambíguo: {name}/{uf}.")
        entries[key] = (ibge_code, name)
    if len(entries) < 5_000:
        raise MunicipalityCatalogError("Catálogo do IBGE nacional incompleto.")
    return entries


def _extract_uf(item: dict) -> str:
    microrregion = item.get("microrregiao") or {}
    mesorregion = microrregion.get("mesorregiao") or {}
    uf = mesorregion.get("UF") or {}
    if uf.get("sigla"):
        return uf["sigla"]
    immediate = item.get("regiao-imediata") or {}
    intermediate = immediate.get("regiao-intermediaria") or {}
    uf = intermediate.get("UF") or {}
    if uf.get("sigla"):
        return uf["sigla"]
    raise MunicipalityCatalogError(f"UF ausente para município {item.get('id')}.")
