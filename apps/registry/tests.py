from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.test_support import create_revision, create_scope, create_window

from .models import Company, CompanySnapshot, PartnerParticipation


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
