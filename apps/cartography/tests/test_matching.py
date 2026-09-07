from decimal import Decimal

from django.test import SimpleTestCase

from apps.cartography.models import AddressResolution
from apps.cartography.services.matching import (
    CnefeCandidate,
    address_fingerprint,
    normalize_number,
    normalize_postal_code,
    normalize_text,
    resolve_candidates,
)


class AddressMatchingTests(SimpleTestCase):
    def test_normalization_is_stable_and_accent_insensitive(self):
        self.assertEqual(normalize_text("  Av. João  Pinheiro "), "AV JOAO PINHEIRO")
        self.assertEqual(normalize_number("00042"), "42")
        self.assertEqual(normalize_number("s/n"), "")
        self.assertEqual(normalize_postal_code("38.400-130"), "38400130")
        self.assertEqual(
            address_fingerprint("3170206", "38400130", "AFONSO PENA", "745"),
            address_fingerprint("3170206", "38400130", "AFONSO PENA", "745"),
        )

    def test_best_cnefe_level_wins_and_selected_point_is_real(self):
        lower_quality = CnefeCandidate("30", -18.9000, -48.2000, 3)
        best_a = CnefeCandidate("20", -18.9000, -48.2000, 1)
        best_b = CnefeCandidate("10", -18.9001, -48.2001, 1)

        result = resolve_candidates(
            address_candidates=[lower_quality, best_a, best_b],
            postal_candidates=[],
        )

        self.assertEqual(result.method, AddressResolution.Method.ADDRESS)
        self.assertEqual(result.cnefe_level, 1)
        self.assertIn(
            (result.latitude, result.longitude),
            {
                (Decimal("-18.900000"), Decimal("-48.200000")),
                (Decimal("-18.900100"), Decimal("-48.200100")),
            },
        )
        self.assertEqual(result.candidate_count, 2)

    def test_address_dispersion_above_limit_downgrades_to_postal_code(self):
        result = resolve_candidates(
            address_candidates=[
                CnefeCandidate("a", -18.9000, -48.2000, 1),
                CnefeCandidate("b", -18.9050, -48.2050, 1),
            ],
            postal_candidates=[
                CnefeCandidate("postal-a", -18.9010, -48.2010, 2),
                CnefeCandidate("postal-b", -18.9020, -48.2020, 2),
            ],
        )

        self.assertEqual(result.method, AddressResolution.Method.POSTAL_CODE)
        self.assertEqual(result.reason, "ambiguous_address_postal_fallback")
        self.assertIn(result.address_code, {"postal-a", "postal-b"})

    def test_missing_address_and_postal_code_remains_unlocated(self):
        result = resolve_candidates(address_candidates=[], postal_candidates=[])

        self.assertEqual(result.method, AddressResolution.Method.UNLOCATED)
        self.assertIsNone(result.latitude)
        self.assertEqual(result.reason, "postal_code_not_found")
