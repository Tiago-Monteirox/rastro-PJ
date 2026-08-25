import hashlib
import json
from dataclasses import asdict, dataclass

CONTRACT_VERSION = "1.0.0"
PROHIBITED_COLUMN_FRAGMENTS = ("cpf", "masked_cpf", "cpf_mascarado")


class ContractError(ValueError):
    """O pacote ou registro viola o contrato tipado."""


@dataclass(frozen=True, slots=True)
class ColumnContract:
    name: str
    duckdb_type: str
    nullable: bool = False


@dataclass(frozen=True, slots=True)
class TableContract:
    name: str
    filename: str
    columns: tuple[ColumnContract, ...]
    identity_columns: tuple[str, ...]

    def __post_init__(self) -> None:
        names = [column.name for column in self.columns]
        if len(names) != len(set(names)):
            raise ContractError(f"Colunas duplicadas no contrato {self.name}.")
        for name in names:
            normalized = name.lower()
            if any(fragment in normalized for fragment in PROHIBITED_COLUMN_FRAGMENTS):
                raise ContractError(f"Coluna proibida no contrato {self.name}: {name}.")
        missing_identities = set(self.identity_columns) - set(names)
        if missing_identities:
            raise ContractError(
                f"Identidades ausentes no contrato {self.name}: {sorted(missing_identities)}."
            )

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns)

    @property
    def schema_hash(self) -> str:
        payload = {
            "contract_version": CONTRACT_VERSION,
            "name": self.name,
            "filename": self.filename,
            "identity_columns": self.identity_columns,
            "columns": [asdict(column) for column in self.columns],
        }
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def create_table_sql(self, table_name: str = "contract_data") -> str:
        definitions = []
        for column in self.columns:
            nullable = "" if column.nullable else " NOT NULL"
            definitions.append(f'"{column.name}" {column.duckdb_type}{nullable}')
        return f'CREATE TABLE "{table_name}" ({", ".join(definitions)})'

    def validate_record(self, record: dict) -> None:
        observed = set(record)
        expected = set(self.column_names)
        if observed != expected:
            missing = sorted(expected - observed)
            extra = sorted(observed - expected)
            raise ContractError(
                f"Registro {self.name} incompatível; ausentes={missing}, extras={extra}."
            )
        null_columns = [
            column.name
            for column in self.columns
            if not column.nullable and record[column.name] is None
        ]
        if null_columns:
            raise ContractError(
                f"Registro {self.name} contém NULL obrigatório: {sorted(null_columns)}."
            )


COMPANIES = TableContract(
    name="companies",
    filename="companies.parquet",
    identity_columns=("cnpj_basic", "competence"),
    columns=(
        ColumnContract("cnpj_basic", "VARCHAR"),
        ColumnContract("legal_name", "VARCHAR"),
        ColumnContract("legal_name_search", "VARCHAR"),
        ColumnContract("legal_nature_code", "VARCHAR", nullable=True),
        ColumnContract("share_capital", "DECIMAL(18,2)", nullable=True),
        ColumnContract("company_size_code", "VARCHAR", nullable=True),
        ColumnContract("simples_optant", "BOOLEAN", nullable=True),
        ColumnContract("simples_option_date", "DATE", nullable=True),
        ColumnContract("simples_exclusion_date", "DATE", nullable=True),
        ColumnContract("mei_optant", "BOOLEAN", nullable=True),
        ColumnContract("mei_option_date", "DATE", nullable=True),
        ColumnContract("mei_exclusion_date", "DATE", nullable=True),
        ColumnContract("competence", "DATE"),
        ColumnContract("record_hash", "VARCHAR"),
    ),
)

ESTABLISHMENTS = TableContract(
    name="establishments",
    filename="establishments.parquet",
    identity_columns=("cnpj", "competence"),
    columns=(
        ColumnContract("cnpj", "VARCHAR"),
        ColumnContract("cnpj_basic", "VARCHAR"),
        ColumnContract("branch_type", "VARCHAR"),
        ColumnContract("trade_name", "VARCHAR"),
        ColumnContract("trade_name_search", "VARCHAR"),
        ColumnContract("registration_status_code", "VARCHAR"),
        ColumnContract("registration_status_date", "DATE", nullable=True),
        ColumnContract("registration_status_reason_code", "VARCHAR", nullable=True),
        ColumnContract("activity_start_date", "DATE", nullable=True),
        ColumnContract("main_cnae_code", "VARCHAR", nullable=True),
        ColumnContract("street_type", "VARCHAR"),
        ColumnContract("street_name", "VARCHAR"),
        ColumnContract("street_number", "VARCHAR"),
        ColumnContract("address_complement", "VARCHAR"),
        ColumnContract("neighborhood", "VARCHAR"),
        ColumnContract("postal_code", "VARCHAR"),
        ColumnContract("state_code", "VARCHAR"),
        ColumnContract("municipality_tom_code", "VARCHAR"),
        ColumnContract("municipality_ibge_code", "VARCHAR"),
        ColumnContract("municipality_name", "VARCHAR"),
        ColumnContract("is_in_region", "BOOLEAN"),
        ColumnContract("competence", "DATE"),
        ColumnContract("record_hash", "VARCHAR"),
    ),
)

PARTNERS = TableContract(
    name="partners",
    filename="partners.parquet",
    identity_columns=("cnpj_basic", "partner_key", "competence"),
    columns=(
        ColumnContract("cnpj_basic", "VARCHAR"),
        ColumnContract("partner_key", "VARCHAR"),
        ColumnContract("partner_type", "VARCHAR"),
        ColumnContract("display_name", "VARCHAR"),
        ColumnContract("partner_cnpj_basic", "VARCHAR", nullable=True),
        ColumnContract("country_code", "VARCHAR", nullable=True),
        ColumnContract("qualification_code", "VARCHAR", nullable=True),
        ColumnContract("entry_date", "DATE", nullable=True),
        ColumnContract("competence", "DATE"),
        ColumnContract("record_hash", "VARCHAR"),
    ),
)

TABLE_CONTRACTS = {contract.name: contract for contract in (COMPANIES, ESTABLISHMENTS, PARTNERS)}


def contract_bundle_hash() -> str:
    payload = {
        "contract_version": CONTRACT_VERSION,
        "schemas": {
            name: contract.schema_hash for name, contract in sorted(TABLE_CONTRACTS.items())
        },
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
