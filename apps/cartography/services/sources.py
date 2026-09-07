from __future__ import annotations

import csv
import gzip
import hashlib
import json
import urllib.error
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from django.db import transaction

from apps.cartography.models import GeographicSource, MunicipalityBoundary
from apps.geography.models import GeographicScope, Municipality

IBGE_BOUNDARY_URL = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/"
    "{ibge_code}?formato=application/vnd.geo+json&qualidade=minima"
)
CNEFE_REQUIRED_COLUMNS = {
    "COD_UNICO_ENDERECO",
    "COD_MUNICIPIO",
    "CEP",
    "NOM_TITULO_SEGLOGR",
    "NOM_SEGLOGR",
    "NUM_ENDERECO",
    "LATITUDE",
    "LONGITUDE",
    "NV_GEO_COORD",
}


class CartographicSourceError(Exception):
    pass


@dataclass(frozen=True)
class SourceInventory:
    content_hash: str
    manifest: dict
    files: tuple[Path, ...]


def scope_municipalities(scope: GeographicScope) -> list[Municipality]:
    return list(Municipality.objects.filter(scope_memberships__scope=scope).order_by("ibge_code"))


def inventory_cnefe_directory(directory: Path, scope: GeographicScope) -> SourceInventory:
    directory = directory.expanduser().resolve()
    if not directory.is_dir():
        raise CartographicSourceError(f"Diretório CNEFE inexistente: {directory}")

    municipalities = scope_municipalities(scope)
    expected_codes = [municipality.ibge_code for municipality in municipalities]
    files = tuple(directory / f"{code}.csv" for code in expected_codes)
    missing = [path.name for path in files if not path.is_file()]
    if missing:
        raise CartographicSourceError(
            f"Arquivos CNEFE ausentes ({len(missing)}): {', '.join(missing[:5])}"
        )

    entries = []
    for path in files:
        file_hash = _file_sha256(path)
        _validate_cnefe_header(path)
        entries.append(
            {
                "ibge_code": path.stem,
                "name": path.name,
                "size": path.stat().st_size,
                "sha256": file_hash,
            }
        )
    manifest = {
        "format": "cnefe-municipal-csv",
        "municipality_count": len(entries),
        "files": entries,
    }
    return SourceInventory(
        content_hash=_canonical_hash(manifest),
        manifest=manifest,
        files=files,
    )


def register_cnefe_source(
    *, directory: Path, scope: GeographicScope, version: str = "2022"
) -> tuple[GeographicSource, SourceInventory]:
    inventory = inventory_cnefe_directory(directory, scope)
    source, _ = GeographicSource.objects.get_or_create(
        kind=GeographicSource.Kind.CNEFE,
        version=version,
        content_hash=inventory.content_hash,
        defaults={"manifest": inventory.manifest},
    )
    if source.manifest != inventory.manifest:
        raise CartographicSourceError("Fonte CNEFE existente possui manifesto divergente.")
    return source, inventory


def load_municipality_boundaries(
    *,
    scope: GeographicScope,
    directory: Path,
    version: str = "2022-minima",
    download_missing: bool = False,
) -> GeographicSource:
    directory = directory.expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    municipalities = scope_municipalities(scope)
    payloads: list[tuple[Municipality, dict, Path]] = []
    entries = []

    for municipality in municipalities:
        path = directory / f"{municipality.ibge_code}.geojson"
        if not path.exists():
            if not download_missing:
                raise CartographicSourceError(f"Limite municipal ausente: {path.name}")
            _download_boundary(municipality.ibge_code, path)
        try:
            payload = _read_geojson(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, gzip.BadGzipFile) as exc:
            raise CartographicSourceError(f"GeoJSON inválido em {path.name}: {exc}") from exc
        geometry = _extract_geometry(payload, municipality.ibge_code)
        payloads.append((municipality, geometry, path))
        entries.append(
            {
                "ibge_code": municipality.ibge_code,
                "name": path.name,
                "size": path.stat().st_size,
                "sha256": _file_sha256(path),
                "url": IBGE_BOUNDARY_URL.format(ibge_code=municipality.ibge_code),
            }
        )

    manifest = {
        "format": "geojson",
        "quality": "minima",
        "municipality_count": len(entries),
        "files": entries,
    }
    content_hash = _canonical_hash(manifest)
    with transaction.atomic():
        source, _ = GeographicSource.objects.get_or_create(
            kind=GeographicSource.Kind.MUNICIPAL_BOUNDARIES,
            version=version,
            content_hash=content_hash,
            defaults={"manifest": manifest},
        )
        if source.manifest != manifest:
            raise CartographicSourceError("Fonte de limites existente possui manifesto divergente.")
        existing = set(
            MunicipalityBoundary.objects.filter(source=source).values_list(
                "municipality_id", flat=True
            )
        )
        MunicipalityBoundary.objects.bulk_create(
            [
                _boundary_record(source, municipality, geometry)
                for municipality, geometry, _ in payloads
                if municipality.id not in existing
            ],
            batch_size=100,
        )
        count = MunicipalityBoundary.objects.filter(source=source).count()
        if count != len(municipalities):
            raise CartographicSourceError(
                f"Fonte de limites incompleta: {count}/{len(municipalities)} municípios."
            )
    return source


