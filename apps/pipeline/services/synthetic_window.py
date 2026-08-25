import hashlib
from datetime import date
from pathlib import Path

from apps.pipeline.contracts import (
    CONTRACT_VERSION,
    TABLE_CONTRACTS,
    ArtifactManifest,
    PackageManifest,
    WindowManifest,
    contract_bundle_hash,
    file_sha256,
    write_json_atomic,
)

from .normalization import canonical_record_hash, normalize_search_text
from .parquet import write_parquet_atomic

SYNTHETIC_WINDOW_ID = "00000000-0000-4000-8000-000000000002"
SYNTHETIC_WINDOW_CODE = "synthetic-g2-2026-07-2026-08"
SYNTHETIC_COMPETENCES = ("2026-07", "2026-08")


def generate_synthetic_window(
    *,
    output_directory: Path,
    scope_code: str,
    scope_version: int,
    scope_hash: str,
    generated_at: str = "2026-08-24T12:00:00Z",
) -> Path:
    output_directory = Path(output_directory)
    records_by_competence = _records_by_competence()
    cnpjs = sorted(
        {
            record["cnpj"]
            for records in records_by_competence.values()
            for record in records["establishments"]
        }
    )
    cohort_hash = hashlib.sha256("\n".join(cnpjs).encode("utf-8")).hexdigest()

    package_references = []
    for competence in SYNTHETIC_COMPETENCES:
        package_directory = output_directory / competence
        package_directory.mkdir(parents=True, exist_ok=True)
        artifacts = []
        for table_name, contract in TABLE_CONTRACTS.items():
            validation = write_parquet_atomic(
                contract=contract,
                records=records_by_competence[competence][table_name],
                output_path=package_directory / contract.filename,
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

        package_manifest = PackageManifest(
            contract_version=CONTRACT_VERSION,
            contract_hash=contract_bundle_hash(),
            window_id=SYNTHETIC_WINDOW_ID,
            competence=competence,
            scope_hash=scope_hash,
            cohort_hash=cohort_hash,
            generated_at=generated_at,
            sources=(),
            artifacts=tuple(artifacts),
        )
        package_manifest_path = package_directory / "package-manifest.json"
        write_json_atomic(package_manifest_path, package_manifest.to_dict())
        package_references.append(
            {
                "competence": competence,
                "manifest_path": f"{competence}/package-manifest.json",
                "manifest_sha256": file_sha256(package_manifest_path),
            }
        )

    window_manifest = WindowManifest(
        contract_version=CONTRACT_VERSION,
        contract_hash=contract_bundle_hash(),
        window_id=SYNTHETIC_WINDOW_ID,
        window_code=SYNTHETIC_WINDOW_CODE,
        start_competence=SYNTHETIC_COMPETENCES[0],
        end_competence=SYNTHETIC_COMPETENCES[-1],
        scope_code=scope_code,
        scope_version=scope_version,
        scope_hash=scope_hash,
        cohort_hash=cohort_hash,
        generated_at=generated_at,
        packages=tuple(package_references),
    )
    window_manifest_path = output_directory / "window-manifest.json"
    write_json_atomic(window_manifest_path, window_manifest.to_dict())
    return window_manifest_path


def _records_by_competence() -> dict[str, dict[str, list[dict]]]:
    july = date(2026, 7, 1)
    august = date(2026, 8, 1)
    return {
        "2026-07": {
            "companies": [
                _company("11111111", "Alfa Comércio Ltda", july, "100000.00"),
                _company("22222222", "Beta Serviços Ltda", july, "50000.00"),
                _company("33333333", "Gama Indústria Ltda", july, "90000.00"),
                _company("44444444", "Delta Logística Ltda", july, "120000.00"),
                _company("66666666", "Zeta Consultoria Ltda", july, "30000.00"),
            ],
            "establishments": [
                _establishment("11111111000191", "11111111", july, "5403", "3170206", "MG", True),
                _establishment("22222222000182", "22222222", july, "5401", "3170107", "MG", True),
                _establishment("33333333000173", "33333333", july, "4069", "3103504", "MG", True),
                _establishment("44444444000164", "44444444", july, "7107", "3550308", "SP", False),
                _establishment("66666666000146", "66666666", july, "5403", "3170206", "MG", True),
            ],
            "partners": [
                _partner("11111111", "PF", "Sócia Alfa", july),
                _partner("22222222", "PF", "Sócio Beta", july),
            ],
        },
        "2026-08": {
            "companies": [
                _company("11111111", "Alfa Comércio Ltda", august, "150000.00"),
                _company("22222222", "Beta Serviços Ltda", august, "50000.00"),
                _company("33333333", "Gama Indústria Ltda", august, "90000.00"),
                _company("44444444", "Delta Logística Ltda", august, "120000.00"),
                _company("55555555", "Épsilon Tecnologia Ltda", august, "25000.00"),
                _company("66666666", "Zeta Consultoria Ltda", august, "30000.00"),
            ],
            "establishments": [
                _establishment(
                    "11111111000191",
                    "11111111",
                    august,
                    "5403",
                    "3170206",
                    "MG",
                    True,
                    street_name="AFONSO PENA",
                    main_cnae_code="4751201",
                ),
                _establishment(
                    "22222222000182",
                    "22222222",
                    august,
                    "5401",
                    "3170107",
                    "MG",
                    True,
                    registration_status_code="08",
                    registration_status_date=date(2026, 7, 15),
                ),
                _establishment(
                    "33333333000173", "33333333", august, "7107", "3550308", "SP", False
                ),
                _establishment("44444444000164", "44444444", august, "4683", "3134202", "MG", True),
                _establishment(
                    "55555555000155",
                    "55555555",
                    august,
                    "5403",
                    "3170206",
                    "MG",
                    True,
                    activity_start_date=date(2026, 7, 20),
                ),
                _establishment(
                    "66666666000146",
                    "66666666",
                    august,
                    "5403",
                    "3170206",
                    "MG",
                    True,
                    registration_status_code="03",
                    registration_status_date=date(2026, 7, 22),
                ),
            ],
            "partners": [
                _partner("11111111", "PF", "Sócia Alfa", august),
                _partner(
                    "11111111",
                    "PJ",
                    "Holding Exemplo S.A.",
                    august,
                    partner_cnpj_basic="66666666",
                ),
            ],
        },
    }


def _company(cnpj_basic: str, legal_name: str, competence: date, capital: str) -> dict:
    record = {
        "cnpj_basic": cnpj_basic,
        "legal_name": legal_name,
        "legal_name_search": normalize_search_text(legal_name),
        "legal_nature_code": "2062",
        "share_capital": capital,
        "company_size_code": "03",
        "simples_optant": True,
        "simples_option_date": date(2020, 1, 1),
        "simples_exclusion_date": None,
        "mei_optant": False,
        "mei_option_date": None,
        "mei_exclusion_date": None,
        "competence": competence,
        "record_hash": "",
    }
    record["record_hash"] = canonical_record_hash(record)
    return record


def _establishment(
    cnpj: str,
    cnpj_basic: str,
    competence: date,
    tom_code: str,
    ibge_code: str,
    state_code: str,
    is_in_region: bool,
    *,
    street_name: str = "BRASIL",
    main_cnae_code: str = "4711302",
    registration_status_code: str = "02",
    registration_status_date: date | None = None,
    activity_start_date: date = date(2020, 1, 1),
) -> dict:
    municipality_names = {
        "3103504": "Araguari",
        "3134202": "Ituiutaba",
        "3170107": "Uberaba",
        "3170206": "Uberlândia",
        "3550308": "São Paulo",
    }
    trade_name = f"Unidade {cnpj_basic}"
    record = {
        "cnpj": cnpj,
        "cnpj_basic": cnpj_basic,
        "branch_type": "1",
        "trade_name": trade_name,
        "trade_name_search": normalize_search_text(trade_name),
        "registration_status_code": registration_status_code,
        "registration_status_date": registration_status_date,
        "registration_status_reason_code": None,
        "activity_start_date": activity_start_date,
        "main_cnae_code": main_cnae_code,
        "street_type": "AVENIDA",
        "street_name": street_name,
        "street_number": "100",
        "address_complement": "",
        "neighborhood": "CENTRO",
        "postal_code": "38400000" if state_code == "MG" else "01001000",
        "state_code": state_code,
        "municipality_tom_code": tom_code,
        "municipality_ibge_code": ibge_code,
        "municipality_name": municipality_names[ibge_code],
        "is_in_region": is_in_region,
        "competence": competence,
        "record_hash": "",
    }
    record["record_hash"] = canonical_record_hash(record)
    return record


def _partner(
    cnpj_basic: str,
    partner_type: str,
    display_name: str,
    competence: date,
    *,
    partner_cnpj_basic: str | None = None,
) -> dict:
    partner_key = hashlib.sha256(
        f"synthetic:{cnpj_basic}:{partner_type}:{display_name}".encode()
    ).hexdigest()
    record = {
        "cnpj_basic": cnpj_basic,
        "partner_key": partner_key,
        "partner_type": partner_type,
        "display_name": display_name,
        "partner_cnpj_basic": partner_cnpj_basic,
        "country_code": None,
        "qualification_code": "49",
        "entry_date": date(2020, 1, 1),
        "competence": competence,
        "record_hash": "",
    }
    record["record_hash"] = canonical_record_hash(record)
    return record
