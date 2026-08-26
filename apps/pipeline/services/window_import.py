from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
from django.db import connection, transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.changes.models import ChangeEvent, RegionalMonthlyMetric
from apps.changes.services import QualityCandidate, compare_snapshots
from apps.geography.models import GeographicScope, Municipality, ScopeMunicipality
from apps.registry.cnpj import is_canonical_cnpj, is_canonical_cnpj_basic
from apps.registry.models import (
    Company,
    CompanySnapshot,
    Establishment,
    EstablishmentSnapshot,
    PartnerParticipation,
    PartnerSnapshot,
)

from ..contracts import TABLE_CONTRACTS
from ..models import (
    CompetenceRevision,
    DataQualityIssue,
    HistoricalWindow,
    ImportBatch,
    PackageArtifact,
    SourceArtifact,
    WindowCompetence,
)
from .normalization import canonical_record_hash
from .package_validation import ValidatedPackage, ValidatedWindow, validate_window_package

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
WARNING_RATE_OVERRIDES = {
    "LATE_FIRST_SEEN": 0.005,
    "SOURCE_ZERO_DATE": 0.0025,
}


class WindowImportError(ValueError):
    pass


@dataclass(frozen=True)
class WindowImportResult:
    window: HistoricalWindow
    imported: bool
    competence_count: int
    event_count: int
    warning_count: int
    batch_id: str
    revised_competences: tuple[str, ...] = ()


def recalculate_quality_metadata(window: HistoricalWindow) -> tuple[int, str]:
    revisions = list(
        CompetenceRevision.objects.filter(
            window_competence__historical_window=window,
            status__in=CompetenceRevision.ACTIVE_STATUSES,
        )
        .select_related("window_competence")
        .order_by("window_competence__position")
    )
    batch = ImportBatch.objects.create(
        operation=ImportBatch.Operation.RECALCULATE,
        status=ImportBatch.Status.LOADING,
        phase="quality_metadata",
        sanitized_options={"window_code": window.code},
    )
    updated_count = 0
    previous_state = {"companies": 0, "establishments": 0, "partners": 0}
    try:
        with transaction.atomic():
            for revision in revisions:
                persisted_issues = list(
                    DataQualityIssue.objects.filter(competence_revision=revision).order_by("pk")
                )
                candidates = []
                for issue in persisted_issues:
                    package_warning = issue.details.get("package_warning")
                    if package_warning:
                        candidate = _package_warning(package_warning)
                    else:
                        candidate = QualityCandidate(
                            rule_code=issue.rule_code,
                            entity_type=issue.entity_type,
                            entity_key=issue.entity_key or "UNKNOWN",
                            details=issue.details,
                            affected_rows=issue.affected_rows,
                        )
                    candidates.append(candidate)
                candidates = _enforce_warning_threshold(
                    candidates,
                    previous_state,
                    revision.row_counts,
                )
                for issue, candidate in zip(persisted_issues, candidates, strict=True):
                    issue.entity_type = candidate.entity_type
                    issue.entity_key = candidate.entity_key
                    issue.eligible_rows = candidate.details["eligible_rows"]
                    issue.affected_rows = candidate.affected_rows
                    issue.details = candidate.details
                if persisted_issues:
                    DataQualityIssue.objects.bulk_update(
                        persisted_issues,
                        ("entity_type", "entity_key", "eligible_rows", "affected_rows", "details"),
                        batch_size=2000,
                    )
                updated_count += len(persisted_issues)
                previous_state = revision.row_counts
        batch.status = ImportBatch.Status.COMPLETED
        batch.phase = "quality_metadata_recalculated"
        batch.counters = {
            "competences": len(revisions),
            "quality_issues": updated_count,
        }
        batch.finished_at = timezone.now()
        batch.save(update_fields=("status", "phase", "counters", "finished_at"))
        return updated_count, str(batch.pk)
    except Exception as exc:
        ImportBatch.objects.filter(pk=batch.pk).update(
            status=ImportBatch.Status.FAILED,
            phase="failed",
            error_code=type(exc).__name__,
            error_message=str(exc)[:2000],
            finished_at=timezone.now(),
        )
        raise


def recalculate_window_events(window: HistoricalWindow) -> int:
    revisions = list(
        CompetenceRevision.objects.filter(
            window_competence__historical_window=window,
            status__in=CompetenceRevision.ACTIVE_STATUSES,
        )
        .select_related("window_competence")
        .order_by("window_competence__competence")
    )
    batch = ImportBatch.objects.create(
        operation=ImportBatch.Operation.RECALCULATE,
        status=ImportBatch.Status.LOADING,
        phase="events",
    )
    event_count = 0
    try:
        with transaction.atomic():
            ChangeEvent.objects.filter(historical_window=window).delete()
            previous_revision = None
            for revision in revisions:
                if previous_revision is not None:
                    candidates = _compare_revisions(
                        previous_revision=previous_revision,
                        current_revision=revision,
                    )
                    event_count += _persist_events(
                        candidates=candidates,
                        window=window,
                        from_revision=previous_revision,
                        to_revision=revision,
                        batch=batch,
                    )
                previous_revision = revision
            batch.status = ImportBatch.Status.COMPLETED
            batch.phase = "events_recalculated"
            batch.counters = {"competences": len(revisions), "events": event_count}
            batch.finished_at = timezone.now()
            batch.save(update_fields=("status", "phase", "counters", "finished_at"))
    except Exception as exc:
        ImportBatch.objects.filter(pk=batch.pk).update(
            status=ImportBatch.Status.FAILED,
            phase="failed",
            error_code=type(exc).__name__,
            error_message=str(exc)[:2000],
            finished_at=timezone.now(),
        )
        raise
    return event_count


