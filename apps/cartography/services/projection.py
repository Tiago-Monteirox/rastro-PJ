from __future__ import annotations

import csv
import gc
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from apps.cartography.models import (
    AddressResolution,
    CartographicObservation,
    CartographicProjection,
    GeographicSource,
)
from apps.pipeline.models import CompetenceRevision, HistoricalWindow
from apps.registry.models import CompanySnapshot, EstablishmentSnapshot

from .matching import (
    CnefeCandidate,
    address_fingerprint,
    address_lookup_key,
    normalize_number,
    normalize_postal_code,
    normalize_street,
    resolve_candidates,
    resolve_postal_candidates,
)
from .sources import (
    CartographicSourceError,
    SourceInventory,
    load_municipality_boundaries,
    register_cnefe_source,
    scope_municipalities,
)

ALGORITHM_VERSION = "1.0.1"
ACTIVE_REGISTRATION_STATUS = "02"
MIN_OVERALL_COVERAGE = 0.90
MIN_MUNICIPAL_COVERAGE = 0.70
MAX_COVERAGE_DROP = 0.05
MG_BOUNDS = (-52.5, -23.5, -39.0, -13.0)
BATCH_SIZE = 5_000
ProgressCallback = Callable[[str], None]


class ProjectionPreparationError(Exception):
    pass


@dataclass(slots=True)
class CnefeIndexes:
    by_address: dict[bytes, list[CnefeCandidate]]
    by_postal_code: dict[tuple[str, str], list[CnefeCandidate]]
    row_count: int


@dataclass(frozen=True)
class ProjectionPreparationResult:
    projection: CartographicProjection
    created: bool
    already_published: bool


def prepare_cartographic_projection(
    *,
    cnefe_directory: Path,
    boundary_directory: Path,
    window_code: str = "",
    cnefe_version: str = "2022",
    boundary_version: str = "2022-minima",
    download_missing_boundaries: bool = False,
    approve_coverage_drop: bool = False,
    progress: ProgressCallback | None = None,
) -> ProjectionPreparationResult:
    notify = progress or (lambda _: None)
    window = _published_window(window_code)
    if not window.manifest_hash:
        raise ProjectionPreparationError("A janela ativa não possui manifest_hash publicado.")

    notify("Inventariando os 35 arquivos CNEFE.")
    cnefe_source, inventory = register_cnefe_source(
        directory=cnefe_directory,
        scope=window.geographic_scope,
        version=cnefe_version,
    )
    notify("Carregando a malha municipal do IBGE.")
    boundary_source = load_municipality_boundaries(
        scope=window.geographic_scope,
        directory=boundary_directory,
        version=boundary_version,
        download_missing=download_missing_boundaries,
    )
    projection, created = CartographicProjection.objects.get_or_create(
        historical_window=window,
        cnefe_source=cnefe_source,
        boundary_source=boundary_source,
        registry_manifest_hash=window.manifest_hash,
        algorithm_version=ALGORITHM_VERSION,
    )
    if projection.status == CartographicProjection.Status.PUBLISHED:
        return ProjectionPreparationResult(projection, created, True)

    projection.status = CartographicProjection.Status.PREPARING
    projection.finished_at = None
    projection.published_at = None
    projection.quality_report = {}
    projection.save(update_fields=("status", "finished_at", "published_at", "quality_report"))

    try:
        revisions = _active_revisions(window)
        if len(revisions) != 13:
            raise ProjectionPreparationError(
                f"A janela deve possuir 13 competências publicadas; recebeu {len(revisions)}."
            )

        notify("Indexando endereços do CNEFE em memória.")
        indexes = build_cnefe_indexes(inventory, notify)
        notify("Resolvendo os endereços distintos das competências.")
        _materialize_address_resolutions(
            source=cnefe_source,
            algorithm_version=ALGORITHM_VERSION,
            revisions=revisions,
            indexes=indexes,
            progress=notify,
        )
        del indexes
        gc.collect()

        notify("Materializando observações cartográficas por competência.")
        _materialize_observations(projection, revisions, notify)
        notify("Executando o quality gate cartográfico.")
        report = calculate_quality_report(
            projection,
            revisions,
            approve_coverage_drop=approve_coverage_drop,
        )
        _finish_projection(projection, report)
    except (KeyboardInterrupt, SystemExit) as exc:
        _mark_projection_failed(projection, f"Preparação interrompida: {type(exc).__name__}.")
        raise
    except Exception as exc:
        if projection.status != CartographicProjection.Status.FAILED_QUALITY_GATE:
            _mark_projection_failed(projection, str(exc))
        if isinstance(exc, (ProjectionPreparationError, CartographicSourceError)):
            raise
        raise ProjectionPreparationError(str(exc)) from exc

    projection.refresh_from_db()
    return ProjectionPreparationResult(projection, created, False)


