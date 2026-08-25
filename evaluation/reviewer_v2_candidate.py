"""Build the non-frozen reviewer-v2 pre-freeze candidate and automated QA."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import fitz

from .manifest import stable_hash


DATASET_VERSION = "reviewer-v2-pre-freeze-candidate-v1"
BUILDER_VERSION = "infocom-pre-freeze-builder-v1"
NO_HEALTH_TERMS = {
    "patient", "diagnosis", "diagnostic", "medical", "medicine", "medication", "treatment",
    "therapy", "hospital", "disease", "symptom", "clinical", "healthcare",
}
QUERY_CLASSES = (
    "direct_answer", "multi_document", "no_answer", "conflict", "citation", "hard_negative",
    "Metadata", "Deny", "Aggregate", "mixed_permission", "purpose", "expiry",
    "grant_revoke_transfer", "stale_index", "controlled_failure",
)
DOCUMENT_TYPES = (
    "manual_user_guide", "quick_start_specification", "warranty",
    "synthetic_purchase_service_record", "thematic_distractor",
)


@dataclass(frozen=True)
class PackageDefinition:
    package_id: str
    category: str
    object_family: str
    object_id: str
    split: str
    accent: str
    warranty_months: int
    setup_fact: str
    support_fact: str


PACKAGES = (
    PackageDefinition("pkg-tv-aurora41", "television", "television-compact", "TV-AURORA-41", "development", "blue", 24, "Connect the receiver to HDMI 2.", "Firmware 5.4 resolves HDMI wake failures."),
    PackageDefinition("pkg-router-r620", "router", "router-home", "ROUTER-R620", "development", "amber", 12, "Connect the blue WAN port.", "Firmware 3.2 enables wired mesh on LAN 1."),
    PackageDefinition("pkg-printer-px220", "printer", "printer-office", "PRINTER-PX220", "development", "green", 18, "Load A4 paper in tray 1.", "Jam J42 is cleared at the rear duplex roller."),
    PackageDefinition("pkg-tv-nebula55", "television", "television-large", "TV-NEBULA-55", "candidate_holdout", "silver", 30, "Attach the receiver to HDMI 3.", "Firmware 7.1 corrects audio return delay."),
    PackageDefinition("pkg-router-r830", "router", "router-mesh", "ROUTER-R830", "candidate_holdout", "violet", 18, "Connect fibre handoff to the red WAN port.", "Firmware 4.8 restores satellite roaming."),
    PackageDefinition("pkg-printer-lx500", "printer", "printer-studio", "PRINTER-LX500", "candidate_holdout", "orange", 24, "Load photo stock in the rear feeder.", "Code F17 is cleared by reseating the rear feed guide."),
)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _document_id(package: PackageDefinition, document_type: str) -> str:
    return f"{package.package_id}-{document_type.replace('_', '-')}"


def _document_pages(package: PackageDefinition, document_type: str) -> tuple[str, str]:
    header = f"SYNTHETIC REVIEWER-V2 CANDIDATE. Object {package.object_id}."
    if document_type == "manual_user_guide":
        return (f"{header} Setup instruction: {package.setup_fact}", f"{header} Support instruction: {package.support_fact}")
    if document_type == "quick_start_specification":
        return (f"{header} Quick start uses the {package.accent} labelled connection.", f"{header} Specification code is QS-{package.object_id}.")
    if document_type == "warranty":
        return (f"{header} Demonstration warranty duration is {package.warranty_months} months.", f"{header} A synthetic invoice code is required; consumable or accidental damage is excluded.")
    if document_type == "synthetic_purchase_service_record":
        return (f"{header} Fictional purchase record code DEMO-{package.object_id}; no person is identified.", f"{header} Fictional service record confirms one routine inspection and no unresolved repair.")
    return (
        f"{header} Thematic distractor discusses generic {package.category} packaging but contains no instructions for {package.object_id}.",
        f"{header} An unverified package insert claims a {max(1, package.warranty_months - 6)} month warranty, "
        f"contradicting the authoritative warranty. It must not override the manual, specification, warranty, or service record.",
    )


def _build_pdf(package: PackageDefinition, document_type: str) -> bytes:
    pdf = fitz.open()
    pdf.set_metadata({
        "title": f"{package.object_id} {document_type}",
        "author": "InfoBank deterministic reviewer-v2 builder",
        "subject": "Generated synthetic pre-freeze candidate",
        "keywords": "synthetic, reviewer-v2, pre-freeze",
        "creationDate": "D:20260819000000Z",
        "modDate": "D:20260819000000Z",
    })
    for text in _document_pages(package, document_type):
        page = pdf.new_page(width=595, height=842)
        page.insert_textbox(fitz.Rect(72, 72, 523, 770), text, fontsize=11, fontname="helv")
    try:
        payload = pdf.tobytes(garbage=4, deflate=True, no_new_id=True)
    except TypeError:
        payload = pdf.tobytes(garbage=4, deflate=True)
    pdf.close()
    return payload


def build_gold_queries() -> list[dict[str, Any]]:
    cases = []
    for package in PACKAGES:
        manual = _document_id(package, "manual_user_guide")
        quick = _document_id(package, "quick_start_specification")
        warranty = _document_id(package, "warranty")
        purchase = _document_id(package, "synthetic_purchase_service_record")
        distractor = _document_id(package, "thematic_distractor")
        template_prefix = "dev-template" if package.split == "development" else "holdout-pattern"
        for index, query_class in enumerate(QUERY_CLASSES, start=1):
            if query_class == "direct_answer":
                gold, pages, output, reason, answer, role = (manual,), {manual: [1]}, "FULL_ANSWER", "supported", package.setup_fact, "primary"
            elif query_class == "multi_document":
                gold, pages, output, reason, answer, role = (manual, quick), {manual: [1], quick: [1]}, "FULL_ANSWER", "supported_multi", f"{package.setup_fact} Use the {package.accent} labelled connection.", "primary"
            elif query_class == "citation":
                gold, pages, output, reason, answer, role = (warranty,), {warranty: [1, 2]}, "FULL_ANSWER", "supported", f"{package.warranty_months} months; synthetic invoice code required.", "primary"
            elif query_class == "conflict":
                gold, pages, output, reason, answer, role = (warranty, distractor), {warranty: [1], distractor: [2]}, "REFUSE_CONFLICT", "conflicting_evidence", None, "contrastive"
            elif query_class == "no_answer":
                gold, pages, output, reason, answer, role = (), {}, "REFUSE_INSUFFICIENT_EVIDENCE", "insufficient_evidence", None, "governance-excluded"
            elif query_class == "hard_negative":
                gold, pages, output, reason, answer, role = (), {}, "REFUSE_NO_MATCH", "wrong_object", None, "governance-excluded"
            elif query_class == "Metadata":
                gold, pages, output, reason, answer, role = (manual,), {}, "METADATA_ONLY", "metadata_only", f"Object metadata: {package.object_id}.", "contextual"
            elif query_class == "Aggregate":
                gold, pages, output, reason, answer, role = (purchase,), {}, "AGGREGATE_RESULT", "aggregate_threshold_satisfied", "Aggregate result only; no individual record content.", "aggregate-only"
            elif query_class in {"Deny", "purpose", "expiry", "stale_index"}:
                reason_map = {"Deny": "governance", "purpose": "purpose_mismatch", "expiry": "expired_policy", "stale_index": "stale_index_denied"}
                gold, pages, output, reason, answer, role = (manual,), {}, "REFUSE_PERMISSION", reason_map[query_class], None, "governance-excluded"
            elif query_class == "mixed_permission":
                gold, pages, output, reason, answer, role = (manual,), {manual: [1]}, "CONSTRAINED_ANSWER", "mixed_policy", package.setup_fact, "primary"
            elif query_class == "grant_revoke_transfer":
                gold, pages, output, reason, answer, role = (purchase,), {}, "REFUSE_PERMISSION", "permission_lifecycle_expected", None, "governance-excluded"
            else:
                gold, pages, output, reason, answer, role = (), {}, "CLARIFICATION", "underspecified_question", None, "governance-excluded"
            wording = (
                f"For {package.object_id}, evaluate the {query_class.replace('_', ' ')} evidence."
                if package.split == "development"
                else f"Assess {query_class.replace('_', ' ')} for the candidate device {package.object_id}."
            )
            required_sources = (
                list(gold)
                if output not in {
                    "CLARIFICATION",
                    "REFUSE_PERMISSION",
                    "REFUSE_INSUFFICIENT_EVIDENCE",
                    "REFUSE_NO_MATCH",
                    "REFUSE_AGGREGATION_THRESHOLD",
                }
                else []
            )
            reference_citations = [
                {"source_id": source_id, "page": page, "message_id": None, "record_id": None}
                for source_id, page_numbers in pages.items()
                for page in page_numbers
            ]
            cases.append({
                "query_id": f"rv2-{package.package_id}-{index:02d}", "query_class": query_class,
                "query": wording, "expected_output_class": output, "gold_document_ids": list(gold),
                "gold_page_or_message_ranges": pages, "required_sources": required_sources,
                "reference_citations": reference_citations, "reference_answer": answer,
                "refusal_reason": reason if output.startswith("REFUSE_") or output == "CLARIFICATION" else None,
                "reason_code": reason,
                "evidence_role": role, "action_status": "NOT_APPLICABLE", "split": package.split,
                "category": package.category, "object_family": package.object_family,
                "template_family": f"{template_prefix}-{query_class.lower()}",
                "document_package": package.package_id, "source_type": "generated_synthetic",
            })
    return cases


def build_permission_counterfactuals() -> list[dict[str, Any]]:
    groups = []
    for index in range(60):
        package = PACKAGES[index % len(PACKAGES)]
        document_id = _document_id(package, "manual_user_guide")
        retrieval = [document_id, _document_id(package, "thematic_distractor")]
        variants = []
        for mode in ("Full", "Aggregate", "Metadata", "Deny"):
            variants.append({
                "variant_id": f"pcg-{index:03d}-{mode.lower()}", "policy": mode,
                "expected_output_class": {
                    "Full": "FULL_ANSWER", "Aggregate": "REFUSE_AGGREGATION_THRESHOLD",
                    "Metadata": "METADATA_ONLY", "Deny": "REFUSE_PERMISSION",
                }[mode],
                "document_ids": retrieval, "retrieved_ids": retrieval,
                "query": f"What is the setup instruction for {package.object_id}?",
            })
        groups.append({"group_id": f"pcg-{index:03d}", "constant_fields": ["document_ids", "retrieved_ids", "query"], "varied_field": "policy", "variants": variants})
    return groups


def build_browser_counterfactuals() -> list[dict[str, Any]]:
    return [
        {
            "case_id": f"browser-only-{index:03d}", "source_type": "BrowserHistory",
            "url": f"https://example.invalid/synthetic-comparison/{index:03d}",
            "title": f"Synthetic device task comparison {index:03d}",
            "semantically_related_to_task": True, "expected_action_count": 0,
            "expected_status": "CONTEXTUAL_ONLY_NOT_ACTION",
        }
        for index in range(60)
    ]


def build_synthetic_mail_candidate() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    threads = []
    for index in range(120):
        outcome = ("OPEN", "CLOSED_COMPLETED", "CLOSED_CANCELLED", "SUPERSEDED")[index % 4]
        thread_id = f"synthetic-mail-thread-{index:03d}"
        threads.append({
            "thread_id": thread_id, "source": "generated_synthetic_not_mailex",
            "licence": "generated_synthetic_project_license",
            "messages": [
                {"message_id": f"{thread_id}-request", "timestamp": "2026-08-01T09:00:00Z", "sender": "requester@example.invalid", "recipients": ["worker@example.invalid"], "subject": f"Synthetic package {index:03d}", "body": f"Please review synthetic package {index:03d}."},
                {"message_id": f"{thread_id}-followup", "timestamp": "2026-08-01T10:00:00Z", "sender": "worker@example.invalid", "recipients": ["requester@example.invalid"], "subject": f"Synthetic package {index:03d}", "body": {"OPEN": "Status update: work is in progress.", "CLOSED_COMPLETED": "Completed and delivered the synthetic package.", "CLOSED_CANCELLED": "The synthetic request was cancelled.", "SUPERSEDED": "The synthetic request was superseded by a revised request."}[outcome]},
            ],
            "preannotation": {"action_status": outcome, "requires_human_validation": True},
            "action_candidate": {
                "normalized_action_key": f"review-synthetic-package-{index:03d}",
                "request_message_id": f"{thread_id}-request",
                "terminal_message_id": None if outcome == "OPEN" else f"{thread_id}-followup",
                "requester": "requester@example.invalid",
                "assignee": "worker@example.invalid",
                "link_signals": ["thread", "participants", "temporal", "semantic-secondary"],
            },
        })
    assignments = [
        {
            "thread_id": item["thread_id"], "primary_annotator": "PENDING_ASSIGNMENT",
            "second_annotation_required": index < 24,
            "second_annotator": "PENDING_ASSIGNMENT" if index < 24 else "NOT_REQUIRED_IN_20_PERCENT_SAMPLE",
            "adjudication_status": "PENDING_HUMAN_ANNOTATION",
        }
        for index, item in enumerate(threads)
    ]
    return threads, assignments


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _near_duplicate_report(queries: list[dict[str, Any]]) -> dict[str, Any]:
    exact: list[tuple[str, str]] = []
    near: list[dict[str, Any]] = []
    for left_index, left in enumerate(queries):
        left_tokens = set(_normalize(left["query"]).split())
        for right in queries[left_index + 1:]:
            right_tokens = set(_normalize(right["query"]).split())
            if _normalize(left["query"]) == _normalize(right["query"]):
                exact.append((left["query_id"], right["query_id"]))
            similarity = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
            if similarity >= 0.80:
                near.append({"left": left["query_id"], "right": right["query_id"], "jaccard": round(similarity, 6), "cross_split": left["split"] != right["split"]})
    return {"method": "normalized-token-jaccard-v1", "threshold": 0.80, "exact_duplicate_pairs": exact, "near_duplicate_pairs": near, "cross_split_near_duplicate_count": sum(item["cross_split"] for item in near)}


def _no_health_scan(values: Any) -> list[dict[str, str]]:
    serialized = json.dumps(values, ensure_ascii=False).lower()
    return [{"term": term, "action": "EXCLUDED"} for term in sorted(NO_HEALTH_TERMS) if re.search(rf"\b{re.escape(term)}\b", serialized)]


def validate_candidate(candidate_dir: Path) -> dict[str, Any]:
    """Run deterministic structural and integrity checks without human claims."""
    manifest = json.loads((candidate_dir / "dataset_manifest.json").read_text(encoding="utf-8"))
    sources = json.loads((candidate_dir / "source_manifest.json").read_text(encoding="utf-8"))["files"]
    queries = json.loads((candidate_dir / "gold_queries.json").read_text(encoding="utf-8"))["queries"]
    permissions = json.loads((candidate_dir / "permission_counterfactuals.json").read_text(encoding="utf-8"))["groups"]
    browser = json.loads((candidate_dir / "browser_counterfactuals.json").read_text(encoding="utf-8"))["cases"]
    threads = json.loads((candidate_dir / "mail_candidate" / "threads.json").read_text(encoding="utf-8"))["threads"]
    checks: dict[str, bool] = {
        "candidate_not_frozen": manifest["status"] == "READY_FOR_HUMAN_QA" and not manifest["final"] and not manifest["frozen"],
        "six_complete_packages": manifest["package_count"] == 6 and manifest["documents_per_package"] == 5,
        "three_categories_two_each": len({item["category"] for item in sources}) == 3
        and all(sum(item["category"] == category for item in sources) == 10 for category in {item["category"] for item in sources}),
        "television_present": any(item["category"] == "television" for item in sources),
        "balanced_ninety_queries": len(queries) == 90
        and all(sum(item["query_class"] == query_class for item in queries) == 6 for query_class in QUERY_CLASSES),
        "query_required_fields": all({
            "query_id", "query_class", "expected_output_class", "gold_document_ids",
            "gold_page_or_message_ranges", "required_sources", "reference_citations",
            "reference_answer", "refusal_reason", "reason_code",
            "evidence_role", "split", "template_family", "object_family",
        } <= set(item) and bool(item["reference_answer"] or item["refusal_reason"]) for item in queries),
        "fifty_permission_groups": len(permissions) >= 50,
        "permission_facts_constant": all(
            len(group["variants"]) == 4
            and len({json.dumps({key: variant[key] for key in ("document_ids", "retrieved_ids", "query")}, sort_keys=True) for variant in group["variants"]}) == 1
            and {variant["policy"] for variant in group["variants"]} == {"Full", "Aggregate", "Metadata", "Deny"}
            for group in permissions
        ),
        "fifty_browser_only": len(browser) >= 50 and all(item["expected_action_count"] == 0 for item in browser),
        "hundred_mail_threads": len(threads) >= 100,
        "mail_thread_preserved": all(len(item["messages"]) >= 2 and item["action_candidate"]["request_message_id"] == item["messages"][0]["message_id"] for item in threads),
        "split_disjoint": all(manifest["split_report"][key] for key in ("object_family_disjoint", "document_package_disjoint", "template_family_disjoint")),
        "no_health_automated": manifest["automated_no_health_hit_count"] == 0,
        "no_external_or_personal_sources": manifest["licence_report"]["external_source_count"] == 0,
        "human_work_pending": not manifest["human_annotation_complete"] and not manifest["adjudication_complete"]
        and not manifest["manual_citation_audit_complete"] and not manifest["manual_no_health_signoff_complete"],
    }
    checksum_rows = list(csv.DictReader((candidate_dir / "checksums.csv").open(encoding="utf-8", newline="")))
    checks["checksums_match"] = all(
        (candidate_dir / item["relative_path"]).is_file()
        and _sha256_bytes((candidate_dir / item["relative_path"]).read_bytes()) == item["sha256"]
        for item in checksum_rows
    )
    checks["source_checksums_match"] = all(
        _sha256_bytes((candidate_dir / item["relative_path"]).read_bytes()) == item["sha256"] for item in sources
    )
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "counts": {
        "packages": manifest["package_count"], "documents": len(sources), "queries": len(queries),
        "permission_groups": len(permissions), "browser_only": len(browser), "mail_threads": len(threads),
        "second_annotation_assignments": manifest["second_annotation_assignment_count"],
    }}


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buffer.getvalue(), encoding="utf-8", newline="")


def build_candidate(output_dir: Path) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Refusing to mix a new candidate with existing artifacts: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    package_dir = output_dir / "packages"
    package_dir.mkdir(parents=True, exist_ok=True)
    files = []
    transformation_log = []
    for package in PACKAGES:
        destination = package_dir / package.package_id
        destination.mkdir(parents=True, exist_ok=True)
        for document_type in DOCUMENT_TYPES:
            payload = _build_pdf(package, document_type)
            filename = f"{document_type}.pdf"
            (destination / filename).write_bytes(payload)
            files.append({
                "document_id": _document_id(package, document_type), "package_id": package.package_id,
                "category": package.category, "object_family": package.object_family, "object_id": package.object_id,
                "split": package.split, "document_type": document_type,
                "relative_path": f"packages/{package.package_id}/{filename}", "page_count": 2,
                "sha256": _sha256_bytes(payload), "source_type": "generated_synthetic",
                "licence": "generated_synthetic_project_license", "redistribution_status": "permitted_with_repository_license",
            })
            transformation_log.append({"document_id": _document_id(package, document_type), "operation": "render_fixed_text_to_pdf", "builder_version": BUILDER_VERSION})

    queries = build_gold_queries()
    permissions = build_permission_counterfactuals()
    browser = build_browser_counterfactuals()
    threads, assignments = build_synthetic_mail_candidate()
    health_hits = _no_health_scan({"files": files, "queries": queries, "permissions": permissions, "browser": browser, "threads": threads})
    near_duplicates = _near_duplicate_report(queries)
    development = [package for package in PACKAGES if package.split == "development"]
    holdout = [package for package in PACKAGES if package.split == "candidate_holdout"]
    split_report = {
        "object_family_disjoint": not ({p.object_family for p in development} & {p.object_family for p in holdout}),
        "document_package_disjoint": not ({p.package_id for p in development} & {p.package_id for p in holdout}),
        "template_family_disjoint": not ({q["template_family"] for q in queries if q["split"] == "development"} & {q["template_family"] for q in queries if q["split"] == "candidate_holdout"}),
        "development_packages": [p.package_id for p in development],
        "candidate_holdout_packages": [p.package_id for p in holdout],
    }
    licence_report = {
        "generated_source_count": len(files) + len(threads), "external_source_count": 0,
        "mailex_used_in_this_synthetic_build": False, "unresolved_redistribution_cases": [],
        "repository_license_reference": "LICENSE",
        "note": "This synthetic builder does not read MailEx. The separate local MailEx candidate has unresolved licence status.",
    }
    manifest = {
        "dataset_version": DATASET_VERSION, "builder_version": BUILDER_VERSION,
        "status": "READY_FOR_HUMAN_QA", "final": False, "frozen": False,
        "package_count": len(PACKAGES), "category_count": len({p.category for p in PACKAGES}),
        "documents_per_package": len(DOCUMENT_TYPES), "document_count": len(files),
        "gold_query_count": len(queries), "permission_counterfactual_group_count": len(permissions),
        "permission_variant_count": sum(len(group["variants"]) for group in permissions),
        "browser_only_case_count": len(browser), "mail_candidate_thread_count": len(threads),
        "second_annotation_assignment_count": sum(item["second_annotation_required"] for item in assignments),
        "split_report": split_report, "near_duplicate_report": near_duplicates,
        "automated_no_health_hit_count": len(health_hits), "licence_report": licence_report,
        "source_config_hash": stable_hash([asdict(package) for package in PACKAGES]),
        "query_config_hash": stable_hash(queries), "code_version": BUILDER_VERSION,
        "human_annotation_complete": False, "adjudication_complete": False,
        "manual_citation_audit_complete": False, "manual_no_health_signoff_complete": False,
    }
    (output_dir / "dataset_manifest.json").write_bytes(_json_bytes(manifest))
    (output_dir / "source_manifest.json").write_bytes(_json_bytes({"files": files}))
    (output_dir / "gold_queries.json").write_bytes(_json_bytes({"queries": queries}))
    (output_dir / "permission_counterfactuals.json").write_bytes(_json_bytes({"groups": permissions}))
    (output_dir / "browser_counterfactuals.json").write_bytes(_json_bytes({"cases": browser}))
    (output_dir / "near_duplicate_report.json").write_bytes(_json_bytes(near_duplicates))
    (output_dir / "split_report.json").write_bytes(_json_bytes(split_report))
    (output_dir / "licence_redistribution_report.json").write_bytes(_json_bytes(licence_report))
    (output_dir / "transformation_log.json").write_bytes(_json_bytes({"transformations": transformation_log}))
    (output_dir / "no_health_exclusion_log.json").write_bytes(_json_bytes({"excluded": health_hits}))
    (output_dir / "automated_no_health_report.json").write_bytes(_json_bytes({"status": "PASS" if not health_hits else "FAIL", "hits": health_hits}))
    (output_dir / "manual_no_health_signoff_template.md").write_text(
        "# Manual no-health sign-off\n\nStatus: PENDING_HUMAN_SIGNOFF\n\nReviewer: __________\n\nDate: __________\n\nDecision: __________\n\nNotes: __________\n",
        encoding="utf-8",
    )
    mail_dir = output_dir / "mail_candidate"
    mail_dir.mkdir(parents=True, exist_ok=True)
    (mail_dir / "threads.json").write_bytes(_json_bytes({"threads": threads}))
    _write_csv(mail_dir / "annotation_assignments.csv", assignments, list(assignments[0]))
    _write_csv(mail_dir / "adjudication.csv", [
        {"thread_id": item["thread_id"], "annotator_a": "", "annotator_b": "", "disagreement": "", "adjudicator": "", "final_label": "", "status": "PENDING_HUMAN_ANNOTATION"}
        for item in threads
    ], ["thread_id", "annotator_a", "annotator_b", "disagreement", "adjudicator", "final_label", "status"])
    (mail_dir / "provenance_manifest.json").write_bytes(_json_bytes({
        "source": "generated_synthetic_not_mailex", "thread_count": len(threads),
        "licence": "generated_synthetic_project_license", "raw_mailex_committed": False,
        "human_validation_complete": False, "second_annotation_required_count": 24,
    }))
    checksum_rows = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != "checksums.csv":
            checksum_rows.append({"relative_path": path.relative_to(output_dir).as_posix(), "sha256": _sha256_bytes(path.read_bytes())})
    _write_csv(output_dir / "checksums.csv", checksum_rows, ["relative_path", "sha256"])
    automated_qa = validate_candidate(output_dir)
    (output_dir / "automated_qa_report.json").write_bytes(_json_bytes(automated_qa))
    checksum_rows = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != "checksums.csv":
            checksum_rows.append({"relative_path": path.relative_to(output_dir).as_posix(), "sha256": _sha256_bytes(path.read_bytes())})
    _write_csv(output_dir / "checksums.csv", checksum_rows, ["relative_path", "sha256"])
    final_qa = validate_candidate(output_dir)
    if final_qa["status"] != "PASS":
        raise RuntimeError(f"Automated reviewer-v2 candidate QA failed: {final_qa}")
    return manifest
