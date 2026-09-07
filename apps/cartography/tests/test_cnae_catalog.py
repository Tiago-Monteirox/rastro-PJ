import io
import json

from django.test import TestCase

from apps.cartography.models import CnaeSubclass
from apps.cartography.services.cnae_catalog import (
    CnaeCatalogError,
    fetch_cnae_catalog,
    replace_cnae_catalog,
)


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class CnaeCatalogTests(TestCase):
    def test_fetch_normalizes_the_official_payload(self):
        payload = [{"id": "4711302", "descricao": "  Comércio   varejista em geral "}]

        catalog = fetch_cnae_catalog(
            opener=lambda *_args, **_kwargs: _Response(json.dumps(payload).encode()),
            minimum_size=1,
        )

        self.assertEqual(catalog, {"4711302": "Comércio varejista em geral"})

    def test_fetch_rejects_an_invalid_or_partial_catalog(self):
        payload = [{"id": "INVALIDO", "descricao": "Inválida"}]

        with self.assertRaises(CnaeCatalogError):
            fetch_cnae_catalog(
                opener=lambda *_args, **_kwargs: _Response(json.dumps(payload).encode()),
                minimum_size=1,
            )

    def test_replace_updates_entries_and_removes_stale_codes(self):
        CnaeSubclass.objects.create(code="9999999", description="Obsoleta")

        total = replace_cnae_catalog({"4711302": "Comércio varejista em geral"})

        self.assertEqual(total, 1)
        self.assertFalse(CnaeSubclass.objects.filter(code="9999999").exists())
        self.assertEqual(
            CnaeSubclass.objects.get(code="4711302").description,
            "Comércio varejista em geral",
        )
