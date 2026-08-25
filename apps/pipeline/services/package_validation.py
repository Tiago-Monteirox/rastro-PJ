from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb

from ..contracts import (
    TABLE_CONTRACTS,
    ManifestError,
    PackageManifest,
    WindowManifest,
    file_sha256,
    load_json,
)
from .parquet import ParquetValidation, validate_parquet


@dataclass(frozen=True)
class ValidatedArtifact:
    path: Path
    validation: ParquetValidation


@dataclass(frozen=True)
class ValidatedPackage:
    path: Path
    manifest_path: Path
    manifest: PackageManifest
    manifest_sha256: str
    artifacts: dict[str, ValidatedArtifact]


@dataclass(frozen=True)
class ValidatedWindow:
    manifest_path: Path
    manifest: WindowManifest
    manifest_sha256: str
    packages: tuple[ValidatedPackage, ...]


def validate_window_package(manifest_path: Path) -> ValidatedWindow:
    manifest_path = Path(manifest_path).resolve()
    manifest = WindowManifest.from_dict(load_json(manifest_path))
    root = manifest_path.parent
    packages = []

    for reference in manifest.packages:
        package_manifest_path = _safe_child(root, reference["manifest_path"])
        observed_manifest_hash = file_sha256(package_manifest_path)
        if observed_manifest_hash != reference["manifest_sha256"]:
            raise ManifestError(f"Hash do manifesto {reference['competence']} não confere.")

        package_manifest = PackageManifest.from_dict(load_json(package_manifest_path))
        _validate_package_identity(manifest, package_manifest, reference["competence"])
        package_root = package_manifest_path.parent
        artifacts = {}
        for artifact in package_manifest.artifacts:
            contract = TABLE_CONTRACTS[artifact.artifact_type]
            if artifact.file_name != contract.filename:
                raise ManifestError(
                    f"Nome inesperado para {artifact.artifact_type}: {artifact.file_name}."
                )
            artifact_path = _safe_child(package_root, artifact.file_name)
            validation = validate_parquet(contract=contract, path=artifact_path)
            expected = (
                artifact.size_bytes,
                artifact.row_count,
                artifact.sha256,
                artifact.schema_hash,
            )
            observed = (
                validation.size_bytes,
                validation.row_count,
                validation.sha256,
                validation.schema_hash,
            )
            if observed != expected:
                raise ManifestError(f"Metadados do artefato {artifact.file_name} não conferem.")
            _validate_competence_column(
                artifact_path, package_manifest.competence, validation.row_count
            )
            artifacts[artifact.artifact_type] = ValidatedArtifact(
                path=artifact_path, validation=validation
            )

        packages.append(
            ValidatedPackage(
                path=package_root,
                manifest_path=package_manifest_path,
                manifest=package_manifest,
                manifest_sha256=observed_manifest_hash,
                artifacts=artifacts,
            )
        )

    return ValidatedWindow(
        manifest_path=manifest_path,
        manifest=manifest,
        manifest_sha256=file_sha256(manifest_path),
        packages=tuple(packages),
    )


def _safe_child(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ManifestError(f"Caminho fora do pacote: {relative_path}.")
    if not candidate.is_file():
        raise ManifestError(f"Arquivo do pacote não encontrado: {relative_path}.")
    return candidate


def _validate_package_identity(
    window: WindowManifest, package: PackageManifest, expected_competence: str
) -> None:
    pairs = (
        ("window_id", package.window_id, window.window_id),
        ("competence", package.competence, expected_competence),
        ("scope_hash", package.scope_hash, window.scope_hash),
        ("cohort_hash", package.cohort_hash, window.cohort_hash),
        ("contract_version", package.contract_version, window.contract_version),
        ("contract_hash", package.contract_hash, window.contract_hash),
    )
    for label, observed, expected in pairs:
        if observed != expected:
            raise ManifestError(f"Identidade {label} divergente no pacote {expected_competence}.")


def _validate_competence_column(path: Path, competence: str, row_count: int) -> None:
    expected_date = f"{competence}-01"
    connection = duckdb.connect(":memory:")
    try:
        invalid_count = connection.execute(
            "SELECT count(*) FROM read_parquet(?) WHERE competence <> CAST(? AS DATE)",
            [str(path), expected_date],
        ).fetchone()[0]
    finally:
        connection.close()
    if invalid_count:
        raise ManifestError(
            f"Artefato {path.name} contém {invalid_count}/{row_count} competências divergentes."
        )