def _mark_projection_failed(
    projection: CartographicProjection,
    message: str,
) -> None:
    projection.status = CartographicProjection.Status.FAILED
    projection.finished_at = timezone.now()
    projection.quality_report = {"passed": False, "error": message}
    projection.save(update_fields=("status", "finished_at", "quality_report"))


def build_cnefe_indexes(
    inventory: SourceInventory, progress: ProgressCallback | None = None
) -> CnefeIndexes:
    notify = progress or (lambda _: None)
    by_address: dict[bytes, list[CnefeCandidate]] = defaultdict(list)
    by_postal_code: dict[tuple[str, str], list[CnefeCandidate]] = defaultdict(list)
    row_count = 0

    for file_number, path in enumerate(inventory.files, start=1):
        expected_ibge_code = path.stem
        try:
            stream = path.open("r", encoding="utf-8-sig", newline="")
        except OSError as exc:
            raise CartographicSourceError(f"Não foi possível abrir {path.name}: {exc}") from exc
        with stream:
            reader = csv.DictReader(stream, delimiter=";")
            for line_number, row in enumerate(reader, start=2):
                candidate = _candidate_from_row(row, path.name, line_number, expected_ibge_code)
                postal_code = normalize_postal_code(row.get("CEP"))
                if postal_code:
                    by_postal_code[(expected_ibge_code, postal_code)].append(candidate)

                normalized_number = normalize_number(row.get("NUM_ENDERECO"))
                street = normalize_street(row.get("NOM_SEGLOGR"))
                title = normalize_street(row.get("NOM_TITULO_SEGLOGR"))
                street_aliases = {street}
                if title and street:
                    street_aliases.add(f"{title} {street}")
                if postal_code and normalized_number:
                    for alias in street_aliases - {""}:
                        key = address_lookup_key(
                            expected_ibge_code,
                            postal_code,
                            alias,
                            normalized_number,
                        )
                        by_address[key].append(candidate)
                row_count += 1
        notify(f"CNEFE {file_number}/{len(inventory.files)}: {path.name}")

    return CnefeIndexes(dict(by_address), dict(by_postal_code), row_count)


def _candidate_from_row(
    row: dict[str, str], file_name: str, line_number: int, expected_ibge_code: str
) -> CnefeCandidate:
    ibge_code = (row.get("COD_MUNICIPIO") or "").strip()
    if ibge_code != expected_ibge_code:
        raise CartographicSourceError(
            f"{file_name}:{line_number}: município {ibge_code!r} difere de {expected_ibge_code}."
        )
    try:
        latitude = float(row.get("LATITUDE") or "")
        longitude = float(row.get("LONGITUDE") or "")
        level = int(row.get("NV_GEO_COORD") or "")
    except ValueError as exc:
        raise CartographicSourceError(
            f"{file_name}:{line_number}: coordenada ou nível CNEFE inválido."
        ) from exc
    west, south, east, north = MG_BOUNDS
    if not (south <= latitude <= north and west <= longitude <= east):
        raise CartographicSourceError(
            f"{file_name}:{line_number}: coordenada fora dos limites amplos de MG."
        )
    if level not in range(1, 7):
        raise CartographicSourceError(
            f"{file_name}:{line_number}: nível CNEFE fora do intervalo 1–6."
        )
    address_code = (row.get("COD_UNICO_ENDERECO") or "").strip()
    if not address_code:
        raise CartographicSourceError(f"{file_name}:{line_number}: COD_UNICO_ENDERECO ausente.")
    return CnefeCandidate(address_code, latitude, longitude, level)


