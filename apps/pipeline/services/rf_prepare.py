from __future__ import annotations

import hashlib
import hmac
import json
import uuid
import zipfile
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import duckdb

from apps.registry.cnpj import (
    InvalidCNPJError,
    extract_cnpj_basic,
    parse_cnpj_identifier,
    validate_cnpj,
    validate_cnpj_basic,
)

from ..contracts import (
    CONTRACT_VERSION,
    TABLE_CONTRACTS,
    ArtifactManifest,
    ContractError,
    ManifestError,
    PackageManifest,
    SourceManifest,
    WindowManifest,
    contract_bundle_hash,
    file_sha256,
    load_json,
    write_json_atomic,
)
from .municipality_catalog import (
    MunicipalityResolver,
    fetch_ibge_catalog,
    load_rf_municipality_names,
)
from .normalization import (
    canonical_record_hash,
    normalize_search_text,
    remove_personal_document_sequences,
)
from .parquet import validate_parquet, write_parquet_atomic

COMPANY_COLUMNS = (
    "cnpj_basic",
    "legal_name",
    "legal_nature_code",
    "responsible_qualification",
    "share_capital",
    "company_size_code",
    "federative_entity",
)
ESTABLISHMENT_COLUMNS = (
    "cnpj_basic",
    "cnpj_order",
    "cnpj_check_digits",
    "branch_type",
    "trade_name",
    "registration_status_code",
    "registration_status_date",
    "registration_status_reason_code",
    "foreign_city_name",
    "country_code",
    "activity_start_date",
    "main_cnae_code",
    "secondary_cnae_codes",
    "street_type",
    "street_name",
    "street_number",
    "address_complement",
    "neighborhood",
    "postal_code",
    "state_code",
    "municipality_tom_code",
    "phone_area_1",
    "phone_1",
    "phone_area_2",
    "phone_2",
    "fax_area",
    "fax",
    "email",
    "special_status",
    "special_status_date",
)
PARTNER_COLUMNS = (
    "cnpj_basic",
    "partner_source_type",
    "display_name",
    "source_identifier",
    "qualification_code",
    "entry_date",
    "country_code",
    "representative_identifier",
    "representative_name",
    "representative_qualification",
    "age_range",
)
SIMPLES_COLUMNS = (
    "cnpj_basic",
    "simples_optant",
    "simples_option_date",
    "simples_exclusion_date",
    "mei_optant",
    "mei_option_date",
    "mei_exclusion_date",
)
RF_SOURCE_ENCODING = "utf-8"


class ReceitaPreparationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ExtractedCsv:
    path: Path
    replacement_count: int


