from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pyarrow as pa

from apps.pipeline.contracts import ContractError, TableContract, file_sha256


@dataclass(frozen=True, slots=True)
class ParquetValidation:
    path: Path
    row_count: int
    size_bytes: int
    sha256: str
    schema_hash: str


def write_parquet_atomic(
    *, contract: TableContract, records: Iterable[dict], output_path: Path
) -> ParquetValidation:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.part")
    if temporary_path.exists():
        temporary_path.unlink()

    rows = list(records)
    for record in rows:
        contract.validate_record(record)

    connection = duckdb.connect(":memory:")
    try:
        connection.execute(contract.create_table_sql())
        if rows:
            columns = ", ".join(f'"{name}"' for name in contract.column_names)
            arrow_table = pa.Table.from_pylist(rows)
            connection.register("incoming_records", arrow_table)
            connection.execute(
                f'INSERT INTO "contract_data" ({columns}) SELECT {columns} FROM incoming_records'
            )
        escaped_path = str(temporary_path).replace("'", "''")
        connection.execute(
            f"COPY contract_data TO '{escaped_path}' "
            "(FORMAT PARQUET, COMPRESSION ZSTD, COMPRESSION_LEVEL 3)"
        )
    finally:
        connection.close()

    try:
        validation = validate_parquet(contract=contract, path=temporary_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    temporary_path.replace(output_path)
    return ParquetValidation(
        path=output_path,
        row_count=validation.row_count,
        size_bytes=output_path.stat().st_size,
        sha256=file_sha256(output_path),
        schema_hash=validation.schema_hash,
    )


def validate_parquet(*, contract: TableContract, path: Path) -> ParquetValidation:
    path = Path(path)
    if not path.is_file():
        raise ContractError(f"Parquet não encontrado: {path}.")

    connection = duckdb.connect(":memory:")
    try:
        description = connection.execute(
            "DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]
        ).fetchall()
        observed = tuple((row[0], _normalize_type(row[1])) for row in description)
        expected = tuple(
            (column.name, _normalize_type(column.duckdb_type)) for column in contract.columns
        )
        if observed != expected:
            raise ContractError(
                f"Schema Parquet incompatível em {path.name}; "
                f"esperado={expected}, observado={observed}."
            )

        required_columns = [column.name for column in contract.columns if not column.nullable]
        if required_columns:
            null_condition = " OR ".join(f'"{name}" IS NULL' for name in required_columns)
            null_count = connection.execute(
                f"SELECT count(*) FROM read_parquet(?) WHERE {null_condition}", [str(path)]
            ).fetchone()[0]
            if null_count:
                raise ContractError(
                    f"Parquet {path.name} possui {null_count} linha(s) com NULL obrigatório."
                )
        row_count = connection.execute(
            "SELECT count(*) FROM read_parquet(?)", [str(path)]
        ).fetchone()[0]
        identity_columns = ", ".join(f'"{name}"' for name in contract.identity_columns)
        duplicate = connection.execute(
            f"SELECT {identity_columns}, count(*) AS occurrences "
            "FROM read_parquet(?) "
            f"GROUP BY {identity_columns} HAVING count(*) > 1 LIMIT 1",
            [str(path)],
        ).fetchone()
        if duplicate:
            raise ContractError(f"Identidade duplicada em {path.name}: {duplicate}.")
    finally:
        connection.close()

    return ParquetValidation(
        path=path,
        row_count=row_count,
        size_bytes=path.stat().st_size,
        sha256=file_sha256(path),
        schema_hash=contract.schema_hash,
    )


def _normalize_type(value: str) -> str:
    return value.upper().replace(" ", "")