def _materialize_address_resolutions(
    *,
    source: GeographicSource,
    algorithm_version: str,
    revisions: list[CompetenceRevision],
    indexes: CnefeIndexes,
    progress: ProgressCallback,
) -> None:
    addresses = (
        EstablishmentSnapshot.objects.filter(
            revision__in=revisions,
            is_in_region=True,
            registration_status_code=ACTIVE_REGISTRATION_STATUS,
        )
        .order_by()
        .values(
            "municipality_id",
            "municipality__ibge_code",
            "postal_code",
            "street_name",
            "street_number",
        )
        .distinct()
    )
    batch: list[AddressResolution] = []
    seen: set[tuple[int, str]] = set()
    progress("Pré-calculando os pontos representativos dos CEPs.")
    postal_resolutions = {
        key: resolve_postal_candidates(candidates)
        for key, candidates in indexes.by_postal_code.items()
    }
    processed = 0
    for row in addresses.iterator(chunk_size=BATCH_SIZE):
        ibge_code = row["municipality__ibge_code"]
        postal_code = normalize_postal_code(row["postal_code"])
        street = normalize_street(row["street_name"])
        number = normalize_number(row["street_number"])
        fingerprint = address_fingerprint(ibge_code, postal_code, street, number)
        identity = (row["municipality_id"], fingerprint)
        if identity in seen:
            continue
        seen.add(identity)
        key = address_lookup_key(ibge_code, postal_code, street, number)
        result = resolve_candidates(
            address_candidates=indexes.by_address.get(key, []),
            prepared_postal_result=postal_resolutions.get((ibge_code, postal_code)),
        )
        batch.append(
            AddressResolution(
                source=source,
                municipality_id=row["municipality_id"],
                algorithm_version=algorithm_version,
                fingerprint=fingerprint,
                postal_code=postal_code,
                normalized_street=street,
                normalized_number=number,
                method=result.method,
                latitude=result.latitude,
                longitude=result.longitude,
                cnefe_level=result.cnefe_level,
                cnefe_address_code=result.address_code,
                candidate_count=result.candidate_count,
                dispersion_meters=result.dispersion_meters,
                reason=result.reason,
            )
        )
        if len(batch) >= BATCH_SIZE:
            _upsert_resolutions(batch)
            processed += len(batch)
            batch.clear()
            if processed % 50_000 == 0:
                progress(f"{processed:,} endereços resolvidos.")
    if batch:
        _upsert_resolutions(batch)
        processed += len(batch)
    progress(f"{processed:,} endereços distintos resolvidos.")


def _upsert_resolutions(batch: list[AddressResolution]) -> None:
    AddressResolution.objects.bulk_create(
        batch,
        batch_size=BATCH_SIZE,
        update_conflicts=True,
        update_fields=(
            "postal_code",
            "normalized_street",
            "normalized_number",
            "method",
            "latitude",
            "longitude",
            "cnefe_level",
            "cnefe_address_code",
            "candidate_count",
            "dispersion_meters",
            "reason",
        ),
        unique_fields=("source", "municipality", "algorithm_version", "fingerprint"),
    )


