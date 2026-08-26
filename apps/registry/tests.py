from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase

from apps.test_support import create_revision, create_scope, create_window

from .cnpj import (
    InvalidCNPJError,
    extract_cnpj_basic,
    format_cnpj,
    format_cnpj_basic,
    normalize_cnpj,
    parse_cnpj_identifier,
    validate_cnpj,
    validate_cnpj_basic,
)
from .models import (
    Company,
    CompanySnapshot,
    Establishment,
    PartnerParticipation,
    PartnerSnapshot,
)


class CNPJDomainTests(SimpleTestCase):
    def test_official_alphanumeric_cnpj_is_normalized_validated_and_formatted(self):
        value = "00.000.000/e08g-12"

        self.assertEqual(normalize_cnpj(value), "00000000E08G12")
        self.assertEqual(validate_cnpj(value), "00000000E08G12")
        self.assertEqual(extract_cnpj_basic(value), "00000000")
        self.assertEqual(format_cnpj(value), "00.000.000/E08G-12")

    def test_alphanumeric_root_and_legacy_numeric_cnpj_are_compatible(self):
        self.assertEqual(validate_cnpj_basic("ab.cde.f12"), "ABCDEF12")
        self.assertEqual(format_cnpj_basic("abcdef12"), "AB.CDE.F12")
        self.assertEqual(validate_cnpj("11.111.111/0001-91"), "11111111000191")
        self.assertEqual(parse_cnpj_identifier("AB.CDE.F12/3456-80"), "ABCDEF12345680")

    def test_invalid_check_digits_final_letter_and_forbidden_character_are_rejected(self):
        for value in ("ABCDEF12345699", "ABCDEF1234568A", "ABC_DEF12345680"):
            with self.subTest(value=value), self.assertRaises(InvalidCNPJError):
                validate_cnpj(value)

        with self.assertRaises(InvalidCNPJError):
            validate_cnpj_basic("ABC_DEF12")


class RegistryIntegrityTests(TestCase):
    def setUp(self):
        self.scope = create_scope()
        self.window = create_window(scope=self.scope)
        _, self.revision = create_revision(window=self.window)
        self.company = Company.objects.create(cnpj_basic="12345678")

    def test_company_has_only_one_snapshot_per_revision(self):
        data = {
            "revision": self.revision,
            "company": self.company,
            "legal_name": "Empresa Exemplo Ltda",
            "legal_name_search": "empresa exemplo ltda",
            "record_hash": "e" * 64,
        }
        CompanySnapshot.objects.create(**data)

        with self.assertRaises(IntegrityError), transaction.atomic():
            CompanySnapshot.objects.create(**data)

    def test_negative_share_capital_is_rejected(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            CompanySnapshot.objects.create(
                revision=self.revision,
                company=self.company,
                legal_name="Empresa Exemplo Ltda",
                legal_name_search="empresa exemplo ltda",
                share_capital="-0.01",
                record_hash="e" * 64,
            )

    def test_partner_key_is_scoped_to_company_and_contains_no_cpf_field(self):
        participation = PartnerParticipation.objects.create(
            company=self.company,
            partner_key="f" * 64,
            partner_type=PartnerParticipation.PartnerType.PERSON,
        )

        field_names = {field.name for field in PartnerParticipation._meta.get_fields()}
        self.assertNotIn("cpf", field_names)
        self.assertNotIn("masked_cpf", field_names)
        self.assertEqual(participation.partner_key, "f" * 64)

    def test_database_accepts_canonical_alphanumeric_company_establishment_and_partner(self):
        company = Company.objects.create(cnpj_basic="ABCDEF12")
        establishment = Establishment.objects.create(
            company=company,
            cnpj="ABCDEF12345680",
        )
        participation = PartnerParticipation.objects.create(
            company=company,
            partner_key="a" * 64,
            partner_type=PartnerParticipation.PartnerType.COMPANY,
        )
        snapshot = PartnerSnapshot.objects.create(
            revision=self.revision,
            participation=participation,
            display_name="Sócia Alfanumérica Ltda",
            partner_cnpj_basic="ZXCVBN12",
            record_hash="b" * 64,
        )

        self.assertEqual(establishment.cnpj, "ABCDEF12345680")
        self.assertEqual(snapshot.partner_cnpj_basic, "ZXCVBN12")

    def test_database_rejects_noncanonical_or_malformed_cnpj_shapes(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Company.objects.create(cnpj_basic="abcdef12")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Establishment.objects.create(company=self.company, cnpj="1234567800019A")
