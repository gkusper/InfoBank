#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.fixture_schema import load_fixture
from evaluation.load_fixtures import case_to_harness_inputs
from evaluation.run_case import run_case
from evaluation.schemas import GenerationConfig, GenerationOutput


class SmokeGenerator:
    def generate(self, system_prompt: str, user_prompt: str, config: GenerationConfig) -> GenerationOutput:
        return GenerationOutput(
            answer="SMOKE",
            api_usage={
                "embedding_calls": 0,
                "generation_calls": 1,
                "keyword_routing_calls": 0,
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
                "errors": [],
                "retries": 0,
            },
        )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a deterministic D1-D8 benchmark smoke test without external APIs.")
    parser.add_argument("--document-fixture", default="evaluation/fixtures/document_rag_v2.yaml")
    parser.add_argument("--evidence-benchmark", default="data/benchmarks/evidence_unit_v1")
    args = parser.parse_args()

    fixture = load_fixture(args.document_fixture)
    representatives = {
        "D1": "FULL_01",
        "D2": "METADATA_01",
        "D3": "AGG_SAFE_01",
        "D4": "DENY_01",
        "D5_mixed": "MIXED_PRIMARY_01",
        "D5_contextual_only": "CONTEXT_ONLY_01",
    }
    config = GenerationConfig("mock-generator", "mock-embedding", temperature=0.0)
    document_results = {}
    for label, case_id in representatives.items():
        retrieval, policy_context = case_to_harness_inputs(fixture, case_id)
        result = run_case(
            run_id="d1_d8_smoke",
            case_id=case_id,
            user_id="eval_reader",
            retrieval=retrieval,
            generation_config=config,
            generator=SmokeGenerator(),
            modes="standard",
            policy_context=policy_context,
        )
        document_results[label] = {"case_id": case_id, "records": len(result)}

    root = Path(args.evidence_benchmark)
    cases = {row["case_id"]: row for row in read_jsonl(root / "cases.jsonl")}
    gold = {row["case_id"]: row for row in read_jsonl(root / "gold.jsonl")}
    evidence_results = {}
    for label, case_id in {"D6": "D6_001", "D7": "D7_001", "D8": "D8_001"}.items():
        case = cases[case_id]
        gold_row = gold[case_id]
        evidence_results[label] = {
            "case_id": case_id,
            "evidence_units": len(case["evidence_units"]),
            "expected_status": gold_row["expected_status"],
            "expected_presence": gold_row["expected_presence"],
        }

    print("SMOKE: PASS")
    print(json.dumps({"document_rag": document_results, "evidence_unit": evidence_results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
