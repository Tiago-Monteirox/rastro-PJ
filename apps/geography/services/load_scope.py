import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from django.db import transaction

from apps.geography.models import GeographicScope, Municipality, ScopeMunicipality

IBGE_PATTERN = re.compile(r"^[0-9]{7}$")
TOM_PATTERN = re.compile(r"^[0-9]{4}$")
UF_PATTERN = re.compile(r"^[A-Z]{2}$")
EXPECTED_HEADERS = ("municipio", "codigo_ibge", "codigo_tom", "uf")


class GeographicReferenceError(ValueError):
    """A referência geográfica viola o contrato aprovado."""


@dataclass(frozen=True, slots=True)
class MunicipalityReference:
    name: str
    ibge_code: str
    tom_code: str
    uf: str


@dataclass(frozen=True, slots=True)
class ScopeLoadResult:
    scope: GeographicScope | None
    municipality_count: int
    scope_hash: str
    created: bool
    dry_run: bool


def read_reference(
    path: Path, *, expected_count: int | None = None
) -> tuple[MunicipalityReference, ...]:
    path = Path(path)
    if not path.is_file():
        raise GeographicReferenceError(f"Referência geográfica não encontrada: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as reference_file:
        reader = csv.DictReader(reference_file)
        if tuple(reader.fieldnames or ()) != EXPECTED_HEADERS:
            raise GeographicReferenceError(
                "Cabeçalho inválido. Esperado: " + ",".join(EXPECTED_HEADERS)
            )
        rows = tuple(_parse_row(row, line_number) for line_number, row in enumerate(reader, 2))

    if expected_count is not None and len(rows) != expected_count:
        raise GeographicReferenceError(
            f"Quantidade inválida: esperado {expected_count}, encontrado {len(rows)}."
        )
    if not rows:
        raise GeographicReferenceError("A referência geográfica está vazia.")

    _assert_unique(rows, "IBGE", lambda row: row.ibge_code)
    _assert_unique(rows, "TOM", lambda row: row.tom_code)
    return tuple(sorted(rows, key=lambda row: row.ibge_code))


def _parse_row(row: dict[str, str], line_number: int) -> MunicipalityReference:
    name = (row.get("municipio") or "").strip()
    ibge_code = (row.get("codigo_ibge") or "").strip()
    tom_code = (row.get("codigo_tom") or "").strip()
    uf = (row.get("uf") or "").strip().upper()

    if not name:
        raise GeographicReferenceError(f"Linha {line_number}: município vazio.")
    if not IBGE_PATTERN.fullmatch(ibge_code):
        raise GeographicReferenceError(f"Linha {line_number}: código IBGE inválido: {ibge_code!r}.")
    if not TOM_PATTERN.fullmatch(tom_code):
        raise GeographicReferenceError(f"Linha {line_number}: código TOM inválido: {tom_code!r}.")
    if not UF_PATTERN.fullmatch(uf):
        raise GeographicReferenceError(f"Linha {line_number}: UF inválida: {uf!r}.")
    return MunicipalityReference(name=name, ibge_code=ibge_code, tom_code=tom_code, uf=uf)


def _assert_unique(rows, label: str, key) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in rows:
        value = key(row)
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        values = ", ".join(sorted(duplicates))
        raise GeographicReferenceError(f"Código {label} duplicado: {values}.")


def calculate_scope_hash(rows: tuple[MunicipalityReference, ...]) -> str:
    canonical = "\n".join(
        f"{row.ibge_code};{row.tom_code};{row.uf};{row.name}"
        for row in sorted(rows, key=lambda row: row.ibge_code)
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_geographic_scope(
    *,
    reference_path: Path,
    code: str,
    name: str,
    version: int,
    expected_count: int | None = None,
    dry_run: bool = False,
) -> ScopeLoadResult:
    rows = read_reference(reference_path, expected_count=expected_count)
    scope_hash = calculate_scope_hash(rows)
    if dry_run:
        return ScopeLoadResult(
            scope=None,
            municipality_count=len(rows),
            scope_hash=scope_hash,
            created=False,
            dry_run=True,
        )

    with transaction.atomic():
        existing_scope = GeographicScope.objects.filter(code=code, version=version).first()
        if existing_scope and existing_scope.scope_hash != scope_hash:
            raise GeographicReferenceError(
                f"O recorte {code} v{version} já existe com outro hash; crie uma nova versão."
            )

        scope = existing_scope
        created = False
        if scope is None:
            scope = GeographicScope.objects.create(
                code=code,
                name=name,
                version=version,
                scope_hash=scope_hash,
            )
            created = True
        elif scope.name != name:
            raise GeographicReferenceError(
                f"O recorte {code} v{version} já existe com outro nome; não será sobrescrito."
            )

        municipalities = [_get_or_create_immutable_municipality(row) for row in rows]
        current_ids = set(
            ScopeMunicipality.objects.filter(scope=scope).values_list("municipality_id", flat=True)
        )
        expected_ids = {municipality.id for municipality in municipalities}
        if current_ids and current_ids != expected_ids:
            raise GeographicReferenceError(
                f"O recorte {code} v{version} já possui associações diferentes; "
                "crie uma nova versão."
            )
        ScopeMunicipality.objects.bulk_create(
            [
                ScopeMunicipality(scope=scope, municipality=municipality)
                for municipality in municipalities
                if municipality.id not in current_ids
            ]
        )

    return ScopeLoadResult(
        scope=scope,
        municipality_count=len(rows),
        scope_hash=scope_hash,
        created=created,
        dry_run=False,
    )


def _get_or_create_immutable_municipality(row: MunicipalityReference) -> Municipality:
    municipality = Municipality.objects.filter(ibge_code=row.ibge_code).first()
    if municipality is None:
        conflicting_tom = Municipality.objects.filter(tom_code=row.tom_code).first()
        if conflicting_tom:
            raise GeographicReferenceError(
                f"TOM {row.tom_code} já pertence ao IBGE {conflicting_tom.ibge_code}."
            )
        return Municipality.objects.create(
            ibge_code=row.ibge_code,
            tom_code=row.tom_code,
            name=row.name,
            uf=row.uf,
        )

    observed = (municipality.tom_code, municipality.name, municipality.uf)
    expected = (row.tom_code, row.name, row.uf)
    if observed != expected:
        raise GeographicReferenceError(
            f"IBGE {row.ibge_code} já existe com TOM, nome ou UF divergente."
        )
    return municipality
