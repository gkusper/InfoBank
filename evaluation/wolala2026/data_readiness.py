from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .yaml_util import load_yaml_subset


REQUIRED_WOLALA_FIELDS = [
    "case_id",
    "query",
    "requested_content",
    "requested_granularity",
    "requested_action",
    "evidence_units",
    "access_modes",
    "expected_evidential_roles",
    "expected_evidence_states",
    "expected_permitted_output",
    "expected_top_level_mode",
    "expected_cfaf_realization",
    "expected_public_reason_class",
    "expected_internal_reason_class",
    "source_existence_visibility",
    "protected_markers",
    "gold_answer",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def unique_case_ids(records: list[dict[str, Any]]) -> bool:
    ids = [record.get("case_id") for record in records]
    return len(ids) == len(set(ids)) and all(ids)


def field_coverage(records: list[dict[str, Any]], fields: list[str]) -> dict[str, bool]:
    return {field: all(field in record for record in records) for field in fields}


def audit_data_readiness(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root)
    entries = [
        audit_document_fixture(root / "evaluation" / "fixtures" / "document_rag_v3.yaml"),
        audit_evidence_cases(root / "data" / "benchmarks" / "evidence_unit_v2_holdout" / "cases.jsonl", root / "data" / "benchmarks" / "evidence_unit_v2_holdout" / "gold.jsonl"),
        audit_wolala_smoke(root / "evaluation" / "wolala2026" / "smoke_config.yaml"),
    ]
    capabilities = {
        "positive_metadata_request_cases": any(entry.get("path", "").endswith("smoke_config.yaml") and entry["checks"].get("positive_metadata_request_cases") for entry in entries),
        "paired_source_existence_leakage_cases": any(entry.get("path", "").endswith("smoke_config.yaml") and entry["checks"].get("paired_source_existence_leakage_cases") for entry in entries),
        "prompt_only_baseline_configuration": (root / "evaluation" / "wolala2026" / "adapters.py").exists(),
        "structured_cfaf_output_gold_labels": any(entry.get("path", "").endswith("smoke_config.yaml") and entry["checks"].get("structured_cfaf_output_gold_labels") for entry in entries),
        "public_internal_reason_labels": any(entry.get("path", "").endswith("smoke_config.yaml") and entry["checks"].get("public_internal_reason_labels") for entry in entries),
        "latency_ready_run_records": (root / "evaluation" / "wolala2026" / "smoke_results.json").exists(),
        "enough_sanitized_evidence_for_publication_scale": False,
    }
    missing_for_publication_scale = [
        "A larger WoLaLa-specific held-out case set with all required structured CFAF labels.",
        "Documented train/development/test split for the WoLaLa case set.",
        "Prompt-only baseline execution records beyond adapter smoke checks.",
        "Latency records from repeated cold/warm runs separated by FULL/CFAF and generation-used/skipped.",
        "Publication-scale sanitized evidence with explicit licence/provenance per WoLaLa case.",
    ]
    return {
        "schema_version": "wolala2026-data-inventory-v1",
        "entries": entries,
        "capability_checks": capabilities,
        "overall_status": "PARTIAL - MISSING_DATA_OR_COMPONENTS",
        "missing_for_publication_scale": missing_for_publication_scale,
    }


def audit_document_fixture(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    case_ids = re.findall(r"^\s*-\s*case_id:\s*(\S+)", text, flags=re.MULTILINE)
    scenario_families = sorted(set(re.findall(r"^\s*scenario_family:\s*(\S+)", text, flags=re.MULTILINE)))
    field_presence = {field: bool(re.search(rf"^\s*{re.escape(field)}:", text, flags=re.MULTILINE)) for field in REQUIRED_WOLALA_FIELDS}
    field_presence["case_id"] = bool(case_ids)
    return {
        "path": str(path.as_posix()),
        "case_count": len(case_ids),
        "source_provenance": "Deterministically generated synthetic D1-D5 document-RAG fixture.",
        "licence_or_reference": "Repository LICENSE plus evaluation/fixtures/README.md synthetic data policy.",
        "checksum_or_version_identifier": sha256(path),
        "train_development_test_separation_documented": False,
        "case_ids_unique": len(case_ids) == len(set(case_ids)) and bool(case_ids),
        "gold_fields_outside_generator_visible_content": True,
        "schema_contains_all_required_wolala_fields": all(field_presence.values()),
        "fixture_used_by_smoke_suite": False,
        "scenario_families": scenario_families,
        "missing_required_wolala_fields": [field for field, present in field_presence.items() if not present],
        "checks": {
            "positive_metadata_request_cases": "D2_metadata_only" in scenario_families,
            "paired_source_existence_leakage_cases": False,
            "structured_cfaf_output_gold_labels": False,
            "public_internal_reason_labels": False,
        },
        "status": "PARTIAL",
    }


def audit_evidence_cases(cases_path: Path, gold_path: Path) -> dict[str, Any]:
    cases = load_jsonl(cases_path)
    gold = load_jsonl(gold_path)
    coverage = field_coverage(cases, REQUIRED_WOLALA_FIELDS)
    gold_ids = {record.get("case_id") for record in gold}
    case_ids = {record.get("case_id") for record in cases}
    return {
        "path": str(cases_path.as_posix()),
        "case_count": len(cases),
        "source_provenance": "Pseudonymized MailEx-derived and controlled synthetic D6-D8 action-reconstruction holdout.",
        "licence_or_reference": "data/benchmarks/evidence_unit_v2_holdout/LICENSE_DATA.md and SOURCE_PROVENANCE.md.",
        "checksum_or_version_identifier": sha256(cases_path),
        "train_development_test_separation_documented": False,
        "case_ids_unique": unique_case_ids(cases),
        "gold_fields_outside_generator_visible_content": case_ids == gold_ids,
        "schema_contains_all_required_wolala_fields": all(coverage.values()),
        "fixture_used_by_smoke_suite": False,
        "missing_required_wolala_fields": [field for field, present in coverage.items() if not present],
        "gold_path": str(gold_path.as_posix()),
        "gold_checksum": sha256(gold_path),
        "checks": {
            "positive_metadata_request_cases": False,
            "paired_source_existence_leakage_cases": False,
            "structured_cfaf_output_gold_labels": False,
            "public_internal_reason_labels": False,
        },
        "status": "PARTIAL",
    }


def audit_wolala_smoke(path: Path) -> dict[str, Any]:
    data = load_yaml_subset(path)
    cases = data.get("cases", [])
    normalized_records = [_normalize_smoke_case(case) for case in cases]
    coverage = field_coverage(normalized_records, REQUIRED_WOLALA_FIELDS)
    return {
        "path": str(path.as_posix()),
        "case_count": len(cases),
        "source_provenance": "Deterministic synthetic WoLaLa smoke fixtures created for branch preparation.",
        "licence_or_reference": "Repository LICENSE; no personal, health, or confidential real-world data.",
        "checksum_or_version_identifier": sha256(path),
        "train_development_test_separation_documented": True,
        "case_ids_unique": unique_case_ids(cases),
        "gold_fields_outside_generator_visible_content": True,
        "schema_contains_all_required_wolala_fields": all(coverage.values()),
        "fixture_used_by_smoke_suite": True,
        "missing_required_wolala_fields": [field for field, present in coverage.items() if not present],
        "checks": {
            "positive_metadata_request_cases": any(case.get("case_id") == "S4A_METADATA_LOOKUP_ALLOWED" for case in cases),
            "paired_source_existence_leakage_cases": {case.get("case_id") for case in cases}.issuperset({"S9A_NO_RELEVANT_SOURCE", "S9B_INTERNAL_INACCESSIBLE_SOURCE"}),
            "structured_cfaf_output_gold_labels": all("expected_top_level_mode" in case for case in cases),
            "public_internal_reason_labels": all("expected_public_reason_class" in case and "expected_internal_reason_class" in case for case in cases),
        },
        "status": "READY",
    }


def _normalize_smoke_case(case: dict[str, Any]) -> dict[str, Any]:
    access_modes = [source.get("access_mode") for source in case.get("sources", [])]
    roles = [source.get("evidential_role") for source in case.get("sources", [])]
    states = [source.get("evidence_state") for source in case.get("sources", [])]
    visibility = [source.get("existence_visibility") for source in case.get("sources", [])]
    return {
        **case,
        "evidence_units": case.get("sources", []),
        "access_modes": access_modes,
        "expected_evidential_roles": roles,
        "expected_evidence_states": states,
        "source_existence_visibility": visibility,
    }


def write_data_inventory(repo_root: str | Path, output_path: str | Path) -> dict[str, Any]:
    inventory = audit_data_readiness(repo_root)
    Path(output_path).write_text(json.dumps(inventory, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return inventory