def _download_boundary(ibge_code: str, target: Path) -> None:
    url = IBGE_BOUNDARY_URL.format(ibge_code=ibge_code)
    request = urllib.request.Request(url, headers={"User-Agent": "RastroPJ/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read()
    except (OSError, urllib.error.URLError) as exc:
        raise CartographicSourceError(
            f"Falha ao baixar limite do município {ibge_code}: {exc}"
        ) from exc
    if content.startswith(b"\x1f\x8b"):
        content = gzip.decompress(content)
    temporary = target.with_suffix(".geojson.part")
    temporary.write_bytes(content)
    temporary.replace(target)


def _read_geojson(path: Path) -> dict:
    content = path.read_bytes()
    if content.startswith(b"\x1f\x8b"):
        content = gzip.decompress(content)
        temporary = path.with_suffix(".geojson.part")
        temporary.write_bytes(content)
        temporary.replace(path)
    return json.loads(content.decode("utf-8"))


def _validate_cnefe_header(path: Path) -> None:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, delimiter=";")
            fields = set(reader.fieldnames or ())
    except OSError as exc:
        raise CartographicSourceError(f"Não foi possível ler {path.name}: {exc}") from exc
    missing = sorted(CNEFE_REQUIRED_COLUMNS - fields)
    if missing:
        raise CartographicSourceError(
            f"Schema CNEFE inválido em {path.name}; faltam: {', '.join(missing)}"
        )


def _extract_geometry(payload: dict, ibge_code: str) -> dict:
    if payload.get("type") == "FeatureCollection":
        features = payload.get("features") or []
        if len(features) != 1:
            raise CartographicSourceError(
                f"Malha {ibge_code} deveria conter uma única feição; recebeu {len(features)}."
            )
        geometry = features[0].get("geometry")
    elif payload.get("type") == "Feature":
        geometry = payload.get("geometry")
    else:
        geometry = payload
    if not isinstance(geometry, dict) or geometry.get("type") not in {
        "Polygon",
        "MultiPolygon",
    }:
        raise CartographicSourceError(f"Geometria municipal inválida para {ibge_code}.")
    coordinates = geometry.get("coordinates")
    if not coordinates:
        raise CartographicSourceError(f"Geometria municipal vazia para {ibge_code}.")
    return geometry


def _boundary_record(
    source: GeographicSource, municipality: Municipality, geometry: dict
) -> MunicipalityBoundary:
    points = list(_coordinate_pairs(geometry["coordinates"]))
    if not points:
        raise CartographicSourceError(f"Geometria municipal vazia para {municipality.ibge_code}.")
    longitudes = [point[0] for point in points]
    latitudes = [point[1] for point in points]
    west, east = min(longitudes), max(longitudes)
    south, north = min(latitudes), max(latitudes)
    return MunicipalityBoundary(
        source=source,
        municipality=municipality,
        geometry=geometry,
        bbox=[west, south, east, north],
        center_latitude=Decimal(f"{(south + north) / 2:.6f}"),
        center_longitude=Decimal(f"{(west + east) / 2:.6f}"),
    )


def _coordinate_pairs(value: Iterable) -> Iterable[tuple[float, float]]:
    for item in value:
        if (
            isinstance(item, (list, tuple))
            and len(item) >= 2
            and isinstance(item[0], (int, float))
            and isinstance(item[1], (int, float))
        ):
            yield float(item[0]), float(item[1])
        elif isinstance(item, (list, tuple)):
            yield from _coordinate_pairs(item)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
