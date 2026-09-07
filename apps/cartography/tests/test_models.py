from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.cartography.models import (
    AddressResolution,
    CartographicProjection,
    GeographicSource,
)
from apps.geography.models import ScopeMunicipality
from apps.pipeline.models import HistoricalWindow
from apps.test_support import create_municipality, create_scope, create_window


class CartographyModelIntegrityTests(TestCase):
    def setUp(self):
        self.scope = create_scope()
        self.municipality = create_municipality()
        ScopeMunicipality.objects.create(scope=self.scope, municipality=self.municipality)
        self.window = create_window(scope=self.scope, status=HistoricalWindow.Status.ACTIVE)
        self.cnefe_source = GeographicSource.objects.create(
            kind=GeographicSource.Kind.CNEFE,
            version="2022",
            content_hash="1" * 64,
        )
        self.boundary_source = GeographicSource.objects.create(
            kind=GeographicSource.Kind.MUNICIPAL_BOUNDARIES,
            version="2022-minima",
            content_hash="2" * 64,
        )

    def test_resolution_requires_coordinate_pair(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            AddressResolution.objects.create(
                source=self.cnefe_source,
                municipality=self.municipality,
                fingerprint="3" * 64,
                method=AddressResolution.Method.ADDRESS,
                latitude=Decimal("-18.900000"),
                longitude=None,
                cnefe_level=1,
                reason="invalid_pair",
            )

    def test_only_one_projection_can_be_published_for_window(self):
        CartographicProjection.objects.create(
            historical_window=self.window,
            cnefe_source=self.cnefe_source,
            boundary_source=self.boundary_source,
            registry_manifest_hash=self.window.manifest_hash,
            algorithm_version="1.0.0",
            status=CartographicProjection.Status.PUBLISHED,
        )
        another_source = GeographicSource.objects.create(
            kind=GeographicSource.Kind.CNEFE,
            version="2022",
            content_hash="4" * 64,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            CartographicProjection.objects.create(
                historical_window=self.window,
                cnefe_source=another_source,
                boundary_source=self.boundary_source,
                registry_manifest_hash=self.window.manifest_hash,
                algorithm_version="1.0.0",
                status=CartographicProjection.Status.PUBLISHED,
            )
