from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .adapters import ALL_MODES
from .common import read_json, sha256_file, stable_hash, write_json
from .execution_spec import validate_execution_spec
from .pilot_data import DATA_DIR, HELDOUT_DATASET_V1, HELDOUT_DATASET_V2, HELDOUT_DATASET_V3, RETIRED_HELDOUT_DATASETS
from .run_pilot import run_pilot


PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[1]
PREHELDOUT_DIR = PACKAGE_DIR / "preheldout_v3_attempt1"
SPEC_PATH = PACKAGE_DIR / "HELDOUT_EXECUTION_SPEC_v4.json"
PROTOCOL_PATH = PACKAGE_DIR / "WOLALA2026_PILOT_PROTOCOL_v4.md"
PREAUDIT_PATH = PACKAGE_DIR / "FINAL_HELDOUT_V3_PREAUDIT.json"
RETIRED_REGISTRY_PATH = PACKAGE_DIR / "RETIRED_HELDOUT_DATASET_REGISTRY_v1.json"
FREEZE_MANIFEST_PATH = PACKAGE_DIR / "PRE_HELDOUT_V3_FREEZE_MANIFEST.json"
PLAN_REPORT_PATH = PREHELDOUT_DIR / "PLAN_VALIDATION_REPORT.md"
RUN_OUTPUT_DIR = PACKAGE_DIR / "heldout_run_real_api_v3_attempt1"
SHARED_RETRIEVAL_TAG = "wolala2026-shared-retrieval-fix-v1"
STARTING_SHARED_RETRIEVAL_COMMIT = "4989de65eea6390623e284e6919bcb4c460b74ac"
REMOTE_SHARED_RETRIEVAL_TAG_OBJECT = "4e807d68bf3bc74d20e54ef96f7f4602027ad800"


