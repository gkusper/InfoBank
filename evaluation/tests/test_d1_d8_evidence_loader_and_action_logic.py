from __future__ import annotations

import datetime as dt
import importlib
import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from evaluation.clean_state import CleanStateError
from evaluation.backend import REPO_ROOT, ensure_backend_path
from evaluation.load_evidence_fixtures import load_benchmark, load_case
from evaluation.run_d1_d8_pilot import DEFAULT_DOCUMENT_FIXTURE, DEFAULT_EVIDENCE_BENCHMARK, run_preflight, sanitize
from evaluation.run_document_rag_pilot import PilotError, validate_runtime_targets


def backend_modules():
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    ensure_backend_path()
    for name in ["database", "models", "policy_engine", "citds_classifier", "evidence_service"]:
        if name in sys.modules:
            importlib.reload(sys.modules[name])
        else:
            importlib.import_module(name)
    import models
    import policy_engine
    import evidence_service

    return models, policy_engine, evidence_service


class EvidenceSqliteCase(unittest.TestCase):
    def setUp(self) -> None:
        self.models, self.policy_engine, self.evidence_service = backend_modules()
        engine = create_engine("sqlite:///:memory:")
        self.models.Base.metadata.create_all(bind=engine)
        Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = Session()
        self.user_id = str(uuid.uuid4())
        self.db.add(
            self.models.User(
                id=self.user_id,
                email=f"{self.user_id}@example.test",
                username=f"u_{self.user_id[:8]}",
                password_hash="test",
            )
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def add_unit(self, *, source_type: str, content: str, relation_key: str, timestamp: str, access_mode: str = "Full") -> str:
        unit_id = "EU_" + uuid.uuid4().hex[:12]
        self.db.add(
            self.models.EvidenceUnit(
                id=unit_id,
                user_id=self.user_id,
                source_type=self.models.EvidenceSourceType(source_type),
                title=f"{source_type} test evidence",
                content=content,
                source_timestamp=dt.datetime.fromisoformat(timestamp),
                thread_id=relation_key,
                relation_key=relation_key,
                metadata_json=json.dumps({"benchmark_evidence_id": unit_id}),
            )
        )
        self.db.commit()
        self.policy_engine.create_policy_rule(self.db, self.user_id, "EvidenceUnit", unit_id, "action_reconstruction", access_mode)
        return unit_id

    def test_relation_key_joins_differently_worded_completion(self) -> None:
        primary = self.add_unit(
            source_type="Email",
            content="Email message. Direction: inbound. Body excerpt: please compile the wetlands budget packet.",
            relation_key="wetlands-budget",
            timestamp="2026-01-01T09:00:00",
        )
        contrastive = self.add_unit(
            source_type="Email",
            content="Email message. Direction: inbound. Later body excerpt: I have finished and sent the finance packet.",
            relation_key="wetlands-budget",
            timestamp="2026-01-02T09:00:00",
        )
        result = self.evidence_service.reconstruct_action_list(self.db, self.user_id)
        self.assertEqual(len(result["closed_items"]), 1)
        closed = result["closed_items"][0]
        self.assertIn(primary, closed["E"])
        self.assertIn(contrastive, closed["E"])

    def test_cancellation_and_supersession_close_only_same_relation(self) -> None:
        self.add_unit(
            source_type="Email",
            content="Email message. Direction: inbound. Body excerpt: please prepare the campus access memo.",
            relation_key="campus-access",
            timestamp="2026-01-01T09:00:00",
        )
        self.add_unit(
            source_type="Email",
            content="Email message. Direction: inbound. Later body excerpt: the request is no longer needed.",
            relation_key="campus-access",
            timestamp="2026-01-02T09:00:00",
        )
        self.add_unit(
            source_type="Email",
            content="Email message. Direction: inbound. Later body excerpt: this has been replaced by a new version instead.",
            relation_key="unrelated-project",
            timestamp="2026-01-02T10:00:00",
        )
        result = self.evidence_service.reconstruct_action_list(self.db, self.user_id)
        self.assertEqual(result["counts"]["closed"], 1)
        self.assertEqual(result["counts"]["open"], 0)

    def test_unrelated_later_message_does_not_close_action(self) -> None:
        primary = self.add_unit(
            source_type="Email",
            content="Email message. Direction: inbound. Body excerpt: please verify the seminar roster.",
            relation_key="seminar-roster",
            timestamp="2026-01-01T09:00:00",
        )
        self.add_unit(
            source_type="Email",
            content="Email message. Direction: inbound. Later body excerpt: I have completed the lab inventory.",
            relation_key="lab-inventory",
            timestamp="2026-01-02T09:00:00",
        )
        result = self.evidence_service.reconstruct_action_list(self.db, self.user_id)
        self.assertEqual(result["counts"]["open"], 1)
        self.assertIn(primary, result["open_items"][0]["E"])

    def test_progress_or_future_commitment_does_not_close(self) -> None:
        primary = self.add_unit(
            source_type="Email",
            content="Email message. Direction: inbound. Body excerpt: please review the scholarship packet.",
            relation_key="scholarship-packet",
            timestamp="2026-01-01T09:00:00",
        )
        later = self.add_unit(
            source_type="Email",
            content="Email message. Direction: inbound. Later body excerpt: I am working on it and will send it tomorrow.",
            relation_key="scholarship-packet",
            timestamp="2026-01-02T09:00:00",
        )
        result = self.evidence_service.reconstruct_action_list(self.db, self.user_id)
        self.assertEqual(result["counts"]["open"], 1)
        self.assertEqual(result["counts"]["closed"], 0)
        self.assertIn(primary, result["open_items"][0]["E"])
        roles = {unit["id"]: unit["role"] for unit in result["classified_units"]}
        self.assertEqual(roles[later], "contextual")

    def test_browser_history_never_creates_primary_action(self) -> None:
        browser = self.add_unit(
            source_type="BrowserHistory",
            content="Search query: scholarship packet review deadline",
            relation_key="scholarship-packet",
            timestamp="2026-01-01T09:00:00",
        )
        result = self.evidence_service.reconstruct_action_list(self.db, self.user_id)
        self.assertEqual(result["counts"]["open"], 0)
        roles = {unit["id"]: unit["role"] for unit in result["classified_units"]}
        self.assertEqual(roles[browser], "contextual")

    def test_query_time_excludes_future_evidence(self) -> None:
        self.add_unit(
            source_type="Email",
            content="Email message. Direction: inbound. Body excerpt: please prepare the faculty agenda.",
            relation_key="faculty-agenda",
            timestamp="2026-01-01T09:00:00",
        )
        self.add_unit(
            source_type="Email",
            content="Email message. Direction: inbound. Later body excerpt: I have completed the faculty agenda.",
            relation_key="faculty-agenda",
            timestamp="2026-01-03T09:00:00",
        )
        result = self.evidence_service.reconstruct_action_list(self.db, self.user_id, as_of=dt.datetime(2026, 1, 2, 9, 0, 0))
        self.assertEqual(result["counts"]["open"], 1)
        self.assertEqual(result["counts"]["closed"], 0)


class EvidenceBenchmarkLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.models, self.policy_engine, self.evidence_service = backend_modules()
        engine = create_engine("sqlite:///:memory:")
        self.models.Base.metadata.create_all(bind=engine)
        Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = Session()
        self.benchmark = load_benchmark(DEFAULT_EVIDENCE_BENCHMARK)

    def tearDown(self) -> None:
        self.db.close()

    def test_all_32_cases_are_available(self) -> None:
        self.assertEqual(len(self.benchmark.cases), 32)

    def test_d7_content_is_loaded_without_role_hint_rewrite(self) -> None:
        case = next(row for row in self.benchmark.cases if row["case_id"] == "D7_001")
        loaded = load_case(self.db, case)
        units = self.db.query(self.models.EvidenceUnit).filter(self.models.EvidenceUnit.user_id == loaded.user_id).all()
        self.assertEqual(len(units), 3)
        original_by_id = {unit["evidence_id"]: unit for unit in case["evidence_units"]}
        for unit in units:
            self.assertEqual(unit.content, original_by_id[unit.id]["content"])
            self.assertEqual(unit.source_type.value, "BrowserHistory")
            self.assertNotIn("contextual support only", unit.content.lower())
            metadata = json.loads(unit.metadata_json)
            self.assertNotIn("gold_role", metadata)
            self.assertNotIn("expected_status", metadata)
            self.assertNotIn("closure_type", metadata)

    def test_loader_preserves_evidence_ids_and_creates_policy_rules(self) -> None:
        case = next(row for row in self.benchmark.cases if row["case_id"] == "D6_001")
        loaded = load_case(self.db, case)
        self.assertEqual(loaded.inserted_evidence_ids, [case["evidence_units"][0]["evidence_id"]])
        rules = self.db.query(self.models.PolicyRule).filter(self.models.PolicyRule.owner_user_id == loaded.user_id).all()
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].access_mode.value, "Full")

    def test_loader_excludes_future_units_at_query_time(self) -> None:
        case = dict(next(row for row in self.benchmark.cases if row["case_id"] == "D6_001"))
        case["case_id"] = "D6_FUTURE_TEST"
        case["query_time"] = "2026-01-02T12:00:00"
        future = dict(case["evidence_units"][0])
        future["evidence_id"] = "EU_future_excluded"
        future["timestamp"] = "2026-01-03T12:00:00"
        case["evidence_units"] = [case["evidence_units"][0], future]
        loaded = load_case(self.db, case)
        self.assertIn("EU_future_excluded", loaded.excluded_future_evidence_ids)
        self.assertNotIn("EU_future_excluded", loaded.inserted_evidence_ids)

    def test_case_isolation_uses_distinct_users(self) -> None:
        first = load_case(self.db, next(row for row in self.benchmark.cases if row["case_id"] == "D6_001"))
        second = load_case(self.db, next(row for row in self.benchmark.cases if row["case_id"] == "D6_002"))
        self.assertNotEqual(first.user_id, second.user_id)
        first_count = self.db.query(self.models.EvidenceUnit).filter(self.models.EvidenceUnit.user_id == first.user_id).count()
        second_count = self.db.query(self.models.EvidenceUnit).filter(self.models.EvidenceUnit.user_id == second.user_id).count()
        self.assertEqual(first_count, 1)
        self.assertEqual(second_count, 1)