def _materialize_observations(
    projection: CartographicProjection,
    revisions: list[CompetenceRevision],
    progress: ProgressCallback,
) -> None:
    resolutions = {
        (row["municipality_id"], row["fingerprint"]): row
        for row in AddressResolution.objects.filter(
            source=projection.cnefe_source,
            algorithm_version=projection.algorithm_version,
        ).values(
            "id",
            "municipality_id",
            "fingerprint",
            "method",
            "latitude",
            "longitude",
            "cnefe_level",
        )
    }

    for index, revision in enumerate(revisions, start=1):
        competence = revision.window_competence.competence.strftime("%Y-%m")
        profiles = {
            row["company_id"]: row
            for row in CompanySnapshot.objects.filter(revision=revision).values(
                "company_id", "company_size_code", "simples_optant", "mei_optant"
            )
        }
        snapshots = EstablishmentSnapshot.objects.filter(
            revision=revision,
            is_in_region=True,
            registration_status_code=ACTIVE_REGISTRATION_STATUS,
        ).values(
            "establishment_id",
            "establishment__company_id",
            "municipality_id",
            "municipality__ibge_code",
            "postal_code",
            "street_name",
            "street_number",
            "main_cnae_code",
            "branch_type",
        )
        expected = snapshots.count()
        batch: list[CartographicObservation] = []
        for row in snapshots.iterator(chunk_size=BATCH_SIZE):
            ibge_code = row["municipality__ibge_code"]
            postal_code = normalize_postal_code(row["postal_code"])
            street = normalize_street(row["street_name"])
            number = normalize_number(row["street_number"])
            fingerprint = address_fingerprint(ibge_code, postal_code, street, number)
            resolution = resolutions.get((row["municipality_id"], fingerprint))
            if resolution is None:
                establishment_id = row["establishment_id"]
                raise ProjectionPreparationError(
                    f"Resolução ausente para estabelecimento {establishment_id} em {competence}."
                )
            company_id = row["establishment__company_id"]
            profile = profiles.get(company_id, {})
            batch.append(
                CartographicObservation(
                    projection=projection,
                    revision=revision,
                    establishment_id=row["establishment_id"],
                    company_id=company_id,
                    municipality_id=row["municipality_id"],
                    address_resolution_id=resolution["id"],
                    latitude=resolution["latitude"],
                    longitude=resolution["longitude"],
                    location_method=resolution["method"],
                    cnefe_level=resolution["cnefe_level"],
                    postal_code=postal_code,
                    main_cnae_code=row["main_cnae_code"] or "",
                    branch_type=row["branch_type"],
                    company_size_code=profile.get("company_size_code") or "",
                    tax_profile=_tax_profile(profile),
                )
            )
            if len(batch) >= BATCH_SIZE:
                CartographicObservation.objects.bulk_create(
                    batch, batch_size=BATCH_SIZE, ignore_conflicts=True
                )
                batch.clear()
        if batch:
            CartographicObservation.objects.bulk_create(
                batch, batch_size=BATCH_SIZE, ignore_conflicts=True
            )
        actual = CartographicObservation.objects.filter(
            projection=projection, revision=revision
        ).count()
        if actual != expected:
            raise ProjectionPreparationError(
                f"Competência {competence}: esperava {expected} observações "
                f"e materializou {actual}."
            )
        progress(f"Competência {index}/{len(revisions)} ({competence}): {actual:,} observações.")
        del profiles


def _tax_profile(profile: dict) -> str:
    if profile.get("mei_optant") is True:
        return CartographicObservation.TaxProfile.MEI
    if profile.get("simples_optant") is True:
        return CartographicObservation.TaxProfile.SIMPLES
    if profile.get("simples_optant") is False:
        return CartographicObservation.TaxProfile.REGULAR
    return CartographicObservation.TaxProfile.UNKNOWN