def import_window_package(
    manifest_path: Path, *, allow_revision: bool = False
) -> WindowImportResult:
    batch = ImportBatch.objects.create(
        operation=ImportBatch.Operation.IMPORT,
        status=ImportBatch.Status.VALIDATING,
        phase="window_validation",
        sanitized_options={
            "manifest_name": Path(manifest_path).name,
            "allow_revision": allow_revision,
        },
    )
    try:
        validated = validate_window_package(manifest_path)
        batch.sanitized_options = {
            **batch.sanitized_options,
            "window_code": validated.manifest.window_code,
            "window_manifest_sha256": validated.manifest_sha256,
            "competences": len(validated.packages),
        }
        batch.save(update_fields=("sanitized_options",))
        existing = HistoricalWindow.objects.filter(code=validated.manifest.window_code).first()
        if existing:
            return _handle_existing_window(
                existing,
                validated,
                batch,
                allow_revision=allow_revision,
            )
        with transaction.atomic():
            result = _import_validated_window(validated, batch)
        return result
    except Exception as exc:
        ImportBatch.objects.filter(pk=batch.pk).update(
            status=ImportBatch.Status.FAILED,
            phase="failed",
            error_code=type(exc).__name__,
            error_message=str(exc)[:2000],
            finished_at=timezone.now(),
        )
        raise


def _handle_existing_window(
    window: HistoricalWindow,
    validated: ValidatedWindow,
    batch: ImportBatch,
    *,
    allow_revision: bool,
) -> WindowImportResult:
    _assert_revision_compatible(window, validated)
    active_revisions = {
        revision.window_competence.competence.strftime("%Y-%m"): revision
        for revision in CompetenceRevision.objects.filter(
            window_competence__historical_window=window,
            status__in=CompetenceRevision.ACTIVE_STATUSES,
        ).select_related("window_competence")
    }
    changed_competences = tuple(
        package.manifest.competence
        for package in validated.packages
        if (
            package.manifest.competence not in active_revisions
            or active_revisions[package.manifest.competence].package_hash != package.manifest_sha256
        )
    )
    if changed_competences:
        if not allow_revision:
            joined = ", ".join(changed_competences)
            raise WindowImportError(
                f"Pacote diferente para competência(s) {joined}; "
                "repita com --allow-revision para publicar revisão explícita."
            )
        if window.status != HistoricalWindow.Status.ACTIVE:
            raise WindowImportError("Somente a janela ativa pode receber correção mensal.")
        with transaction.atomic():
            return _revise_existing_window(window, validated, batch, changed_competences)

    with transaction.atomic():
        for package in validated.packages:
            revision = active_revisions.get(package.manifest.competence)
            if revision is None or revision.package_hash != package.manifest_sha256:
                raise WindowImportError(
                    "A janela existente não possui a revisão ativa declarada pelo manifesto."
                )
            _persist_revision_artifacts(revision, package)
    event_count = window.change_events.count()
    warning_count = sum(
        revision.warning_count
        for competence in window.competences.all()
        for revision in competence.revisions.filter(status__in=CompetenceRevision.ACTIVE_STATUSES)
    )
    batch.status = ImportBatch.Status.COMPLETED
    batch.phase = "no_op"
    batch.counters = {
        "no_op": True,
        "window_manifest_changed": window.manifest_hash != validated.manifest_sha256,
        "competences": window.competences.count(),
        "events": event_count,
        "warnings": warning_count,
    }
    batch.finished_at = timezone.now()
    batch.save(update_fields=("status", "phase", "counters", "finished_at"))
    return WindowImportResult(
        window=window,
        imported=False,
        competence_count=window.competences.count(),
        event_count=event_count,
        warning_count=warning_count,
        batch_id=str(batch.pk),
    )


def _assert_revision_compatible(window, validated) -> None:
    manifest = validated.manifest
    existing_competences = list(
        window.competences.order_by("position").values_list("competence", flat=True)
    )
    incoming_competences = [
        _competence_date(package.manifest.competence) for package in validated.packages
    ]
    same_identity = (
        str(window.pk) == manifest.window_id
        and window.geographic_scope.code == manifest.scope_code
        and window.geographic_scope.version == manifest.scope_version
        and window.geographic_scope.scope_hash == manifest.scope_hash
        and window.cohort_hash == manifest.cohort_hash
        and window.contract_version == manifest.contract_version
        and window.start_competence == _competence_date(manifest.start_competence)
        and window.end_competence == _competence_date(manifest.end_competence)
        and existing_competences == incoming_competences
    )
    if not same_identity:
        raise WindowImportError(
            f"A janela {window.code} mudou recorte, coorte, contrato ou sequência; "
            "prepare uma nova identidade de janela."
        )


