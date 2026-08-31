"""Bind external ScenarioPack bundles to actual-pipeline corpus fixtures.

The binder writes three separate artifacts:

* runtime-only query inputs;
* scorer-only gold annotations;
* a corpus fixture that points at copied source PDFs by relative path.

The actual runner only receives the runtime query and corpus fixture paths.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping

from .actual_pipeline_inputs import CORPUS_SCHEMA_VERSION, CorpusDocument, PolicyFixture, write_jsonl
from .scenario_pack import SCENARIO_DATASET_VERSION, project_scenario_pack, validate_scenario_pack


EXTERNAL_CORPUS_BUILDER_VERSION = "external-scenario-corpus-v1"
PRIMARY_CONTRACT_CORPUS_BUILDER_VERSION = "external-primary-contract-corpus-v1"
RUNTIME_FORBIDDEN_KEYS = {
    "acceptable_page_ranges",
    "aggregate_input_sources",
    "aggregate_k",
    "author_decision_id",
    "expected_output_class",
    "expected_output",
    "expected_contributor_count",
    "factual_atoms",
    "reason_code",
    "negative_reason",
    "gold_document_ids",
    "gold_page_or_message_ranges",
    "manual_validation_state",
    "prohibited_disclosures",
    "required_sources",
    "required_evidence_roles",
    "reference_answer",
    "reference_citations",
}
STOP_KEYWORDS = {
    "and",
    "for",
    "from",
    "manual",
    "notice",
    "page",
    "pdf",
    "source",
    "terms",
    "the",
    "this",
    "user",
}
ANSWER_OUTPUT_CLASSES = {"FULL_ANSWER", "CONSTRAINED_ANSWER", "AGGREGATE_RESULT"}


def stable_document_id(package_identity: str, scenario_id: str, source_id: str) -> str:
    identity = f"infobank:external-scenario:{package_identity}:{scenario_id}:{source_id}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, identity))


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Expected JSONL object row: {path}")
            rows.append(value)
    return rows


def _checksum_file_path(package_root: Path) -> Path:
    for name in ("SHA256SUMS.txt", "PACKAGE_SHA256SUMS.txt"):
        path = package_root / name
        if path.is_file():
            return path
    raise FileNotFoundError("Package checksum file is missing")


def _parse_sha256sums(package_root: Path) -> dict[str, str]:
    checksum_path = _checksum_file_path(package_root)
    checksums: dict[str, str] = {}
    for line_number, line in enumerate(checksum_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 64:
            raise ValueError(f"Invalid SHA256SUMS row at line {line_number}")
        relative = parts[1].lstrip("*").replace("\\", "/")
        checksums[relative] = parts[0].lower()
    return checksums


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows = _read_jsonl(path)
    seen: set[str] = set()
    for row in rows:
        case_id = str(row.get("case_id", ""))
        if not case_id or case_id in seen:
            raise ValueError(f"Missing or duplicate case_id in {path}")
        seen.add(case_id)
    return rows


def verify_package_checksums(package_root: str | Path) -> dict[str, Any]:
    root = Path(package_root)
    expected = _parse_sha256sums(root)
    missing: list[str] = []
    mismatched: list[str] = []
    for relative, digest in expected.items():
        path = root / relative
        if not path.is_file():
            missing.append(relative)
            continue
        if sha256_file(path) != digest:
            mismatched.append(relative)
    return {
        "status": "PASS" if not missing and not mismatched else "FAIL",
        "entry_count": len(expected),
        "checksum_file": _checksum_file_path(root).name,
        "missing": missing,
        "mismatched": mismatched,
    }


def _scenario_ids_from_package(package_root: Path) -> tuple[str, ...]:
    manifest = _read_json(package_root / "PACKAGE_MANIFEST.json")
    scenario_ids = manifest.get("scenario_ids")
    if not isinstance(scenario_ids, list) or not all(isinstance(item, str) and item for item in scenario_ids):
        raise ValueError("PACKAGE_MANIFEST.json must provide scenario_ids")
    return tuple(scenario_ids)


def _projection_rows(package_root: Path, scenario_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    projection_root = package_root / "projections" / scenario_id
    manifest = _read_json(projection_root / "projection_manifest.json")
    runtime_path = projection_root / str(manifest["runtime_query_path"])
    scorer_path = projection_root / str(manifest["scorer_gold_path"])
    if sha256_file(runtime_path) != manifest["runtime_query_sha256"]:
        raise ValueError(f"Runtime projection hash mismatch for {scenario_id}")
    if sha256_file(scorer_path) != manifest["scorer_gold_sha256"]:
        raise ValueError(f"Scorer projection hash mismatch for {scenario_id}")
    return _read_jsonl(runtime_path), _read_jsonl(scorer_path)


def _primary_scenario_entries(
    package_root: Path,
    scenario_ids: tuple[str, ...] | None = None,
) -> tuple[dict[str, Any], ...]:
    index_path = package_root / "scenario_pack_index.json"
    if index_path.is_file():
        index = _read_json(index_path)
        raw_entries = index.get("primary_scenarios")
        if isinstance(raw_entries, list):
            entries_by_id: dict[str, dict[str, Any]] = {}
            for entry in raw_entries:
                if not isinstance(entry, dict):
                    raise ValueError("primary_scenarios entries must be objects")
                scenario_id = entry.get("scenario_id")
                manifest_path = entry.get("manifest_path")
                if not isinstance(scenario_id, str) or not scenario_id:
                    raise ValueError("primary_scenarios entries require scenario_id")
                if not isinstance(manifest_path, str) or not manifest_path:
                    raise ValueError("primary_scenarios entries require manifest_path")
                entries_by_id[scenario_id] = dict(entry)
            expected = scenario_ids or tuple(entry["scenario_id"] for entry in raw_entries)
            missing = [scenario_id for scenario_id in expected if scenario_id not in entries_by_id]
            if missing:
                raise ValueError(f"Primary scenario manifest entries are missing: {', '.join(missing)}")
            return tuple(entries_by_id[scenario_id] for scenario_id in expected)

    expected = scenario_ids or _scenario_ids_from_package(package_root)
    return tuple(
        {
            "scenario_id": scenario_id,
            "manifest_path": f"scenario_packs/{scenario_id}/scenario_pack.json",
        }
        for scenario_id in expected
    )


def _scenario_dir_from_entry(package_root: Path, entry: Mapping[str, Any]) -> Path:
    return package_root / Path(str(entry["manifest_path"])).parent


def _scenario_pack_from_entry(package_root: Path, entry: Mapping[str, Any]) -> dict[str, Any]:
    pack = _read_json(package_root / str(entry["manifest_path"]))
    if pack.get("scenario_id") != entry["scenario_id"]:
        raise ValueError(f"Scenario entry does not match pack scenario_id: {entry['scenario_id']}")
    return pack


def _source_manifest_filename_map(scenario_dir: Path) -> dict[str, str]:
    path = scenario_dir / "source_documents_manifest.json"
    if not path.is_file():
        return {}
    value = _read_json(path)
    rows = value.get("documents")
    if not isinstance(rows, list):
        raise ValueError(f"Invalid source document manifest: {path}")
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"Invalid source document manifest row: {path}")
        source_id = row.get("source_id")
        filename = row.get("filename")
        if not isinstance(source_id, str) or not isinstance(filename, str):
            raise ValueError(f"Source document manifest rows require source_id and filename: {path}")
        result[source_id] = filename
    return result


def _scenario_source_filename_map(
    scenario_dir: Path,
    explicit_map: Mapping[str, str] | None,
) -> dict[str, str]:
    scenario_id = scenario_dir.name
    combined = _source_manifest_filename_map(scenario_dir)
    for source_id, filename in list(combined.items()):
        combined[f"{scenario_id}:{source_id}"] = filename
    if explicit_map:
        combined.update(explicit_map)
    return combined


def _primary_contract_paths(package_root: Path) -> dict[str, Path]:
    root = package_root / "evaluation_contracts" / "primary"
    return {
        "root": root,
        "manifest": root / "contract_manifest.json",
        "runtime": root / "runtime" / "query_inputs.jsonl",
        "reference": root / "scorer" / "gold_annotations.jsonl",
        "policy": root / "policy_fixtures.json",
        "retrieval": root / "retrieval_contracts.json",
    }


def _package_source_dirs(package_root: Path) -> tuple[str, ...]:
    return tuple(sorted(path.name for path in (package_root / "scenario_packs").iterdir() if path.is_dir()))


def _package_projection_dirs(package_root: Path) -> tuple[str, ...]:
    return tuple(sorted(path.name for path in (package_root / "projections").iterdir() if path.is_dir()))


def _rewrite_access_source_ids(
    access_by_document: Mapping[str, Any],
    *,
    scenario_id: str,
    document_ids_by_source_id: Mapping[str, str],
) -> dict[str, str]:
    access: dict[str, str] = {}
    for source_id, value in access_by_document.items():
        source_id_text = str(source_id)
        if source_id_text not in document_ids_by_source_id:
            raise ValueError(f"Unknown policy source ID for {scenario_id}: {source_id_text}")
        access_value = str(value)
        if access_value not in {"Full", "Aggregate", "Metadata", "Deny"}:
            raise ValueError(f"Unsupported policy access value for {source_id_text}: {access_value}")
        access[document_ids_by_source_id[source_id_text]] = access_value
    return access


def _policy_fixture_from_contract(
    row: Mapping[str, Any],
    *,
    scenario_id: str,
    document_ids_by_source_id: Mapping[str, str],
) -> PolicyFixture:
    raw_access = row.get("access_by_document")
    if not isinstance(raw_access, dict):
        raise ValueError(f"Policy fixture access_by_document must be an object: {row.get('fixture_id')}")
    fixture_id = row.get("fixture_id")
    if not isinstance(fixture_id, str) or not fixture_id:
        raise ValueError("Policy fixture requires fixture_id")
    return PolicyFixture(
        fixture_id=fixture_id,
        access_by_document=_rewrite_access_source_ids(
            raw_access,
            scenario_id=scenario_id,
            document_ids_by_source_id=document_ids_by_source_id,
        ),
        purpose=str(row.get("purpose") or "grounded_question_answering"),
        conflict_policy=str(row.get("conflict_policy") or "query_sensitive"),
        aggregate_k=int(row.get("aggregate_k") or 3),
        prohibited_markers=tuple(str(item) for item in row.get("prohibited_markers") or ()),
    )


def _source_map_lookup(source_filename_map: Mapping[str, str], scenario_id: str, source_id: str) -> str | None:
    return source_filename_map.get(f"{scenario_id}:{source_id}") or source_filename_map.get(source_id)


def resolve_source_pdf(
    scenario_dir: str | Path,
    source: Mapping[str, Any],
    *,
    source_filename_map: Mapping[str, str] | None = None,
) -> Path:
    source_id = str(source["source_id"])
    source_root = Path(scenario_dir) / "source_documents"
    exact = source_root / f"{source_id}.pdf"
    if exact.is_file():
        return exact
    scenario_id = Path(scenario_dir).name
    mapped = _source_map_lookup(source_filename_map or {}, scenario_id, source_id)
    if mapped:
        candidate = (source_root / mapped).resolve()
        source_root_resolved = source_root.resolve()
        try:
            candidate.relative_to(source_root_resolved)
        except ValueError as exc:
            raise ValueError(f"Source map path escapes source_documents for {source_id}") from exc
        if candidate.is_file():
            return candidate
        raise FileNotFoundError(f"Mapped source PDF does not exist for {source_id}: {mapped}")
    raise FileNotFoundError(
        f"No PDF named {source_id}.pdf and no source_filename_map entry for {scenario_id}:{source_id}"
    )


def _pdf_pages(path: Path) -> tuple[str, ...]:
    import fitz

    pdf = fitz.open(path)
    try:
        pages = tuple((page.get_text("text") or "") for page in pdf)
    finally:
        pdf.close()
    if not pages:
        raise ValueError(f"Source PDF has no pages: {path}")
    return pages


def _keyword_values(pack: Mapping[str, Any], source: Mapping[str, Any], filename: str, pages: tuple[str, ...]) -> tuple[str, ...]:
    text = " ".join(
        [
            str(pack.get("scenario_id") or ""),
            str(pack.get("object_id") or pack.get("account_id") or ""),
            str(source.get("source_id") or ""),
            str(source.get("source_type") or ""),
            str(source.get("relation_key") or ""),
            Path(filename).stem,
            " ".join(pages[:2])[:2000],
        ]
    )
    values: set[str] = set()
    for token in re.findall(r"[a-z0-9][a-z0-9_-]{1,}", text.lower()):
        token = token.strip("_-")
        if len(token) < 2 or token in STOP_KEYWORDS:
            continue
        values.add(token)
        for part in re.split(r"[_-]+", token):
            if len(part) >= 2 and part not in STOP_KEYWORDS:
                values.add(part)
    return tuple(sorted(values)[:40])


def _fixture_access(permission: str) -> str | None:
    return {
        "Owner": "Full",
        "Reader": "Full",
        "Aggregate": "Aggregate",
        "Metadata": "Metadata",
        "Deny": None,
    }.get(permission)


def _rewrite_gold_source_ids(
    row: Mapping[str, Any],
    *,
    scenario_id: str,
    document_ids_by_source_id: Mapping[str, str],
) -> dict[str, Any]:
    def mapped(source_id: str) -> str:
        if source_id not in document_ids_by_source_id:
            raise ValueError(f"Unknown scorer source ID for {scenario_id}: {source_id}")
        return document_ids_by_source_id[source_id]

    value = dict(row)
    value["gold_document_ids"] = [mapped(str(source_id)) for source_id in value.get("gold_document_ids", [])]
    value["gold_page_or_message_ranges"] = {
        mapped(str(source_id)): pages
        for source_id, pages in value.get("gold_page_or_message_ranges", {}).items()
    }
    if "required_sources" in value:
        value["required_sources"] = [mapped(str(source_id)) for source_id in value["required_sources"]]
    if "reference_citations" in value:
        value["reference_citations"] = [
            {**citation, "source_id": mapped(str(citation["source_id"]))}
            for citation in value["reference_citations"]
        ]
    metadata = dict(value.get("metadata") or {})
    metadata["logical_source_id_map"] = dict(sorted(document_ids_by_source_id.items()))
    metadata["logical_scenario_id"] = scenario_id
    value["metadata"] = metadata
    return value


def _validate_runtime_projection(rows: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for row in rows:
        case_id = str(row.get("case_id", ""))
        if not case_id or case_id in seen:
            raise ValueError("Runtime projection has missing or duplicate case_id")
        seen.add(case_id)
        leaked = RUNTIME_FORBIDDEN_KEYS.intersection(row)
        if leaked:
            raise ValueError(f"Runtime projection contains scorer-only fields for {case_id}: {sorted(leaked)}")


def _validate_gold_projection(rows: list[dict[str, Any]], runtime_case_ids: set[str]) -> None:
    gold_case_ids = [str(row.get("case_id", "")) for row in rows]
    if gold_case_ids != list(runtime_case_ids):
        if set(gold_case_ids) != runtime_case_ids:
            raise ValueError("Gold projection case IDs do not match runtime case IDs")
    if len(gold_case_ids) != len(set(gold_case_ids)):
        raise ValueError("Gold projection has duplicate case IDs")


def verify_external_primary_contract_package(
    package_root: str | Path,
    *,
    scenario_ids: tuple[str, ...] | None = None,
    source_filename_map: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    root = Path(package_root)
    checksum_result = verify_package_checksums(root)
    if checksum_result["status"] != "PASS":
        raise ValueError("Package checksum verification failed")

    entries = _primary_scenario_entries(root, scenario_ids)
    paths = _primary_contract_paths(root)
    contract_manifest = _read_json(paths["manifest"])
    runtime_rows = _jsonl_rows(paths["runtime"])
    reference_rows = _jsonl_rows(paths["reference"])
    policy_value = _read_json(paths["policy"])
    policy_rows = policy_value.get("policy_fixtures")
    if not isinstance(policy_rows, list):
        raise ValueError("Primary policy_fixtures.json must contain a policy_fixtures array")
    retrieval_value = _read_json(paths["retrieval"])
    retrieval_rows = retrieval_value.get("bounded_queries")
    if not isinstance(retrieval_rows, list):
        raise ValueError("Primary retrieval_contracts.json must contain a bounded_queries array")

    _validate_runtime_projection(runtime_rows)
    runtime_case_ids = [str(row["case_id"]) for row in runtime_rows]
    reference_case_ids = [str(row["case_id"]) for row in reference_rows]
    if runtime_case_ids != reference_case_ids:
        raise ValueError("Primary runtime/reference case order mismatch")
    if runtime_case_ids != [str(row.get("fixture_id", "")).split(":", 1)[0] for row in policy_rows]:
        raise ValueError("Primary runtime/policy fixture order mismatch")

    packs_by_scenario: dict[str, dict[str, Any]] = {}
    source_pages_by_scenario: dict[str, dict[str, int]] = {}
    pdf_count = 0
    page_checks: list[dict[str, Any]] = []
    question_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    case_checks: list[dict[str, Any]] = []
    mismatches: list[dict[str, str]] = []

    for entry in entries:
        scenario_id = str(entry["scenario_id"])
        scenario_dir = _scenario_dir_from_entry(root, entry)
        pack = _scenario_pack_from_entry(root, entry)
        errors = [issue for issue in validate_scenario_pack(pack) if issue["severity"] == "ERROR"]
        if errors:
            raise ValueError(f"ScenarioPack has structural errors for {scenario_id}")
        packs_by_scenario[scenario_id] = pack
        question_counts[scenario_id] = len(pack["queries"])
        source_counts[scenario_id] = len(pack["sources"])
        source_pages: dict[str, int] = {}
        scenario_map = _scenario_source_filename_map(scenario_dir, source_filename_map)
        for source in pack["sources"]:
            pdf_path = resolve_source_pdf(scenario_dir, source, source_filename_map=scenario_map)
            pdf_count += 1
            pages = _pdf_pages(pdf_path)
            source_pages[str(source["source_id"])] = len(pages)
        source_pages_by_scenario[scenario_id] = source_pages

    runtime_by_case = {str(row["case_id"]): row for row in runtime_rows}
    reference_by_case = {str(row["case_id"]): row for row in reference_rows}
    policy_by_case = {str(row["fixture_id"]).split(":", 1)[0]: row for row in policy_rows}
    retrieval_by_case = {str(row.get("query_id")): row for row in retrieval_rows}
    pack_query_by_case = {
        str(query["query_id"]): (scenario_id, query)
        for scenario_id, pack in packs_by_scenario.items()
        for query in pack["queries"]
    }

    if set(runtime_by_case) != set(pack_query_by_case):
        raise ValueError("Primary contract cases do not match primary scenario-pack queries")
    if set(runtime_by_case) != set(policy_by_case):
        raise ValueError("Primary contract cases do not match case-policy fixtures")
    if set(runtime_by_case) != set(retrieval_by_case):
        raise ValueError("Primary contract cases do not match retrieval contracts")

    output_class_counts: dict[str, int] = {}
    human_validated_count = 0
    factual_atom_coverage: dict[str, int] = {}
    for case_id in runtime_case_ids:
        runtime = runtime_by_case[case_id]
        reference = reference_by_case[case_id]
        policy = policy_by_case[case_id]
        retrieval = retrieval_by_case[case_id]
        scenario_id, query = pack_query_by_case[case_id]
        row_mismatches: list[str] = []

        def check(field: str, left: Any, right: Any) -> None:
            if left != right:
                row_mismatches.append(field)
                mismatches.append(
                    {
                        "case_id": case_id,
                        "field": field,
                        "decision_record_value": json.dumps(left, ensure_ascii=False, sort_keys=True),
                        "package_value": json.dumps(right, ensure_ascii=False, sort_keys=True),
                    }
                )

        check("scenario_id", scenario_id, runtime.get("corpus_package_ref"))
        check("question", query.get("query"), runtime.get("query_text"))
        check("expected_output_class", query.get("expected_output"), reference.get("expected_output_class"))
        check("reference_answer", query.get("reference_answer"), reference.get("reference_answer"))
        check("required_sources", query.get("required_sources"), reference.get("required_sources"))
        check("reference_citations", query.get("reference_citations"), reference.get("reference_citations"))
        check("retrieval_required_sources", query.get("required_sources"), retrieval.get("required_sources"))
        check("retrieval_reference_citations", query.get("reference_citations"), retrieval.get("reference_citations"))
        check("policy_fixture_ref", runtime.get("policy_fixture_ref"), policy.get("fixture_id"))
        metadata = reference.get("metadata") or {}
        check("supporting_sources", query.get("supporting_sources"), metadata.get("supporting_sources"))
        check("author_decision_id", metadata.get("author_decision_id"), policy.get("author_decision_id"))
        check("effective_use_decision", metadata.get("effective_use_decision"), policy.get("effective_use_decision"))
        check("aggregate_k", metadata.get("aggregate_k"), None if policy.get("effective_use_decision") != "Aggregate" else policy.get("aggregate_k"))
        check("expected_contributor_count", metadata.get("expected_contributor_count"), policy.get("expected_contributor_count"))
        check("prohibited_disclosures", metadata.get("prohibited_disclosures"), policy.get("prohibited_markers"))
        check(
            "public_document_citations_expected",
            bool(metadata.get("public_document_citations_expected")),
            bool(retrieval.get("public_citations_expected")),
        )

        if reference.get("manual_validation_state") == "HUMAN_VALIDATED":
            human_validated_count += 1
        else:
            row_mismatches.append("manual_validation_state")
        output_class = str(reference.get("expected_output_class"))
        output_class_counts[output_class] = output_class_counts.get(output_class, 0) + 1
        factual_atoms = reference.get("factual_atoms") or []
        factual_atom_coverage[output_class] = factual_atom_coverage.get(output_class, 0) + int(bool(factual_atoms))
        if output_class in ANSWER_OUTPUT_CLASSES and not factual_atoms:
            row_mismatches.append("factual_atoms")
        if output_class not in ANSWER_OUTPUT_CLASSES and factual_atoms:
            row_mismatches.append("factual_atoms")

        source_pages = source_pages_by_scenario[scenario_id]
        for citation in query.get("reference_citations") or []:
            source_id = str(citation["source_id"])
            page = citation.get("page")
            if page is None:
                continue
            valid = source_id in source_pages and 1 <= int(page) <= source_pages[source_id]
            page_checks.append(
                {
                    "case_id": case_id,
                    "source_id": source_id,
                    "page": page,
                    "page_count": source_pages.get(source_id),
                    "valid": valid,
                }
            )
            if not valid:
                row_mismatches.append("reference_citation_page")

        case_checks.append(
            {
                "case_id": case_id,
                "scenario_id": scenario_id,
                "question": runtime["query_text"],
                "expected_output_class": output_class,
                "reference_answer": reference.get("reference_answer"),
                "required_sources": reference.get("required_sources"),
                "required_pages": reference.get("gold_page_or_message_ranges"),
                "supporting_sources": metadata.get("supporting_sources"),
                "persistent_permission": metadata.get("permission_mode"),
                "effective_use_decision": metadata.get("effective_use_decision"),
                "aggregate_k": metadata.get("aggregate_k"),
                "expected_contributor_count": metadata.get("expected_contributor_count"),
                "prohibited_disclosure_count": len(metadata.get("prohibited_disclosures") or []),
                "public_document_citations_expected": metadata.get("public_document_citations_expected"),
                "factual_atom_count": len(factual_atoms),
                "manual_validation_state": reference.get("manual_validation_state"),
                "author_decision_id": metadata.get("author_decision_id"),
                "status": "PASS" if not row_mismatches else "FAIL",
                "mismatched_fields": row_mismatches,
            }
        )

    manifest_distribution = contract_manifest.get("output_class_distribution")
    if isinstance(manifest_distribution, dict) and manifest_distribution != output_class_counts:
        raise ValueError("Primary contract output-class distribution mismatch")
    if contract_manifest.get("question_count") != len(runtime_rows):
        raise ValueError("Primary contract question count mismatch")
    if contract_manifest.get("scenario_count") != len(entries):
        raise ValueError("Primary contract scenario count mismatch")
    if contract_manifest.get("source_pdf_count") != pdf_count:
        raise ValueError("Primary contract source PDF count mismatch")
    if mismatches:
        raise ValueError("Primary author-review contract consistency failed")

    return {
        "status": "PASS",
        "scenario_ids": [str(entry["scenario_id"]) for entry in entries],
        "question_counts": question_counts,
        "source_counts": source_counts,
        "total_questions": len(runtime_rows),
        "pdf_source_count": pdf_count,
        "checksum_entry_count": checksum_result["entry_count"],
        "checksum_file": checksum_result["checksum_file"],
        "output_class_distribution": dict(sorted(output_class_counts.items())),
        "human_validated_count": human_validated_count,
        "factual_atom_coverage": factual_atom_coverage,
        "page_checks": page_checks,
        "case_checks": case_checks,
        "runtime_gold_separated": True,
        "policy_fixture_count": len(policy_rows),
    }


def verify_external_scenario_package(
    package_root: str | Path,
    *,
    scenario_ids: tuple[str, ...] | None = None,
    source_filename_map: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    root = Path(package_root)
    expected_scenarios = scenario_ids or _scenario_ids_from_package(root)
    if _package_source_dirs(root) != tuple(sorted(expected_scenarios)):
        raise ValueError("scenario_packs directory does not match expected scenarios")
    if _package_projection_dirs(root) != tuple(sorted(expected_scenarios)):
        raise ValueError("projections directory does not match expected scenarios")
    checksum_result = verify_package_checksums(root)
    if checksum_result["status"] != "PASS":
        raise ValueError("Package checksum verification failed")

    question_counts: dict[str, int] = {}
    pdf_count = 0
    runtime_case_ids: list[str] = []
    gold_case_ids: list[str] = []
    page_checks: list[dict[str, Any]] = []
    for scenario_id in expected_scenarios:
        scenario_dir = root / "scenario_packs" / scenario_id
        pack = _read_json(scenario_dir / "scenario_pack.json")
        errors = [issue for issue in validate_scenario_pack(pack) if issue["severity"] == "ERROR"]
        if errors:
            raise ValueError(f"ScenarioPack has structural errors for {scenario_id}")
        runtime_rows, gold_rows = _projection_rows(root, scenario_id)
        projected_runtime, projected_gold = project_scenario_pack(pack)
        if runtime_rows != [item.to_dict() for item in projected_runtime]:
            raise ValueError(f"Pack projection/runtime mismatch for {scenario_id}")
        if gold_rows != [item.to_dict() for item in projected_gold]:
            raise ValueError(f"Pack projection/gold mismatch for {scenario_id}")
        _validate_runtime_projection(runtime_rows)
        case_ids = [str(row["case_id"]) for row in runtime_rows]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError(f"Duplicate runtime case ID in {scenario_id}")
        _validate_gold_projection(gold_rows, set(case_ids))
        runtime_case_ids.extend(case_ids)
        gold_case_ids.extend(str(row["case_id"]) for row in gold_rows)
        question_counts[scenario_id] = len(case_ids)

        source_pages: dict[str, int] = {}
        for source in pack["sources"]:
            pdf_path = resolve_source_pdf(scenario_dir, source, source_filename_map=source_filename_map)
            pdf_count += 1
            source_pages[str(source["source_id"])] = len(_pdf_pages(pdf_path))
        for query in pack["queries"]:
            for citation in query["reference_citations"]:
                page = citation.get("page")
                if page is None:
                    continue
                source_id = str(citation["source_id"])
                page_count = source_pages[source_id]
                valid = 1 <= int(page) <= page_count
                page_checks.append(
                    {
                        "case_id": query["query_id"],
                        "source_id": source_id,
                        "page": page,
                        "page_count": page_count,
                        "valid": valid,
                    }
                )
                if not valid:
                    raise ValueError(f"Reference page {page} does not exist in {source_id}")
    if len(runtime_case_ids) != len(set(runtime_case_ids)):
        raise ValueError("Duplicate runtime case ID across scenarios")
    if runtime_case_ids != gold_case_ids:
        raise ValueError("Combined runtime/gold case order mismatch")
    return {
        "status": "PASS",
        "scenario_ids": list(expected_scenarios),
        "question_counts": question_counts,
        "total_questions": len(runtime_case_ids),
        "pdf_source_count": pdf_count,
        "checksum_entry_count": checksum_result["entry_count"],
        "page_checks": page_checks,
        "runtime_gold_separated": True,
    }


def write_external_scenario_actual_inputs(
    package_root: str | Path,
    output_dir: str | Path,
    *,
    scenario_ids: tuple[str, ...] | None = None,
    source_filename_map: Mapping[str, str] | None = None,
    package_sha256: str | None = None,
    dataset_version: str = SCENARIO_DATASET_VERSION,
) -> dict[str, Any]:
    root = Path(package_root).resolve()
    destination = Path(output_dir).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"Refusing to mix external scenario output: {destination}")
    destination.mkdir(parents=True, exist_ok=True)

    verification = verify_external_scenario_package(
        root,
        scenario_ids=scenario_ids,
        source_filename_map=source_filename_map,
    )
    expected_scenarios = tuple(verification["scenario_ids"])
    package_identity = package_sha256 or sha256_file(root / "PACKAGE_MANIFEST.json")
    documents: list[CorpusDocument] = []
    fixtures: list[PolicyFixture] = []
    runtime_queries: list[dict[str, Any]] = []
    scorer_gold: list[dict[str, Any]] = []
    source_bindings: list[dict[str, Any]] = []

    for scenario_id in expected_scenarios:
        scenario_dir = root / "scenario_packs" / scenario_id
        pack = _read_json(scenario_dir / "scenario_pack.json")
        document_ids_by_source_id = {
            str(source["source_id"]): stable_document_id(package_identity, scenario_id, str(source["source_id"]))
            for source in pack["sources"]
        }
        projected_runtime, projected_gold = project_scenario_pack(pack, dataset_version=dataset_version)
        runtime_queries.extend(item.to_dict() for item in projected_runtime)
        scorer_gold.extend(
            _rewrite_gold_source_ids(
                item.to_dict(),
                scenario_id=scenario_id,
                document_ids_by_source_id=document_ids_by_source_id,
            )
            for item in projected_gold
        )
        fixture_access: dict[str, str] = {}
        denied: list[str] = []
        for source in pack["sources"]:
            pdf_path = resolve_source_pdf(scenario_dir, source, source_filename_map=source_filename_map)
            digest = sha256_file(pdf_path)
            pages = _pdf_pages(pdf_path)
            target_pdf = destination / "source_documents" / scenario_id / pdf_path.name
            target_pdf.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(pdf_path, target_pdf)
            source_id = str(source["source_id"])
            document_id = document_ids_by_source_id[source_id]
            access = _fixture_access(str(source["permission"]))
            if access is None:
                denied.append(document_id)
            else:
                fixture_access[document_id] = access
            relative_pdf = target_pdf.relative_to(destination).as_posix()
            documents.append(
                CorpusDocument(
                    document_id=document_id,
                    package_ref=scenario_id,
                    object_id=str(source["relation_key"]),
                    document_type=str(source["source_type"]),
                    original_filename=pdf_path.name,
                    pages=pages,
                    keywords=_keyword_values(pack, source, pdf_path.name, pages),
                    archived=False,
                    source_pdf_path=relative_pdf,
                    source_pdf_sha256=digest,
                    relation_key=str(source["relation_key"]),
                )
            )
            source_bindings.append(
                {
                    "scenario_id": scenario_id,
                    "source_id": source_id,
                    "document_id": document_id,
                    "original_filename": pdf_path.name,
                    "source_pdf_path": relative_pdf,
                    "source_pdf_sha256": digest,
                    "page_count": len(pages),
                    "permission": source["permission"],
                    "relation_key": source["relation_key"],
                    "source_type": source["source_type"],
                }
            )
        fixtures.append(
            PolicyFixture(
                fixture_id=f"{scenario_id}:source-permissions",
                access_by_document=fixture_access,
                prohibited_markers=tuple(denied),
            )
        )

    query_path = destination / "query_inputs.jsonl"
    gold_path = destination / "gold_annotations.jsonl"
    write_jsonl(query_path, runtime_queries)
    write_jsonl(gold_path, scorer_gold)
    corpus = {
        "schema_version": CORPUS_SCHEMA_VERSION,
        "metadata": {
            "dataset_version": dataset_version,
            "builder_version": EXTERNAL_CORPUS_BUILDER_VERSION,
            "external_package_name": root.name,
            "external_package_sha256": package_sha256,
            "scenario_ids": list(expected_scenarios),
            "synthetic": True,
            "gold_blind_runtime": True,
        },
        "documents": [item.to_dict() for item in documents],
        "policy_fixtures": [item.to_dict() for item in fixtures],
    }
    corpus_path = destination / "corpus_fixture.json"
    corpus_path.write_text(json.dumps(corpus, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "status": "READY_FOR_ACTUAL_PIPELINE",
        "builder_version": EXTERNAL_CORPUS_BUILDER_VERSION,
        "dataset_version": dataset_version,
        "package_root": str(root),
        "package_sha256": package_sha256,
        "scenario_ids": list(expected_scenarios),
        "query_count": len(runtime_queries),
        "gold_count": len(scorer_gold),
        "document_count": len(documents),
        "source_bindings": source_bindings,
        "query_input_path": query_path.name,
        "query_input_sha256": sha256_file(query_path),
        "gold_annotation_path": gold_path.name,
        "gold_annotation_sha256": sha256_file(gold_path),
        "corpus_fixture_path": corpus_path.name,
        "corpus_fixture_sha256": sha256_file(corpus_path),
        "verification": verification,
    }
    (destination / "binding_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def write_external_primary_contract_actual_inputs(
    package_root: str | Path,
    output_dir: str | Path,
    *,
    scenario_ids: tuple[str, ...] | None = None,
    source_filename_map: Mapping[str, str] | None = None,
    package_sha256: str | None = None,
    dataset_version: str | None = None,
) -> dict[str, Any]:
    root = Path(package_root).resolve()
    destination = Path(output_dir).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"Refusing to mix external scenario output: {destination}")
    destination.mkdir(parents=True, exist_ok=True)

    verification = verify_external_primary_contract_package(
        root,
        scenario_ids=scenario_ids,
        source_filename_map=source_filename_map,
    )
    expected_scenarios = tuple(verification["scenario_ids"])
    package_identity = package_sha256 or sha256_file(root / "PACKAGE_MANIFEST.json")
    resolved_dataset_version = dataset_version or str(_read_json(root / "PACKAGE_MANIFEST.json").get("dataset_version") or SCENARIO_DATASET_VERSION)
    paths = _primary_contract_paths(root)
    runtime_queries = _jsonl_rows(paths["runtime"])
    reference_rows = _jsonl_rows(paths["reference"])
    policy_rows = _read_json(paths["policy"])["policy_fixtures"]

    documents: list[CorpusDocument] = []
    fixtures: list[PolicyFixture] = []
    scorer_reference_rows: list[dict[str, Any]] = []
    source_bindings: list[dict[str, Any]] = []
    document_ids_by_scenario_source: dict[str, dict[str, str]] = {}

    for entry in _primary_scenario_entries(root, expected_scenarios):
        scenario_id = str(entry["scenario_id"])
        scenario_dir = _scenario_dir_from_entry(root, entry)
        pack = _scenario_pack_from_entry(root, entry)
        scenario_map = _scenario_source_filename_map(scenario_dir, source_filename_map)
        document_ids_by_source_id = {
            str(source["source_id"]): stable_document_id(package_identity, scenario_id, str(source["source_id"]))
            for source in pack["sources"]
        }
        document_ids_by_scenario_source[scenario_id] = document_ids_by_source_id
        for source in pack["sources"]:
            pdf_path = resolve_source_pdf(scenario_dir, source, source_filename_map=scenario_map)
            digest = sha256_file(pdf_path)
            pages = _pdf_pages(pdf_path)
            target_pdf = destination / "source_documents" / scenario_id / pdf_path.name
            target_pdf.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(pdf_path, target_pdf)
            source_id = str(source["source_id"])
            document_id = document_ids_by_source_id[source_id]
            relative_pdf = target_pdf.relative_to(destination).as_posix()
            documents.append(
                CorpusDocument(
                    document_id=document_id,
                    package_ref=scenario_id,
                    object_id=str(source["relation_key"]),
                    document_type=str(source["source_type"]),
                    original_filename=pdf_path.name,
                    pages=pages,
                    keywords=_keyword_values(pack, source, pdf_path.name, pages),
                    archived=False,
                    source_pdf_path=relative_pdf,
                    source_pdf_sha256=digest,
                    relation_key=str(source["relation_key"]),
                )
            )
            source_bindings.append(
                {
                    "scenario_id": scenario_id,
                    "source_id": source_id,
                    "document_id": document_id,
                    "original_filename": pdf_path.name,
                    "source_pdf_path": relative_pdf,
                    "source_pdf_sha256": digest,
                    "page_count": len(pages),
                    "permission": source["permission"],
                    "relation_key": source["relation_key"],
                    "source_type": source["source_type"],
                }
            )

    case_to_scenario = {str(row["case_id"]): str(row["corpus_package_ref"]) for row in runtime_queries}
    for row in reference_rows:
        scenario_id = case_to_scenario[str(row["case_id"])]
        scorer_reference_rows.append(
            _rewrite_gold_source_ids(
                row,
                scenario_id=scenario_id,
                document_ids_by_source_id=document_ids_by_scenario_source[scenario_id],
            )
        )
    for row in policy_rows:
        case_id = str(row["fixture_id"]).split(":", 1)[0]
        scenario_id = case_to_scenario[case_id]
        fixtures.append(
            _policy_fixture_from_contract(
                row,
                scenario_id=scenario_id,
                document_ids_by_source_id=document_ids_by_scenario_source[scenario_id],
            )
        )

    query_path = destination / "query_inputs.jsonl"
    reference_path = destination / "gold_annotations.jsonl"
    write_jsonl(query_path, runtime_queries)
    write_jsonl(reference_path, scorer_reference_rows)
    corpus = {
        "schema_version": CORPUS_SCHEMA_VERSION,
        "metadata": {
            "dataset_version": resolved_dataset_version,
            "builder_version": PRIMARY_CONTRACT_CORPUS_BUILDER_VERSION,
            "external_package_name": root.name,
            "external_package_sha256": package_sha256,
            "scenario_ids": list(expected_scenarios),
            "synthetic": True,
            "gold_blind_runtime": True,
            "primary_contracts_used": True,
        },
        "documents": [item.to_dict() for item in documents],
        "policy_fixtures": [item.to_dict() for item in fixtures],
    }
    corpus_path = destination / "corpus_fixture.json"
    corpus_path.write_text(json.dumps(corpus, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "status": "READY_FOR_ACTUAL_PIPELINE",
        "builder_version": PRIMARY_CONTRACT_CORPUS_BUILDER_VERSION,
        "dataset_version": resolved_dataset_version,
        "package_root": str(root),
        "package_sha256": package_sha256,
        "scenario_ids": list(expected_scenarios),
        "query_count": len(runtime_queries),
        "reference_annotation_count": len(scorer_reference_rows),
        "gold_count": len(scorer_reference_rows),
        "document_count": len(documents),
        "policy_fixture_count": len(fixtures),
        "source_bindings": source_bindings,
        "query_input_path": query_path.name,
        "query_input_sha256": sha256_file(query_path),
        "reference_annotation_path": reference_path.name,
        "reference_annotation_sha256": sha256_file(reference_path),
        "gold_annotation_path": reference_path.name,
        "gold_annotation_sha256": sha256_file(reference_path),
        "corpus_fixture_path": corpus_path.name,
        "corpus_fixture_sha256": sha256_file(corpus_path),
        "verification": verification,
    }
    (destination / "binding_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