def prepare_rf_window(
    *,
    competences: list[str],
    sources_root: Path,
    output_root: Path,
    work_root: Path,
    scope_code: str,
    scope_version: int,
    scope_hash: str,
    scope_tom_codes: set[str],
    partner_hmac_secret: str,
    ibge_cache_path: Path,
    window_code: str | None = None,
    progress: Callable[[str], None] | None = None,
    resume: bool = False,
) -> Path:
    _validate_competences(competences)
    if not partner_hmac_secret:
        raise ReceitaPreparationError("Segredo HMAC de sócios PF não configurado.")
    sources_root = Path(sources_root)
    output_root = Path(output_root)
    work_root = Path(work_root)
    output_root.mkdir(parents=True, exist_ok=True)
    work_root.mkdir(parents=True, exist_ok=True)
    duckdb_temp_directory = work_root / "duckdb-tmp"
    duckdb_temp_directory.mkdir(parents=True, exist_ok=True)
    emit = progress or (lambda message: None)
    source_manifests = {}
    for competence in competences:
        emit(f"Verificando hashes das 32 fontes de {competence}...")
        source_manifests[competence] = _verify_sources(sources_root / competence)
        emit(f"Fontes de {competence} verificadas.")
    ibge_catalog = fetch_ibge_catalog(ibge_cache_path)
    preparation_fingerprint = _preparation_fingerprint(
        competences=competences,
        source_manifests=source_manifests,
        scope_hash=scope_hash,
        scope_tom_codes=scope_tom_codes,
        partner_hmac_secret=partner_hmac_secret,
        ibge_source=ibge_catalog.to_source_manifest(),
    )
    resume_state_path = work_root / "preparation-state.json"
    resume_state = _load_resume_state(resume_state_path) if resume else None
    matching_resume_state = bool(
        resume_state and resume_state.get("fingerprint") == preparation_fingerprint
    )

    database_path = work_root / "preparation.duckdb"
    connection = duckdb.connect(str(database_path))
    try:
        connection.execute("SET memory_limit = '4GB'")
        connection.execute("SET threads = 4")
        connection.execute(f"SET temp_directory = '{_sql_path(duckdb_temp_directory)}'")
        cohort = _reusable_cohort(connection, resume_state) if matching_resume_state else None
        if cohort is None:
            emit(f"Descobrindo a coorte em {len(competences)} competência(s)...")
            _discover_cohort(
                connection,
                competences=competences,
                sources_root=sources_root,
                work_root=work_root,
                scope_tom_codes=scope_tom_codes,
                progress=emit,
            )
            cohort = [
                row[0]
                for row in connection.execute("SELECT cnpj FROM cohort ORDER BY cnpj").fetchall()
            ]
        else:
            emit(f"Coorte retomada do estado validado: {len(cohort)} estabelecimentos.")
        if not cohort:
            raise ReceitaPreparationError("A coorte regional ficou vazia.")
        emit(f"Coorte descoberta: {len(cohort)} estabelecimentos.")
        cohort_hash = hashlib.sha256("\n".join(cohort).encode()).hexdigest()
        (work_root / "cohort.txt").write_text("\n".join(cohort) + "\n", encoding="utf-8")
        write_json_atomic(
            resume_state_path,
            {
                "fingerprint": preparation_fingerprint,
                "cohort_hash": cohort_hash,
                "cohort_count": len(cohort),
            },
        )

        window_code = window_code or (
            f"rf-{competences[0]}-{competences[-1]}-{scope_code}-v{scope_version}"
        )
        window_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{window_code}:{scope_hash}:{cohort_hash}:{CONTRACT_VERSION}",
            )
        )
        generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        package_references = []
        for competence in competences:
            package_manifest_path = None
            if matching_resume_state:
                package_manifest_path = _reusable_package(
                    output_directory=output_root / competence,
                    competence=competence,
                    window_id=window_id,
                    scope_hash=scope_hash,
                    cohort_hash=cohort_hash,
                    expected_sources=tuple(source_manifests[competence])
                    + (ibge_catalog.to_source_manifest(),),
                )
            if package_manifest_path is None:
                emit(f"Preparando pacote normalizado de {competence}...")
                package_manifest_path = _prepare_competence(
                    connection,
                    competence=competence,
                    sources_directory=sources_root / competence,
                    output_directory=output_root / competence,
                    work_root=work_root,
                    window_id=window_id,
                    scope_hash=scope_hash,
                    scope_tom_codes=scope_tom_codes,
                    cohort_hash=cohort_hash,
                    source_manifests=source_manifests[competence],
                    ibge_catalog=ibge_catalog,
                    partner_hmac_secret=partner_hmac_secret,
                    generated_at=generated_at,
                    progress=emit,
                )
                emit(f"Pacote de {competence} preparado.")
            else:
                emit(f"Pacote validado de {competence} retomado.")
            package_references.append(
                {
                    "competence": competence,
                    "manifest_path": f"{competence}/package-manifest.json",
                    "manifest_sha256": file_sha256(package_manifest_path),
                }
            )
    finally:
        connection.close()

    manifest = WindowManifest(
        contract_version=CONTRACT_VERSION,
        contract_hash=contract_bundle_hash(),
        window_id=window_id,
        window_code=window_code,
        start_competence=competences[0],
        end_competence=competences[-1],
        scope_code=scope_code,
        scope_version=scope_version,
        scope_hash=scope_hash,
        cohort_hash=cohort_hash,
        generated_at=generated_at,
        packages=tuple(package_references),
    )
    manifest_path = output_root / "window-manifest.json"
    write_json_atomic(manifest_path, manifest.to_dict())
    return manifest_path