def _revise_existing_window(
    window,
    validated,
    batch,
    changed_competences: tuple[str, ...],
) -> WindowImportResult:
    window = (
        HistoricalWindow.objects.select_for_update()
        .select_related("geographic_scope")
        .get(pk=window.pk)
    )
    _assert_revision_compatible(window, validated)
    window_competences = list(window.competences.select_for_update().order_by("position"))
    active_revisions = {
        revision.window_competence_id: revision
        for revision in CompetenceRevision.objects.filter(
            window_competence__historical_window=window,
            status__in=CompetenceRevision.ACTIVE_STATUSES,
        ).select_related("window_competence")
    }
    if len(active_revisions) != len(window_competences):
        raise WindowImportError("A janela não possui uma revisão ativa para cada competência.")

    changed_indexes = {
        index
        for index, package in enumerate(validated.packages)
        if package.manifest.competence in changed_competences
    }
    scope_pairs = set(
        ScopeMunicipality.objects.filter(scope=window.geographic_scope).values_list(
            "municipality__ibge_code", "municipality__tom_code"
        )
    )
    batch.status = ImportBatch.Status.LOADING
    batch.phase = "revision_snapshots"
    batch.save(update_fields=("status", "phase"))

    selected_revisions = []
    old_revisions = {}
    row_counts_by_index = {}
    revision_issues = {}
    for index, (window_competence, package) in enumerate(
        zip(window_competences, validated.packages, strict=True)
    ):
        active_revision = active_revisions[window_competence.pk]
        if index not in changed_indexes:
            selected_revisions.append(active_revision)
            row_counts_by_index[index] = active_revision.row_counts
            continue

        revision = CompetenceRevision.objects.create(
            window_competence=window_competence,
            revision_number=active_revision.revision_number + 1,
            package_hash=package.manifest_sha256,
            contract_version=package.manifest.contract_version,
            manifest=package.manifest.to_dict(),
        )
        _persist_revision_artifacts(revision, package)
        row_counts = _load_package_snapshots(
            package=package,
            revision=revision,
            scope_pairs=scope_pairs,
        )
        package_issues = [_package_warning(value) for value in package.manifest.warnings]
        package_issues = _enforce_warning_threshold(package_issues, row_counts, row_counts)
        selected_revisions.append(revision)
        old_revisions[index] = active_revision
        row_counts_by_index[index] = row_counts
        revision_issues[index] = package_issues

    affected_intervals = sorted(
        {
            interval
            for index in changed_indexes
            for interval in (index - 1, index)
            if 0 <= interval < len(validated.packages) - 1
        }
    )
    interval_events = {}
    for interval in affected_intervals:
        previous_package = validated.packages[interval]
        current_package = validated.packages[interval + 1]
        candidates, issues = _compare_packages(
            previous_package=previous_package,
            current_package=current_package,
            previous_competence=_competence_date(previous_package.manifest.competence),
            current_competence=_competence_date(current_package.manifest.competence),
        )
        issues = _enforce_warning_threshold(
            issues,
            row_counts_by_index[interval],
            row_counts_by_index[interval + 1],
        )
        owner_index = interval + 1 if interval + 1 in changed_indexes else interval
        revision_issues[owner_index].extend(issues)
        interval_events[interval] = candidates

    batch.status = ImportBatch.Status.PUBLISHING
    batch.phase = "revision_publication"
    batch.save(update_fields=("status", "phase"))
    for interval in affected_intervals:
        previous_competence = window_competences[interval]
        current_competence = window_competences[interval + 1]
        ChangeEvent.objects.filter(
            historical_window=window,
            from_revision__window_competence=previous_competence,
            to_revision__window_competence=current_competence,
        ).delete()

    revised_warning_count = 0
    for index in sorted(changed_indexes):
        revision = selected_revisions[index]
        issues = revision_issues[index]
        _persist_quality_issues(issues, revision, batch)
        revised_warning_count += len(issues)
        old_revision = old_revisions[index]
        old_revision.status = CompetenceRevision.Status.SUPERSEDED
        old_revision.save(update_fields=("status",))
        revision.row_counts = row_counts_by_index[index]
        revision.warning_count = len(issues)
        revision.status = (
            CompetenceRevision.Status.PUBLISHED_WITH_WARNINGS
            if issues
            else CompetenceRevision.Status.PUBLISHED
        )
        revision.validated_at = timezone.now()
        revision.published_at = revision.validated_at
        revision.save(
            update_fields=(
                "row_counts",
                "warning_count",
                "status",
                "validated_at",
                "published_at",
            )
        )
        persist_revision_metrics(revision)

    for interval in affected_intervals:
        _persist_events(
            candidates=interval_events[interval],
            window=window,
            from_revision=selected_revisions[interval],
            to_revision=selected_revisions[interval + 1],
            batch=batch,
        )

    window.manifest_hash = validated.manifest_sha256
    window.save(update_fields=("manifest_hash",))
    active_warning_count = sum(revision.warning_count for revision in selected_revisions)
    event_count = window.change_events.count()
    batch.competence_revision = (
        selected_revisions[next(iter(changed_indexes))] if len(changed_indexes) == 1 else None
    )
    batch.status = ImportBatch.Status.COMPLETED
    batch.phase = "revision_published"
    batch.counters = {
        "revised_competences": list(changed_competences),
        "affected_intervals": len(affected_intervals),
        "revision_warnings": revised_warning_count,
        "competences": len(selected_revisions),
        "events": event_count,
        "warnings": active_warning_count,
    }
    batch.finished_at = timezone.now()
    batch.save(
        update_fields=(
            "competence_revision",
            "status",
            "phase",
            "counters",
            "finished_at",
        )
    )
    return WindowImportResult(
        window=window,
        imported=True,
        competence_count=len(selected_revisions),
        event_count=event_count,
        warning_count=active_warning_count,
        batch_id=str(batch.pk),
        revised_competences=changed_competences,
    )


def _import_validated_window(validated: ValidatedWindow, batch: ImportBatch) -> WindowImportResult:
    manifest = validated.manifest
    scope = GeographicScope.objects.select_for_update().get(
        code=manifest.scope_code, version=manifest.scope_version
    )
    if scope.scope_hash != manifest.scope_hash:
        raise WindowImportError("O hash do recorte carregado diverge do pacote.")
    scope_pairs = set(
        ScopeMunicipality.objects.filter(scope=scope).values_list(
            "municipality__ibge_code", "municipality__tom_code"
        )
    )

    window = HistoricalWindow.objects.create(
        id=manifest.window_id,
        geographic_scope=scope,
        code=manifest.window_code,
        start_competence=_competence_date(manifest.start_competence),
        end_competence=_competence_date(manifest.end_competence),
        contract_version=manifest.contract_version,
        cohort_hash=manifest.cohort_hash,
        manifest_hash=validated.manifest_sha256,
        status=HistoricalWindow.Status.PREPARING,
    )
    batch.status = ImportBatch.Status.LOADING
    batch.phase = "snapshots"
    batch.save(update_fields=("status", "phase"))

    previous_package = None
    previous_competence = None
    previous_row_counts = None
    event_count = 0
    warning_count = 0
    row_totals = {name: 0 for name in TABLE_CONTRACTS}
    revisions = []

    for position, package in enumerate(validated.packages, start=1):
        competence = _competence_date(package.manifest.competence)
        window_competence = WindowCompetence.objects.create(
            historical_window=window, competence=competence, position=position
        )
        revision = CompetenceRevision.objects.create(
            window_competence=window_competence,
            revision_number=1,
            package_hash=package.manifest_sha256,
            contract_version=package.manifest.contract_version,
            manifest=package.manifest.to_dict(),
        )
        _persist_revision_artifacts(revision, package)
        row_counts = _load_package_snapshots(
            package=package,
            revision=revision,
            scope_pairs=scope_pairs,
        )
        for name, count in row_counts.items():
            row_totals[name] += count

        revision_issues = [_package_warning(item) for item in package.manifest.warnings]
        if previous_package is not None:
            candidates, comparison_issues = _compare_packages(
                previous_package=previous_package,
                current_package=package,
                previous_competence=previous_competence,
                current_competence=competence,
            )
            revision_issues.extend(comparison_issues)
            event_count += _persist_events(
                candidates=candidates,
                window=window,
                from_revision=revisions[-1],
                to_revision=revision,
                batch=batch,
            )
        revision_issues = _enforce_warning_threshold(
            revision_issues,
            previous_row_counts or {"companies": 0, "establishments": 0, "partners": 0},
            row_counts,
        )
        _persist_quality_issues(revision_issues, revision, batch)
        warning_count += len(revision_issues)

        revision.row_counts = row_counts
        revision.warning_count = len(revision_issues)
        revision.status = (
            CompetenceRevision.Status.PUBLISHED_WITH_WARNINGS
            if revision_issues
            else CompetenceRevision.Status.PUBLISHED
        )
        revision.validated_at = timezone.now()
        revision.published_at = revision.validated_at
        revision.save(
            update_fields=(
                "row_counts",
                "warning_count",
                "status",
                "validated_at",
                "published_at",
            )
        )
        persist_revision_metrics(revision)
        revisions.append(revision)
        previous_package = package
        previous_competence = competence
        previous_row_counts = row_counts

    HistoricalWindow.objects.filter(status=HistoricalWindow.Status.ACTIVE).exclude(
        pk=window.pk
    ).update(status=HistoricalWindow.Status.SUPERSEDED)
    window.status = HistoricalWindow.Status.ACTIVE
    window.activated_at = timezone.now()
    window.save(update_fields=("status", "activated_at"))

    batch.status = ImportBatch.Status.COMPLETED
    batch.phase = "published"
    batch.counters = {
        "competences": len(validated.packages),
        "rows": row_totals,
        "events": event_count,
        "warnings": warning_count,
    }
    batch.finished_at = timezone.now()
    batch.save(update_fields=("status", "phase", "counters", "finished_at"))
    return WindowImportResult(
        window=window,
        imported=True,
        competence_count=len(validated.packages),
        event_count=event_count,
        warning_count=warning_count,
        batch_id=str(batch.pk),
    )