def calculate_quality_report(
    projection: CartographicProjection,
    revisions: list[CompetenceRevision],
    *,
    approve_coverage_drop: bool = False,
) -> dict:
    observations = CartographicObservation.objects.filter(
        projection=projection, revision__in=revisions
    )
    totals = observations.aggregate(
        eligible=Count("id"),
        address=Count("id", filter=Q(location_method=AddressResolution.Method.ADDRESS)),
        postal_code=Count("id", filter=Q(location_method=AddressResolution.Method.POSTAL_CODE)),
        unlocated=Count("id", filter=Q(location_method=AddressResolution.Method.UNLOCATED)),
    )
    eligible = totals["eligible"]
    located = totals["address"] + totals["postal_code"]
    overall_coverage = located / eligible if eligible else 0.0
    structural_errors = []
    if projection.cnefe_source.kind != GeographicSource.Kind.CNEFE:
        structural_errors.append("A fonte de coordenadas não é CNEFE.")
    if projection.boundary_source.kind != GeographicSource.Kind.MUNICIPAL_BOUNDARIES:
        structural_errors.append("A fonte de polígonos não é uma malha municipal.")
    boundary_count = projection.boundary_source.municipality_boundaries.count()
    if boundary_count != 35:
        structural_errors.append(f"A malha possui {boundary_count}/35 municípios.")
    if len(revisions) != 13:
        structural_errors.append(f"Foram encontradas {len(revisions)}/13 competências.")
    expected_eligible = EstablishmentSnapshot.objects.filter(
        revision__in=revisions,
        is_in_region=True,
        registration_status_code=ACTIVE_REGISTRATION_STATUS,
    ).count()
    if eligible != expected_eligible:
        structural_errors.append(
            f"A projeção possui {eligible} observações para {expected_eligible} "
            "fotografias elegíveis."
        )
    wrong_window = observations.exclude(
        revision__window_competence__historical_window=projection.historical_window
    ).count()
    if wrong_window:
        structural_errors.append(
            f"Há {wrong_window} observações associadas a outra janela histórica."
        )
    wrong_company = observations.exclude(company_id=F("establishment__company_id")).count()
    if wrong_company:
        structural_errors.append(
            f"Há {wrong_company} observações cuja empresa difere do estabelecimento."
        )
    inconsistent_precision = observations.filter(
        Q(location_method=AddressResolution.Method.UNLOCATED)
        & (Q(latitude__isnull=False) | Q(longitude__isnull=False))
        | ~Q(location_method=AddressResolution.Method.UNLOCATED)
        & (Q(latitude__isnull=True) | Q(longitude__isnull=True) | Q(cnefe_level__isnull=True))
    ).count()
    if inconsistent_precision:
        structural_errors.append(
            f"Há {inconsistent_precision} observações com precisão ou coordenadas inconsistentes."
        )

    municipality_rows = {
        row["municipality_id"]: row
        for row in observations.values("municipality_id").annotate(
            eligible=Count("id"),
            located=Count("id", filter=~Q(location_method=AddressResolution.Method.UNLOCATED)),
        )
    }
    municipalities = []
    municipal_failures = []
    for municipality in scope_municipalities(projection.historical_window.geographic_scope):
        row = municipality_rows.get(municipality.id, {"eligible": 0, "located": 0})
        coverage = row["located"] / row["eligible"] if row["eligible"] else None
        passed = coverage is None or coverage >= MIN_MUNICIPAL_COVERAGE
        if not passed:
            municipal_failures.append(municipality.ibge_code)
        municipalities.append(
            {
                "ibge_code": municipality.ibge_code,
                "name": municipality.name,
                "eligible": row["eligible"],
                "located": row["located"],
                "coverage": round(coverage, 6) if coverage is not None else None,
                "passed": passed,
            }
        )

    competence_rows = []
    for revision in revisions:
        row = observations.filter(revision=revision).aggregate(
            eligible=Count("id"),
            located=Count("id", filter=~Q(location_method=AddressResolution.Method.UNLOCATED)),
        )
        coverage = row["located"] / row["eligible"] if row["eligible"] else 0.0
        competence_rows.append(
            {
                "competence": revision.window_competence.competence.strftime("%Y-%m"),
                "eligible": row["eligible"],
                "located": row["located"],
                "coverage": round(coverage, 6),
            }
        )

    previous = (
        CartographicProjection.objects.filter(
            historical_window=projection.historical_window,
            status=CartographicProjection.Status.PUBLISHED,
        )
        .exclude(pk=projection.pk)
        .first()
    )
    previous_coverage = None
    coverage_drop = 0.0
    requires_review = False
    if previous and previous.eligible_count:
        previous_coverage = previous.located_count / previous.eligible_count
        coverage_drop = previous_coverage - overall_coverage
        requires_review = coverage_drop > MAX_COVERAGE_DROP and not approve_coverage_drop

    passed = (
        not structural_errors
        and eligible > 0
        and overall_coverage >= MIN_OVERALL_COVERAGE
        and not municipal_failures
        and not requires_review
    )
    return {
        "passed": passed,
        "thresholds": {
            "overall": MIN_OVERALL_COVERAGE,
            "municipality": MIN_MUNICIPAL_COVERAGE,
            "coverage_drop_review": MAX_COVERAGE_DROP,
        },
        "totals": {
            **totals,
            "located": located,
            "coverage": round(overall_coverage, 6),
        },
        "municipalities": municipalities,
        "municipal_failures": municipal_failures,
        "competences": competence_rows,
        "structural_errors": structural_errors,
        "previous_coverage": (
            round(previous_coverage, 6) if previous_coverage is not None else None
        ),
        "coverage_drop": round(coverage_drop, 6),
        "coverage_drop_approved": approve_coverage_drop,
        "requires_review": requires_review,
    }


