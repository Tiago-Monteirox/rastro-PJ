import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase

from apps.cartography.models import GeographicSource, MunicipalityBoundary
from apps.cartography.services.projection import build_cnefe_indexes
from apps.cartography.services.sources import (
    inventory_cnefe_directory,
    load_municipality_boundaries,
)
from apps.geography.models import ScopeMunicipality
from apps.test_support import create_municipality, create_scope

CNEFE_HEADER = (
    "COD_UNICO_ENDERECO;COD_MUNICIPIO;CEP;NOM_TITULO_SEGLOGR;NOM_SEGLOGR;"
    "NUM_ENDERECO;LATITUDE;LONGITUDE;NV_GEO_COORD\n"
)


class CartographicSourceTests(TestCase):
    def setUp(self):
        self.scope = create_scope()
        self.municipality = create_municipality()
        ScopeMunicipality.objects.create(scope=self.scope, municipality=self.municipality)

    def test_cnefe_inventory_and_index_are_deterministic(self):
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            (directory / "3170206.csv").write_text(
                CNEFE_HEADER + "100;3170206;38400130;;AFONSO PENA;745;-18.900000;-48.200000;1\n",
                encoding="utf-8",
            )

            first = inventory_cnefe_directory(directory, self.scope)
            second = inventory_cnefe_directory(directory, self.scope)
            indexes = build_cnefe_indexes(first)

        self.assertEqual(first.content_hash, second.content_hash)
        self.assertEqual(first.manifest, second.manifest)
        self.assertEqual(indexes.row_count, 1)
        self.assertEqual(len(indexes.by_address), 1)
        self.assertEqual(len(indexes.by_postal_code[("3170206", "38400130")]), 1)

    def test_boundary_loader_is_idempotent_and_preserves_geometry(self):
        geometry = {
            "type": "Polygon",
            "coordinates": [
                [
                    [-48.3, -19.0],
                    [-48.1, -19.0],
                    [-48.1, -18.8],
                    [-48.3, -19.0],
                ]
            ],
        }
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            (directory / "3170206.geojson").write_text(
                json.dumps({"type": "Feature", "geometry": geometry}),
                encoding="utf-8",
            )

            first = load_municipality_boundaries(
                scope=self.scope,
                directory=directory,
                version="test",
            )
            second = load_municipality_boundaries(
                scope=self.scope,
                directory=directory,
                version="test",
            )

        self.assertEqual(first, second)
        self.assertEqual(
            GeographicSource.objects.filter(
                kind=GeographicSource.Kind.MUNICIPAL_BOUNDARIES
            ).count(),
            1,
        )
        boundary = MunicipalityBoundary.objects.get(source=first)
        self.assertEqual(boundary.geometry, geometry)
        self.assertEqual(boundary.bbox, [-48.3, -19.0, -48.1, -18.8])

    def test_boundary_loader_normalizes_gzip_response_saved_as_geojson(self):
        geometry = {
            "type": "Polygon",
            "coordinates": [[[-48.3, -19.0], [-48.1, -19.0], [-48.3, -19.0]]],
        }
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "3170206.geojson"
            path.write_bytes(
                gzip.compress(json.dumps({"type": "Feature", "geometry": geometry}).encode("utf-8"))
            )

            source = load_municipality_boundaries(
                scope=self.scope,
                directory=path.parent,
                version="gzip-test",
            )

            self.assertFalse(path.read_bytes().startswith(b"\x1f\x8b"))
            self.assertEqual(
                MunicipalityBoundary.objects.get(source=source).geometry,
                geometry,
            )