def _persist_revision_artifacts(revision, package) -> None:
    competence = package.manifest.competence
    generated_at = parse_datetime(package.manifest.generated_at)
    if generated_at is None:
        raise WindowImportError(f"generated_at inválido no pacote da competência {competence}.")

    PackageArtifact.objects.update_or_create(
        competence_revision=revision,
        artifact_type=PackageArtifact.ArtifactType.MANIFEST,
        defaults={
            "relative_path": f"{competence}/{package.manifest_path.name}",
            "sha256": package.manifest_sha256,
            "size_bytes": package.manifest_path.stat().st_size,
            "row_count": 0,
            "schema": {
                "contract_version": package.manifest.contract_version,
                "contract_hash": package.manifest.contract_hash,
            },
        },
    )
    artifact_types = {
        "companies": PackageArtifact.ArtifactType.COMPANIES,
        "establishments": PackageArtifact.ArtifactType.ESTABLISHMENTS,
        "partners": PackageArtifact.ArtifactType.PARTNERS,
    }
    for artifact in package.manifest.artifacts:
        PackageArtifact.objects.update_or_create(
            competence_revision=revision,
            artifact_type=artifact_types[artifact.artifact_type],
            defaults={
                "relative_path": f"{competence}/{artifact.file_name}",
                "sha256": artifact.sha256,
                "size_bytes": artifact.size_bytes,
                "row_count": artifact.row_count,
                "schema": {"schema_hash": artifact.schema_hash},
            },
        )

    for source in package.manifest.sources:
        SourceArtifact.objects.update_or_create(
            competence_revision=revision,
            source_type=source.source_type,
            file_name=source.file_name,
            defaults={
                "source_url": source.url,
                "competence": _competence_date(competence),
                "size_bytes": source.size_bytes,
                "sha256": source.sha256,
                "acquired_at": generated_at,
            },
        )


def _load_package_snapshots(
    *, package: ValidatedPackage, revision: CompetenceRevision, scope_pairs: set
) -> dict[str, int]:
    row_counts = {}

    company_rows = _read_parquet_rows(package.artifacts["companies"].path)
    _validate_table_rows("companies", company_rows, scope_pairs)
    company_map = _ensure_companies(row["cnpj_basic"] for row in company_rows)
    for chunk in _chunks(company_rows, 2000):
        CompanySnapshot.objects.bulk_create(
            [
                CompanySnapshot(
                    revision=revision,
                    company=company_map[row["cnpj_basic"]],
                    **_without(row, "cnpj_basic", "competence"),
                )
                for row in chunk
            ],
            batch_size=2000,
        )
    row_counts["companies"] = len(company_rows)
    del company_rows, company_map

    establishment_rows = _read_parquet_rows(package.artifacts["establishments"].path)
    _validate_table_rows("establishments", establishment_rows, scope_pairs)
    company_map = _ensure_companies(row["cnpj_basic"] for row in establishment_rows)
    municipality_map = _ensure_municipalities(establishment_rows)
    establishment_map = _ensure_establishments(establishment_rows, company_map)
    for chunk in _chunks(establishment_rows, 2000):
        EstablishmentSnapshot.objects.bulk_create(
            [
                EstablishmentSnapshot(
                    revision=revision,
                    establishment=establishment_map[row["cnpj"]],
                    municipality=municipality_map[row["municipality_ibge_code"]],
                    **_without(
                        row,
                        "cnpj",
                        "cnpj_basic",
                        "competence",
                        "municipality_ibge_code",
                        "municipality_name",
                    ),
                )
                for row in chunk
            ],
            batch_size=2000,
        )
    row_counts["establishments"] = len(establishment_rows)
    del establishment_rows, company_map, municipality_map, establishment_map

    partner_rows = _read_parquet_rows(package.artifacts["partners"].path)
    _validate_table_rows("partners", partner_rows, scope_pairs)
    company_map = _ensure_companies(row["cnpj_basic"] for row in partner_rows)
    participation_map = _ensure_participations(partner_rows, company_map)
    for chunk in _chunks(partner_rows, 2000):
        PartnerSnapshot.objects.bulk_create(
            [
                PartnerSnapshot(
                    revision=revision,
                    participation=participation_map[(row["cnpj_basic"], row["partner_key"])],
                    **_without(
                        row,
                        "cnpj_basic",
                        "partner_key",
                        "partner_type",
                        "competence",
                    ),
                )
                for row in chunk
            ],
            batch_size=2000,
        )
    row_counts["partners"] = len(partner_rows)
    return row_counts