def prepare(test_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    dataset_manifest = read_json(DATA_DIR / HELDOUT_DATASET_V3 / "manifest.json")
    generation_manifest = read_json(DATA_DIR / HELDOUT_DATASET_V3 / "generation_manifest.json")
    overlap_audit = read_json(DATA_DIR / HELDOUT_DATASET_V3 / "OVERLAP_AUDIT.json")
    git_evidence = _git_evidence()
    preaudit = _preaudit(dataset_manifest, generation_manifest, overlap_audit, git_evidence)
    retired_registry = _retired_registry()
    write_json(PREAUDIT_PATH, preaudit)
    write_json(RETIRED_REGISTRY_PATH, retired_registry)

    first_checksums = _artifact_checksums(include_protocol_v4=False)
    PROTOCOL_PATH.write_text(_protocol_v4_text(dataset_manifest, first_checksums), encoding="utf-8")
    checksums = _artifact_checksums(include_protocol_v4=True)
    spec = _execution_spec_v4(dataset_manifest, checksums)
    write_json(SPEC_PATH, spec)
    validate_execution_spec(
        spec,
        cases=_read_cases(),
        modes=ALL_MODES,
        repetitions=3,
        max_mode_executions=360,
        max_embedding_calls=60,
        max_generation_calls=380,
        max_total_external_calls=420,
        plan_only=True,
    )
    plan_manifest = run_pilot(
        dataset=HELDOUT_DATASET_V3,
        modes=ALL_MODES,
        repetitions=3,
        output_dir=PREHELDOUT_DIR,
        max_mode_executions=360,
        max_embedding_calls=60,
        max_generation_calls=380,
        max_total_external_calls=420,
        plan_only=True,
        execution_spec=SPEC_PATH,
    )
    plan = read_json(PREHELDOUT_DIR / "execution_plan.json")
    PLAN_REPORT_PATH.write_text(_plan_report(plan, plan_manifest, spec), encoding="utf-8")
    freeze_manifest = _freeze_manifest(dataset_manifest, generation_manifest, preaudit, retired_registry, spec, plan, git_evidence, test_summary)
    write_json(FREEZE_MANIFEST_PATH, freeze_manifest)
    return freeze_manifest


def _artifact_checksums(*, include_protocol_v4: bool) -> dict[str, str]:
    checksums = {
        "protocol_v1": sha256_file(PACKAGE_DIR / "WOLALA2026_PILOT_PROTOCOL_v1.md"),
        "protocol_v2": sha256_file(PACKAGE_DIR / "WOLALA2026_PILOT_PROTOCOL_v2.md"),
        "protocol_v3": sha256_file(PACKAGE_DIR / "WOLALA2026_PILOT_PROTOCOL_v3.md"),
        "prompt_only_prompt": sha256_file(PACKAGE_DIR / "prompts" / "prompt_only_v1.txt"),
        "cfaf_generator_prompt": sha256_file(PACKAGE_DIR / "prompts" / "cfaf_generator_v1.txt"),
        "provider_wrapper": sha256_file(PACKAGE_DIR / "real_api.py"),
        "retry_policy_module": sha256_file(PACKAGE_DIR / "retry_policy.py"),
        "adapters": sha256_file(PACKAGE_DIR / "adapters.py"),
        "parser": sha256_file(PACKAGE_DIR / "adapters.py"),
        "runner": sha256_file(PACKAGE_DIR / "run_pilot.py"),
        "retrieval": sha256_file(PACKAGE_DIR / "retrieval.py"),
        "scorer": sha256_file(PACKAGE_DIR / "score_pilot.py"),
        "statistical_analysis_module": sha256_file(PACKAGE_DIR / "analyze_heldout.py"),
        "statistical_plan": sha256_file(PACKAGE_DIR / "WOLALA2026_STATISTICAL_ANALYSIS_PLAN_v1.md"),
        "latency_analysis_module": sha256_file(PACKAGE_DIR / "latency_analysis.py"),
        "latency_definition": sha256_file(PACKAGE_DIR / "WOLALA2026_LATENCY_DEFINITION_v1.md"),
        "execution_spec_module": sha256_file(PACKAGE_DIR / "execution_spec.py"),
        "pilot_data_module": sha256_file(PACKAGE_DIR / "pilot_data.py"),
        "heldout_v3_generator": sha256_file(PACKAGE_DIR / "generate_heldout_v3.py"),
        "heldout_v3_cases": sha256_file(DATA_DIR / HELDOUT_DATASET_V3 / "cases.jsonl"),
        "heldout_v3_gold": sha256_file(DATA_DIR / HELDOUT_DATASET_V3 / "gold.jsonl"),
        "heldout_v3_generation_manifest": sha256_file(DATA_DIR / HELDOUT_DATASET_V3 / "generation_manifest.json"),
        "heldout_v3_pair_design_manifest": sha256_file(DATA_DIR / HELDOUT_DATASET_V3 / "pair_design_manifest.json"),
        "heldout_v3_overlap_audit": sha256_file(DATA_DIR / HELDOUT_DATASET_V3 / "OVERLAP_AUDIT.json"),
        "heldout_dataset": read_json(DATA_DIR / HELDOUT_DATASET_V3 / "manifest.json")["dataset_checksum"],
    }
    if include_protocol_v4:
        checksums["protocol_v4"] = sha256_file(PROTOCOL_PATH)
    return checksums


def _execution_spec_v4(dataset_manifest: dict[str, Any], checksums: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": "wolala-heldout-execution-spec-v4",
        "protocol": "WOLALA2026_PILOT_PROTOCOL_v4.md",
        "dataset": HELDOUT_DATASET_V3,
        "case_id_prefix": "HELD3_",
        "pair_id_prefix": "H3PAIR_",
        "cases": 40,
        "provider": "openai",
        "provider_implementation": "direct_https_openai_provider_wrapper",
        "embedding_model": "text-embedding-3-small",
        "generator_model": "gpt-4o-mini",
        "temperature": 0,
        "top_k": 4,
        "max_output_tokens": 160,
        "modes": ALL_MODES,
        "repetitions": 3,
        "planned_mode_executions": 360,
        "planned_unique_embedding_requests": 40,
        "planned_generation_requests_maximum": 360,
        "planned_external_requests_without_retries_maximum": 400,
        "max_mode_executions": 360,
        "max_embedding_calls": 60,
        "max_generation_calls": 380,
        "max_total_external_calls": 420,
        "max_total_retry_attempts": 20,
        "max_retries_per_logical_request": 1,
        "external_warmup_calls": 0,
        "allow_real_api_required": True,
        "allow_heldout_required": True,
        "run_attempt": 1,
        "output_dir": "evaluation/wolala2026/heldout_run_real_api_v3_attempt1",
        "authorization_path": "evaluation/wolala2026/preheldout_v3_attempt1/HELDOUT_RUN_AUTHORIZATION.json",
        "dataset_checksum": dataset_manifest["dataset_checksum"],
        "checksums": checksums,
    }


def _protocol_v4_text(dataset_manifest: dict[str, Any], checksums: dict[str, str]) -> str:
    return f"""# WoLaLa 2026 Pilot Protocol v4

## Status

This protocol is frozen before collecting any `heldout_pilot_v3` model outputs.
It supersedes `WOLALA2026_PILOT_PROTOCOL_v3.md` only for the final CFAF-focused
WoLaLa held-out experiment after the shared-retrieval repair. Protocol v1, v2,
and v3 remain historical artifacts.

Protocol v4 preserves the research questions, compared modes, prompts, parser,
scorer, statistical semantics, latency semantics, retry policy, invalid-run
policy, and no-result-driven-rerun rule from Protocol v3. It changes only the
held-out dataset, case prefix, dataset/generation manifests, and execution
specification needed for `heldout_pilot_v3`.

This experiment validates the evidential and governance instantiation of CFAF.
It does not evaluate the complete InfoBank, full action-list reconstruction,
general safety triggers, prompt-injection resistance, production security, or
cross-domain generality.

## Historical Attempt Record

`heldout_pilot_v1` is retired after the pre-execution implementation guard
failure. No model saw `heldout_pilot_v1`.

`heldout_pilot_v2` attempt 1 is preserved as an invalidated scientific-integrity
failure because the runner used one retrieval embedding per case per repetition
instead of one shared retrieval per unique case. It is not a confirmatory result
and must not be rerun or reused as publication evidence.

## Research Questions

RQ1, external enforcement: does the explicit CFAF pipeline reduce prohibited
answering and leakage relative to Standard RAG and a prompt-only abstention
control?

RQ2, request relativity: does the system select `FULL` or `CFAF` according to
the requested output, not only according to source type?

RQ3, non-leaking explanations: does public-trace filtering prevent protected
content and protected source-existence disclosure?

RQ4, runtime overhead: what diagnostic user-visible latency and model-call
overhead does the explicit CFAF pipeline add relative to the two baselines?

## Compared Configurations

1. `standard_rag`: raw retrieved synthetic candidates and user query only.
2. `prompt_only_control`: same raw retrieved candidates plus the frozen
   prompt-only abstain/restrict instruction.
3. `cfaf_pipeline`: explicit eight-stage CFAF pipeline with external policy,
   evidence, permitted-output, trace, and validation gates.

All modes consume one shared retrieval snapshot per unique held-out case. That
snapshot is reused across all three modes and all three repetitions.

## Frozen Dataset And Prompts

- Held-out dataset: `heldout_pilot_v3`
- Held-out case ID prefix: `HELD3_`
- Held-out pair ID prefix: `H3PAIR_`
- Held-out cases: `40`
- Matched pairs: `20`
- Scenario families: `P1`, `P2`, `P3`, `P4`, `P5`
- Fixed generation seed: `{dataset_manifest['fixed_seed']}`
- Held-out dataset checksum: `{dataset_manifest['dataset_checksum']}`
- Runtime case file checksum: `{checksums['heldout_v3_cases']}`
- Gold scorer-only file checksum: `{checksums['heldout_v3_gold']}`
- Generation manifest checksum: `{checksums['heldout_v3_generation_manifest']}`
- Pair-design manifest checksum: `{checksums['heldout_v3_pair_design_manifest']}`
- Overlap audit checksum: `{checksums['heldout_v3_overlap_audit']}`
- Protocol v1 checksum: `{checksums['protocol_v1']}`
- Protocol v2 checksum: `{checksums['protocol_v2']}`
- Protocol v3 checksum: `{checksums['protocol_v3']}`
- Prompt-only prompt checksum: `{checksums['prompt_only_prompt']}`
- CFAF generator prompt checksum: `{checksums['cfaf_generator_prompt']}`

`cases.jsonl` is runtime-visible only. `gold.jsonl` is scorer-only and is merged
only after raw run outputs have been frozen. The generator-visible gold-hint
scanner count is `0`.

Do not modify `heldout_pilot_v3`, `prompt_only_v1.txt`,
`cfaf_generator_v1.txt`, Protocol v1, v2, or v3 for this final held-out run.

## Frozen Provider And Model Configuration

- Provider: `openai`
- Provider implementation: repository direct HTTPS OpenAI provider wrapper
- Embedding model: `text-embedding-3-small`
- Generator model: `gpt-4o-mini`
- Temperature: `0`
- Top-k retrieval: `4`
- Maximum output tokens: `160`

No model or provider replacement is permitted.

Frozen implementation checksums:

- Provider wrapper `real_api.py`: `{checksums['provider_wrapper']}`
- Adapters and parser `adapters.py`: `{checksums['adapters']}`
- Runner `run_pilot.py`: `{checksums['runner']}`
- Retrieval `retrieval.py`: `{checksums['retrieval']}`
- Scorer `score_pilot.py`: `{checksums['scorer']}`
- Execution-spec validator `execution_spec.py`: `{checksums['execution_spec_module']}`

## Frozen Execution Counts

The held-out experiment has 40 cases, 3 modes, and 3 measured repetitions per
case and mode:

- `planned_mode_executions = 360`
- `planned_unique_embedding_requests = 40`
- `planned_generation_requests_maximum = 360`
- `planned_external_requests_without_retries_maximum = 400`

Retrieval and query embedding are shared once per unique case and reused across
all modes and repetitions.

## Frozen Hard Caps

- `max_mode_executions = 360`
- `max_embedding_calls = 60`
- `max_generation_calls = 380`
- `max_total_external_calls = 420`
- `max_total_retry_attempts = 20`
- `max_retries_per_logical_request = 1`
- `external_warmup_calls = 0`

Every retry counts as an external call. Caps must not be increased
automatically.

## Warm-Up And Retry Policy

No unmeasured provider warm-up request is permitted. Every embedding and
generation call must be recorded, count against the call caps, appear in the
run manifest, and contribute to documented latency records.

Retry behavior is inherited unchanged from Protocol v3 and implemented by
`retry_policy.py`, checksum `{checksums['retry_policy_module']}`.

## Invalid-Run And Rerun Policy

Wrong answers, false CFAF, refusals, over-refusals, leakage, poor latency, poor
baseline performance, poor CFAF performance, and unfavorable statistical
results are valid empirical outcomes and must not trigger invalidation.

`INVALIDATED_SCIENTIFIC_INTEGRITY_FAILURE` must be assigned for checksum drift,
wrong model or provider, wrong prompt, wrong dataset, gold-label contamination,
baseline receipt of CFAF decision labels, shared-retrieval mismatch, scorer or
parser defect affecting a primary metric, manifest defect affecting auditability,
incorrect case/mode/repetition coverage, held-out data corruption,
cap-enforcement defect, or non-frozen code used for execution.

No rerun is permitted because results are unfavorable.

## Primary Sample Units And Metrics

Primary sample units and metric denominators are inherited unchanged from
Protocol v3. Use unique held-out cases for primary inferential metrics, matched
P5 pairs for source-existence leakage, and case-mode medians across repetitions
for latency.

## Statistical Analysis Plan

Protocol v4 incorporates:

- File: `WOLALA2026_STATISTICAL_ANALYSIS_PLAN_v1.md`
- Checksum: `{checksums['statistical_plan']}`
- Implementation: `analyze_heldout.py`
- Implementation checksum: `{checksums['statistical_analysis_module']}`

Use `alpha = 0.05`, two-sided tests, bootstrap seed `20261012`, and 10,000
bootstrap samples. Apply one Holm correction family across the four primary
tests.

## Latency Definition

Protocol v4 incorporates:

- File: `WOLALA2026_LATENCY_DEFINITION_v1.md`
- Checksum: `{checksums['latency_definition']}`
- Implementation: `latency_analysis.py`
- Implementation checksum: `{checksums['latency_analysis_module']}`

For every case, mode, and repetition:
`user_visible_end_to_end_ms = shared_retrieval_ms + mode_processing_ms`.

## Machine-Readable Execution Specification

The machine-readable Protocol v4 execution specification is
`HELDOUT_EXECUTION_SPEC_v4.json`. The runner's plan-only path must load and
validate it before any later held-out execution.

Plan-only validation may read held-out metadata, schema, case IDs, and
checksums, but it must perform no retrieval, embedding, adapter execution,
generation, or model-output scoring. It must not require an API key.

Actual held-out execution requires `--allow-real-api`, `--allow-heldout`, and
`--execution-spec HELDOUT_EXECUTION_SPEC_v4.json`; the output directory must be
empty; a matching authorization artifact must exist; and all call caps must
validate before provider initialization.

The execution-spec file checksum is recorded in
`PRE_HELDOUT_V3_FREEZE_MANIFEST.json` to avoid a circular checksum dependency
between this protocol file and the machine-readable spec.

## Held-Out Authorization And Execution Lock

No held-out model output may be generated before the Protocol v4 freeze commit
and tag have been pushed. A later authorization commit must record
`AUTHORIZED_NOT_STARTED` for `heldout_pilot_v3` attempt 1 before execution.

No full D1-D8 benchmark run is part of this protocol.

## Protocol v4 Change Log From Protocol v3

- Replaces retired `heldout_pilot_v2` with `heldout_pilot_v3`.
- Replaces case prefix `HELD2_` with `HELD3_`.
- Uses pair prefix `H3PAIR_`.
- Physically separates runtime cases from scorer-only gold labels.
- Adds deterministic generation, pair-design, overlap, and gold-hint audit
  manifests for `heldout_pilot_v3`.
- Uses `HELDOUT_EXECUTION_SPEC_v4.json`.
- Preserves the shared-retrieval repair and requires tag
  `wolala2026-shared-retrieval-fix-v1` as an ancestor of the freeze state.
"""


def _preaudit(dataset_manifest: dict[str, Any], generation_manifest: dict[str, Any], overlap_audit: dict[str, Any], git_evidence: dict[str, Any]) -> dict[str, Any]:
    output_absent_or_empty = (not RUN_OUTPUT_DIR.exists()) or not any(RUN_OUTPUT_DIR.iterdir())
    checks = {
        "remote_branch_wolala2026_verified": git_evidence["remote_branch_sha"] == STARTING_SHARED_RETRIEVAL_COMMIT,
        "remote_shared_retrieval_tag_exists": git_evidence["remote_tag_object"] == REMOTE_SHARED_RETRIEVAL_TAG_OBJECT,
        "remote_shared_retrieval_tag_peeled_to_repair_commit": git_evidence["remote_tag_peeled"] == STARTING_SHARED_RETRIEVAL_COMMIT,
        "local_shared_retrieval_tag_ancestor_of_head": git_evidence["local_tag_is_ancestor_of_head"],
        "heldout_v3_dataset_exists": True,
        "heldout_v3_case_count_is_40": dataset_manifest["case_count"] == 40,
        "heldout_v3_pair_count_is_20": dataset_manifest["pair_count"] == 20,
        "heldout_v3_family_counts_are_balanced": dataset_manifest["families"] == {"P1": 8, "P2": 8, "P3": 8, "P4": 8, "P5": 8},
        "runtime_cases_and_gold_are_separate": dataset_manifest["runtime_gold_separation"]["runtime_cases_contain_gold_fields"] is False,
        "generator_visible_gold_hint_count_is_zero": dataset_manifest["generator_visible_gold_hint_count"] == 0,
        "overlap_audit_all_required_sets_empty": overlap_audit["all_required_overlap_sets_empty"] is True,
        "deterministic_generation_no_external_api_calls": generation_manifest["external_api_calls"] == 0 and generation_manifest["llm_generation_used"] is False,
        "retired_v1_and_v2_are_execution_blocked": HELDOUT_DATASET_V1 in RETIRED_HELDOUT_DATASETS and HELDOUT_DATASET_V2 in RETIRED_HELDOUT_DATASETS,
        "heldout_v3_real_api_output_dir_absent_or_empty": output_absent_or_empty,
    }
    return {
        "schema_version": "wolala-final-heldout-v3-preaudit-v1",
        "audited_branch": "wolala2026",
        "starting_commit": STARTING_SHARED_RETRIEVAL_COMMIT,
        "shared_retrieval_repair_tag": SHARED_RETRIEVAL_TAG,
        "git_evidence": git_evidence,
        "dataset": {
            "dataset_name": HELDOUT_DATASET_V3,
            "dataset_checksum": dataset_manifest["dataset_checksum"],
            "case_count": dataset_manifest["case_count"],
            "pair_count": dataset_manifest["pair_count"],
            "fixed_seed": dataset_manifest["fixed_seed"],
            "case_prefix": dataset_manifest["case_id_prefix"],
            "pair_prefix": dataset_manifest["pair_id_prefix"],
        },
        "checks": checks,
        "all_booleans_true": all(checks.values()),
        "audit_passed": all(checks.values()),
        "heldout_model_outputs_generated_for_v3": 0,
        "external_api_calls_in_preaudit": 0,
    }


def _retired_registry() -> dict[str, Any]:
    v2_audit = read_json(PACKAGE_DIR / "HELDOUT_V2_ATTEMPT1_FAILED_RUN_AUDIT_v1.json")
    return {
        "schema_version": "wolala-retired-heldout-dataset-registry-v1",
        "active_heldout_dataset": HELDOUT_DATASET_V3,
        "registry_status": "FROZEN_FOR_AUDIT",
        "datasets": [
            {
                "dataset": HELDOUT_DATASET_V1,
                "status": RETIRED_HELDOUT_DATASETS[HELDOUT_DATASET_V1],
                "execution_permitted": False,
                "model_saw_dataset": False,
                "retirement_artifact": "evaluation/wolala2026/HELDOUT_PILOT_V1_RETIREMENT_RECORD.md",
            },
            {
                "dataset": HELDOUT_DATASET_V2,
                "status": RETIRED_HELDOUT_DATASETS[HELDOUT_DATASET_V2],
                "execution_permitted": False,
                "model_saw_dataset": True,
                "valid_for_manuscript": False,
                "post_run_invalidation_class": v2_audit["attempt"]["post_run_invalidation_class"],
                "failure_root_cause": v2_audit["failure"]["root_cause"],
                "attempt1_run_id": v2_audit["attempt"]["run_id"],
                "run_manifest_checksum": v2_audit["artifact_checksums_sha256"]["run_manifest.json"],
                "raw_results_checksum": v2_audit["artifact_checksums_sha256"]["raw_results.jsonl"],
                "shared_retrieval_snapshot_checksum": v2_audit["artifact_checksums_sha256"]["shared_retrieval_snapshots.jsonl"],
                "retirement_artifact": "evaluation/wolala2026/HELDOUT_PILOT_V2_RETIREMENT_RECORD.md",
            },
        ],
        "retired_datasets_execution_blocked_in_code": True,
        "no_future_execution_allowed_for_v1_or_v2": True,
    }


def _plan_report(plan: dict[str, Any], plan_manifest: dict[str, Any], spec: dict[str, Any]) -> str:
    return f"""# Held-Out v3 Attempt 1 Plan Validation

Status: PASS.

- Dataset: `{plan['dataset']}`
- Protocol: `{plan['protocol']}`
- Execution spec: `HELDOUT_EXECUTION_SPEC_v4.json`
- Planned mode executions: `{plan['planned_mode_executions']}`
- Planned unique embedding requests: `{plan['planned_unique_embedding_requests']}`
- Planned generation requests maximum: `{plan['planned_generation_requests_maximum']}`
- Planned external requests without retries: `{plan['planned_external_requests_without_retries_maximum']}`
- Hard total external cap: `{plan['hard_total_external_cap']}`
- Retry budget: `{plan['max_total_retry_attempts']}`
- External warmup calls: `{plan['external_warmup_calls']}`
- Plan-only external API calls: `{plan['external_api_calls_in_plan_only']}`
- Held-out model execution count: `{plan['heldout_model_execution_count']}`
- Held-out embedding calls: `{plan['heldout_embedding_calls']}`
- Held-out generation calls: `{plan['heldout_generation_calls']}`

The plan-only command created only `execution_plan.json`. It performed no
retrieval, embedding, adapter execution, generation, model-output scoring, or
real-API provider initialization.

Runner return summary:

```json
{json.dumps(plan_manifest, ensure_ascii=True, indent=2, sort_keys=True)}
```

Spec validation returned:

```json
{json.dumps(validate_execution_spec(spec, cases=_read_cases(), modes=ALL_MODES, repetitions=3, max_mode_executions=360, max_embedding_calls=60, max_generation_calls=380, max_total_external_calls=420, plan_only=True), ensure_ascii=True, indent=2, sort_keys=True)}
```
"""


def _freeze_manifest(
    dataset_manifest: dict[str, Any],
    generation_manifest: dict[str, Any],
    preaudit: dict[str, Any],
    retired_registry: dict[str, Any],
    spec: dict[str, Any],
    plan: dict[str, Any],
    git_evidence: dict[str, Any],
    test_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    checksums = dict(spec["checksums"])
    checksums.update(
        {
            "protocol_v4": sha256_file(PROTOCOL_PATH),
            "execution_spec_v4": sha256_file(SPEC_PATH),
            "final_heldout_v3_preaudit": sha256_file(PREAUDIT_PATH),
            "retired_heldout_dataset_registry": sha256_file(RETIRED_REGISTRY_PATH),
            "execution_plan_v3_attempt1": sha256_file(PREHELDOUT_DIR / "execution_plan.json"),
            "plan_validation_report_v3_attempt1": sha256_file(PLAN_REPORT_PATH),
        }
    )
    return {
        "schema_version": "wolala-pre-heldout-v3-freeze-manifest-v1",
        "branch": "wolala2026",
        "starting_commit": STARTING_SHARED_RETRIEVAL_COMMIT,
        "freeze_commit_placeholder": "TO_BE_FILLED_AFTER_COMMIT",
        "shared_retrieval_repair": git_evidence,
        "dataset": {
            "dataset_name": HELDOUT_DATASET_V3,
            "dataset_checksum": dataset_manifest["dataset_checksum"],
            "case_count": dataset_manifest["case_count"],
            "pair_count": dataset_manifest["pair_count"],
            "case_prefix": dataset_manifest["case_id_prefix"],
            "pair_prefix": dataset_manifest["pair_id_prefix"],
            "fixed_seed": dataset_manifest["fixed_seed"],
            "generator_visible_gold_hint_count": dataset_manifest["generator_visible_gold_hint_count"],
            "external_api_calls_in_generation": generation_manifest["external_api_calls"],
        },
        "execution_caps": {
            "repetitions": 3,
            "planned_mode_executions": spec["planned_mode_executions"],
            "planned_unique_embedding_requests": spec["planned_unique_embedding_requests"],
            "planned_generation_requests_maximum": spec["planned_generation_requests_maximum"],
            "planned_external_requests_without_retries_maximum": spec["planned_external_requests_without_retries_maximum"],
            "max_mode_executions": spec["max_mode_executions"],
            "max_embedding_calls": spec["max_embedding_calls"],
            "max_generation_calls": spec["max_generation_calls"],
            "max_total_external_calls": spec["max_total_external_calls"],
            "max_total_retry_attempts": spec["max_total_retry_attempts"],
            "max_retries_per_logical_request": spec["max_retries_per_logical_request"],
            "external_warmup_calls": spec["external_warmup_calls"],
        },
        "provider_configuration": {
            "provider": spec["provider"],
            "embedding_model": spec["embedding_model"],
            "generator_model": spec["generator_model"],
            "temperature": spec["temperature"],
            "top_k": spec["top_k"],
            "max_output_tokens": spec["max_output_tokens"],
        },
        "plan_only": {
            "path": "evaluation/wolala2026/preheldout_v3_attempt1/execution_plan.json",
            "heldout_model_execution_count": plan["heldout_model_execution_count"],
            "heldout_embedding_calls": plan["heldout_embedding_calls"],
            "heldout_generation_calls": plan["heldout_generation_calls"],
            "external_api_calls": plan["external_api_calls_in_plan_only"],
            "no_retrieval_embedding_adapter_generation_or_scoring_performed": plan["no_retrieval_embedding_adapter_generation_or_scoring_performed"],
        },
        "audit_artifacts": {
            "final_heldout_v3_preaudit": "evaluation/wolala2026/FINAL_HELDOUT_V3_PREAUDIT.json",
            "retired_heldout_dataset_registry": "evaluation/wolala2026/RETIRED_HELDOUT_DATASET_REGISTRY_v1.json",
            "preheldout_plan_validation_report": "evaluation/wolala2026/preheldout_v3_attempt1/PLAN_VALIDATION_REPORT.md",
            "protocol_v4": "evaluation/wolala2026/WOLALA2026_PILOT_PROTOCOL_v4.md",
            "execution_spec_v4": "evaluation/wolala2026/HELDOUT_EXECUTION_SPEC_v4.json",
        },
        "checksums": checksums,
        "tests": test_summary or {"status": "PENDING_REGENERATE_AFTER_TESTS"},
        "no_external_api_calls_performed_in_freeze_task": True,
        "heldout_mode_executions_in_freeze_phase": 0,
        "authorization_created_in_freeze_phase": False,
        "retired_registry_summary": {
            "active_heldout_dataset": retired_registry["active_heldout_dataset"],
            "retired_datasets_execution_blocked_in_code": retired_registry["retired_datasets_execution_blocked_in_code"],
        },
        "preaudit_passed": preaudit["audit_passed"],
    }


def _git_evidence() -> dict[str, Any]:
    remote = _git("ls-remote", "origin", "refs/heads/wolala2026", f"refs/tags/{SHARED_RETRIEVAL_TAG}", f"refs/tags/{SHARED_RETRIEVAL_TAG}^{{}}", openssl=True)
    rows = [line.split() for line in remote.splitlines() if line.strip()]
    by_ref = {row[1]: row[0] for row in rows}
    local_peeled = _git("rev-parse", f"{SHARED_RETRIEVAL_TAG}^{{}}")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", f"{SHARED_RETRIEVAL_TAG}^{{}}", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "remote_branch": "refs/heads/wolala2026",
        "remote_branch_sha": by_ref.get("refs/heads/wolala2026"),
        "remote_tag": f"refs/tags/{SHARED_RETRIEVAL_TAG}",
        "remote_tag_object": by_ref.get(f"refs/tags/{SHARED_RETRIEVAL_TAG}"),
        "remote_tag_peeled": by_ref.get(f"refs/tags/{SHARED_RETRIEVAL_TAG}^{{}}"),
        "local_tag_peeled": local_peeled,
        "local_tag_is_ancestor_of_head": ancestor.returncode == 0,
        "remote_verification_method": "git ls-remote with http.sslBackend=openssl",
        "fetch_head_write_required": False,
    }


def _git(*args: str, openssl: bool = False) -> str:
    command = ["git"]
    if openssl:
        command.extend(["-c", "http.sslBackend=openssl"])
    command.extend(args)
    return subprocess.check_output(command, cwd=REPO_ROOT, text=True).strip()


def _read_cases() -> list[dict[str, Any]]:
    with (DATA_DIR / HELDOUT_DATASET_V3 / "cases.jsonl").open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _test_summary_from_args(args: argparse.Namespace) -> dict[str, Any] | None:
    if not args.focused_tests_result and not args.wolala_tests_result:
        return None
    return {
        "external_api_calls": 0,
        "focused_v3": {
            "command": args.focused_tests_command,
            "result": args.focused_tests_result,
            "tests_run": args.focused_tests_run,
        },
        "wolala": {
            "command": args.wolala_tests_command,
            "result": args.wolala_tests_result,
            "tests_run": args.wolala_tests_run,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare WoLaLa held-out v3 freeze artifacts without API execution.")
    parser.add_argument("--focused-tests-result")
    parser.add_argument("--focused-tests-run", type=int)
    parser.add_argument("--focused-tests-command", default="python -m unittest evaluation.tests.test_wolala_final_experiment_v3 -v")
    parser.add_argument("--wolala-tests-result")
    parser.add_argument("--wolala-tests-run", type=int)
    parser.add_argument("--wolala-tests-command", default='python -m unittest discover -s evaluation/tests -p "test_wolala*.py" -v')
    args = parser.parse_args()
    manifest = prepare(_test_summary_from_args(args))
    print(json.dumps({"freeze_manifest": str(FREEZE_MANIFEST_PATH.relative_to(REPO_ROOT)).replace("\\", "/"), "preaudit_passed": manifest["preaudit_passed"]}, sort_keys=True))


if __name__ == "__main__":
    main()
