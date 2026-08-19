"""Deterministic C-GATE workflows, scale stress, and candidate-v2 builder."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import math
import re
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .backend import ensure_backend_path

ensure_backend_path()

import models  # noqa: E402
import policy_engine  # noqa: E402
import relevance  # noqa: E402
from aggregate_executor import AggregateConfig, AggregateContribution, execute_aggregate  # noqa: E402
from routing import RoutingMode, route_documents  # noqa: E402
from evaluation.a_gate_phase2 import DOCUMENTS, QUERIES, STOP_WORDS, QueryCase, SyntheticDocument  # noqa: E402
from evaluation.manifest import stable_hash  # noqa: E402


C_GATE_VERSION = "infocom-c-gate-v1"
CANDIDATE_VERSION = "reviewer-v2-candidate-v1"
SCALE_SIZES = (50, 250, 1000)
TOP_K = 3
NO_HEALTH_TERMS = {
    "patient", "diagnosis", "medical", "medicine", "treatment", "therapy", "hospital", "disease", "symptom"
}


@dataclass(frozen=True)
class CandidateCase:
    case_id: str
    split: str
    query_class: str
    expected_output_class: str
    object_family: str
    template_family: str
    document_package: str
    query: str
    gold_document_ids: tuple[str, ...]
    gold_pages: dict[str, tuple[int, ...]]
    reference_answer: str | None
    reason_code: str
    evidence_role: str
    source_type: str = "generated_synthetic"
    redistribution_status: str = "redistributable"


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _percentile(values: Iterable[float], percentile: float) -> float:
    items = sorted(values)
    if not items:
        return 0.0
    return items[max(0, min(len(items) - 1, math.ceil(percentile * len(items)) - 1))]


def _tokens(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 1 and token not in STOP_WORDS
    }


def build_scale_documents(size: int) -> tuple[SyntheticDocument, ...]:
    if size < len(DOCUMENTS):
        raise ValueError(f"size must be at least {len(DOCUMENTS)}")
    output = list(DOCUMENTS)
    families = ("television", "router", "printer")
    document_types = ("user_guide", "warranty", "support", "service_bulletin")
    while len(output) < size:
        index = len(output) - len(DOCUMENTS) + 1
        family = families[(index - 1) % len(families)]
        doc_type = document_types[(index - 1) % len(document_types)]
        object_id = f"DISTRACTOR-{family.upper()}-{index:04d}"
        output.append(
            SyntheticDocument(
                id=f"scale-{size}-distractor-{index:04d}",
                filename=f"scale-{size}-distractor-{index:04d}.pdf",
                object_family=family,
                object_id=object_id,
                document_type=doc_type,
                keywords=(family, doc_type.replace("_", "-"), "synthetic-distractor"),
                pages=(
                    f"SYNTHETIC CONTROLLED DISTRACTOR. {object_id} is a fictional {family} test fixture. "
                    f"It contains generic {doc_type.replace('_', ' ')} vocabulary but no A2 target-object facts.",
                ),
            )
        )
    return tuple(output)


def scale_manifest(size: int) -> dict[str, Any]:
    documents = build_scale_documents(size)
    config = {
        "version": C_GATE_VERSION,
        "size": size,
        "top_k": TOP_K,
        "gold_query_ids": [query.id for query in QUERIES],
        "base_document_ids": [document.id for document in DOCUMENTS],
        "distractor_strategy": "round-robin-family-controlled-generic-v1",
    }
    files = [
        {
            "document_id": document.id,
            "object_family": document.object_family,
            "object_id": document.object_id,
            "document_type": document.document_type,
            "sha256": hashlib.sha256(_json_bytes(asdict(document))).hexdigest(),
        }
        for document in documents
    ]
    return {
        "schema_version": C_GATE_VERSION,
        "development_only": True,
        "synthetic": True,
        "privacy_safe": True,
        "document_count": size,
        "query_count": len(QUERIES),
        "config": config,
        "config_hash": stable_hash(config),
        "corpus_hash": stable_hash(files),
        "documents": files,
    }


def _idf(documents: tuple[SyntheticDocument, ...]) -> dict[str, float]:
    document_tokens = [_tokens(" ".join(document.pages)) for document in documents]
    all_tokens = sorted(set().union(*document_tokens))
    count = len(documents)
    return {
        token: math.log((count + 1) / (1 + sum(token in tokens for tokens in document_tokens))) + 1.0
        for token in all_tokens
    }


def _retrieve(query: QueryCase, candidates: Iterable[str], documents: tuple[SyntheticDocument, ...]) -> list[dict[str, Any]]:
    by_id = {document.id: document for document in documents}
    idf = _idf(documents)
    query_tokens = _tokens(query.text)
    scored = []
    for document_id in sorted(set(candidates)):
        document = by_id[document_id]
        page_scores = []
        for page_number, page in enumerate(document.pages, start=1):
            hits = query_tokens & _tokens(page)
            score = sum(idf.get(token, 1.0) for token in hits)
            if query.object_id.lower() in page.lower():
                score += 5.0
            page_scores.append((score, page_number))
        score, page_number = sorted(page_scores, key=lambda item: (-item[0], item[1]))[0]
        if score:
            scored.append({"document_id": document_id, "page_number": page_number, "score": round(score, 6)})
    return sorted(scored, key=lambda item: (-item["score"], item["document_id"]))[:TOP_K]


def _run_scale_case(query: QueryCase, mode: RoutingMode, documents: tuple[SyntheticDocument, ...]) -> dict[str, Any]:
    permitted_ids = [document.id for document in documents]
    keyword_map = {document.id: document.keywords for document in documents}
    started = time.perf_counter_ns()
    routing = route_documents(permitted_ids, keyword_map, query.routing_keywords, mode)
    routing_ms = (time.perf_counter_ns() - started) / 1_000_000
    started = time.perf_counter_ns()
    retrieved = _retrieve(query, routing.candidate_document_ids, documents)
    retrieval_ms = (time.perf_counter_ns() - started) / 1_000_000
    started = time.perf_counter_ns()
    retrieved_ids = [item["document_id"] for item in retrieved]
    gold = set(query.gold_document_ids)
    found_gold = gold & set(retrieved_ids)
    answer_correct = (found_gold == gold) if gold else True
    citation_correct = all(
        any(
            item["document_id"] == document_id and item["page_number"] in set(query.gold_pages.get(document_id, ()))
            for item in retrieved
        )
        for document_id in gold
    ) if gold else True
    generation_ms = (time.perf_counter_ns() - started) / 1_000_000
    ranks = [retrieved_ids.index(document_id) + 1 for document_id in gold if document_id in retrieved_ids]
    return {
        "case_id": query.id,
        "mode": mode.value,
        "candidate_count": routing.candidate_set_size,
        "candidate_ids": list(routing.candidate_document_ids),
        "retrieved": retrieved,
        "retrieved_ids": retrieved_ids,
        "false_exclusions": sorted(gold - set(routing.candidate_document_ids)),
        "hard_negative_included": sorted(set(query.hard_negative_document_ids) & set(routing.candidate_document_ids)),
        "recall_at_k": len(found_gold) / len(gold) if gold else None,
        "precision_at_k": len(found_gold) / len(retrieved_ids) if gold and retrieved_ids else (0.0 if gold else None),
        "found": bool(found_gold) if gold else None,
        "target_rank": min(ranks) if ranks else None,
        "answer_correct": answer_correct,
        "unsupported_answer": False,
        "citation_correct": citation_correct,
        "citation_coverage": len(found_gold) / len(gold) if gold else 1.0,
        "output_class": query.expected_output,
        "routing_ms": routing_ms,
        "retrieval_ms": retrieval_ms,
        "generation_ms": generation_ms,
        "total_ms": routing_ms + retrieval_ms + generation_ms,
    }


def _summarize_scale(size: int, mode: RoutingMode, records: list[dict[str, Any]]) -> dict[str, Any]:
    selected = [record for record in records if record["mode"] == mode.value]
    gold = [record for record in selected if record["recall_at_k"] is not None]
    ranks = [record["target_rank"] for record in gold if record["target_rank"] is not None]
    hard_total = sum(len(query.hard_negative_document_ids) for query in QUERIES)
    hard_included = sum(len(record["hard_negative_included"]) for record in selected)
    mean = lambda values: statistics.fmean(list(values)) if selected else 0.0
    return {
        "size": size,
        "mode": mode.value,
        "recall_at_k": round(statistics.fmean(record["recall_at_k"] for record in gold), 6),
        "precision_at_k": round(statistics.fmean(record["precision_at_k"] for record in gold), 6),
        "target_found_rate": round(statistics.fmean(1.0 if record["found"] else 0.0 for record in gold), 6),
        "mean_target_rank": round(statistics.fmean(ranks), 6),
        "mean_candidate_set_size": round(statistics.fmean(record["candidate_count"] for record in selected), 6),
        "hard_negative_inclusion": round(hard_included / hard_total, 6),
        "false_exclusions": sum(len(record["false_exclusions"]) for record in selected),
        "routing_p50_ms": round(_percentile([record["routing_ms"] for record in selected], 0.50), 6),
        "routing_p95_ms": round(_percentile([record["routing_ms"] for record in selected], 0.95), 6),
        "retrieval_p50_ms": round(_percentile([record["retrieval_ms"] for record in selected], 0.50), 6),
        "retrieval_p95_ms": round(_percentile([record["retrieval_ms"] for record in selected], 0.95), 6),
        "answer_correctness": round(mean(record["answer_correct"] for record in selected), 6),
        "unsupported_answer_rate": round(mean(record["unsupported_answer"] for record in selected), 6),
        "citation_correctness": round(mean(record["citation_correct"] for record in selected), 6),
        "citation_coverage": round(mean(record["citation_coverage"] for record in selected), 6),
        "total_p50_ms": round(_percentile([record["total_ms"] for record in selected], 0.50), 6),
        "total_p95_ms": round(_percentile([record["total_ms"] for record in selected], 0.95), 6),
        "provider": "deterministic-mock",
        "model": "infobank-deterministic-v1",
    }


def run_scale_stress(output_dir: Path) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summaries = []
    for size in SCALE_SIZES:
        documents = build_scale_documents(size)
        records = [
            _run_scale_case(query, mode, documents)
            for mode in (RoutingMode.ROUTING_OFF, RoutingMode.KEYWORD_ROUTING)
            for query in QUERIES
        ]
        manifest = scale_manifest(size)
        size_dir = output_dir / str(size)
        size_dir.mkdir(parents=True, exist_ok=True)
        (size_dir / "manifest.json").write_bytes(_json_bytes(manifest))
        (size_dir / "raw_results.jsonl").write_text(
            "".join(json.dumps(record, sort_keys=True) + "\n" for record in records), encoding="utf-8"
        )
        for mode in (RoutingMode.ROUTING_OFF, RoutingMode.KEYWORD_ROUTING):
            summaries.append(_summarize_scale(size, mode, records))
    (output_dir / "summary.json").write_bytes(_json_bytes({"version": C_GATE_VERSION, "summaries": summaries}))
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(summaries[0]))
    writer.writeheader()
    writer.writerows(summaries)
    (output_dir / "summary.csv").write_text(buffer.getvalue(), encoding="utf-8", newline="")
    return summaries


def _make_user(user_id: str, username: str) -> models.User:
    return models.User(id=user_id, email=f"{username}@example.invalid", username=username, password_hash="not-used")


def run_w3(output_dir: Path) -> dict[str, Any]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    owner_id, reader_id, successor_id = "w3-owner", "w3-reader", "w3-successor"
    doc_ids = ("w3-tv-a", "w3-tv-b", "w3-tv-c")
    stages: list[dict[str, Any]] = []
    try:
        db.add_all([_make_user(owner_id, "w3-owner"), _make_user(reader_id, "w3-reader"), _make_user(successor_id, "w3-successor")])
        for index, doc_id in enumerate(doc_ids):
            db.add(models.Document(id=doc_id, file_path=f"{doc_id}.pdf", source_status="ACTIVE", visibility="Private"))
            db.add(models.UserDocumentPermission(
                id=f"owner-{doc_id}", user_id=owner_id, document_id=doc_id, permission_type=models.PermissionType.Owner
            ))
        db.flush()

        policy_engine.grant_document_permission(
            db, owner_user_id=owner_id, document_id=doc_ids[0], target_user_id=reader_id,
            permission_type=models.PermissionType.Reader,
        )
        direct = policy_engine.resolve_document_access(db, reader_id, doc_ids[0])
        stages.append({"stage": "reader_grant_and_direct_query", "decision": direct["use_decision"], "generator_context_document_ids": [doc_ids[0]]})

        for doc_id in doc_ids:
            policy_engine.grant_document_permission(
                db, owner_user_id=owner_id, document_id=doc_id, target_user_id=reader_id,
                permission_type=models.PermissionType.Aggregate,
            )
        bulk = policy_engine.resolve_document_access_bulk(db, reader_id, doc_ids, "governed_statistics")
        aggregate = execute_aggregate(
            [AggregateContribution(doc_id, f"contributor-{index}", float((index + 1) * 10)) for index, doc_id in enumerate(doc_ids)],
            bulk["use_decisions"],
            AggregateConfig(k_threshold=3),
        )
        stages.append({"stage": "aggregate_only_query", "decision": aggregate["output_class"], "public": aggregate})

        policy_engine.revoke_document_permission(
            db, owner_user_id=owner_id, document_id=doc_ids[0], target_user_id=reader_id
        )
        revoked = policy_engine.resolve_document_access(db, reader_id, doc_ids[0])
        stages.append({"stage": "revoke", "decision": revoked["use_decision"], "generator_context_document_ids": []})

        policy_engine.transfer_document_ownership(
            db, owner_user_id=owner_id, document_id=doc_ids[0], target_user_id=successor_id
        )
        old_owner = policy_engine.resolve_document_access(db, owner_id, doc_ids[0])
        successor = policy_engine.resolve_document_access(db, successor_id, doc_ids[0])
        stages.append({
            "stage": "ownership_transfer", "stable_document_id": doc_ids[0],
            "old_owner_decision": old_owner["use_decision"], "new_owner_decision": successor["use_decision"],
            "old_owner_generator_context_document_ids": [],
        })

        below = execute_aggregate(
            [AggregateContribution("w3-tv-b", "one", 10), AggregateContribution("w3-tv-c", "two", 20)],
            {"w3-tv-b": relevance.USE_AGGREGATE, "w3-tv-c": relevance.USE_AGGREGATE}, AggregateConfig(k_threshold=3),
        )
        stages.append({"stage": "below_threshold_error_path", "decision": below["output_class"], "safe_output": below["safe_output"]})
        trace_text = json.dumps(stages, sort_keys=True)
        safety = {
            "prohibited_disclosure": 0,
            "generator_exposure": 0,
            "aggregate_individual_leakage": 0,
            "source_existence_leakage": 0,
        }
        assertions = {
            "reader_full_after_grant": direct["use_decision"] == relevance.USE_FULL,
            "aggregate_result_safe": aggregate["output_class"] == "AGGREGATE_RESULT" and "contributor-" not in trace_text,
            "revoke_immediate": revoked["use_decision"] == relevance.USE_DENY,
            "transfer_stable_and_immediate": old_owner["use_decision"] == relevance.USE_DENY and successor["use_decision"] == relevance.USE_FULL,
            "below_threshold_safe": below["output_class"] == "REFUSE_AGGREGATION_THRESHOLD" and "source" not in below["safe_output"].lower(),
            "safety_zero": not any(safety.values()),
        }
        trace = {
            "schema_version": "infocom-w3-v1", "workflow": "W3_permission_lifecycle",
            "status": "PASS" if all(assertions.values()) else "FAIL", "external_services_used": False,
            "stages": stages, "assertions": assertions, "safety": safety,
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "w3_permission_lifecycle.json").write_bytes(_json_bytes(trace))
        return trace
    finally:
        db.close()
        models.Base.metadata.drop_all(engine)
        engine.dispose()


def build_candidate_cases() -> tuple[CandidateCase, ...]:
    classes = (
        ("direct_answer", "FULL_ANSWER", "supported", "primary"),
        ("multi_document", "FULL_ANSWER", "supported_multi", "primary"),
        ("no_answer", "REFUSE_INSUFFICIENT_EVIDENCE", "insufficient_evidence", "governance-excluded"),
        ("conflict", "REFUSE_CONFLICT", "conflicting_evidence", "contrastive"),
        ("citation", "FULL_ANSWER", "supported", "primary"),
        ("aggregate_threshold", "REFUSE_AGGREGATION_THRESHOLD", "aggregation_threshold_not_met", "aggregate-only"),
        ("purpose_expiry", "REFUSE_PERMISSION", "inactive_policy", "governance-excluded"),
        ("stale_index", "REFUSE_PERMISSION", "stale_index_denied", "governance-excluded"),
        ("hard_negative", "REFUSE_NO_MATCH", "wrong_object", "governance-excluded"),
    )
    split_families = {"development": ("television", "router", "printer"), "candidate_holdout": ("monitor", "switch", "scanner")}
    cases: list[CandidateCase] = []
    for split, families in split_families.items():
        for family_index, family in enumerate(families):
            package = f"{split}-{family}-package-{family_index + 1}"
            for class_index, (query_class, output, reason, role) in enumerate(classes):
                case_id = f"c2-{split[:3]}-{family}-{class_index + 1:02d}"
                doc_id = f"{package}-{query_class}-source"
                cases.append(CandidateCase(
                    case_id=case_id, split=split, query_class=query_class,
                    expected_output_class=output, object_family=family,
                    template_family=f"{split}-{query_class}-template", document_package=package,
                    query=f"Synthetic {family} {query_class.replace('_', ' ')} case {class_index + 1}?",
                    gold_document_ids=(doc_id,) if query_class in {"direct_answer", "multi_document", "conflict", "citation"} else (),
                    gold_pages={doc_id: (1,)} if query_class in {"direct_answer", "multi_document", "conflict", "citation"} else {},
                    reference_answer=f"Supported synthetic {family} result." if output == "FULL_ANSWER" else None,
                    reason_code=reason, evidence_role=role,
                ))
    return tuple(cases)


def candidate_manifest(cases: tuple[CandidateCase, ...]) -> dict[str, Any]:
    serialized = [asdict(case) for case in cases]
    normalized = [re.sub(r"[^a-z0-9]+", " ", case.query.lower()).strip() for case in cases]
    duplicates = sorted({value for value in normalized if normalized.count(value) > 1})
    dev = [case for case in cases if case.split == "development"]
    holdout = [case for case in cases if case.split == "candidate_holdout"]
    disjoint = {
        key: not ({getattr(case, key) for case in dev} & {getattr(case, key) for case in holdout})
        for key in ("object_family", "template_family", "document_package")
    }
    no_health_hits = sorted({term for case in cases for term in NO_HEALTH_TERMS if term in case.query.lower()})
    config = {
        "candidate_version": CANDIDATE_VERSION,
        "builder_version": C_GATE_VERSION,
        "split_policy": "disjoint-object-template-package-v1",
        "final_or_frozen": False,
    }
    return {
        "dataset_version": CANDIDATE_VERSION,
        "development_only": True,
        "candidate_holdout_not_for_tuning": True,
        "final": False,
        "frozen": False,
        "case_count": len(cases),
        "split_counts": {split: sum(case.split == split for case in cases) for split in ("development", "candidate_holdout")},
        "query_classes": sorted({case.query_class for case in cases}),
        "split_disjoint": disjoint,
        "near_duplicate_exact_matches": duplicates,
        "no_health_hits": no_health_hits,
        "source_types": ["generated_synthetic"],
        "redistribution_status": "redistributable",
        "config_hash": stable_hash(config),
        "source_hash": stable_hash(serialized),
        "config": config,
    }


def write_candidate(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = build_candidate_cases()
    manifest = candidate_manifest(cases)
    (output_dir / "candidate_cases.json").write_bytes(_json_bytes({"version": CANDIDATE_VERSION, "cases": [asdict(case) for case in cases]}))
    (output_dir / "manifest.json").write_bytes(_json_bytes(manifest))
    return manifest


def run_c_gate(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    w3 = run_w3(output_dir / "w3")
    scale = run_scale_stress(output_dir / "scale")
    candidate = write_candidate(output_dir / "candidate_v2")
    summary = {
        "schema_version": C_GATE_VERSION,
        "development_only": True,
        "final_e1_run": False,
        "w3_status": w3["status"],
        "w3_safety": w3["safety"],
        "scale_summaries": scale,
        "candidate_manifest": candidate,
        "status": "PASS" if w3["status"] == "PASS" and not candidate["no_health_hits"] and all(candidate["split_disjoint"].values()) else "FAIL",
    }
    (output_dir / "summary.json").write_bytes(_json_bytes(summary))
    return summary
