import io
import json

from django.test import TestCase

from apps.cartography.models import GeographicSource, MunicipalityPopulation
from apps.cartography.services.population_reference import (
    PopulationReferenceError,
    fetch_population_reference,
    population_reference_url,
    replace_population_reference,
)
from apps.geography.models import Municipality


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _sidra_payload(*rows):
    return [
        {
            "D1C": "Município (Código)",
            "D2C": "Variável (Código)",
            "D3C": "Ano (Código)",
            "V": "Valor",
        },
        *[
            {
                "D1C": code,
                "D1N": name,
                "D2C": "93",
                "D2N": "População residente",
                "D3C": "2022",
                "D3N": "2022",
                "V": str(population),
            }
            for code, name, population in rows
        ],
    ]


class PopulationReferenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.uberlandia = Municipality.objects.create(
            ibge_code="3170206",
            tom_code="5403",
            name="Uberlândia",
            uf="MG",
        )
        cls.uberaba = Municipality.objects.create(
            ibge_code="3170107",
            tom_code="5401",
            name="Uberaba",
            uf="MG",
        )

    def test_fetch_requires_every_requested_municipality_and_normalizes_values(self):
        payload = _sidra_payload(
            ("3170206", "Uberlândia (MG)", 713_224),
            ("3170107", "Uberaba (MG)", 337_836),
        )

        result = fetch_population_reference(
            ["3170206", "3170107"],
            opener=lambda *_args, **_kwargs: _Response(json.dumps(payload).encode()),
        )

        self.assertEqual(result, {"3170107": 337_836, "3170206": 713_224})
        self.assertIn("3170107,3170206", population_reference_url(result))

    def test_fetch_rejects_partial_or_inconsistent_payload(self):
        partial_payload = _sidra_payload(("3170206", "Uberlândia (MG)", 713_224))
        wrong_period_payload = _sidra_payload(("3170206", "Uberlândia (MG)", 713_224))
        wrong_period_payload[1]["D3C"] = "2021"

        with self.subTest("missing municipality"), self.assertRaises(PopulationReferenceError):
            fetch_population_reference(
                ["3170206", "3170107"],
                opener=lambda *_args, **_kwargs: _Response(json.dumps(partial_payload).encode()),
            )
        with self.subTest("wrong reference year"), self.assertRaises(PopulationReferenceError):
            fetch_population_reference(
                ["3170206"],
                opener=lambda *_args, **_kwargs: _Response(
                    json.dumps(wrong_period_payload).encode()
                ),
            )

    def test_replace_is_idempotent_and_preserves_an_auditable_manifest(self):
        values = {"3170206": 713_224, "3170107": 337_836}

        first_source, first_total = replace_population_reference(values)
        second_source, second_total = replace_population_reference(values)

        self.assertEqual(first_total, 2)
        self.assertEqual(second_total, 2)
        self.assertEqual(first_source, second_source)
        self.assertEqual(
            GeographicSource.objects.filter(
                kind=GeographicSource.Kind.MUNICIPAL_POPULATION
            ).count(),
            1,
        )
        self.assertEqual(MunicipalityPopulation.objects.count(), 2)
        self.assertEqual(
            MunicipalityPopulation.objects.get(municipality=self.uberlandia).population,
            713_224,
        )
        self.assertEqual(first_source.manifest["reference_year"], 2022)
        self.assertEqual(first_source.manifest["municipality_count"], 2)
        self.assertEqual(len(first_source.manifest["values"]), 2)
