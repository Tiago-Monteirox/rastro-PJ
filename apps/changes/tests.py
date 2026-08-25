from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.test_support import (
    create_company_with_establishment,
    create_import_batch,
    create_revision,
    create_scope,
    create_window,
)

from .models import ChangeEvent


class ChangeEventIntegrityTests(TestCase):
    def setUp(self):
        scope = create_scope()
        self.window = create_window(scope=scope)
        _, self.from_revision = create_revision(window=self.window)
        _, self.to_revision = create_revision(
            window=self.window,
            competence=date(2025, 9, 1),
            position=1,
            hash_char="e",
        )
        self.batch = create_import_batch(revision=self.to_revision)
        self.company, self.establishment = create_company_with_establishment()

    def event_data(self):
        return {
            "event_key": "f" * 64,
            "historical_window": self.window,
            "from_revision": self.from_revision,
            "to_revision": self.to_revision,
            "entity_type": ChangeEvent.EntityType.COMPANY,
            "dimension": "share_capital",
            "event_type": "SHARE_CAPITAL_CHANGED",
            "import_batch": self.batch,
        }

    def test_event_requires_exactly_one_relational_target(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ChangeEvent.objects.create(**self.event_data())

        with self.assertRaises(IntegrityError), transaction.atomic():
            ChangeEvent.objects.create(
                **self.event_data(), company=self.company, establishment=self.establishment
            )

    def test_event_accepts_one_target(self):
        event = ChangeEvent.objects.create(**self.event_data(), company=self.company)
        self.assertEqual(event.company, self.company)

    def test_event_rejects_equal_revisions(self):
        data = self.event_data()
        data["to_revision"] = self.from_revision

        with self.assertRaises(IntegrityError), transaction.atomic():
            ChangeEvent.objects.create(**data, company=self.company)
