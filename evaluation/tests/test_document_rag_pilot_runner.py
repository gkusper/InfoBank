from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from evaluation import run_document_rag_pilot as pilot
from evaluation.clean_state import CleanStateError


class DocumentRagPilotRunnerTests(unittest.TestCase):
    def test_a_default_case_selection(self) -> None:
        self.assertEqual(
            pilot.parse_case_ids(None),
            [
                "FULL_01",
                "METADATA_01",
                "DENY_01",
                "AGG_SAFE_01",
                "AGG_INDIVIDUAL_01",
                "MIXED_PRIMARY_01",
                "CONTEXT_ONLY_01",
            ],
        )

    def test_b_expected_result_count(self) -> None:
        self.assertEqual(pilot.expected_result_count(pilot.APPROVED_PILOT_CASE_IDS, 1), 21)

    def test_c_real_api_is_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(pilot, "OpenAIGenerator", side_effect=AssertionError("real generator used")):
                code = pilot.main(["--mock-generation", "--results-dir", tmpdir])
            self.assertEqual(code, 0)

    def test_d_missing_key_blocks_real_mode(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(pilot.PilotError) as raised:
                pilot.require_openai_key()
        self.assertEqual(str(raised.exception), "PILOT BLOCKED: OPENAI_API_KEY NOT CONFIGURED")

    def test_e_chroma_path_resolution_uses_backend_dir(self) -> None:
        env_file = pilot.BACKEND_DIR / ".env.eval"
        self.assertEqual(
            pilot.resolve_chroma_path("./chroma_eval", env_file),
            (pilot.BACKEND_DIR / "chroma_eval").resolve(),
        )
        self.assertEqual(
            pilot.resolve_chroma_path("backend_python/chroma_eval", env_file),
            (pilot.BACKEND_DIR / "chroma_eval").resolve(),
        )

    def test_f_wrong_database_refusal(self) -> None:
        with self.assertRaises(pilot.PilotError):
            pilot.validate_runtime_targets(
                database_url="mysql+pymysql://user@127.0.0.1:3307/infobank_db?charset=utf8mb4",
                chroma_path=(pilot.BACKEND_DIR / "chroma_eval").resolve(),
            )

    def test_g_contamination_refusal(self) -> None:
        config = pilot.PilotConfig(env_file=pilot.DEFAULT_ENV_FILE)
        with mock.patch.object(pilot, "configure_real_environment", return_value={"database_name": "infobank_eval", "chroma_persist_dir": str(pilot.EXPECTED_CHROMA_DIR)}):
            with mock.patch.object(pilot, "run_subprocess", return_value={"returncode": 0, "stdout": "", "stderr": ""}):
                with mock.patch.object(pilot.package_metadata, "version", return_value="4.1.3"):
                    with mock.patch.object(pilot, "is_tcp_reachable", return_value=True):
                        with mock.patch.object(pilot, "check_clean_state", side_effect=CleanStateError("contaminated")):
                            with self.assertRaises(pilot.PilotError) as raised:
                                pilot.run_preflight(config, require_key=False)
        self.assertEqual(str(raised.exception), "PILOT BLOCKED: EVALUATION STATE NOT CLEAN")

    def test_h_shared_retrieval_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = self._run_mock_pilot(tmpdir)
            records = self._read_jsonl(run_dir / "results.jsonl")
        for case_id in pilot.APPROVED_PILOT_CASE_IDS:
            case_records = [record for record in records if record["case_id"] == case_id]
            self.assertEqual(len(case_records), 3)
            baseline = case_records[0]
            for record in case_records[1:]:
                self.assertEqual(record["query_embedding_identifier"], baseline["query_embedding_identifier"])
                self.assertEqual(record["retrieved_chunk_ids"], baseline["retrieved_chunk_ids"])
                self.assertEqual(record["document_ids"], baseline["document_ids"])
                self.assertEqual(record["retrieval_rank"], baseline["retrieval_rank"])
                self.assertEqual(record["retrieval_distances"], baseline["retrieval_distances"])
                self.assertEqual(record["raw_retrieved_chunks"], baseline["raw_retrieved_chunks"])

    def test_i_artifact_creation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = self._run_mock_pilot(tmpdir)
            self.assertEqual(len(self._read_jsonl(run_dir / "results.jsonl")), 21)
            self.assertEqual(len(self._read_jsonl(run_dir / "shared_retrieval.jsonl")), 7)
            for name in [
                "run_manifest.json",
                "fixture_subset_manifest.json",
                "pilot_inspection.json",
            ]:
                self.assertTrue((run_dir / name).exists(), name)

    def test_j_failure_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            code = pilot.main(["--mock-generation", "--results-dir", tmpdir, "--mock-fail-stage", "indexing"])
            self.assertNotEqual(code, 0)
            run_dirs = sorted(Path(tmpdir).glob("pilot_*"))
            self.assertEqual(len(run_dirs), 1)
            failure = json.loads((run_dirs[0] / "pilot_failure.json").read_text(encoding="utf-8"))
            self.assertEqual(failure["classification"], "fixture loading")

    def test_k_secret_protection(self) -> None:
        secret = "unit-test-redaction-token-value"
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": secret}, clear=False):
                run_dir = self._run_mock_pilot(tmpdir)
                combined = "\n".join(path.read_text(encoding="utf-8") for path in run_dir.glob("*.json*"))
        self.assertNotIn(secret, combined)

    def test_l_production_ask_remains_without_mode_selector(self) -> None:
        source = (pilot.REPO_ROOT / "backend_python" / "routers" / "chat.py").read_text(encoding="utf-8")
        start = source.index("async def ask_infobank(")
        signature = source[start:source.index("):", start)]
        self.assertNotIn("mode", signature)

    def _run_mock_pilot(self, results_dir: str) -> Path:
        code = pilot.main(["--mock-generation", "--results-dir", results_dir])
        self.assertEqual(code, 0)
        run_dirs = sorted(Path(results_dir).glob("pilot_*"))
        self.assertEqual(len(run_dirs), 1)
        return run_dirs[0]

    def _read_jsonl(self, path: Path) -> list[dict]:
        with path.open("r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]


if __name__ == "__main__":
    unittest.main()