class D1D8EnvironmentTests(unittest.TestCase):
    def test_development_database_is_rejected(self) -> None:
        with self.assertRaises(PilotError):
            validate_runtime_targets(
                database_url="mysql+pymysql://infobank:pw@127.0.0.1:3307/infobank_db",
                chroma_path=REPO_ROOT / "backend_python" / "chroma_eval",
            )

    def test_development_chroma_path_is_rejected(self) -> None:
        with self.assertRaises(PilotError):
            validate_runtime_targets(
                database_url="mysql+pymysql://infobank:pw@127.0.0.1:3307/infobank_eval",
                chroma_path=REPO_ROOT / "chroma_data",
            )

    def test_d1_d8_preflight_rejects_stale_evaluation_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env.eval"
            env_file.write_text(
                "\n".join(
                    [
                        "DATABASE_URL=mysql+pymysql://infobank:pw@127.0.0.1:3307/infobank_eval",
                        "CHROMA_PERSIST_DIR=backend_python/chroma_eval",
                    ]
                ),
                encoding="utf-8",
            )
            with mock.patch("evaluation.run_d1_d8_pilot.tcp_reachable", return_value=True):
                with mock.patch("evaluation.run_d1_d8_pilot.check_clean_state", side_effect=CleanStateError("contaminated")):
                    with self.assertRaises(CleanStateError):
                        run_preflight(
                            env_file=env_file,
                            document_fixture=DEFAULT_DOCUMENT_FIXTURE,
                            evidence_benchmark=DEFAULT_EVIDENCE_BENCHMARK,
                            require_openai_key=False,
                        )

    def test_sanitize_preserves_usage_token_counts(self) -> None:
        payload = sanitize({"api_key": "secret", "input_tokens": 11, "output_tokens": 7, "total_tokens": 18})
        self.assertEqual(payload["api_key"], "<redacted>")
        self.assertEqual(payload["input_tokens"], 11)
        self.assertEqual(payload["output_tokens"], 7)
        self.assertEqual(payload["total_tokens"], 18)


if __name__ == "__main__":
    unittest.main()
