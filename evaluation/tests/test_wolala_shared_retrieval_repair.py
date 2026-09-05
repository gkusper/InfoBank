from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from evaluation.wolala2026.common import read_json, read_jsonl
from evaluation.wolala2026.pilot_data import DEV_DATASET, HELDOUT_DATASET_V2
from evaluation.wolala2026.real_api import EmbeddingCallResult, ProviderCallResult
from evaluation.wolala2026.run_pilot import run_pilot


ROOT = Path(__file__).resolve().parents[1] / "wolala2026"
DEV_CASES = read_jsonl(ROOT / "data" / DEV_DATASET / "cases.jsonl")
ALL_MODES = ["standard_rag", "prompt_only_control", "cfaf_pipeline"]


class RecordingProvider:
    provider_name = "fake-openai"
    embedding_model = "text-embedding-3-small"
    generator_model = "gpt-4o-mini"
    is_mock = True

    def __init__(self, *, fail_first_embedding_retryably: bool = False) -> None:
        self.embedding_queries: list[str] = []
        self.generation_requests: list[dict[str, Any]] = []
        self.fail_first_embedding_retryably = fail_first_embedding_retryably

    def embed_query(self, query: str) -> EmbeddingCallResult:
        self.embedding_queries.append(query)
        if self.fail_first_embedding_retryably and len(self.embedding_queries) == 1:
            raise RuntimeError("OpenAI API HTTP 500: synthetic retryable embedding failure")
        return EmbeddingCallResult(
            model=self.embedding_model,
            latency_ms=7.5,
            input_tokens=len(query.split()),
            response_id=f"fake-embedding-{len(self.embedding_queries)}",
        )

    def generate_json(self, *, mode_name: str, system_prompt: str, user_payload: dict[str, Any], max_output_tokens: int) -> ProviderCallResult:
        self.generation_requests.append({"mode_name": mode_name, "payload": user_payload})
        if mode_name == "cfaf_pipeline":
            contract = user_payload["response_contract_and_permitted_evidence"][0]["response_contract"]
            if contract["mode"] == "FULL":
                answer = " ".join(claim.get("answer", "") for claim in contract.get("allowed_claims", [])).strip()
            else:
                answer = contract["public_reason_text"]
            payload = {
                "answer": answer,
                "top_level_mode": contract["mode"],
                "fulfilment_status": contract["fulfilment_status"],
                "realization": contract["cfaf_realization"],
                "public_reason_class": contract["public_reason_class"],
                "next_step_codes": contract["allowed_next_steps"],
            }
        else:
            payload = {
                "answer": "Development baseline response.",
                "top_level_mode": "FULL",
                "fulfilment_status": "FULL",
                "realization": None,
                "public_reason_class": None,
                "next_step_codes": [],
            }
        return ProviderCallResult(
            content=json.dumps(payload),
            model=self.generator_model,
            input_tokens=17,
            output_tokens=11,
            latency_ms=3.0,
            response_id=f"fake-generation-{len(self.generation_requests)}",
        )