def _validate_table_rows(table_name: str, table_rows: list[dict], scope_pairs: set) -> None:
    rows = {name: [] for name in TABLE_CONTRACTS}
    rows[table_name] = table_rows
    _validate_business_rows(rows, scope_pairs)


def _compare_revisions(*, previous_revision, current_revision):
    candidates = []
    empty = {"companies": {}, "establishments": {}, "partners": {}}

    previous_companies, current_companies = _changed_company_revision_rows(
        previous_revision, current_revision
    )
    table_candidates, _ = compare_snapshots(
        previous_competence=previous_revision.window_competence.competence,
        current_competence=current_revision.window_competence.competence,
        previous_companies=previous_companies,
        current_companies=current_companies,
        previous_establishments=empty["establishments"],
        current_establishments=empty["establishments"],
        previous_partners=empty["partners"],
        current_partners=empty["partners"],
    )
    candidates.extend(table_candidates)

    previous_establishments, current_establishments = _changed_establishment_revision_rows(
        previous_revision, current_revision
    )
    table_candidates, _ = compare_snapshots(
        previous_competence=previous_revision.window_competence.competence,
        current_competence=current_revision.window_competence.competence,
        previous_companies=empty["companies"],
        current_companies=empty["companies"],
        previous_establishments=previous_establishments,
        current_establishments=current_establishments,
        previous_partners=empty["partners"],
        current_partners=empty["partners"],
    )
    candidates.extend(table_candidates)

    previous_partners, current_partners = _changed_partner_revision_rows(
        previous_revision, current_revision
    )
    company_keys = {key[0] for key in previous_partners.keys() | current_partners.keys()}
    previous_company_keys = set(
        CompanySnapshot.objects.filter(
            revision=previous_revision, company__cnpj_basic__in=company_keys
        ).values_list("company__cnpj_basic", flat=True)
    )
    current_company_keys = set(
        CompanySnapshot.objects.filter(
            revision=current_revision, company__cnpj_basic__in=company_keys
        ).values_list("company__cnpj_basic", flat=True)
    )
    comparable_companies = _unchanged_company_placeholders(
        previous_company_keys & current_company_keys
    )
    table_candidates, _ = compare_snapshots(
        previous_competence=previous_revision.window_competence.competence,
        current_competence=current_revision.window_competence.competence,
        previous_companies=comparable_companies,
        current_companies=comparable_companies,
        previous_establishments=empty["establishments"],
        current_establishments=empty["establishments"],
        previous_partners=previous_partners,
        current_partners=current_partners,
    )
    candidates.extend(table_candidates)
    return candidates


def _changed_company_revision_rows(previous_revision, current_revision):
    fields = (
        "share_capital",
        "legal_nature_code",
        "company_size_code",
        "simples_optant",
        "simples_option_date",
        "simples_exclusion_date",
        "mei_optant",
        "mei_option_date",
        "mei_exclusion_date",
    )
    pairs = _changed_snapshot_values(
        CompanySnapshot, "company", fields, previous_revision.pk, current_revision.pk
    )
    entity_ids = {side[0] for pair in pairs for side in pair if side[0] is not None}
    entities = Company.objects.in_bulk(entity_ids)
    return _snapshot_value_maps(pairs, fields, entities, lambda entity: entity.cnpj_basic)


def _changed_establishment_revision_rows(previous_revision, current_revision):
    fields = (
        "street_type",
        "street_name",
        "street_number",
        "address_complement",
        "neighborhood",
        "postal_code",
        "state_code",
        "municipality",
        "registration_status_code",
        "registration_status_date",
        "activity_start_date",
        "main_cnae_code",
        "is_in_region",
    )
    pairs = _changed_snapshot_values(
        EstablishmentSnapshot,
        "establishment",
        fields,
        previous_revision.pk,
        current_revision.pk,
    )
    entity_ids = {side[0] for pair in pairs for side in pair if side[0] is not None}
    entities = Establishment.objects.in_bulk(entity_ids)
    municipality_ids = {
        side[fields.index("municipality") + 1]
        for pair in pairs
        for side in pair
        if side[0] is not None
    }
    municipalities = Municipality.objects.in_bulk(municipality_ids)

    def transform(values):
        row = dict(zip(fields, values[1:], strict=True))
        municipality_id = row.pop("municipality")
        row["municipality_ibge_code"] = municipalities[municipality_id].ibge_code
        return row

    return _snapshot_value_maps(
        pairs, fields, entities, lambda entity: entity.cnpj, transform=transform
    )


def _changed_partner_revision_rows(previous_revision, current_revision):
    fields = (
        "display_name",
        "partner_cnpj_basic",
        "qualification_code",
        "entry_date",
    )
    pairs = _changed_snapshot_values(
        PartnerSnapshot,
        "participation",
        fields,
        previous_revision.pk,
        current_revision.pk,
    )
    entity_ids = {side[0] for pair in pairs for side in pair if side[0] is not None}
    entities = {
        participation.pk: participation
        for participation in PartnerParticipation.objects.filter(pk__in=entity_ids).select_related(
            "company"
        )
    }

    def key(participation):
        return participation.company.cnpj_basic, participation.partner_key

    def transform(values):
        participation = entities[values[0]]
        return {
            "partner_type": participation.partner_type,
            **dict(zip(fields, values[1:], strict=True)),
        }

    return _snapshot_value_maps(pairs, fields, entities, key, transform=transform)


def _changed_snapshot_values(
    model, entity_field, fields, previous_revision_id, current_revision_id
):
    quote = connection.ops.quote_name
    table = quote(model._meta.db_table)
    entity_column = quote(model._meta.get_field(entity_field).column)
    field_columns = [quote(model._meta.get_field(field).column) for field in fields]
    selected = ", ".join([entity_column, *field_columns])
    sql = (
        f"SELECT {', '.join(f'p.{column}' for column in [entity_column, *field_columns])}, "
        f"{', '.join(f'c.{column}' for column in [entity_column, *field_columns])} "
        f"FROM (SELECT {selected}, record_hash FROM {table} WHERE revision_id = %s) p "
        f"FULL OUTER JOIN (SELECT {selected}, record_hash FROM {table} "
        f"WHERE revision_id = %s) c ON p.{entity_column} = c.{entity_column} "
        "WHERE p.record_hash IS DISTINCT FROM c.record_hash"
    )
    width = len(fields) + 1
    with connection.cursor() as cursor:
        cursor.execute(sql, [previous_revision_id, current_revision_id])
        return [(row[:width], row[width:]) for row in cursor.fetchall()]


