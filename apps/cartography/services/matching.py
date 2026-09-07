from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from dataclasses import dataclass, replace
from decimal import Decimal
from statistics import median

from apps.cartography.models import AddressResolution

NON_ALPHANUMERIC = re.compile(r"[^A-Z0-9]+")
NON_DIGIT = re.compile(r"\D+")
NO_NUMBER_VALUES = {"", "0", "SN", "S N", "SEM NUMERO", "SNUMERO"}
EARTH_RADIUS_METERS = 6_371_008.8
AMBIGUITY_LIMIT_METERS = 100.0


@dataclass(frozen=True, slots=True)
class CnefeCandidate:
    address_code: str
    latitude: float
    longitude: float
    level: int


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    method: str
    latitude: Decimal | None
    longitude: Decimal | None
    cnefe_level: int | None
    address_code: str
    candidate_count: int
    dispersion_meters: Decimal | None
    reason: str


def normalize_text(value: object) -> str:
    raw = unicodedata.normalize("NFKD", str(value or "").strip().upper())
    ascii_text = "".join(character for character in raw if not unicodedata.combining(character))
    return " ".join(NON_ALPHANUMERIC.sub(" ", ascii_text).split())


def normalize_street(value: object) -> str:
    return normalize_text(value)


def normalize_number(value: object) -> str:
    normalized = normalize_text(value)
    if normalized in NO_NUMBER_VALUES:
        return ""
    if normalized.isdigit():
        return str(int(normalized))
    return normalized.replace(" ", "")


def normalize_postal_code(value: object) -> str:
    digits = NON_DIGIT.sub("", str(value or ""))
    return digits if len(digits) == 8 else ""


def address_fingerprint(
    municipality_ibge_code: str,
    postal_code: str,
    normalized_street: str,
    normalized_number: str,
) -> str:
    canonical = "\x1f".join(
        (municipality_ibge_code, postal_code, normalized_street, normalized_number)
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def address_lookup_key(
    municipality_ibge_code: str,
    postal_code: str,
    normalized_street: str,
    normalized_number: str,
) -> bytes:
    canonical = "\x1f".join(
        (municipality_ibge_code, postal_code, normalized_street, normalized_number)
    )
    return hashlib.blake2b(canonical.encode("utf-8"), digest_size=16).digest()


def resolve_candidates(
    *,
    address_candidates: list[CnefeCandidate],
    postal_candidates: list[CnefeCandidate] | None = None,
    prepared_postal_result: ResolutionResult | None = None,
) -> ResolutionResult:
    postal_result = prepared_postal_result or resolve_postal_candidates(postal_candidates or [])
    address = _best_level_candidates(address_candidates)
    if address:
        spread = _dispersion_meters(address)
        if spread <= AMBIGUITY_LIMIT_METERS:
            chosen = _representative_candidate(address)
            return _located_result(
                AddressResolution.Method.ADDRESS,
                chosen,
                address,
                spread,
                "address_match",
            )
        return replace(
            postal_result,
            reason=(
                "ambiguous_address_postal_fallback"
                if postal_result.method != AddressResolution.Method.UNLOCATED
                else "ambiguous_address_without_postal_fallback"
            ),
            candidate_count=len(address),
            dispersion_meters=_decimal_distance(spread),
        )

    return postal_result


def resolve_postal_candidates(candidates: list[CnefeCandidate]) -> ResolutionResult:
    unique = _unique_candidates(candidates)
    if not unique:
        return ResolutionResult(
            method=AddressResolution.Method.UNLOCATED,
            latitude=None,
            longitude=None,
            cnefe_level=None,
            address_code="",
            candidate_count=0,
            dispersion_meters=None,
            reason="postal_code_not_found",
        )

    chosen = _representative_candidate(unique)
    return _located_result(
        AddressResolution.Method.POSTAL_CODE,
        chosen,
        unique,
        _dispersion_meters(unique),
        "address_not_matched_postal_fallback",
    )


def _located_result(
    method: str,
    chosen: CnefeCandidate,
    candidates: list[CnefeCandidate],
    spread: float,
    reason: str,
) -> ResolutionResult:
    return ResolutionResult(
        method=method,
        latitude=Decimal(f"{chosen.latitude:.6f}"),
        longitude=Decimal(f"{chosen.longitude:.6f}"),
        cnefe_level=chosen.level,
        address_code=chosen.address_code,
        candidate_count=len(candidates),
        dispersion_meters=_decimal_distance(spread),
        reason=reason,
    )


def _best_level_candidates(candidates: list[CnefeCandidate]) -> list[CnefeCandidate]:
    unique = _unique_candidates(candidates)
    if not unique:
        return []
    best_level = min(candidate.level for candidate in unique)
    return [candidate for candidate in unique if candidate.level == best_level]


def _unique_candidates(candidates: list[CnefeCandidate]) -> list[CnefeCandidate]:
    by_coordinate: dict[tuple[float, float], CnefeCandidate] = {}
    for candidate in candidates:
        key = (round(candidate.latitude, 6), round(candidate.longitude, 6))
        current = by_coordinate.get(key)
        if current is None or (candidate.level, candidate.address_code) < (
            current.level,
            current.address_code,
        ):
            by_coordinate[key] = candidate
    return sorted(
        by_coordinate.values(),
        key=lambda item: (item.latitude, item.longitude, item.level, item.address_code),
    )


def _representative_candidate(candidates: list[CnefeCandidate]) -> CnefeCandidate:
    median_latitude = median(candidate.latitude for candidate in candidates)
    median_longitude = median(candidate.longitude for candidate in candidates)
    return min(
        candidates,
        key=lambda candidate: (
            _haversine_meters(
                median_latitude,
                median_longitude,
                candidate.latitude,
                candidate.longitude,
            ),
            candidate.address_code,
            candidate.latitude,
            candidate.longitude,
        ),
    )


def _dispersion_meters(candidates: list[CnefeCandidate]) -> float:
    if len(candidates) < 2:
        return 0.0
    if len(candidates) > 100:
        latitudes = [candidate.latitude for candidate in candidates]
        longitudes = [candidate.longitude for candidate in candidates]
        return _haversine_meters(min(latitudes), min(longitudes), max(latitudes), max(longitudes))
    return max(
        _haversine_meters(
            left.latitude,
            left.longitude,
            right.latitude,
            right.longitude,
        )
        for index, left in enumerate(candidates)
        for right in candidates[index + 1 :]
    )


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return EARTH_RADIUS_METERS * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _decimal_distance(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(f"{value:.2f}")