class WolalaSharedRetrievalRepairTests(unittest.TestCase):
    def test_t1_retrieval_once_per_case_across_repetitions(self) -> None:
        provider = RecordingProvider()
        manifest, output = self._run_fake(case_count=5, repetitions=3, modes=ALL_MODES, provider=provider)
        raw = read_jsonl(output / "raw_results.jsonl")
        shared = read_json(output / "shared_retrieval_verification.json")
        self.assertEqual(len(raw), 45)
        self.assertEqual(manifest["planned_logical_embedding_requests"], 5)
        self.assertEqual(manifest["successful_logical_embedding_requests"], 5)
        self.assertEqual(manifest["actual_embedding_attempts"], 5)
        self.assertEqual(manifest["retrieval_snapshot_count"], 5)
        self.assertEqual(manifest["snapshot_reuse_count"], 45)
        self.assertTrue(shared["all_cases_share_retrieval"])
        self.assertTrue(all(row["record_count"] == 9 for row in shared["records"]))

    def test_t2_snapshot_hash_stability(self) -> None:
        provider = RecordingProvider()
        _, output = self._run_fake(case_count=5, repetitions=3, modes=ALL_MODES, provider=provider)
        raw = read_jsonl(output / "raw_results.jsonl")
        snapshots = {row["case_id"]: row for row in read_jsonl(output / "retrieval_snapshots.jsonl")}
        for case_id in {row["case_id"] for row in raw}:
            case_rows = [row for row in raw if row["case_id"] == case_id]
            self.assertEqual({row["retrieval_snapshot_hash"] for row in case_rows}, {snapshots[case_id]["snapshot_hash"]})
            self.assertEqual(len({tuple(snapshots[case_id]["candidate_ids"]) for _ in case_rows}), 1)
            self.assertEqual(len({tuple(snapshots[case_id]["candidate_order"]) for _ in case_rows}), 1)
            self.assertEqual(len({tuple(snapshots[case_id]["retrieval_scores"]) for _ in case_rows}), 1)

    def test_t3_repetition_count_does_not_affect_embedding_count(self) -> None:
        for repetitions in [1, 2, 3, 5]:
            provider = RecordingProvider()
            manifest, _ = self._run_fake(case_count=5, repetitions=repetitions, modes=ALL_MODES, provider=provider)
            self.assertEqual(manifest["actual_embedding_attempts"], 5)
            self.assertEqual(len(provider.embedding_queries), 5)
            self.assertEqual(manifest["result_record_count"], 5 * len(ALL_MODES) * repetitions)

    def test_t4_mode_count_does_not_affect_embedding_count(self) -> None:
        mode_sets = [ALL_MODES[:1], ALL_MODES[:2], ALL_MODES]
        for modes in mode_sets:
            provider = RecordingProvider()
            manifest, _ = self._run_fake(case_count=5, repetitions=3, modes=modes, provider=provider)
            self.assertEqual(manifest["actual_embedding_attempts"], 5)
            self.assertEqual(len(provider.embedding_queries), 5)
            self.assertEqual(manifest["result_record_count"], 5 * len(modes) * 3)

    def test_t5_exact_embedding_cap_succeeds(self) -> None:
        provider = RecordingProvider()
        manifest, _ = self._run_fake(case_count=10, repetitions=1, modes=ALL_MODES, provider=provider, max_embedding_calls=10)
        self.assertEqual(manifest["completion_status"], "COMPLETED")
        self.assertEqual(manifest["actual_embedding_attempts"], 10)

    def test_t6_insufficient_embedding_cap_fails_before_provider_use(self) -> None:
        provider = RecordingProvider()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "Embedding call cap exceeded"):
                run_pilot(
                    dataset=DEV_DATASET,
                    case_ids=[case["case_id"] for case in DEV_CASES[:10]],
                    modes=ALL_MODES,
                    repetitions=1,
                    output_dir=tmp,
                    max_mode_executions=30,
                    max_embedding_calls=9,
                    max_generation_calls=30,
                    max_total_external_calls=39,
                    allow_real_api=True,
                    provider=provider,
                )
            self.assertEqual(provider.embedding_queries, [])
            self.assertEqual(provider.generation_requests, [])
            self.assertFalse(Path(tmp).exists() and any(Path(tmp).iterdir()))

    def test_t7_retry_accounting(self) -> None:
        provider = RecordingProvider(fail_first_embedding_retryably=True)
        manifest, output = self._run_fake(
            case_count=1,
            repetitions=1,
            modes=["standard_rag"],
            provider=provider,
            max_embedding_calls=2,
            max_generation_calls=1,
            max_total_external_calls=3,
            max_total_retry_attempts=1,
            max_retries_per_logical_request=1,
        )
        accounting = read_json(output / "call_accounting_verification.json")
        self.assertEqual(manifest["successful_logical_embedding_requests"], 1)
        self.assertEqual(manifest["actual_embedding_attempts"], 2)
        self.assertEqual(manifest["embedding_retry_attempts"], 1)
        self.assertEqual(manifest["retrieval_snapshot_count"], 1)
        self.assertEqual(manifest["retry_count"], 1)
        self.assertEqual(accounting["retrieval_snapshot_count"], 1)

    def test_t8_existing_one_repetition_behavior_remains_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = run_pilot(
                dataset=DEV_DATASET,
                modes=ALL_MODES,
                repetitions=1,
                output_dir=tmp,
                max_mode_executions=30,
                max_embedding_calls=10,
                max_generation_calls=30,
                max_total_external_calls=40,
            )
            raw = read_jsonl(Path(tmp) / "raw_results.jsonl")
            self.assertEqual(manifest["completion_status"], "COMPLETED")
            self.assertEqual(len(raw), 30)
            self.assertTrue(all("retrieval_snapshot_hash" in row for row in raw))
            self.assertTrue(all("observed_top_level_mode" in row for row in raw))
            exposure = read_json(Path(tmp) / "generator_context_exposure_verification.json")
            self.assertTrue(exposure["all_cfaf_contexts_filtered"])

    def test_t9_retired_heldout_pilot_v2_is_blocked(self) -> None:
        provider = RecordingProvider()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "heldout_pilot_v2 is retired"):
                run_pilot(
                    dataset=HELDOUT_DATASET_V2,
                    modes=ALL_MODES,
                    repetitions=3,
                    output_dir=tmp,
                    max_mode_executions=360,
                    max_embedding_calls=60,
                    max_generation_calls=380,
                    max_total_external_calls=420,
                    allow_real_api=True,
                    allow_heldout=True,
                    provider=provider,
                    execution_spec=ROOT / "HELDOUT_EXECUTION_SPEC_v3.json",
                )
            self.assertEqual(provider.embedding_queries, [])
            self.assertEqual(provider.generation_requests, [])
            self.assertFalse(Path(tmp).exists() and any(Path(tmp).iterdir()))

    def test_t10_plan_only_and_runtime_accounting_agree(self) -> None:
        case_ids = [case["case_id"] for case in DEV_CASES[:5]]
        with tempfile.TemporaryDirectory() as plan_tmp, tempfile.TemporaryDirectory() as run_tmp:
            plan_manifest = run_pilot(
                dataset=DEV_DATASET,
                case_ids=case_ids,
                modes=ALL_MODES,
                repetitions=3,
                output_dir=plan_tmp,
                max_mode_executions=45,
                max_embedding_calls=5,
                max_generation_calls=45,
                max_total_external_calls=50,
                allow_real_api=True,
                provider=RecordingProvider(),
                plan_only=True,
            )
            run_manifest = run_pilot(
                dataset=DEV_DATASET,
                case_ids=case_ids,
                modes=ALL_MODES,
                repetitions=3,
                output_dir=run_tmp,
                max_mode_executions=45,
                max_embedding_calls=5,
                max_generation_calls=45,
                max_total_external_calls=50,
                allow_real_api=True,
                provider=RecordingProvider(),
            )
            plan = read_json(Path(plan_tmp) / "execution_plan.json")
            self.assertEqual(plan_manifest["completion_status"], "PLANNED")
            self.assertEqual(plan["planned_logical_embedding_requests"], run_manifest["successful_logical_embedding_requests"])
            self.assertEqual(run_manifest["successful_logical_embedding_requests"], run_manifest["retrieval_snapshot_count"])

    def test_t11_shared_retrieval_latency_is_reused(self) -> None:
        provider = RecordingProvider()
        _, output = self._run_fake(case_count=5, repetitions=3, modes=ALL_MODES, provider=provider)
        latency = read_json(output / "latency_verification.json")
        self.assertTrue(latency["shared_retrieval_latency_reused"])
        self.assertTrue(latency["no_second_retrieval_timing_event_per_case"])
        self.assertTrue(all(len(row["shared_retrieval_ms_values"]) == 1 for row in latency["records"]))

    def test_t12_no_heldout_execution_in_repair_tests(self) -> None:
        provider = RecordingProvider()
        _, output = self._run_fake(case_count=5, repetitions=3, modes=ALL_MODES, provider=provider)
        raw_ids = {row["case_id"] for row in read_jsonl(output / "raw_results.jsonl")}
        snapshot_ids = {row["case_id"] for row in read_jsonl(output / "retrieval_snapshots.jsonl")}
        self.assertTrue(all(case_id.startswith("DEV_") for case_id in raw_ids | snapshot_ids))
        self.assertFalse(any(case_id.startswith(("HELD_", "HELD2_", "HELD3_")) for case_id in raw_ids | snapshot_ids))

    def _run_fake(
        self,
        *,
        case_count: int,
        repetitions: int,
        modes: list[str],
        provider: RecordingProvider,
        max_embedding_calls: int | None = None,
        max_generation_calls: int | None = None,
        max_total_external_calls: int | None = None,
        max_total_retry_attempts: int = 0,
        max_retries_per_logical_request: int = 0,
    ) -> tuple[dict[str, Any], Path]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        output = Path(tmp.name)
        mode_executions = case_count * len(modes) * repetitions
        embedding_cap = max_embedding_calls if max_embedding_calls is not None else case_count
        generation_cap = max_generation_calls if max_generation_calls is not None else mode_executions
        total_cap = max_total_external_calls if max_total_external_calls is not None else embedding_cap + generation_cap
        manifest = run_pilot(
            dataset=DEV_DATASET,
            case_ids=[case["case_id"] for case in DEV_CASES[:case_count]],
            modes=modes,
            repetitions=repetitions,
            output_dir=output,
            max_mode_executions=mode_executions,
            max_embedding_calls=embedding_cap,
            max_generation_calls=generation_cap,
            max_total_external_calls=total_cap,
            max_total_retry_attempts=max_total_retry_attempts,
            max_retries_per_logical_request=max_retries_per_logical_request,
            allow_real_api=True,
            provider=provider,
        )
        return manifest, output


if __name__ == "__main__":
    unittest.main()
