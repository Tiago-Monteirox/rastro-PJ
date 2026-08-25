import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .schemas import CONTRACT_VERSION, TABLE_CONTRACTS, contract_bundle_hash

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COMPETENCE_PATTERN = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")


class ManifestError(ValueError):
    """Manifesto incompatível, incompleto ou adulterado."""


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def file_sha256(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.part")
    temporary_path.write_bytes(canonical_json_bytes(payload) + b"\n")
    temporary_path.replace(path)


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Manifesto ilegível: {path}.") from exc
    if not isinstance(payload, dict):
        raise ManifestError(f"Manifesto deve ser um objeto JSON: {path}.")
    return payload


@dataclass(frozen=True, slots=True)
class SourceManifest:
    source_type: str
    url: str
    file_name: str
    size_bytes: int
    sha256: str

    def validate(self) -> None:
        if not self.source_type or not self.url or not self.file_name:
            raise ManifestError("Fonte sem tipo, URL ou nome.")
        if self.size_bytes < 0:
            raise ManifestError(f"Fonte {self.file_name} possui tamanho negativo.")
        _validate_sha256(self.sha256, f"fonte {self.file_name}")


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    artifact_type: str
    file_name: str
    size_bytes: int
    row_count: int
    sha256: str
    schema_hash: str

    def validate(self) -> None:
        contract = TABLE_CONTRACTS.get(self.artifact_type)
        if contract is None:
            raise ManifestError(f"Tipo de artefato desconhecido: {self.artifact_type}.")
        if self.file_name != contract.filename:
            raise ManifestError(
                f"Arquivo incompatível para {self.artifact_type}: {self.file_name}."
            )
        if self.size_bytes < 0 or self.row_count < 0:
            raise ManifestError(f"Contagem negativa no artefato {self.file_name}.")
        _validate_sha256(self.sha256, f"artefato {self.file_name}")
        _validate_sha256(self.schema_hash, f"schema {self.file_name}")
        if self.schema_hash != contract.schema_hash:
            raise ManifestError(f"Schema incompatível no artefato {self.file_name}.")


@dataclass(frozen=True, slots=True)
class PackageManifest:
    contract_version: str
    contract_hash: str
    window_id: str
    competence: str
    scope_hash: str
    cohort_hash: str
    generated_at: str
    sources: tuple[SourceManifest, ...]
    artifacts: tuple[ArtifactManifest, ...]
    warnings: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.contract_version != CONTRACT_VERSION:
            raise ManifestError(f"Contrato incompatível: {self.contract_version}.")
        if self.contract_hash != contract_bundle_hash():
            raise ManifestError("Hash do contrato incompatível.")
        if not self.window_id:
            raise ManifestError("Pacote sem window_id.")
        if not COMPETENCE_PATTERN.fullmatch(self.competence):
            raise ManifestError(f"Competência inválida: {self.competence}.")
        _validate_sha256(self.scope_hash, "recorte")
        _validate_sha256(self.cohort_hash, "coorte")
        for source in self.sources:
            source.validate()
        for artifact in self.artifacts:
            artifact.validate()
        artifact_types = [artifact.artifact_type for artifact in self.artifacts]
        if len(artifact_types) != len(set(artifact_types)):
            raise ManifestError("Artefato duplicado no manifesto do pacote.")
        if set(artifact_types) != set(TABLE_CONTRACTS):
            raise ManifestError("O pacote deve conter companies, establishments e partners.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "contract_version": self.contract_version,
            "contract_hash": self.contract_hash,
            "window_id": self.window_id,
            "competence": self.competence,
            "scope_hash": self.scope_hash,
            "cohort_hash": self.cohort_hash,
            "generated_at": self.generated_at,
            "sources": [asdict(source) for source in self.sources],
            "artifacts": [asdict(artifact) for artifact in self.artifacts],
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PackageManifest":
        try:
            manifest = cls(
                contract_version=payload["contract_version"],
                contract_hash=payload["contract_hash"],
                window_id=payload["window_id"],
                competence=payload["competence"],
                scope_hash=payload["scope_hash"],
                cohort_hash=payload["cohort_hash"],
                generated_at=payload["generated_at"],
                sources=tuple(SourceManifest(**item) for item in payload["sources"]),
                artifacts=tuple(ArtifactManifest(**item) for item in payload["artifacts"]),
                warnings=tuple(payload.get("warnings", ())),
            )
        except (KeyError, TypeError) as exc:
            raise ManifestError("Estrutura inválida no manifesto do pacote.") from exc
        manifest.validate()
        return manifest


@dataclass(frozen=True, slots=True)
class WindowManifest:
    contract_version: str
    contract_hash: str
    window_id: str
    window_code: str
    start_competence: str
    end_competence: str
    scope_code: str
    scope_version: int
    scope_hash: str
    cohort_hash: str
    generated_at: str
    packages: tuple[dict[str, str], ...]

    def validate(self) -> None:
        if self.contract_version != CONTRACT_VERSION:
            raise ManifestError(f"Contrato incompatível: {self.contract_version}.")
        if self.contract_hash != contract_bundle_hash():
            raise ManifestError("Hash do contrato incompatível.")
        if not self.window_id or not self.window_code or not self.scope_code:
            raise ManifestError("Identidade incompleta no manifesto da janela.")
        if self.scope_version <= 0:
            raise ManifestError("Versão do recorte deve ser positiva.")
        for value in (self.start_competence, self.end_competence):
            if not COMPETENCE_PATTERN.fullmatch(value):
                raise ManifestError(f"Competência inválida: {value}.")
        if self.start_competence > self.end_competence:
            raise ManifestError("Início da janela posterior ao fim.")
        _validate_sha256(self.scope_hash, "recorte")
        _validate_sha256(self.cohort_hash, "coorte")
        observed = []
        for package in self.packages:
            try:
                competence = package["competence"]
                manifest_path = package["manifest_path"]
                manifest_sha256 = package["manifest_sha256"]
            except KeyError as exc:
                raise ManifestError("Referência de pacote incompleta.") from exc
            if not COMPETENCE_PATTERN.fullmatch(competence) or not manifest_path:
                raise ManifestError("Referência de pacote inválida.")
            _validate_sha256(manifest_sha256, f"manifesto {competence}")
            observed.append(competence)
        if observed != sorted(set(observed)):
            raise ManifestError("Pacotes da janela devem ser únicos e ordenados.")
        if observed and (
            observed[0] != self.start_competence or observed[-1] != self.end_competence
        ):
            raise ManifestError("Extremos dos pacotes não coincidem com a janela.")
        expected = _month_sequence(self.start_competence, self.end_competence)
        if observed != expected:
            raise ManifestError("Pacotes da janela devem formar uma sequência mensal contínua.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "contract_version": self.contract_version,
            "contract_hash": self.contract_hash,
            "window_id": self.window_id,
            "window_code": self.window_code,
            "start_competence": self.start_competence,
            "end_competence": self.end_competence,
            "scope_code": self.scope_code,
            "scope_version": self.scope_version,
            "scope_hash": self.scope_hash,
            "cohort_hash": self.cohort_hash,
            "generated_at": self.generated_at,
            "packages": list(self.packages),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WindowManifest":
        try:
            manifest = cls(
                contract_version=payload["contract_version"],
                contract_hash=payload["contract_hash"],
                window_id=payload["window_id"],
                window_code=payload["window_code"],
                start_competence=payload["start_competence"],
                end_competence=payload["end_competence"],
                scope_code=payload["scope_code"],
                scope_version=payload["scope_version"],
                scope_hash=payload["scope_hash"],
                cohort_hash=payload["cohort_hash"],
                generated_at=payload["generated_at"],
                packages=tuple(payload["packages"]),
            )
        except (KeyError, TypeError) as exc:
            raise ManifestError("Estrutura inválida no manifesto da janela.") from exc
        manifest.validate()
        return manifest


def _validate_sha256(value: str, label: str) -> None:
    if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
        raise ManifestError(f"SHA-256 inválido para {label}.")


def _month_sequence(start: str, end: str) -> list[str]:
    current = date.fromisoformat(f"{start}-01")
    last = date.fromisoformat(f"{end}-01")
    values = []
    while current <= last:
        values.append(current.strftime("%Y-%m"))
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return values
