import hashlib
import zipfile
from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import duckdb
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase

from apps.changes.models import ChangeEvent, RegionalMonthlyMetric
from apps.changes.services import QualityCandidate, compare_snapshots
from apps.geography.models import GeographicScope
from apps.registry.models import CompanySnapshot
from apps.test_support import create_import_batch, create_revision, create_scope, create_window

from .contracts import (
    CONTRACT_VERSION,
    TABLE_CONTRACTS,
    ArtifactManifest,
    ContractError,
    ManifestError,
    PackageManifest,
    WindowManifest,
    contract_bundle_hash,
    file_sha256,
    load_json,
    write_json_atomic,
)
from .models import (
    CompetenceRevision,
    DataQualityIssue,
    HistoricalWindow,
    ImportBatch,
    PackageArtifact,
    SourceArtifact,
)
from .services import (
    import_window_package,
    recalculate_quality_metadata,
    recalculate_window_events,
    validate_parquet,
    validate_window_package,
    write_parquet_atomic,
)
from .services.municipality_catalog import IbgeCatalog, MunicipalityResolver
from .services.normalization import (
    PrivacyViolation,
    assert_no_prohibited_personal_data,
    canonical_record_hash,
    remove_personal_document_sequences,
)
from .services.rf_prepare import (
    ReceitaPreparationError,
    _company_records,
    _extracted_archive,
    _partner_identity,
    _read_csv_sql,
    _reusable_cohort,
    _reusable_package,
    _rf_date,
)
from .services.rf_sources import inventory_competence
from .services.synthetic_window import generate_synthetic_window
from .services.window_import import (
    WindowImportError,
    _compare_revisions,
    _enforce_warning_threshold,
    _package_warning,
)