def _snapshot_value_maps(pairs, fields, entities, key, *, transform=None):
    transform = transform or (lambda values: dict(zip(fields, values[1:], strict=True)))
    previous = {}
    current = {}
    for previous_values, current_values in pairs:
        if previous_values[0] is not None:
            previous[key(entities[previous_values[0]])] = transform(previous_values)
        if current_values[0] is not None:
            current[key(entities[current_values[0]])] = transform(current_values)
    return previous, current


def _read_parquet_rows(path: Path) -> list[dict[str, Any]]:
    connection = duckdb.connect(":memory:")
    try:
        cursor = connection.execute("SELECT * FROM read_parquet(?)", [str(path)])
        columns = [item[0] for item in cursor.description]
        result = []
        while batch := cursor.fetchmany(10_000):
            result.extend(dict(zip(columns, row, strict=True)) for row in batch)
        return result
    finally:
        connection.close()


def _compare_packages(
    *,
    previous_package,
    current_package,
    previous_competence,
    current_competence,
):
    candidates = []
    issues = []
    empty = {"companies": {}, "establishments": {}, "partners": {}}
    for table_name, contract in TABLE_CONTRACTS.items():
        previous_rows, current_rows = _read_changed_parquet_rows(
            previous_package.artifacts[table_name].path,
            current_package.artifacts[table_name].path,
            contract,
        )
        previous = {**empty, table_name: previous_rows}
        current = {**empty, table_name: current_rows}
        if table_name == "partners":
            partner_company_keys = {key[0] for key in previous_rows.keys() | current_rows.keys()}
            comparable_companies = _comparable_company_placeholders(
                previous_package.artifacts["companies"].path,
                current_package.artifacts["companies"].path,
                partner_company_keys,
            )
            previous["companies"] = comparable_companies
            current["companies"] = comparable_companies
        table_candidates, table_issues = compare_snapshots(
            previous_competence=previous_competence,
            current_competence=current_competence,
            previous_companies=previous["companies"],
            current_companies=current["companies"],
            previous_establishments=previous["establishments"],
            current_establishments=current["establishments"],
            previous_partners=previous["partners"],
            current_partners=current["partners"],
        )
        candidates.extend(table_candidates)
        issues.extend(table_issues)
    return candidates, issues


def _read_changed_parquet_rows(previous_path: Path, current_path: Path, contract):
    identity_columns = tuple(
        column for column in contract.identity_columns if column != "competence"
    )
    join = " AND ".join(f'p."{column}" = c."{column}"' for column in identity_columns)
    sql = (
        "SELECT p, c FROM read_parquet(?) p FULL OUTER JOIN read_parquet(?) c ON "
        f"{join} WHERE p.record_hash IS DISTINCT FROM c.record_hash"
    )
    previous_rows = {}
    current_rows = {}
    connection = duckdb.connect(":memory:")
    try:
        cursor = connection.execute(sql, [str(previous_path), str(current_path)])
        while batch := cursor.fetchmany(10_000):
            for previous, current in batch:
                if previous[identity_columns[0]] is not None:
                    previous_rows[_record_identity(previous, identity_columns)] = previous
                if current[identity_columns[0]] is not None:
                    current_rows[_record_identity(current, identity_columns)] = current
    finally:
        connection.close()
    return previous_rows, current_rows


def _comparable_company_placeholders(previous_path: Path, current_path: Path, keys: set[str]):
    if not keys:
        return {}
    comparable = set()
    connection = duckdb.connect(":memory:")
    try:
        cursor = connection.execute(
            "SELECT p.cnpj_basic FROM read_parquet(?) p JOIN read_parquet(?) c USING (cnpj_basic)",
            [str(previous_path), str(current_path)],
        )
        while batch := cursor.fetchmany(10_000):
            comparable.update(row[0] for row in batch if row[0] in keys)
    finally:
        connection.close()
    return _unchanged_company_placeholders(comparable)


def _unchanged_company_placeholders(keys):
    unchanged = {
        "share_capital": None,
        "legal_nature_code": None,
        "company_size_code": None,
        "simples_optant": None,
        "simples_option_date": None,
        "simples_exclusion_date": None,
        "mei_optant": None,
        "mei_option_date": None,
        "mei_exclusion_date": None,
    }
    return {key: unchanged for key in keys}


def _record_identity(row: dict, identity_columns):
    values = tuple(row[column] for column in identity_columns)
    return values[0] if len(values) == 1 else values


def _validate_business_rows(rows: dict[str, list[dict]], scope_pairs: set) -> None:
    for table_rows in rows.values():
        for row in table_rows:
            if not SHA256_PATTERN.fullmatch(row["record_hash"]):
                raise WindowImportError("Hash de registro malformado.")
            if canonical_record_hash(row) != row["record_hash"]:
                raise WindowImportError("Hash de registro divergente.")

    for row in rows["companies"]:
        if not is_canonical_cnpj_basic(row["cnpj_basic"]):
            raise WindowImportError("CNPJ básico inválido no pacote.")
    for row in rows["establishments"]:
        if not is_canonical_cnpj(row["cnpj"]):
            raise WindowImportError("CNPJ completo inválido no pacote.")
        if row["cnpj"][:8] != row["cnpj_basic"]:
            raise WindowImportError("CNPJ básico diverge do estabelecimento.")
        pair = (row["municipality_ibge_code"], row["municipality_tom_code"])
        if row["is_in_region"] != (pair in scope_pairs):
            raise WindowImportError("Indicador regional diverge do recorte canônico.")
    for row in rows["partners"]:
        if not is_canonical_cnpj_basic(row["cnpj_basic"]):
            raise WindowImportError("Participação com CNPJ básico inválido.")
        if not SHA256_PATTERN.fullmatch(row["partner_key"]):
            raise WindowImportError("Chave de participação inválida.")
        if row["partner_type"] not in PartnerParticipation.PartnerType.values:
            raise WindowImportError("Tipo de participação inválido.")
        if row["partner_cnpj_basic"] and not is_canonical_cnpj_basic(row["partner_cnpj_basic"]):
            raise WindowImportError("CNPJ básico de sócio PJ inválido.")


