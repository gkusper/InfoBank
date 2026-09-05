from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from evaluation.wolala2026.common import read_json
from evaluation.wolala2026.pilot_data import DEV_DATASET
from evaluation.wolala2026.real_api import EmbeddingCallResult, ProviderCallResult
from evaluation.wolala2026.run_pilot import run_pilot


class FakeRealApiProvider:
    provider_name = "fake-openai"
    embedding_model = "text-embedding-3-small"
    generator_model = "gpt-4o-mini"
    is_mock = True

    def embed_query(self, query: str) -> EmbeddingCallResult:
        return EmbeddingCallResult(model=self.embedding_model, latency_ms=1.0, input_tokens=len(query.split()), response_id="fake-embedding")

    def generate_json(self, *, mode_name: str, system_prompt: str, user_payload: dict[str, Any], max_output_tokens: int) -> ProviderCallResult:
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
            latency_ms=2.0,
            response_id=f"fake-{mode_name}",
        )


class WolalaRealApiPhase3Tests(unittest.TestCase):
    def test_plan_only_writes_exact_development_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = run_pilot(
                dataset=DEV_DATASET,
                modes=["standard_rag", "prompt_only_control", "cfaf_pipeline"],
                repetitions=1,
                output_dir=tmp,
                max_mode_executions=30,
                max_embedding_calls=10,
                max_generation_calls=30,
                max_total_external_calls=40,
                plan_only=True,
            )
            self.assertEqual(manifest["completion_status"], "PLANNED")
            plan = read_json(Path(tmp) / "execution_plan.json")
            self.assertEqual(plan["development_cases"], 10)
            self.assertEqual(plan["mode_count"], 3)
            self.assertEqual(plan["planned_mode_executions"], 30)
            self.assertEqual(plan["heldout_mode_executions"], 0)
            self.assertTrue(all(case_id.startswith("DEV_") for case_id in plan["case_ids"]))
            self.assertTrue(plan["retrieval_computed_once_per_case"])
            self.assertTrue(plan["retrieval_reused_across_modes"])

    def test_injected_real_api_provider_records_caps_and_verifications(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = run_pilot(
                dataset=DEV_DATASET,
                modes=["standard_rag", "prompt_only_control", "cfaf_pipeline"],
                repetitions=1,
                output_dir=tmp,
                max_mode_executions=30,
                max_embedding_calls=10,
                max_generation_calls=30,
                max_total_external_calls=40,
                allow_real_api=True,
                provider=FakeRealApiProvider(),
            )
            self.assertEqual(manifest["completion_status"], "COMPLETED")
            self.assertEqual(manifest["actual_embedding_calls"], 10)
            self.assertEqual(manifest["actual_generation_calls"], 30)
            self.assertEqual(manifest["actual_total_external_calls"], 40)
            self.assertTrue(manifest["real_api"])
            self.assertTrue(manifest["mock_or_stub_used"])
            shared = read_json(Path(tmp) / "shared_retrieval_verification.json")
            integrity = read_json(Path(tmp) / "adapter_integrity_verification.json")
            exposure = read_json(Path(tmp) / "generator_context_exposure_verification.json")
            self.assertTrue(shared["all_cases_share_retrieval"])
            self.assertTrue(integrity["baselines_free_of_gold_or_external_cfaf_labels"])
            self.assertTrue(integrity["cfaf_uses_filtered_pipeline_context"])
            self.assertEqual(exposure["generator_exposure_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