class PipelineIntegrityTests(TestCase):
    def setUp(self):
        self.scope = create_scope()

    def test_database_allows_only_one_active_window(self):
        create_window(scope=self.scope, status=HistoricalWindow.Status.ACTIVE)

        with self.assertRaises(IntegrityError), transaction.atomic():
            create_window(
                scope=self.scope,
                code="outra-janela",
                status=HistoricalWindow.Status.ACTIVE,
            )

    def test_published_window_requires_auditable_hashes(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            HistoricalWindow.objects.create(
                geographic_scope=self.scope,
                code="sem-hashes",
                start_competence="2025-08-01",
                end_competence="2026-08-01",
                contract_version="1.0.0",
                status=HistoricalWindow.Status.ACTIVE,
            )

    def test_database_allows_only_one_published_revision_per_competence(self):
        window = create_window(scope=self.scope)
        window_competence, _ = create_revision(
            window=window, status=CompetenceRevision.Status.PUBLISHED
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            CompetenceRevision.objects.create(
                window_competence=window_competence,
                revision_number=2,
                package_hash="e" * 64,
                contract_version="1.0.0",
                status=CompetenceRevision.Status.PUBLISHED_WITH_WARNINGS,
            )

    def test_quality_issue_cannot_affect_more_rows_than_eligible(self):
        window = create_window(scope=self.scope)
        _, revision = create_revision(
            window=window,
            status=CompetenceRevision.Status.PUBLISHED,
        )
        batch = create_import_batch(revision=revision)

        with self.assertRaises(IntegrityError), transaction.atomic():
            DataQualityIssue.objects.create(
                import_batch=batch,
                competence_revision=revision,
                rule_code="AFFECTED_OVERFLOW",
                severity=DataQualityIssue.Severity.FATAL,
                eligible_rows=2,
                affected_rows=3,
            )

    def test_synthetic_window_command_uses_loaded_scope(self):
        with TemporaryDirectory() as temporary_directory:
            output = StringIO()
            call_command(
                "generate_synthetic_window",
                Path(temporary_directory),
                stdout=output,
                no_color=True,
            )

            self.assertIn("Janela sintética gerada", output.getvalue())
            self.assertTrue(Path(temporary_directory, "window-manifest.json").is_file())

    def test_quality_metadata_recalculation_restores_affected_and_eligible_rows(self):
        window = create_window(scope=self.scope, status=HistoricalWindow.Status.ACTIVE)
        _, revision = create_revision(
            window=window,
            status=CompetenceRevision.Status.PUBLISHED,
        )
        revision.row_counts = {"companies": 900, "establishments": 1000, "partners": 400}
        revision.save(update_fields=("row_counts",))
        issue = DataQualityIssue.objects.create(
            import_batch=create_import_batch(revision=revision),
            competence_revision=revision,
            rule_code="SOURCE_ZERO_DATE",
            severity=DataQualityIssue.Severity.WARNING,
            entity_type="PARTICIPATION",
            entity_key="establishments_raw.registration_status_date",
            eligible_rows=1,
            affected_rows=1,
            details={
                "package_warning": (
                    "SOURCE_ZERO_DATE:establishments_raw.registration_status_date:3"
                )
            },
        )

        updated, _ = recalculate_quality_metadata(window)

        issue.refresh_from_db()
        self.assertEqual(updated, 1)
        self.assertEqual(issue.entity_type, "ESTABLISHMENT")
        self.assertEqual(issue.eligible_rows, 1000)
        self.assertEqual(issue.affected_rows, 3)
        self.assertEqual(issue.details["group_affected_rows"], 3)
        self.assertEqual(issue.details["warning_limit"], 10)

    def test_event_recalculation_uses_baseline_and_only_adjacent_competences(self):
        window = create_window(scope=self.scope, status=HistoricalWindow.Status.ACTIVE)
        _, october = create_revision(
            window=window,
            competence=date(2025, 10, 1),
            position=2,
            status=CompetenceRevision.Status.PUBLISHED,
            hash_char="f",
        )
        _, august = create_revision(
            window=window,
            competence=date(2025, 8, 1),
            position=0,
            status=CompetenceRevision.Status.PUBLISHED,
            hash_char="d",
        )
        _, september = create_revision(
            window=window,
            competence=date(2025, 9, 1),
            position=1,
            status=CompetenceRevision.Status.PUBLISHED,
            hash_char="e",
        )

        with patch(
            "apps.pipeline.services.window_import._compare_revisions",
            wraps=_compare_revisions,
        ) as compare_revisions:
            event_count = recalculate_window_events(window)

        compared_pairs = [
            (
                call.kwargs["previous_revision"].pk,
                call.kwargs["current_revision"].pk,
            )
            for call in compare_revisions.call_args_list
        ]
        self.assertEqual(
            compared_pairs,
            [(august.pk, september.pk), (september.pk, october.pk)],
        )
        self.assertEqual(event_count, 0)
        self.assertFalse(ChangeEvent.objects.filter(historical_window=window).exists())


def company_record(*, cnpj_basic: str = "12345678") -> dict:
    return {
        "cnpj_basic": cnpj_basic,
        "legal_name": "Empresa Exemplo Ltda",
        "legal_name_search": "empresa exemplo ltda",
        "legal_nature_code": "2062",
        "share_capital": "1000.00",
        "company_size_code": "03",
        "simples_optant": True,
        "simples_option_date": date(2020, 1, 1),
        "simples_exclusion_date": None,
        "mei_optant": False,
        "mei_option_date": None,
        "mei_exclusion_date": None,
        "competence": date(2026, 7, 1),
        "record_hash": "a" * 64,
    }


class FakeWebDavResponse:
    status = 207

    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


def webdav_inventory_payload() -> bytes:
    names = [
        *(f"Empresas{index}.zip" for index in range(10)),
        *(f"Estabelecimentos{index}.zip" for index in range(10)),
        *(f"Socios{index}.zip" for index in range(10)),
        "Simples.zip",
        "Municipios.zip",
    ]
    responses = "".join(
        "<d:response>"
        f"<d:href>/public.php/dav/files/token/2026-08/{name}</d:href>"
        "<d:propstat><d:prop><d:getcontentlength>100</d:getcontentlength>"
        f"<d:getetag>&quot;{name}&quot;</d:getetag>"
        "</d:prop></d:propstat>"
        "</d:response>"
        for name in names
    )
    return f'<d:multistatus xmlns:d="DAV:">{responses}</d:multistatus>'.encode()


class ComparisonQualityTests(SimpleTestCase):
    def test_missing_establishment_is_quality_issue_not_business_event(self):
        events, issues = compare_snapshots(
            previous_competence=date(2026, 7, 1),
            current_competence=date(2026, 8, 1),
            previous_companies={},
            current_companies={},
            previous_establishments={"11111111000191": {}},
            current_establishments={},
            previous_partners={},
            current_partners={},
        )

        self.assertEqual(events, [])
        self.assertEqual([item.rule_code for item in issues], ["ESTABLISHMENT_MISSING_IN_CURRENT"])

    def test_warning_volume_above_approved_limit_blocks_publication(self):
        issues = [
            QualityCandidate("TEST_RULE", "ESTABLISHMENT", str(index), {}) for index in range(11)
        ]
        state = {
            "companies": {},
            "establishments": {str(index): {} for index in range(100)},
            "partners": {},
        }

        with self.assertRaisesMessage(ValueError, "excedeu o limite"):
            _enforce_warning_threshold(issues, state, state)

    def test_late_first_seen_uses_longitudinally_calibrated_limit(self):
        state = {"companies": 0, "establishments": 677401, "partners": 0}
        observed = [
            QualityCandidate("LATE_FIRST_SEEN", "ESTABLISHMENT", str(index), {})
            for index in range(2879)
        ]

        _enforce_warning_threshold(observed, state, state)

        excessive = [
            QualityCandidate("LATE_FIRST_SEEN", "ESTABLISHMENT", str(index), {})
            for index in range(3389)
        ]
        with self.assertRaisesMessage(ValueError, "excedeu o limite"):
            _enforce_warning_threshold(excessive, state, state)

    def test_late_first_seen_is_generated_instead_of_false_opening(self):
        events, issues = compare_snapshots(
            previous_competence=date(2026, 7, 1),
            current_competence=date(2026, 8, 1),
            previous_companies={},
            current_companies={},
            previous_establishments={},
            current_establishments={
                "11111111000191": {
                    "activity_start_date": date(2020, 1, 1),
                    "registration_status_code": "02",
                }
            },
            previous_partners={},
            current_partners={},
        )

        self.assertEqual(events, [])
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule_code, "LATE_FIRST_SEEN")
        self.assertEqual(issues[0].entity_key, "11111111000191")
        self.assertEqual(issues[0].details["activity_start_date"], "2020-01-01")
        self.assertTrue(issues[0].details["comparison_suspended"])

    def test_opening_date_uses_left_open_right_closed_competence_interval(self):
        def compare_new_establishment(started):
            return compare_snapshots(
                previous_competence=date(2026, 7, 1),
                current_competence=date(2026, 8, 1),
                previous_companies={},
                current_companies={},
                previous_establishments={},
                current_establishments={
                    "11111111000191": {
                        "activity_start_date": started,
                        "registration_status_code": "02",
                    }
                },
                previous_partners={},
                current_partners={},
            )

        previous_border_events, previous_border_issues = compare_new_establishment(date(2026, 7, 1))
        current_border_events, current_border_issues = compare_new_establishment(date(2026, 8, 1))

        self.assertEqual(previous_border_events, [])
        self.assertEqual(
            [issue.rule_code for issue in previous_border_issues],
            ["LATE_FIRST_SEEN"],
        )
        self.assertEqual(current_border_issues, [])
        self.assertEqual(
            [event.event_type for event in current_border_events],
            ["ESTABLISHMENT_OPENED"],
        )
        self.assertEqual(current_border_events[0].source_effective_date, date(2026, 8, 1))

    def test_source_zero_date_uses_affected_rows_and_calibrated_limit(self):
        warning = _package_warning(
            "SOURCE_ZERO_DATE:establishments_raw.registration_status_date:1303"
        )
        state = {"companies": 0, "establishments": 647793, "partners": 0}

        enriched = _enforce_warning_threshold([warning], state, state)

        self.assertEqual(warning.entity_type, "ESTABLISHMENT")
        self.assertEqual(warning.affected_rows, 1303)
        self.assertEqual(enriched[0].details["eligible_rows"], 647793)
        self.assertEqual(enriched[0].details["group_affected_rows"], 1303)
        self.assertEqual(enriched[0].details["warning_limit"], 1620)

    def test_five_delivery_events_use_fields_already_present_in_snapshots(self):
        before_company = {
            "share_capital": "100.00",
            "legal_nature_code": "2062",
            "company_size_code": "01",
            "simples_optant": False,
            "simples_option_date": None,
            "simples_exclusion_date": None,
            "mei_optant": False,
            "mei_option_date": None,
            "mei_exclusion_date": None,
        }
        after_company = {
            **before_company,
            "legal_nature_code": "2135",
            "company_size_code": "03",
            "simples_optant": True,
            "simples_option_date": date(2026, 7, 10),
            "mei_optant": True,
            "mei_option_date": date(2026, 7, 10),
        }
        before_partner = {
            "partner_type": "PF",
            "display_name": "Pessoa Exemplo",
            "partner_cnpj_basic": None,
            "qualification_code": "49",
            "entry_date": date(2020, 1, 1),
        }
        after_partner = {**before_partner, "qualification_code": "22"}

        events, issues = compare_snapshots(
            previous_competence=date(2026, 7, 1),
            current_competence=date(2026, 8, 1),
            previous_companies={"11111111": before_company},
            current_companies={"11111111": after_company},
            previous_establishments={},
            current_establishments={},
            previous_partners={("11111111", "a" * 64): before_partner},
            current_partners={("11111111", "a" * 64): after_partner},
        )

        self.assertEqual(issues, [])
        self.assertEqual(
            {event.event_type for event in events},
            {
                "LEGAL_NATURE_CHANGED",
                "COMPANY_SIZE_CHANGED",
                "SIMPLES_STATUS_CHANGED",
                "MEI_STATUS_CHANGED",
                "PARTNER_QUALIFICATION_CHANGED",
            },
        )


class PackageContractTests(SimpleTestCase):
    def test_record_hash_represents_content_not_snapshot_competence(self):
        july = company_record()
        august = {**july, "competence": date(2026, 8, 1)}

        self.assertEqual(canonical_record_hash(july), canonical_record_hash(august))

    def test_company_snapshot_allows_future_cohort_members_but_not_orphan_establishments(self):
        connection = duckdb.connect(":memory:")
        try:
            connection.execute(
                "CREATE TABLE companies_raw(cnpj_basic VARCHAR, legal_name VARCHAR, "
                "legal_nature_code VARCHAR, share_capital VARCHAR, company_size_code VARCHAR)"
            )
            connection.execute(
                "CREATE TABLE simples_raw(cnpj_basic VARCHAR, simples_optant VARCHAR, "
                "simples_option_date VARCHAR, simples_exclusion_date VARCHAR, "
                "mei_optant VARCHAR, mei_option_date VARCHAR, mei_exclusion_date VARCHAR)"
            )
            connection.execute("CREATE TABLE establishments_raw(cnpj_basic VARCHAR)")
            connection.execute(
                "INSERT INTO companies_raw VALUES ('11111111', 'Empresa existente', "
                "'2062', '100.00', '01')"
            )
            connection.execute("INSERT INTO establishments_raw VALUES ('11111111')")

            records = _company_records(connection, date(2026, 7, 1))

            self.assertEqual([record["cnpj_basic"] for record in records], ["11111111"])
            connection.execute("INSERT INTO establishments_raw VALUES ('22222222')")
            with self.assertRaises(ReceitaPreparationError):
                _company_records(connection, date(2026, 7, 1))
        finally:
            connection.close()

    def test_resume_reuses_only_an_intact_package(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            window_path = generate_synthetic_window(
                output_directory=root,
                scope_code="triangulo-mineiro-35",
                scope_version=1,
                scope_hash="e" * 64,
            )
            window = WindowManifest.from_dict(load_json(window_path))
            package_root = root / "2026-07"

            reused = _reusable_package(
                output_directory=package_root,
                competence="2026-07",
                window_id=window.window_id,
                scope_hash=window.scope_hash,
                cohort_hash=window.cohort_hash,
                expected_sources=(),
            )

            self.assertEqual(reused, package_root / "package-manifest.json")
            with (package_root / "companies.parquet").open("ab") as artifact:
                artifact.write(b"tampered")
            self.assertIsNone(
                _reusable_package(
                    output_directory=package_root,
                    competence="2026-07",
                    window_id=window.window_id,
                    scope_hash=window.scope_hash,
                    cohort_hash=window.cohort_hash,
                    expected_sources=(),
                )
            )

    def test_resume_reuses_only_a_cohort_matching_its_state(self):
        connection = duckdb.connect(":memory:")
        try:
            connection.execute("CREATE TABLE cohort(cnpj VARCHAR)")
            connection.execute("INSERT INTO cohort VALUES ('11111111000191'), ('22222222000191')")
            values = ["11111111000191", "22222222000191"]
            state = {
                "cohort_count": len(values),
                "cohort_hash": hashlib.sha256("\n".join(values).encode()).hexdigest(),
            }

            self.assertEqual(_reusable_cohort(connection, state), values)
            state["cohort_hash"] = "0" * 64
            self.assertIsNone(_reusable_cohort(connection, state))
        finally:
            connection.close()

    def test_receita_zero_date_sentinel_becomes_null(self):
        self.assertIsNone(_rf_date("0"))
        self.assertIsNone(_rf_date("00000000"))

    def test_receita_csv_reader_uses_pretranscoded_utf8(self):
        sql = _read_csv_sql(Path("fonte.csv"), ("cnpj_basic", "legal_name"))

        self.assertIn("encoding='utf-8'", sql)

    def test_receita_archive_transcodes_cp1252_and_counts_invalid_bytes(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_directory = root / "2026-07"
            source_directory.mkdir()
            archive_path = source_directory / "Empresas0.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("EMPRESAS.CSV", b'"1";"caf\xe9\x81"\n')

            with _extracted_archive(archive_path, root / "work") as extracted:
                self.assertEqual(extracted.replacement_count, 1)
                self.assertEqual(extracted.path.read_text(encoding="utf-8"), '"1";"café�"\n')
                extracted_path = extracted.path

            self.assertFalse(extracted_path.exists())

    def test_municipality_resolver_accepts_historical_rf_name(self):
        resolver = MunicipalityResolver(
            tom_names={"0345": "FORTALEZA DO TABOCAO"},
            ibge_catalog=IbgeCatalog(
                path=Path("ibge.json"),
                sha256="a" * 64,
                entries={("tabocao", "TO"): ("1708254", "Tabocão")},
            ),
        )

        municipality = resolver.resolve("0345", "TO")

        self.assertEqual(municipality.ibge_code, "1708254")
        self.assertEqual(municipality.name, "Tabocão")

    def test_rf_inventory_requires_and_returns_the_32_source_archives(self):
        payload = webdav_inventory_payload()

        files = inventory_competence(
            "2026-08",
            share_token="token",
            webdav_root="https://example.test/dav",
            opener=lambda *args, **kwargs: FakeWebDavResponse(payload),
        )

        self.assertEqual(len(files), 32)
        self.assertEqual(sum(item.size_bytes for item in files), 3200)
        self.assertEqual(files[0].file_name, "Empresas0.zip")

    def test_contract_has_three_typed_tables_and_no_cpf_column(self):
        self.assertEqual(set(TABLE_CONTRACTS), {"companies", "establishments", "partners"})
        for contract in TABLE_CONTRACTS.values():
            for column_name in contract.column_names:
                self.assertNotIn("cpf", column_name.lower())
        self.assertEqual(len(contract_bundle_hash()), 64)

    def test_record_with_missing_column_is_rejected(self):
        record = company_record()
        del record["record_hash"]

        with self.assertRaises(ContractError):
            TABLE_CONTRACTS["companies"].validate_record(record)

    def test_parquet_is_written_atomically_and_validated(self):
        contract = TABLE_CONTRACTS["companies"]
        with TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / contract.filename
            written = write_parquet_atomic(
                contract=contract, records=[company_record()], output_path=output
            )
            validated = validate_parquet(contract=contract, path=output)

            self.assertEqual(written.row_count, 1)
            self.assertEqual(validated.row_count, 1)
            self.assertEqual(written.sha256, validated.sha256)
            self.assertFalse(output.with_name(f".{output.name}.part").exists())

    def test_duplicate_parquet_identity_is_rejected(self):
        contract = TABLE_CONTRACTS["companies"]
        with TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / contract.filename

            with self.assertRaisesMessage(ContractError, "Identidade duplicada"):
                write_parquet_atomic(
                    contract=contract,
                    records=[company_record(), company_record()],
                    output_path=output,
                )
            self.assertFalse(output.exists())
            self.assertFalse(output.with_name(f".{output.name}.part").exists())

    def test_package_manifest_round_trip_uses_contract_hashes(self):
        artifacts = tuple(
            ArtifactManifest(
                artifact_type=name,
                file_name=contract.filename,
                size_bytes=10,
                row_count=1,
                sha256="b" * 64,
                schema_hash=contract.schema_hash,
            )
            for name, contract in TABLE_CONTRACTS.items()
        )
        manifest = PackageManifest(
            contract_version=CONTRACT_VERSION,
            contract_hash=contract_bundle_hash(),
            window_id="synthetic-window",
            competence="2026-07",
            scope_hash="c" * 64,
            cohort_hash="d" * 64,
            generated_at="2026-08-24T12:00:00Z",
            sources=(),
            artifacts=artifacts,
        )

        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "package-manifest.json"
            write_json_atomic(path, manifest.to_dict())
            restored = PackageManifest.from_dict(load_json(path))

        self.assertEqual(restored, manifest)

    def test_manifest_rejects_incompatible_contract_hash(self):
        manifest = PackageManifest(
            contract_version=CONTRACT_VERSION,
            contract_hash="0" * 64,
            window_id="synthetic-window",
            competence="2026-07",
            scope_hash="c" * 64,
            cohort_hash="d" * 64,
            generated_at="2026-08-24T12:00:00Z",
            sources=(),
            artifacts=(),
        )

        with self.assertRaisesMessage(ManifestError, "Hash do contrato"):
            manifest.validate()

    def test_privacy_guard_rejects_key_and_masked_cpf_value(self):
        with self.assertRaises(PrivacyViolation):
            assert_no_prohibited_personal_data({"cpf_mascarado": "***123456**"})
        with self.assertRaises(PrivacyViolation):
            assert_no_prohibited_personal_data({"details": "identidade ***123456**"})
        with self.assertRaises(PrivacyViolation):
            assert_no_prohibited_personal_data({"details": "identidade 123.456.789-00"})
        with self.assertRaises(PrivacyViolation):
            assert_no_prohibited_personal_data({"details": "identidade 12345678900"})
        assert_no_prohibited_personal_data({"cnpj": "12345678000190"})
        assert_no_prohibited_personal_data({"partner_key": "abc12345678901def"})
        assert_no_prohibited_personal_data(
            {"sha256": "abc12345678901def", "scope_hash": "12345678900abcdef"}
        )

    def test_personal_document_sequences_are_removed_without_losing_the_name(self):
        self.assertEqual(
            remove_personal_document_sequences("123.456.789-00 EMPRESA EXEMPLO"),
            "EMPRESA EXEMPLO",
        )
        self.assertEqual(
            remove_personal_document_sequences("EMPRESA 12345678900 EXEMPLO"),
            "EMPRESA EXEMPLO",
        )

    def test_pf_partner_identity_is_secret_and_scoped_to_company(self):
        first, cnpj, warning = _partner_identity(
            basic="11111111",
            partner_type="PF",
            display_name="Pessoa Exemplo",
            source_identifier="***123456**",
            country_code=None,
            secret="segredo-de-teste",
        )
        second, _, _ = _partner_identity(
            basic="22222222",
            partner_type="PF",
            display_name="Pessoa Exemplo",
            source_identifier="***123456**",
            country_code=None,
            secret="segredo-de-teste",
        )

        self.assertNotEqual(first, second)
        self.assertEqual(len(first), 64)
        self.assertNotIn("123456", first)
        self.assertIsNone(cnpj)
        self.assertIsNone(warning)

    def test_pj_partner_identity_normalizes_full_cnpj_and_root(self):
        july_key, july_root, july_warning = _partner_identity(
            basic="11111111",
            partner_type="PJ",
            display_name="Empresa Sócia Ltda",
            source_identifier="66666666000146",
            country_code=None,
            secret="segredo-de-teste",
        )
        august_key, august_root, august_warning = _partner_identity(
            basic="11111111",
            partner_type="PJ",
            display_name="Empresa Sócia Ltda",
            source_identifier="66666666",
            country_code=None,
            secret="segredo-de-teste",
        )

        self.assertEqual(july_key, august_key)
        self.assertEqual(july_root, "66666666")
        self.assertEqual(august_root, "66666666")
        self.assertIsNone(july_warning)
        self.assertIsNone(august_warning)

    def test_synthetic_window_has_two_valid_consecutive_packages(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path = generate_synthetic_window(
                output_directory=root,
                scope_code="triangulo-mineiro-35",
                scope_version=1,
                scope_hash="e" * 64,
            )
            window = WindowManifest.from_dict(load_json(manifest_path))

            self.assertEqual(
                [item["competence"] for item in window.packages], ["2026-07", "2026-08"]
            )
            for item in window.packages:
                package_manifest_path = root / item["manifest_path"]
                self.assertEqual(file_sha256(package_manifest_path), item["manifest_sha256"])
                package = PackageManifest.from_dict(load_json(package_manifest_path))
                for artifact in package.artifacts:
                    artifact_path = package_manifest_path.parent / artifact.file_name
                    validated = validate_parquet(
                        contract=TABLE_CONTRACTS[artifact.artifact_type], path=artifact_path
                    )
                    self.assertEqual(validated.sha256, artifact.sha256)

            establishments = root / "2026-08/establishments.parquet"
            scenarios = duckdb.sql(
                "SELECT count(*) FROM read_parquet(?) "
                "WHERE registration_status_code = '08' OR is_in_region = false",
                params=[str(establishments)],
            ).fetchone()[0]
            self.assertGreaterEqual(scenarios, 2)


class WindowImportTests(TestCase):
    expected_event_types = {
        "ESTABLISHMENT_OPENED",
        "ESTABLISHMENT_CLOSED",
        "REGISTRATION_STATUS_CHANGED",
        "ADDRESS_CHANGED",
        "MAIN_CNAE_CHANGED",
        "ENTERED_REGION",
        "LEFT_REGION",
        "SHARE_CAPITAL_CHANGED",
        "PARTNER_ADDED",
        "PARTNER_REMOVED",
    }

    def test_two_competences_publish_ten_events_and_reimport_is_no_op(self):
        reference = Path(__file__).parents[2] / "data/reference/triangulo_mineiro_35_municipios.csv"
        call_command("load_geographic_scope", reference, no_color=True, verbosity=0)
        scope = GeographicScope.objects.get(code="triangulo-mineiro-35", version=1)

        with TemporaryDirectory() as temporary_directory:
            manifest_path = generate_synthetic_window(
                output_directory=Path(temporary_directory),
                scope_code=scope.code,
                scope_version=scope.version,
                scope_hash=scope.scope_hash,
            )
            first = import_window_package(manifest_path)
            second = import_window_package(manifest_path)

        original_keys = set(ChangeEvent.objects.values_list("event_key", flat=True))
        recalculated = recalculate_window_events(first.window)
        recalculated_keys = set(ChangeEvent.objects.values_list("event_key", flat=True))

        self.assertTrue(first.imported)
        self.assertFalse(second.imported)
        self.assertEqual(first.competence_count, 2)
        self.assertEqual(first.event_count, 10)
        self.assertEqual(first.warning_count, 0)
        self.assertEqual(recalculated, 10)
        self.assertEqual(recalculated_keys, original_keys)
        self.assertEqual(
            set(ChangeEvent.objects.values_list("event_type", flat=True)),
            self.expected_event_types,
        )
        self.assertEqual(HistoricalWindow.objects.get().status, HistoricalWindow.Status.ACTIVE)
        self.assertEqual(ChangeEvent.objects.count(), 10)
        self.assertEqual(PackageArtifact.objects.count(), 8)
        self.assertEqual(SourceArtifact.objects.count(), 0)
        self.assertEqual(
            CompetenceRevision.objects.filter(status=CompetenceRevision.Status.PUBLISHED).count(),
            2,
        )

    def test_changed_package_requires_and_publishes_explicit_atomic_revision(self):
        reference = Path(__file__).parents[2] / "data/reference/triangulo_mineiro_35_municipios.csv"
        call_command("load_geographic_scope", reference, no_color=True, verbosity=0)
        scope = GeographicScope.objects.get(code="triangulo-mineiro-35", version=1)

        with TemporaryDirectory() as temporary_directory:
            manifest_path = generate_synthetic_window(
                output_directory=Path(temporary_directory),
                scope_code=scope.code,
                scope_version=scope.version,
                scope_hash=scope.scope_hash,
            )
            initial = import_window_package(manifest_path)
            august_competence = initial.window.competences.get(competence="2026-08-01")
            old_revision = august_competence.revisions.get(
                status=CompetenceRevision.Status.PUBLISHED
            )
            old_capital = (
                CompanySnapshot.objects.filter(revision=old_revision).first().share_capital
            )
            old_metric_count = RegionalMonthlyMetric.objects.filter(revision=old_revision).count()
            old_event_keys = set(ChangeEvent.objects.values_list("event_key", flat=True))

            window_payload = load_json(manifest_path)
            august_reference = window_payload["packages"][1]
            package_manifest_path = manifest_path.parent / august_reference["manifest_path"]
            package_payload = load_json(package_manifest_path)
            company_artifact = next(
                item
                for item in package_payload["artifacts"]
                if item["artifact_type"] == "companies"
            )
            company_path = package_manifest_path.parent / company_artifact["file_name"]
            records = (
                duckdb.connect()
                .execute("SELECT * FROM read_parquet(?)", [str(company_path)])
                .fetch_arrow_table()
                .to_pylist()
            )
            records[0]["share_capital"] += 1
            records[0]["record_hash"] = canonical_record_hash(records[0])
            validation = write_parquet_atomic(
                contract=TABLE_CONTRACTS["companies"],
                records=records,
                output_path=company_path,
            )
            company_artifact.update(
                size_bytes=validation.size_bytes,
                row_count=validation.row_count,
                sha256=validation.sha256,
                schema_hash=validation.schema_hash,
            )
            write_json_atomic(package_manifest_path, package_payload)
            august_reference["manifest_sha256"] = file_sha256(package_manifest_path)
            write_json_atomic(manifest_path, window_payload)

            with self.assertRaisesMessage(WindowImportError, "--allow-revision"):
                import_window_package(manifest_path)

            old_revision.refresh_from_db()
            self.assertEqual(old_revision.status, CompetenceRevision.Status.PUBLISHED)
            self.assertEqual(august_competence.revisions.count(), 1)

            revised = import_window_package(manifest_path, allow_revision=True)

        old_revision.refresh_from_db()
        new_revision = august_competence.revisions.get(
            status__in=CompetenceRevision.ACTIVE_STATUSES
        )
        self.assertEqual(revised.revised_competences, ("2026-08",))
        self.assertEqual(old_revision.status, CompetenceRevision.Status.SUPERSEDED)
        self.assertEqual(new_revision.revision_number, 2)
        self.assertEqual(august_competence.revisions.count(), 2)
        self.assertEqual(
            CompanySnapshot.objects.filter(revision=new_revision).first().share_capital,
            old_capital + 1,
        )
        self.assertFalse(ChangeEvent.objects.filter(from_revision=old_revision).exists())
        self.assertFalse(ChangeEvent.objects.filter(to_revision=old_revision).exists())
        self.assertEqual(ChangeEvent.objects.count(), 10)
        self.assertNotEqual(
            set(ChangeEvent.objects.values_list("event_key", flat=True)), old_event_keys
        )
        self.assertEqual(PackageArtifact.objects.count(), 12)
        self.assertEqual(
            RegionalMonthlyMetric.objects.filter(revision=new_revision).count(),
            old_metric_count,
        )
        completed_batch = ImportBatch.objects.get(pk=revised.batch_id)
        self.assertEqual(completed_batch.phase, "revision_published")

    def test_failed_revision_quality_gate_preserves_active_revision_and_events(self):
        reference = Path(__file__).parents[2] / "data/reference/triangulo_mineiro_35_municipios.csv"
        call_command("load_geographic_scope", reference, no_color=True, verbosity=0)
        scope = GeographicScope.objects.get(code="triangulo-mineiro-35", version=1)

        with TemporaryDirectory() as temporary_directory:
            manifest_path = generate_synthetic_window(
                output_directory=Path(temporary_directory),
                scope_code=scope.code,
                scope_version=scope.version,
                scope_hash=scope.scope_hash,
            )
            initial = import_window_package(manifest_path)
            august_competence = initial.window.competences.get(competence="2026-08-01")
            active_revision = august_competence.revisions.get(
                status=CompetenceRevision.Status.PUBLISHED
            )
            event_keys = set(ChangeEvent.objects.values_list("event_key", flat=True))
            snapshot_count = CompanySnapshot.objects.filter(revision=active_revision).count()

            window_payload = load_json(manifest_path)
            august_reference = window_payload["packages"][1]
            package_manifest_path = manifest_path.parent / august_reference["manifest_path"]
            package_payload = load_json(package_manifest_path)
            package_payload["warnings"] = [
                f"AMBIGUOUS_PARTNER:source-{index}" for index in range(11)
            ]
            write_json_atomic(package_manifest_path, package_payload)
            august_reference["manifest_sha256"] = file_sha256(package_manifest_path)
            write_json_atomic(manifest_path, window_payload)

            with self.assertRaisesMessage(WindowImportError, "AMBIGUOUS_PARTNER"):
                import_window_package(manifest_path, allow_revision=True)

        active_revision.refresh_from_db()
        self.assertEqual(active_revision.status, CompetenceRevision.Status.PUBLISHED)
        self.assertEqual(august_competence.revisions.count(), 1)
        self.assertEqual(
            CompanySnapshot.objects.filter(revision=active_revision).count(), snapshot_count
        )
        self.assertEqual(set(ChangeEvent.objects.values_list("event_key", flat=True)), event_keys)
        failed_batch = ImportBatch.objects.filter(status=ImportBatch.Status.FAILED).latest(
            "started_at"
        )
        self.assertEqual(failed_batch.error_code, "WindowImportError")

    def test_tampered_package_manifest_fails_without_partial_window(self):
        with TemporaryDirectory() as temporary_directory:
            manifest_path = generate_synthetic_window(
                output_directory=Path(temporary_directory),
                scope_code="triangulo-mineiro-35",
                scope_version=1,
                scope_hash="e" * 64,
            )
            payload = load_json(manifest_path)
            payload["packages"][0]["manifest_sha256"] = "0" * 64
            write_json_atomic(manifest_path, payload)

            with self.assertRaisesMessage(ManifestError, "não confere"):
                import_window_package(manifest_path)

        self.assertFalse(HistoricalWindow.objects.exists())
        self.assertEqual(ImportBatch.objects.get().status, ImportBatch.Status.FAILED)

    def test_validator_returns_all_artifacts(self):
        with TemporaryDirectory() as temporary_directory:
            manifest_path = generate_synthetic_window(
                output_directory=Path(temporary_directory),
                scope_code="triangulo-mineiro-35",
                scope_version=1,
                scope_hash="e" * 64,
            )
            validated = validate_window_package(manifest_path)

        self.assertEqual(len(validated.packages), 2)
        self.assertTrue(
            all(set(package.artifacts) == set(TABLE_CONTRACTS) for package in validated.packages)
        )