def _ensure_companies(values: Iterable[str]) -> dict[str, Company]:
    unique = sorted(set(values))
    for chunk in _chunks(unique, 2000):
        Company.objects.bulk_create(
            [Company(cnpj_basic=value) for value in chunk],
            ignore_conflicts=True,
            batch_size=2000,
        )
    return _in_bulk_chunks(Company, "cnpj_basic", unique)


def _ensure_municipalities(rows: list[dict]) -> dict[str, Municipality]:
    references = {row["municipality_ibge_code"]: row for row in rows}
    existing = _in_bulk_chunks(Municipality, "ibge_code", references)
    for ibge_code, municipality in existing.items():
        row = references[ibge_code]
        observed = (municipality.tom_code, municipality.name, municipality.uf)
        expected = (
            row["municipality_tom_code"],
            row["municipality_name"],
            row["state_code"],
        )
        if observed != expected:
            raise WindowImportError(f"Município {ibge_code} diverge do catálogo canônico.")
    missing = references.keys() - existing.keys()
    Municipality.objects.bulk_create(
        [
            Municipality(
                ibge_code=ibge_code,
                tom_code=references[ibge_code]["municipality_tom_code"],
                name=references[ibge_code]["municipality_name"],
                uf=references[ibge_code]["state_code"],
            )
            for ibge_code in missing
        ],
        batch_size=2000,
    )
    return _in_bulk_chunks(Municipality, "ibge_code", references)


def _ensure_establishments(
    rows: list[dict], companies: dict[str, Company]
) -> dict[str, Establishment]:
    references = {row["cnpj"]: row for row in rows}
    for chunk in _chunks(references.values(), 2000):
        Establishment.objects.bulk_create(
            [
                Establishment(company=companies[row["cnpj_basic"]], cnpj=row["cnpj"])
                for row in chunk
            ],
            ignore_conflicts=True,
            batch_size=2000,
        )
    result = _in_bulk_chunks(Establishment, "cnpj", references)
    for cnpj, establishment in result.items():
        if establishment.company_id != companies[references[cnpj]["cnpj_basic"]].pk:
            raise WindowImportError(f"Empresa divergente para o estabelecimento {cnpj}.")
    return result


def _ensure_participations(
    rows: list[dict], companies: dict[str, Company]
) -> dict[tuple[str, str], PartnerParticipation]:
    references = {(row["cnpj_basic"], row["partner_key"]): row for row in rows}
    for chunk in _chunks(references.values(), 2000):
        PartnerParticipation.objects.bulk_create(
            [
                PartnerParticipation(
                    company=companies[row["cnpj_basic"]],
                    partner_key=row["partner_key"],
                    partner_type=row["partner_type"],
                )
                for row in chunk
            ],
            ignore_conflicts=True,
            batch_size=2000,
        )
    result = {}
    keys = [key[1] for key in references]
    for chunk in _chunks(keys, 2000):
        for participation in PartnerParticipation.objects.filter(
            partner_key__in=chunk
        ).select_related("company"):
            natural_key = (participation.company.cnpj_basic, participation.partner_key)
            if natural_key in references:
                if participation.partner_type != references[natural_key]["partner_type"]:
                    raise WindowImportError("Tipo divergente para participação existente.")
                result[natural_key] = participation
    if result.keys() != references.keys():
        raise WindowImportError("Não foi possível materializar todas as participações.")
    return result


def _persist_events(*, candidates, window, from_revision, to_revision, batch) -> int:
    entities = _event_entities(candidates)
    objects = []
    for candidate in candidates:
        target = {}
        if candidate.entity_type == "COMPANY":
            target["company"] = entities["companies"][candidate.entity_key]
        elif candidate.entity_type == "ESTABLISHMENT":
            target["establishment"] = entities["establishments"][candidate.entity_key]
        else:
            target["participation"] = entities["participations"][candidate.entity_key]
        event_key = _event_key(
            window.code,
            from_revision.package_hash,
            to_revision.package_hash,
            candidate.entity_type,
            candidate.entity_key,
            candidate.dimension,
            candidate.event_type,
        )
        objects.append(
            ChangeEvent(
                event_key=event_key,
                historical_window=window,
                from_revision=from_revision,
                to_revision=to_revision,
                entity_type=candidate.entity_type,
                dimension=candidate.dimension,
                event_type=candidate.event_type,
                previous_value=candidate.previous_value,
                new_value=candidate.new_value,
                source_effective_date=candidate.source_effective_date,
                import_batch=batch,
                **target,
            )
        )
    ChangeEvent.objects.bulk_create(objects, batch_size=2000)
    return len(objects)


def _event_entities(candidates) -> dict[str, dict]:
    company_keys = {
        candidate.entity_key for candidate in candidates if candidate.entity_type == "COMPANY"
    }
    establishment_keys = {
        candidate.entity_key for candidate in candidates if candidate.entity_type == "ESTABLISHMENT"
    }
    participation_keys = {
        candidate.entity_key for candidate in candidates if candidate.entity_type == "PARTICIPATION"
    }
    participations = {}
    for chunk in _chunks((key[1] for key in participation_keys), 2000):
        for participation in PartnerParticipation.objects.filter(
            partner_key__in=chunk
        ).select_related("company"):
            key = (participation.company.cnpj_basic, participation.partner_key)
            if key in participation_keys:
                participations[key] = participation
    entities = {
        "companies": _in_bulk_chunks(Company, "cnpj_basic", company_keys),
        "establishments": _in_bulk_chunks(Establishment, "cnpj", establishment_keys),
        "participations": participations,
    }
    expected_by_name = {
        "companies": company_keys,
        "establishments": establishment_keys,
        "participations": participation_keys,
    }
    missing_counts = {
        name: len(expected - entities[name].keys())
        for name, expected in expected_by_name.items()
        if entities[name].keys() != expected
    }
    if missing_counts:
        raise WindowImportError(
            f"Não foi possível resolver todas as entidades dos eventos: {missing_counts}."
        )
    return entities


