from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.test_support import create_municipality, create_scope

from .models import Municipality, ScopeMunicipality
from .services import GeographicReferenceError, load_geographic_scope, read_reference

REFERENCE_PATH = Path(settings.BASE_DIR) / "data/reference/triangulo_mineiro_35_municipios.csv"


class GeographyIntegrityTests(TestCase):
    def test_codes_keep_leading_zero_and_scope_membership_is_unique(self):
        scope = create_scope()
        municipality = Municipality.objects.create(
            ibge_code="3100104", tom_code="0602", name="Abadia dos Dourados", uf="MG"
        )
        ScopeMunicipality.objects.create(scope=scope, municipality=municipality)

        municipality.refresh_from_db()
        self.assertEqual(municipality.tom_code, "0602")

        with self.assertRaises(IntegrityError), transaction.atomic():
            ScopeMunicipality.objects.create(scope=scope, municipality=municipality)

    def test_invalid_ibge_code_is_rejected_by_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Municipality.objects.create(
                ibge_code="317020", tom_code="5403", name="Inválido", uf="MG"
            )

    def test_factory_municipality_is_valid(self):
        self.assertEqual(create_municipality().ibge_code, "3170206")


class GeographicReferenceTests(TestCase):
    def test_versioned_reference_has_35_unique_textual_codes(self):
        rows = read_reference(REFERENCE_PATH, expected_count=35)

        self.assertEqual(len(rows), 35)
        self.assertEqual(len({row.ibge_code for row in rows}), 35)
        self.assertEqual(len({row.tom_code for row in rows}), 35)
        self.assertIn("0602", {row.tom_code for row in rows})
        self.assertIn("0742", {row.tom_code for row in rows})

    def test_load_is_atomic_and_idempotent(self):
        first = load_geographic_scope(
            reference_path=REFERENCE_PATH,
            code="triangulo-mineiro-35",
            name="Triângulo Mineiro — 35 municípios",
            version=1,
            expected_count=35,
        )
        second = load_geographic_scope(
            reference_path=REFERENCE_PATH,
            code="triangulo-mineiro-35",
            name="Triângulo Mineiro — 35 municípios",
            version=1,
            expected_count=35,
        )

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(Municipality.objects.count(), 35)
        self.assertEqual(ScopeMunicipality.objects.count(), 35)
        self.assertEqual(first.scope_hash, second.scope_hash)

    def test_dry_run_command_validates_without_writing(self):
        output = StringIO()

        call_command(
            "load_geographic_scope",
            REFERENCE_PATH,
            dry_run=True,
            stdout=output,
            no_color=True,
        )

        self.assertIn("35 municípios", output.getvalue())
        self.assertEqual(Municipality.objects.count(), 0)

    def test_duplicate_tom_is_rejected_before_database_write(self):
        with TemporaryDirectory() as temporary_directory:
            invalid_path = Path(temporary_directory) / "invalid.csv"
            invalid_path.write_text(
                "municipio,codigo_ibge,codigo_tom,uf\n"
                "Uberlândia,3170206,5403,MG\n"
                "Uberaba,3170107,5403,MG\n",
                encoding="utf-8",
            )

            with self.assertRaisesMessage(GeographicReferenceError, "TOM duplicado"):
                load_geographic_scope(
                    reference_path=invalid_path,
                    code="invalid",
                    name="Inválido",
                    version=1,
                    expected_count=2,
                )

        self.assertEqual(Municipality.objects.count(), 0)

    def test_command_translates_domain_error(self):
        with self.assertRaises(CommandError):
            call_command("load_geographic_scope", Path("missing.csv"), no_color=True)
