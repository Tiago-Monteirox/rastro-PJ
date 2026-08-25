import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from typing import Any

MASKED_CPF_PATTERN = re.compile(r"\*{3}[0-9]{6}\*{2}")
FULL_CPF_PATTERN = re.compile(r"(?<![0-9])[0-9]{3}\.?[0-9]{3}\.?[0-9]{3}-?[0-9]{2}(?![0-9])")
PROHIBITED_KEY_FRAGMENTS = ("cpf", "masked_cpf", "cpf_mascarado", "hmac_secret")
OPAQUE_IDENTIFIER_KEYS = frozenset(
    {
        "cohort_hash",
        "contract_hash",
        "manifest_sha256",
        "package_hash",
        "partner_key",
        "record_hash",
        "schema_hash",
        "scope_hash",
        "sha256",
        "window_id",
    }
)


class PrivacyViolation(ValueError):
    """Um artefato persistente contém dado proibido."""


def normalize_search_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    alphanumeric = "".join(char.lower() if char.isalnum() else " " for char in without_accents)
    return " ".join(alphanumeric.split())


def remove_personal_document_sequences(value: str) -> str:
    cleaned = MASKED_CPF_PATTERN.sub("", value)
    cleaned = FULL_CPF_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip(" ./-")


def canonical_record_hash(record: dict[str, Any]) -> str:
    assert_no_prohibited_personal_data(record)
    payload = {
        key: value for key, value in record.items() if key not in {"competence", "record_hash"}
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def assert_no_prohibited_personal_data(value: Any, *, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized_key = str(key).lower()
            if any(fragment in normalized_key for fragment in PROHIBITED_KEY_FRAGMENTS):
                raise PrivacyViolation(f"Chave proibida em {path}: {key}.")
            if normalized_key in OPAQUE_IDENTIFIER_KEYS:
                if isinstance(item, str) and MASKED_CPF_PATTERN.search(item):
                    raise PrivacyViolation(f"CPF mascarado encontrado em {path}.{key}.")
                continue
            assert_no_prohibited_personal_data(item, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple, set)):
        for index, item in enumerate(value):
            assert_no_prohibited_personal_data(item, path=f"{path}[{index}]")
        return
    if isinstance(value, str):
        if MASKED_CPF_PATTERN.search(value):
            raise PrivacyViolation(f"CPF mascarado encontrado em {path}.")
        if FULL_CPF_PATTERN.search(value):
            raise PrivacyViolation(f"Sequência compatível com CPF encontrada em {path}.")


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    raise TypeError(f"Tipo não serializável no hash: {type(value).__name__}.")