def _persist_quality_issues(candidates, revision, batch) -> None:
    DataQualityIssue.objects.bulk_create(
        [
            DataQualityIssue(
                import_batch=batch,
                competence_revision=revision,
                rule_code=candidate.rule_code,
                severity=DataQualityIssue.Severity.WARNING,
                entity_type=candidate.entity_type,
                entity_key=candidate.entity_key,
                eligible_rows=candidate.details.get("eligible_rows", 1),
                affected_rows=candidate.affected_rows,
                details=candidate.details,
            )
            for candidate in candidates
        ],
        batch_size=2000,
    )


def _package_warning(value: str) -> QualityCandidate:
    parts = value.split(":", 2)
    rule_code = parts[0][:80]
    entity_key = parts[1][:80] if len(parts) > 1 else "PACKAGE"
    affected_rows = 1
    if len(parts) > 2 and parts[2].isdigit():
        affected_rows = int(parts[2])
    return QualityCandidate(
        rule_code=rule_code,
        entity_type=_package_warning_entity_type(rule_code, entity_key),
        entity_key=entity_key,
        details={"package_warning": value, "comparison_suspended": True},
        affected_rows=affected_rows,
    )


def _package_warning_entity_type(rule_code: str, entity_key: str) -> str:
    value = f"{rule_code}:{entity_key}".upper()
    if "PARTNER" in value or "SOCIO" in value:
        return "PARTICIPATION"
    if "ESTABLISH" in value or "ESTABELE" in value:
        return "ESTABLISHMENT"
    return "COMPANY"


def _enforce_warning_threshold(issues, previous_state, current_state):
    grouped = {}
    for issue in issues:
        grouped.setdefault((issue.rule_code, issue.entity_type), 0)
        grouped[(issue.rule_code, issue.entity_type)] += issue.affected_rows
    state_key = {
        "COMPANY": "companies",
        "ESTABLISHMENT": "establishments",
        "PARTICIPATION": "partners",
    }
    statistics = {}
    for (rule_code, entity_type), affected in grouped.items():
        key = state_key[entity_type]
        eligible = max(_state_size(previous_state[key]), _state_size(current_state[key]))
        warning_rate = WARNING_RATE_OVERRIDES.get(rule_code, 0.001)
        limit = max(10, math.ceil(eligible * warning_rate))
        statistics[(rule_code, entity_type)] = {
            "eligible_rows": eligible,
            "group_affected_rows": affected,
            "warning_rate": warning_rate,
            "warning_limit": limit,
        }
        if affected > limit:
            raise WindowImportError(
                f"Regra {rule_code} excedeu o limite de alertas: "
                f"afetados={affected}, elegíveis={eligible}, limite={limit}."
            )
    return [
        QualityCandidate(
            rule_code=issue.rule_code,
            entity_type=issue.entity_type,
            entity_key=issue.entity_key,
            details={
                **issue.details,
                **statistics[(issue.rule_code, issue.entity_type)],
            },
            affected_rows=issue.affected_rows,
        )
        for issue in issues
    ]


def _state_size(value) -> int:
    return value if isinstance(value, int) else len(value)


def persist_revision_metrics(revision: CompetenceRevision) -> None:
    regional = EstablishmentSnapshot.objects.filter(revision=revision, is_in_region=True)
    regional_company_ids = regional.values("establishment__company_id").distinct()
    specifications = [
        (
            "REGIONAL_COMPANIES_TOTAL",
            RegionalMonthlyMetric.EntityType.COMPANY,
            regional_company_ids.count(),
            {},
        ),
        (
            "REGIONAL_ESTABLISHMENTS_TOTAL",
            RegionalMonthlyMetric.EntityType.ESTABLISHMENT,
            regional.count(),
            {},
        ),
    ]
    for row in regional.values("municipality_id").annotate(value=Count("id")):
        specifications.append(
            (
                "REGIONAL_ESTABLISHMENTS_BY_MUNICIPALITY",
                RegionalMonthlyMetric.EntityType.ESTABLISHMENT,
                row["value"],
                {"municipality_id": row["municipality_id"]},
            )
        )
    for field, metric_type, dimension in (
        ("main_cnae_code", "REGIONAL_ESTABLISHMENTS_BY_CNAE", "cnae_code"),
        (
            "registration_status_code",
            "REGIONAL_ESTABLISHMENTS_BY_STATUS",
            "registration_status_code",
        ),
    ):
        for row in regional.values(field).annotate(value=Count("id")):
            specifications.append(
                (
                    metric_type,
                    RegionalMonthlyMetric.EntityType.ESTABLISHMENT,
                    row["value"],
                    {dimension: row[field]},
                )
            )

    for row in (
        CompanySnapshot.objects.filter(revision=revision, company_id__in=regional_company_ids)
        .values("company_size_code")
        .annotate(value=Count("id"))
    ):
        specifications.append(
            (
                "REGIONAL_COMPANIES_BY_SIZE",
                RegionalMonthlyMetric.EntityType.COMPANY,
                row["value"],
                {"company_size_code": row["company_size_code"]},
            )
        )

    objects = []
    for metric_type, entity_type, value, dimensions in specifications:
        key_payload = json.dumps(
            [revision.package_hash, metric_type, dimensions],
            sort_keys=True,
            separators=(",", ":"),
        )
        objects.append(
            RegionalMonthlyMetric(
                metric_key=hashlib.sha256(key_payload.encode()).hexdigest(),
                revision=revision,
                metric_type=metric_type,
                entity_type=entity_type,
                municipality_id=dimensions.get("municipality_id"),
                cnae_code=dimensions.get("cnae_code"),
                registration_status_code=dimensions.get("registration_status_code"),
                company_size_code=dimensions.get("company_size_code"),
                value=value,
            )
        )
    RegionalMonthlyMetric.objects.bulk_create(objects, batch_size=2000)


def _event_key(*parts: Any) -> str:
    payload = "\x1f".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode()).hexdigest()


def _in_bulk_chunks(model, field: str, values: Iterable[str]) -> dict:
    result = {}
    for chunk in _chunks(list(values), 2000):
        result.update(model.objects.in_bulk(chunk, field_name=field))
    return result


def _chunks(values: Iterable, size: int):
    chunk = []
    for value in values:
        chunk.append(value)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def _without(row: dict, *keys: str) -> dict:
    excluded = set(keys)
    return {key: value for key, value in row.items() if key not in excluded}


def _competence_date(value: str) -> date:
    return date.fromisoformat(f"{value}-01")