def _preparation_fingerprint(
    *,
    competences,
    source_manifests,
    scope_hash,
    scope_tom_codes,
    partner_hmac_secret,
    ibge_source,
) -> str:
    implementation_digest = hashlib.sha256()
    for path in (
        Path(__file__),
        Path(__file__).with_name("normalization.py"),
        Path(__file__).with_name("parquet.py"),
    ):
        implementation_digest.update(path.read_bytes())
    payload = {
        "competences": competences,
        "contract_hash": contract_bundle_hash(),
        "implementation_hash": implementation_digest.hexdigest(),
        "scope_hash": scope_hash,
        "scope_tom_codes": sorted(scope_tom_codes),
        "partner_hmac_secret_hash": hashlib.sha256(partner_hmac_secret.encode()).hexdigest(),
        "ibge_sha256": ibge_source.sha256,
        "sources": {
            competence: [
                {
                    "file_name": source.file_name,
                    "size_bytes": source.size_bytes,
                    "sha256": source.sha256,
                }
                for source in source_manifests[competence]
            ]
            for competence in competences
        },
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load_resume_state(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return load_json(path)
    except ManifestError:
        return None


def _reusable_cohort(connection, state: dict | None) -> list[str] | None:
    if not state:
        return None
    try:
        cohort = [
            row[0] for row in connection.execute("SELECT cnpj FROM cohort ORDER BY cnpj").fetchall()
        ]
    except duckdb.Error:
        return None
    observed_hash = hashlib.sha256("\n".join(cohort).encode()).hexdigest()
    if len(cohort) != state.get("cohort_count") or observed_hash != state.get("cohort_hash"):
        return None
    return cohort


def _reusable_package(
    *,
    output_directory,
    competence,
    window_id,
    scope_hash,
    cohort_hash,
    expected_sources,
) -> Path | None:
    manifest_path = output_directory / "package-manifest.json"
    try:
        manifest = PackageManifest.from_dict(load_json(manifest_path))
        expected_identity = (
            CONTRACT_VERSION,
            contract_bundle_hash(),
            window_id,
            competence,
            scope_hash,
            cohort_hash,
        )
        observed_identity = (
            manifest.contract_version,
            manifest.contract_hash,
            manifest.window_id,
            manifest.competence,
            manifest.scope_hash,
            manifest.cohort_hash,
        )
        if observed_identity != expected_identity:
            return None
        if manifest.sources != expected_sources:
            return None
        for artifact in manifest.artifacts:
            validation = validate_parquet(
                contract=TABLE_CONTRACTS[artifact.artifact_type],
                path=output_directory / artifact.file_name,
            )
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
                return None
    except (ContractError, ManifestError, OSError, duckdb.Error):
        return None
    return manifest_path


def _discover_cohort(
    connection,
    *,
    competences,
    sources_root,
    work_root,
    scope_tom_codes,
    progress: Callable[[str], None] | None = None,
) -> None:
    connection.execute("DROP TABLE IF EXISTS cohort")
    connection.execute("CREATE TABLE cohort(cnpj VARCHAR PRIMARY KEY)")
    connection.execute("CREATE OR REPLACE TEMP TABLE scope_tom(tom VARCHAR PRIMARY KEY)")
    connection.executemany(
        "INSERT INTO scope_tom VALUES (?)", [(value,) for value in sorted(scope_tom_codes)]
    )
    for competence in competences:
        archives = sorted((sources_root / competence).glob("Estabelecimentos[0-9]*.zip"))
        for position, archive in enumerate(archives, start=1):
            if progress:
                progress(
                    f"Coorte {competence}: lendo estabelecimentos "
                    f"{position}/{len(archives)} ({archive.name})."
                )
            with _extracted_archive(archive, work_root) as extracted:
                if extracted.replacement_count and progress:
                    progress(
                        f"{archive.name}: {extracted.replacement_count} byte(s) "
                        "inválido(s) substituído(s) na transcodificação."
                    )
                connection.execute(
                    "INSERT OR IGNORE INTO cohort "
                    "SELECT upper(trim(coalesce(e.cnpj_basic, ''))) || "
                    "upper(trim(coalesce(e.cnpj_order, ''))) || "
                    "trim(coalesce(e.cnpj_check_digits, '')) "
                    f"FROM {_read_csv_sql(extracted.path, ESTABLISHMENT_COLUMNS)} e "
                    "JOIN scope_tom s ON s.tom = trim(e.municipality_tom_code)"
                )
    _validate_cohort_cnpjs(connection)
    connection.execute(
        "CREATE OR REPLACE TABLE cohort_basics AS "
        "SELECT DISTINCT substr(cnpj, 1, 8) AS cnpj_basic FROM cohort"
    )


def _prepare_competence(
    connection,
    *,
    competence,
    sources_directory,
    output_directory,
    work_root,
    window_id,
    scope_hash,
    scope_tom_codes,
    cohort_hash,
    source_manifests,
    ibge_catalog,
    partner_hmac_secret,
    generated_at,
    progress: Callable[[str], None] | None = None,
) -> Path:
    output_directory.mkdir(parents=True, exist_ok=True)
    warnings = _load_filtered_tables(connection, sources_directory, work_root, progress=progress)
    resolver = MunicipalityResolver(
        tom_names=load_rf_municipality_names(sources_directory / "Municipios.zip"),
        ibge_catalog=ibge_catalog,
    )
    competence_date = date.fromisoformat(f"{competence}-01")
    if progress:
        progress("Normalizando empresas...")
    companies = _company_records(connection, competence_date)
    if progress:
        progress(f"Empresas normalizadas: {len(companies)}.")
        progress("Normalizando estabelecimentos...")
    establishments = _establishment_records(connection, competence_date, resolver, scope_tom_codes)
    if progress:
        progress(f"Estabelecimentos normalizados: {len(establishments)}.")
        progress("Normalizando sócios...")
    partners = _partner_records(connection, competence_date, partner_hmac_secret, warnings)
    if progress:
        progress(f"Sócios normalizados: {len(partners)}.")
    records = {
        "companies": companies,
        "establishments": establishments,
        "partners": partners,
    }
    artifacts = []
    for table_name, contract in TABLE_CONTRACTS.items():
        if progress:
            progress(f"Gravando e validando {contract.filename}...")
        validation = write_parquet_atomic(
            contract=contract,
            records=records[table_name],
            output_path=output_directory / contract.filename,
        )
        artifacts.append(
            ArtifactManifest(
                artifact_type=table_name,
                file_name=contract.filename,
                size_bytes=validation.size_bytes,
                row_count=validation.row_count,
                sha256=validation.sha256,
                schema_hash=validation.schema_hash,
            )
        )
    manifest = PackageManifest(
        contract_version=CONTRACT_VERSION,
        contract_hash=contract_bundle_hash(),
        window_id=window_id,
        competence=competence,
        scope_hash=scope_hash,
        cohort_hash=cohort_hash,
        generated_at=generated_at,
        sources=tuple(source_manifests) + (ibge_catalog.to_source_manifest(),),
        artifacts=tuple(artifacts),
        warnings=tuple(sorted(set(warnings))),
    )
    path = output_directory / "package-manifest.json"
    write_json_atomic(path, manifest.to_dict())
    return path


def _load_filtered_tables(
    connection,
    sources_directory: Path,
    work_root: Path,
    *,
    progress: Callable[[str], None] | None = None,
) -> list[str]:
    warnings = []
    definitions = {
        "companies_raw": COMPANY_COLUMNS,
        "establishments_raw": ESTABLISHMENT_COLUMNS,
        "partners_raw": PARTNER_COLUMNS,
        "simples_raw": SIMPLES_COLUMNS,
    }
    for table, columns in definitions.items():
        connection.execute(f"DROP TABLE IF EXISTS {table}")
        connection.execute(f"CREATE TABLE {table} AS SELECT * FROM {_empty_relation(columns)}")

    groups = (
        ("Empresas[0-9]*.zip", "companies_raw", COMPANY_COLUMNS, "cohort_basics", "cnpj_basic"),
        (
            "Estabelecimentos[0-9]*.zip",
            "establishments_raw",
            ESTABLISHMENT_COLUMNS,
            "cohort",
            "cnpj",
        ),
        ("Socios[0-9]*.zip", "partners_raw", PARTNER_COLUMNS, "cohort_basics", "cnpj_basic"),
    )
    for pattern, table, columns, cohort_table, key in groups:
        archives = sorted(sources_directory.glob(pattern))
        for position, archive in enumerate(archives, start=1):
            if progress:
                progress(f"{table}: lendo {position}/{len(archives)} ({archive.name}).")
            with _extracted_archive(archive, work_root) as extracted:
                if extracted.replacement_count:
                    warnings.append(
                        f"SOURCE_ENCODING_REPLACEMENTS:{archive.name}:{extracted.replacement_count}"
                    )
                relation = _read_csv_sql(extracted.path, columns)
                if key == "cnpj":
                    join = (
                        "c.cnpj = upper(trim(r.cnpj_basic)) || upper(trim(r.cnpj_order)) || "
                        "trim(r.cnpj_check_digits)"
                    )
                else:
                    join = f"c.{key} = upper(trim(r.{key}))"
                connection.execute(
                    f"INSERT INTO {table} SELECT r.* FROM {relation} r "
                    f"JOIN {cohort_table} c ON {join}"
                )
    if progress:
        progress("simples_raw: lendo Simples.zip.")
    simples_archive = sources_directory / "Simples.zip"
    with _extracted_archive(simples_archive, work_root) as extracted:
        if extracted.replacement_count:
            warnings.append(
                f"SOURCE_ENCODING_REPLACEMENTS:{simples_archive.name}:{extracted.replacement_count}"
            )
        connection.execute(
            "INSERT INTO simples_raw SELECT r.* FROM "
            f"{_read_csv_sql(extracted.path, SIMPLES_COLUMNS)} r "
            "JOIN cohort_basics c ON c.cnpj_basic = upper(trim(r.cnpj_basic))"
        )
    for table, column in (
        ("establishments_raw", "registration_status_date"),
        ("establishments_raw", "activity_start_date"),
        ("partners_raw", "entry_date"),
        ("simples_raw", "simples_option_date"),
        ("simples_raw", "simples_exclusion_date"),
        ("simples_raw", "mei_option_date"),
        ("simples_raw", "mei_exclusion_date"),
    ):
        count = connection.execute(
            f"SELECT count(*) FROM {table} WHERE trim(coalesce({column}, '')) = '0'"
        ).fetchone()[0]
        if count:
            warnings.append(f"SOURCE_ZERO_DATE:{table}.{column}:{count}")
    return warnings


def _company_records(connection, competence: date) -> list[dict]:
    simples = {}
    for row in connection.execute(
        "SELECT cnpj_basic, simples_optant, simples_option_date, "
        "simples_exclusion_date, mei_optant, mei_option_date, mei_exclusion_date "
        "FROM simples_raw"
    ).fetchall():
        simples[_required_cnpj_basic(row[0], "Simples")] = row[1:]
    records = []
    observed = set()
    for row in connection.execute(
        "SELECT cnpj_basic, legal_name, legal_nature_code, share_capital, company_size_code "
        "FROM companies_raw ORDER BY cnpj_basic"
    ).fetchall():
        raw_cnpj_basic, legal_name, nature, capital, size = row
        cnpj_basic = _required_cnpj_basic(raw_cnpj_basic, "empresa")
        if cnpj_basic in observed:
            raise ReceitaPreparationError(f"Empresa duplicada: {cnpj_basic}.")
        observed.add(cnpj_basic)
        regime = simples.get(cnpj_basic, (None,) * 6)
        legal_name = remove_personal_document_sequences(_text(legal_name)) or "NOME SUPRIMIDO"
        record = {
            "cnpj_basic": cnpj_basic,
            "legal_name": legal_name,
            "legal_name_search": normalize_search_text(legal_name),
            "legal_nature_code": _nullable_text(nature),
            "share_capital": _decimal(capital),
            "company_size_code": _nullable_text(size),
            "simples_optant": _boolean(regime[0]),
            "simples_option_date": _rf_date(regime[1]),
            "simples_exclusion_date": _rf_date(regime[2]),
            "mei_optant": _boolean(regime[3]),
            "mei_option_date": _rf_date(regime[4]),
            "mei_exclusion_date": _rf_date(regime[5]),
            "competence": competence,
            "record_hash": "",
        }
        record["record_hash"] = canonical_record_hash(record)
        records.append(record)
    missing_for_establishments = connection.execute(
        "SELECT count(*) FROM ("
        "SELECT DISTINCT upper(trim(e.cnpj_basic)) AS cnpj_basic FROM establishments_raw e "
        "LEFT JOIN companies_raw c "
        "ON upper(trim(c.cnpj_basic)) = upper(trim(e.cnpj_basic)) "
        "WHERE c.cnpj_basic IS NULL"
        ") missing"
    ).fetchone()[0]
    if missing_for_establishments:
        raise ReceitaPreparationError(
            "Empresa ausente para "
            f"{missing_for_establishments} CNPJ(s) básico(s) com estabelecimento na competência."
        )
    return records


def _establishment_records(
    connection,
    competence: date,
    resolver: MunicipalityResolver,
    scope_tom_codes: set[str],
) -> list[dict]:
    selected = (
        "cnpj_basic, cnpj_order, cnpj_check_digits, branch_type, trade_name, "
        "registration_status_code, registration_status_date, "
        "registration_status_reason_code, activity_start_date, main_cnae_code, "
        "street_type, street_name, street_number, address_complement, neighborhood, "
        "postal_code, state_code, municipality_tom_code"
    )
    records = []
    for row in connection.execute(
        f"SELECT {selected} FROM establishments_raw "
        "ORDER BY cnpj_basic, cnpj_order, cnpj_check_digits"
    ).fetchall():
        (
            basic,
            order,
            digits,
            branch_type,
            trade_name,
            status,
            status_date,
            status_reason,
            activity_date,
            cnae,
            street_type,
            street_name,
            number,
            complement,
            neighborhood,
            postal_code,
            uf,
            tom,
        ) = row
        raw_cnpj = f"{_text(basic)}{_text(order)}{_text(digits)}"
        try:
            cnpj = validate_cnpj(raw_cnpj)
        except InvalidCNPJError as error:
            raise ReceitaPreparationError(
                f"CNPJ de estabelecimento inválido: {raw_cnpj}."
            ) from error
        cnpj_basic = extract_cnpj_basic(cnpj)
        identity = resolver.resolve(_text(tom), _text(uf))
        trade_name = remove_personal_document_sequences(_text(trade_name))
        record = {
            "cnpj": cnpj,
            "cnpj_basic": cnpj_basic,
            "branch_type": _text(branch_type),
            "trade_name": trade_name,
            "trade_name_search": normalize_search_text(trade_name),
            "registration_status_code": _text(status),
            "registration_status_date": _rf_date(status_date),
            "registration_status_reason_code": _nullable_text(status_reason),
            "activity_start_date": _rf_date(activity_date),
            "main_cnae_code": _nullable_text(cnae),
            "street_type": _text(street_type),
            "street_name": _text(street_name),
            "street_number": _text(number),
            "address_complement": _text(complement),
            "neighborhood": _text(neighborhood),
            "postal_code": _postal_code(postal_code),
            "state_code": identity.uf,
            "municipality_tom_code": identity.tom_code,
            "municipality_ibge_code": identity.ibge_code,
            "municipality_name": identity.name,
            "is_in_region": identity.tom_code in scope_tom_codes,
            "competence": competence,
            "record_hash": "",
        }
        record["record_hash"] = canonical_record_hash(record)
        records.append(record)
    return records


def _partner_records(connection, competence: date, secret: str, warnings: list[str]) -> list[dict]:
    records = {}
    for row in connection.execute(
        "SELECT cnpj_basic, partner_source_type, display_name, source_identifier, "
        "qualification_code, entry_date, country_code FROM partners_raw "
        "ORDER BY cnpj_basic, partner_source_type, display_name, source_identifier"
    ).fetchall():
        raw_basic, source_type, display_name, source_id, qualification, entry_date, country = row
        basic = _required_cnpj_basic(raw_basic, "participação")
        display_name = remove_personal_document_sequences(_text(display_name)) or "NOME SUPRIMIDO"
        partner_type = {"1": "PJ", "2": "PF", "3": "FOREIGN"}.get(_text(source_type))
        if not partner_type:
            raise ReceitaPreparationError(f"Tipo de sócio desconhecido: {source_type}.")
        partner_key, partner_cnpj_basic, warning = _partner_identity(
            basic=basic,
            partner_type=partner_type,
            display_name=display_name,
            source_identifier=_text(source_id),
            country_code=_nullable_text(country),
            secret=secret,
        )
        if warning:
            warnings.append(warning)
        key = (basic, partner_key)
        record = {
            "cnpj_basic": basic,
            "partner_key": partner_key,
            "partner_type": partner_type,
            "display_name": display_name,
            "partner_cnpj_basic": partner_cnpj_basic,
            "country_code": _nullable_text(country),
            "qualification_code": _nullable_text(qualification),
            "entry_date": _rf_date(entry_date),
            "competence": competence,
            "record_hash": "",
        }
        record["record_hash"] = canonical_record_hash(record)
        if key in records and records[key] != record:
            warnings.append(f"AMBIGUOUS_PARTNER:{basic}:{partner_key[:12]}")
            continue
        records[key] = record
    return list(records.values())


def _partner_identity(
    *, basic, partner_type, display_name, source_identifier, country_code, secret
) -> tuple[str, str | None, str | None]:
    basic = validate_cnpj_basic(basic)
    warning = None
    if partner_type == "PF":
        identity = source_identifier or normalize_search_text(display_name)
        if not source_identifier:
            warning = f"PF_WITHOUT_SOURCE_IDENTIFIER:{basic}"
        digest = hmac.new(
            secret.encode(), f"PF\x1f{basic}\x1f{identity}".encode(), hashlib.sha256
        ).hexdigest()
        return digest, None, warning
    parsed_identifier = parse_cnpj_identifier(source_identifier) if partner_type == "PJ" else None
    if parsed_identifier:
        partner_cnpj_basic = extract_cnpj_basic(parsed_identifier)
        raw = f"PJ\x1f{basic}\x1f{partner_cnpj_basic}"
        return hashlib.sha256(raw.encode()).hexdigest(), partner_cnpj_basic, None
    identity = (
        f"{partner_type}\x1f{basic}\x1f{normalize_search_text(display_name)}"
        f"\x1f{country_code or ''}"
    )
    if partner_type == "PJ":
        warning = f"PJ_WITHOUT_VALID_CNPJ:{basic}"
    return hashlib.sha256(identity.encode()).hexdigest(), None, warning


def _validate_cohort_cnpjs(connection) -> None:
    cursor = connection.execute("SELECT cnpj FROM cohort ORDER BY cnpj")
    invalid_count = 0
    examples = []
    while rows := cursor.fetchmany(10_000):
        for (cnpj,) in rows:
            try:
                validate_cnpj(cnpj)
            except InvalidCNPJError:
                invalid_count += 1
                if len(examples) < 5:
                    examples.append(cnpj)
    if invalid_count:
        raise ReceitaPreparationError(
            f"Coorte contém {invalid_count} CNPJ(s) inválido(s); exemplos={examples}."
        )


def _required_cnpj_basic(value: object, entity: str) -> str:
    try:
        return validate_cnpj_basic(value)
    except InvalidCNPJError as error:
        raise ReceitaPreparationError(f"CNPJ básico inválido em {entity}: {value}.") from error


def _verify_sources(directory: Path) -> tuple[SourceManifest, ...]:
    manifest_path = directory / "source-manifest.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReceitaPreparationError(f"Manifesto de fontes inválido: {directory}.") from exc
    sources = []
    for item in payload.get("files", []):
        path = directory / item["path"]
        if not path.is_file() or path.stat().st_size != item["size_bytes"]:
            raise ReceitaPreparationError(f"Fonte ausente ou incompleta: {path.name}.")
        if file_sha256(path) != item["sha256"]:
            raise ReceitaPreparationError(f"Hash da fonte diverge: {path.name}.")
        sources.append(
            SourceManifest(
                source_type=item["source_type"],
                url=item["url"],
                file_name=item["file_name"],
                size_bytes=item["size_bytes"],
                sha256=item["sha256"],
            )
        )
    if len(sources) != 32:
        raise ReceitaPreparationError(f"Competência {directory.name} sem 32 fontes.")
    return tuple(sources)


@contextmanager
def _extracted_archive(archive_path: Path, work_root: Path):
    extraction_root = work_root / "extracted"
    extraction_root.mkdir(parents=True, exist_ok=True)
    output = extraction_root / f"{archive_path.parent.name}-{archive_path.stem}.csv"
    partial = output.with_suffix(".csv.part")
    replacement_count = 0
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = [member for member in archive.infolist() if not member.is_dir()]
            if len(members) != 1:
                raise ReceitaPreparationError(f"ZIP inesperado: {archive_path.name}.")
            with archive.open(members[0]) as source, partial.open("wb") as destination:
                while chunk := source.read(4 * 1024 * 1024):
                    decoded = chunk.decode("cp1252", errors="replace")
                    replacement_count += decoded.count("\N{REPLACEMENT CHARACTER}")
                    destination.write(decoded.encode("utf-8"))
        partial.replace(output)
        yield ExtractedCsv(path=output, replacement_count=replacement_count)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ReceitaPreparationError(f"Falha ao extrair {archive_path.name}.") from exc
    finally:
        partial.unlink(missing_ok=True)
        output.unlink(missing_ok=True)


def _read_csv_sql(path: Path, columns: tuple[str, ...]) -> str:
    schema = ", ".join(f"'{name}':'VARCHAR'" for name in columns)
    return (
        f"read_csv('{_sql_path(path)}', delim=';', header=false, quote='\"', "
        f"escape='\"', encoding='{RF_SOURCE_ENCODING}', columns={{ {schema} }}, nullstr='')"
    )


def _empty_relation(columns: tuple[str, ...]) -> str:
    selected = ", ".join(f"CAST(NULL AS VARCHAR) AS {name}" for name in columns)
    return f"(SELECT {selected} WHERE false)"


def _sql_path(path: Path) -> str:
    return str(Path(path).resolve()).replace("'", "''")


def _text(value) -> str:
    return str(value or "").strip()


def _nullable_text(value) -> str | None:
    return _text(value) or None


def _postal_code(value) -> str:
    text = _text(value)
    return text if len(text) == 8 and text.isdigit() else ""


def _boolean(value) -> bool | None:
    text = _text(value).upper()
    if not text:
        return None
    if text == "S":
        return True
    if text == "N":
        return False
    raise ReceitaPreparationError(f"Booleano da Receita inválido: {text}.")


def _rf_date(value) -> date | None:
    text = _text(value)
    if not text or text in {"0", "00000000"}:
        return None
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError as exc:
        raise ReceitaPreparationError(f"Data da Receita inválida: {text}.") from exc


def _decimal(value) -> Decimal | None:
    text = _text(value).replace(",", ".")
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ReceitaPreparationError(f"Decimal da Receita inválido: {text}.") from exc


def _validate_competences(competences: list[str]) -> None:
    expected = []
    current = date.fromisoformat(f"{competences[0]}-01") if competences else None
    end = date.fromisoformat(f"{competences[-1]}-01") if competences else None
    while current and end and current <= end:
        expected.append(current.strftime("%Y-%m"))
        current = date(current.year + (current.month == 12), current.month % 12 + 1, 1)
    if competences != expected:
        raise ReceitaPreparationError("Competências devem ser únicas, ordenadas e contínuas.")