def _finish_projection(projection: CartographicProjection, report: dict) -> None:
    totals = report["totals"]
    now = timezone.now()
    projection.eligible_count = totals["eligible"]
    projection.located_count = totals["located"]
    projection.address_count = totals["address"]
    projection.postal_code_count = totals["postal_code"]
    projection.unlocated_count = totals["unlocated"]
    projection.quality_report = report
    projection.finished_at = now
    if not report["passed"]:
        projection.status = CartographicProjection.Status.FAILED_QUALITY_GATE
        projection.save()
        raise ProjectionPreparationError("A projeção foi reprovada no quality gate cartográfico.")

    with transaction.atomic():
        locked = CartographicProjection.objects.select_for_update().get(pk=projection.pk)
        CartographicProjection.objects.filter(
            historical_window=projection.historical_window,
            status=CartographicProjection.Status.PUBLISHED,
        ).exclude(pk=projection.pk).update(status=CartographicProjection.Status.SUPERSEDED)
        locked.status = CartographicProjection.Status.PUBLISHED
        locked.eligible_count = projection.eligible_count
        locked.located_count = projection.located_count
        locked.address_count = projection.address_count
        locked.postal_code_count = projection.postal_code_count
        locked.unlocated_count = projection.unlocated_count
        locked.quality_report = report
        locked.finished_at = now
        locked.published_at = now
        locked.save()


def _published_window(window_code: str) -> HistoricalWindow:
    queryset = HistoricalWindow.objects.filter(status=HistoricalWindow.Status.ACTIVE)
    if window_code:
        queryset = HistoricalWindow.objects.filter(code=window_code)
    window = queryset.select_related("geographic_scope").first()
    if window is None:
        suffix = f" {window_code!r}" if window_code else " ativa"
        raise ProjectionPreparationError(f"Janela histórica{suffix} não encontrada.")
    if window.status != HistoricalWindow.Status.ACTIVE:
        raise ProjectionPreparationError("Somente a janela histórica ativa pode ser projetada.")
    return window


def _active_revisions(window: HistoricalWindow) -> list[CompetenceRevision]:
    return list(
        CompetenceRevision.objects.filter(
            window_competence__historical_window=window,
            status__in=CompetenceRevision.ACTIVE_STATUSES,
        )
        .select_related("window_competence")
        .order_by("window_competence__competence")
    )
