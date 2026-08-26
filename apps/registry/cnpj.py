from __future__ import annotations

import re

CNPJ_BASIC_PATTERN = re.compile(r"^[A-Z0-9]{8}$")
CNPJ_PATTERN = re.compile(r"^[A-Z0-9]{12}[0-9]{2}$")
_SEPARATOR_PATTERN = re.compile(r"[\s./-]+")
_FIRST_DIGIT_WEIGHTS = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_SECOND_DIGIT_WEIGHTS = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


class InvalidCNPJError(ValueError):
    pass


def normalize_cnpj(value: object) -> str:
    if value is None:
        return ""
    return _SEPARATOR_PATTERN.sub("", str(value).strip()).upper()


def validate_cnpj_basic(value: object) -> str:
    normalized = normalize_cnpj(value)
    if not CNPJ_BASIC_PATTERN.fullmatch(normalized):
        raise InvalidCNPJError("CNPJ básico deve conter oito caracteres alfanuméricos.")
    return normalized


def validate_cnpj(value: object) -> str:
    normalized = normalize_cnpj(value)
    if not CNPJ_PATTERN.fullmatch(normalized):
        raise InvalidCNPJError(
            "CNPJ deve conter doze caracteres alfanuméricos e dois dígitos verificadores."
        )
    if len(set(normalized)) == 1:
        raise InvalidCNPJError("CNPJ não pode ser uma sequência repetida.")

    first_digit = _calculate_digit(normalized[:12], _FIRST_DIGIT_WEIGHTS)
    second_digit = _calculate_digit(normalized[:12] + first_digit, _SECOND_DIGIT_WEIGHTS)
    if normalized[-2:] != first_digit + second_digit:
        raise InvalidCNPJError("Dígitos verificadores do CNPJ são inválidos.")
    return normalized


def parse_cnpj_identifier(value: object) -> str | None:
    normalized = normalize_cnpj(value)
    try:
        if len(normalized) == 8:
            return validate_cnpj_basic(normalized)
        if len(normalized) == 14:
            return validate_cnpj(normalized)
    except InvalidCNPJError:
        return None
    return None


def parse_cnpj_basic(value: object) -> str | None:
    try:
        return validate_cnpj_basic(value)
    except InvalidCNPJError:
        return None


def looks_like_cnpj_identifier(value: object) -> bool:
    normalized = normalize_cnpj(value)
    return bool(CNPJ_BASIC_PATTERN.fullmatch(normalized) or CNPJ_PATTERN.fullmatch(normalized))


def extract_cnpj_basic(value: object) -> str:
    normalized = normalize_cnpj(value)
    if len(normalized) == 8:
        return validate_cnpj_basic(normalized)
    return validate_cnpj(normalized)[:8]


def is_valid_cnpj_basic(value: object) -> bool:
    try:
        validate_cnpj_basic(value)
    except InvalidCNPJError:
        return False
    return True


def is_valid_cnpj(value: object) -> bool:
    try:
        validate_cnpj(value)
    except InvalidCNPJError:
        return False
    return True


def is_canonical_cnpj_basic(value: object) -> bool:
    return isinstance(value, str) and is_valid_cnpj_basic(value) and value == normalize_cnpj(value)


def is_canonical_cnpj(value: object) -> bool:
    return isinstance(value, str) and is_valid_cnpj(value) and value == normalize_cnpj(value)


def format_cnpj_basic(value: object) -> str:
    normalized = normalize_cnpj(value)
    if len(normalized) != 8:
        return normalized
    return f"{normalized[:2]}.{normalized[2:5]}.{normalized[5:8]}"


def format_cnpj(value: object) -> str:
    normalized = normalize_cnpj(value)
    if len(normalized) != 14:
        return normalized
    return (
        f"{normalized[:2]}.{normalized[2:5]}.{normalized[5:8]}/{normalized[8:12]}-{normalized[12:]}"
    )


def _calculate_digit(base: str, weights: tuple[int, ...]) -> str:
    total = sum(
        (ord(character) - 48) * weight for character, weight in zip(base, weights, strict=True)
    )
    remainder = total % 11
    return "0" if remainder < 2 else str(11 - remainder)
