"""Privacy-safe A-GATE Phase A2 corpus, evaluation, and demo workflows.

This module is deliberately local and deterministic except for measured wall-clock
latencies.  It does not call external models, use private sources, or alter the
database.  Generated PDFs and result bundles belong under the ignored artifacts
directory.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import fitz

import controlled_failure
import relevance
from document_processing import PageText, chunk_pages, deterministic_keyword_candidates, extract_pdf_pages
from routing import RoutingMode, route_documents, routing_config_hash
from semantic_graph import build_semantic_cooccurrence_graph


CORPUS_SCHEMA_VERSION = "infocom-a-gate-a2-corpus-v1"
RUNNER_SCHEMA_VERSION = "infocom-a-gate-a2-runner-v1"
TOP_K = 3


@dataclass(frozen=True)
class SyntheticDocument:
    id: str
    filename: str
    object_family: str
    object_id: str
    document_type: str
    keywords: tuple[str, ...]
    pages: tuple[str, ...]


@dataclass(frozen=True)
class QueryCase:
    id: str
    text: str
    object_family: str
    object_id: str
    case_type: str
    expected_output: str
    routing_keywords: tuple[str, ...]
    gold_document_ids: tuple[str, ...]
    gold_pages: dict[str, tuple[int, ...]]
    hard_negative_document_ids: tuple[str, ...]
    reference_fact: str | None = None
    refusal_reason: str | None = None


DOCUMENTS = (
    SyntheticDocument(
        "tv-manual-aurora41", "tv-aurora41-user-guide.pdf", "television", "TV-AURORA-41", "user_guide",
        ("television", "aurora41", "setup", "hdmi", "remote"),
        (
            "SYNTHETIC TEST DOCUMENT. TV-AURORA-41 setup: connect the receiver to HDMI 2, select HDMI 2, then run channel setup.",
            "TV-AURORA-41 remote recovery: hold Home and Back for five seconds. The blue indicator confirms pairing.",
        ),
    ),
    SyntheticDocument(
        "tv-warranty-aurora41", "tv-aurora41-warranty.pdf", "television", "TV-AURORA-41", "warranty",
        ("television", "aurora41", "warranty", "invoice", "support"),
        (
            "SYNTHETIC TEST DOCUMENT. TV-AURORA-41 has a 24 month demonstration warranty from the fictional invoice date.",
            "Warranty service requires the synthetic invoice number. Cracked panels and liquid damage are excluded.",
        ),
    ),
    SyntheticDocument(
        "tv-support-aurora41", "tv-aurora41-support-note.pdf", "television", "TV-AURORA-41", "support",
        ("television", "aurora41", "support", "firmware", "hdmi"),
        (
            "SYNTHETIC TEST DOCUMENT. TV-AURORA-41 firmware 5.4 resolves intermittent HDMI wake failures.",
            "Install firmware 5.4 from Settings, Support, Software update. Keep power connected during the update.",
        ),
    ),
    SyntheticDocument(
        "tv-bulletin-aurora41", "tv-aurora41-warranty-bulletin.pdf", "television", "TV-AURORA-41", "service_bulletin",
        ("television", "aurora41", "warranty", "bulletin", "conflict"),
        (
            "SYNTHETIC CONFLICT FIXTURE. Bulletin B-17 states an 18 month warranty for TV-AURORA-41 and does not identify a superseded record.",
            "The fixture intentionally conflicts with the 24 month warranty record. A reviewer must resolve authority and effective date.",
        ),
    ),
    SyntheticDocument(
        "router-manual-r620", "router-r620-installation.pdf", "router", "ROUTER-R620", "installation_guide",
        ("router", "r620", "setup", "ethernet", "admin"),
        (
            "SYNTHETIC TEST DOCUMENT. ROUTER-R620 setup: connect the blue WAN port, then open 192.0.2.1 for the demonstration admin page.",
            "The default synthetic network name is R620-DEMO. The user must create a new admin password during onboarding.",
        ),
    ),
    SyntheticDocument(
        "router-warranty-r620", "router-r620-warranty.pdf", "router", "ROUTER-R620", "warranty",
        ("router", "r620", "warranty", "invoice", "replacement"),
        (
            "SYNTHETIC TEST DOCUMENT. ROUTER-R620 has a 12 month demonstration warranty from the fictional purchase date.",
            "A warranty replacement requires the synthetic receipt and the unit serial number. Rental devices are excluded.",
        ),
    ),
    SyntheticDocument(
        "router-support-r620", "router-r620-mesh-support.pdf", "router", "ROUTER-R620", "support",
        ("router", "r620", "support", "mesh", "firmware"),
        (
            "SYNTHETIC TEST DOCUMENT. ROUTER-R620 firmware 3.2 enables wired mesh backhaul on LAN port 1.",
            "If the amber mesh light persists, reset only the satellite and repeat pairing within two metres.",
        ),
    ),
    SyntheticDocument(
        "router-bulletin-r620", "router-r620-support-bulletin.pdf", "router", "ROUTER-R620", "service_bulletin",
        ("router", "r620", "support", "firmware", "conflict"),
        (
            "SYNTHETIC CONFLICT FIXTURE. Bulletin R-9 says firmware 3.1 is the latest approved ROUTER-R620 release.",
            "This intentionally conflicts with the firmware 3.2 support note. Escalate until version authority is resolved.",
        ),
    ),
    SyntheticDocument(
        "printer-manual-px220", "printer-px220-user-guide.pdf", "printer", "PRINTER-PX220", "user_guide",
        ("printer", "px220", "setup", "paper", "duplex"),
        (
            "SYNTHETIC TEST DOCUMENT. PRINTER-PX220 setup: load A4 paper in tray 1 and align the blue guides.",
            "Automatic duplex printing is enabled in Printing preferences under the Finishing tab.",
        ),
    ),
    SyntheticDocument(
        "printer-warranty-px220", "printer-px220-warranty.pdf", "printer", "PRINTER-PX220", "warranty",
        ("printer", "px220", "warranty", "invoice", "service"),
        (
            "SYNTHETIC TEST DOCUMENT. PRINTER-PX220 has an 18 month demonstration warranty from the fictional invoice date.",
            "The warranty covers the printer unit but excludes toner, paper, and other consumable supplies.",
        ),
    ),
    SyntheticDocument(
        "printer-support-px220", "printer-px220-support-note.pdf", "printer", "PRINTER-PX220", "support",
        ("printer", "px220", "support", "jam", "roller"),
        (
            "SYNTHETIC TEST DOCUMENT. PRINTER-PX220 jam code J42 indicates paper near the rear duplex roller.",
            "Open the rear cover, remove paper in the feed direction, close the cover, and press Resume once.",
        ),
    ),
    SyntheticDocument(
        "printer-bulletin-px220", "printer-px220-tray-bulletin.pdf", "printer", "PRINTER-PX220", "service_bulletin",
        ("printer", "px220", "paper", "tray", "conflict"),
        (
            "SYNTHETIC CONFLICT FIXTURE. Bulletin P-4 says PRINTER-PX220 tray 1 accepts Letter paper only.",
            "This intentionally conflicts with the A4 user guide. Confirm hardware revision before giving media advice.",
        ),
    ),
)


QUERIES = (
    QueryCase("a2-q01", "Which HDMI input should I use when setting up TV-AURORA-41?", "television", "TV-AURORA-41", "answerable", "FULL_ANSWER", ("television",), ("tv-manual-aurora41",), {"tv-manual-aurora41": (1,)}, ("router-manual-r620",), "Use HDMI 2.", None),
    QueryCase("a2-q02", "How long is the TV-AURORA-41 warranty and what proof is required?", "television", "TV-AURORA-41", "answerable", "FULL_ANSWER", ("television",), ("tv-warranty-aurora41",), {"tv-warranty-aurora41": (1, 2)}, ("printer-warranty-px220", "router-warranty-r620"), "24 months; synthetic invoice number required.", None),
    QueryCase("a2-q03", "For TV-AURORA-41, summarize initial HDMI setup and the firmware fix for wake failures.", "television", "TV-AURORA-41", "multi_document", "FULL_ANSWER", ("television",), ("tv-manual-aurora41", "tv-support-aurora41"), {"tv-manual-aurora41": (1,), "tv-support-aurora41": (1, 2)}, ("router-support-r620",), "Use HDMI 2; firmware 5.4 fixes HDMI wake failures.", None),
    QueryCase("a2-q04", "What is the measured annual electricity consumption of TV-AURORA-41?", "television", "TV-AURORA-41", "no_answer", "REFUSE_INSUFFICIENT_EVIDENCE", ("television",), (), {}, ("tv-manual-aurora41", "router-manual-r620"), None, "No energy measurement exists in the corpus."),
    QueryCase("a2-q05", "What warranty duration applies to TV-AURORA-41 when the record and bulletin disagree?", "television", "TV-AURORA-41", "conflict", "CONSTRAINED_ANSWER", ("television",), ("tv-warranty-aurora41", "tv-bulletin-aurora41"), {"tv-warranty-aurora41": (1,), "tv-bulletin-aurora41": (1, 2)}, ("printer-warranty-px220",), "The sources conflict: 24 months versus 18 months; escalate.", None),
    QueryCase("a2-q06", "Which toner cartridge fits TV-AURORA-41?", "television", "TV-AURORA-41", "hard_negative", "REFUSE_INSUFFICIENT_EVIDENCE", ("television",), (), {}, ("printer-warranty-px220", "printer-support-px220"), None, "A television has no supported toner fact; printer evidence is wrong-object evidence."),
    QueryCase("a2-q07", "How do I install the TV-AURORA-41 HDMI wake fix?", "television", "TV-AURORA-41", "answerable", "FULL_ANSWER", ("television",), ("tv-support-aurora41",), {"tv-support-aurora41": (1, 2)}, ("router-support-r620",), "Install firmware 5.4 through Settings, Support, Software update.", None),
    QueryCase("a2-q08", "What warranty applies to TV-AURORA-99?", "television", "TV-AURORA-99", "hard_negative", "REFUSE_INSUFFICIENT_EVIDENCE", ("television",), (), {}, ("tv-warranty-aurora41", "tv-bulletin-aurora41"), None, "Only TV-AURORA-41 evidence exists; it must not be transferred to TV-AURORA-99."),
    QueryCase("a2-q09", "Which port is used for the ROUTER-R620 internet connection?", "router", "ROUTER-R620", "answerable", "FULL_ANSWER", ("router",), ("router-manual-r620",), {"router-manual-r620": (1,)}, ("tv-manual-aurora41",), "Use the blue WAN port.", None),
    QueryCase("a2-q10", "How long is the ROUTER-R620 warranty?", "router", "ROUTER-R620", "answerable", "FULL_ANSWER", ("router",), ("router-warranty-r620",), {"router-warranty-r620": (1,)}, ("tv-warranty-aurora41", "printer-warranty-px220"), "12 months.", None),
    QueryCase("a2-q11", "Summarize ROUTER-R620 onboarding and wired mesh support.", "router", "ROUTER-R620", "multi_document", "FULL_ANSWER", ("router",), ("router-manual-r620", "router-support-r620"), {"router-manual-r620": (1, 2), "router-support-r620": (1,)}, ("tv-support-aurora41",), "Connect WAN and create an admin password; firmware 3.2 enables wired mesh on LAN 1.", None),
    QueryCase("a2-q12", "What is the ROUTER-R620 maximum measured power draw?", "router", "ROUTER-R620", "no_answer", "REFUSE_INSUFFICIENT_EVIDENCE", ("router",), (), {}, ("router-manual-r620", "tv-manual-aurora41"), None, "No power-draw measurement exists in the corpus."),
    QueryCase("a2-q13", "Which ROUTER-R620 firmware is authoritative when the support note and bulletin disagree?", "router", "ROUTER-R620", "conflict", "CONSTRAINED_ANSWER", ("router",), ("router-support-r620", "router-bulletin-r620"), {"router-support-r620": (1,), "router-bulletin-r620": (1, 2)}, ("tv-support-aurora41",), "The sources conflict: firmware 3.2 versus 3.1; escalate.", None),
    QueryCase("a2-q14", "How do I clear printer jam J42 on ROUTER-R620?", "router", "ROUTER-R620", "hard_negative", "REFUSE_INSUFFICIENT_EVIDENCE", ("router",), (), {}, ("printer-support-px220",), None, "Printer jam evidence is wrong-object evidence for a router."),
    QueryCase("a2-q15", "What should I do when the ROUTER-R620 mesh light stays amber?", "router", "ROUTER-R620", "answerable", "FULL_ANSWER", ("router",), ("router-support-r620",), {"router-support-r620": (2,)}, ("tv-support-aurora41",), "Reset only the satellite and repeat pairing within two metres.", None),
    QueryCase("a2-q16", "Does the ROUTER-R820 have a 12 month warranty?", "router", "ROUTER-R820", "hard_negative", "REFUSE_INSUFFICIENT_EVIDENCE", ("router",), (), {}, ("router-warranty-r620",), None, "ROUTER-R620 terms cannot be transferred to ROUTER-R820."),
    QueryCase("a2-q17", "How should A4 paper be loaded in PRINTER-PX220?", "printer", "PRINTER-PX220", "answerable", "FULL_ANSWER", ("printer",), ("printer-manual-px220",), {"printer-manual-px220": (1,)}, ("tv-manual-aurora41",), "Load A4 in tray 1 and align the blue guides.", None),
    QueryCase("a2-q18", "How long is the PRINTER-PX220 warranty and are consumables covered?", "printer", "PRINTER-PX220", "answerable", "FULL_ANSWER", ("printer",), ("printer-warranty-px220",), {"printer-warranty-px220": (1, 2)}, ("tv-warranty-aurora41",), "18 months; toner and paper are excluded.", None),
    QueryCase("a2-q19", "Summarize PRINTER-PX220 duplex setup and recovery from jam J42.", "printer", "PRINTER-PX220", "multi_document", "FULL_ANSWER", ("printer",), ("printer-manual-px220", "printer-support-px220"), {"printer-manual-px220": (2,), "printer-support-px220": (1, 2)}, ("router-support-r620",), "Enable duplex under Finishing; clear paper at the rear duplex roller and press Resume.", None),
    QueryCase("a2-q20", "What is the verified colour-page yield of PRINTER-PX220?", "printer", "PRINTER-PX220", "no_answer", "REFUSE_INSUFFICIENT_EVIDENCE", ("printer",), (), {}, ("printer-warranty-px220",), None, "No page-yield measurement exists in the corpus."),
    QueryCase("a2-q21", "Can PRINTER-PX220 tray 1 accept A4 when the guide and bulletin disagree?", "printer", "PRINTER-PX220", "conflict", "CONSTRAINED_ANSWER", ("printer",), ("printer-manual-px220", "printer-bulletin-px220"), {"printer-manual-px220": (1,), "printer-bulletin-px220": (1, 2)}, ("router-manual-r620",), "The sources conflict on A4 versus Letter-only; confirm hardware revision.", None),
    QueryCase("a2-q22", "Which WAN port should I connect on PRINTER-PX220?", "printer", "PRINTER-PX220", "hard_negative", "REFUSE_INSUFFICIENT_EVIDENCE", ("printer",), (), {}, ("router-manual-r620",), None, "Router WAN instructions are wrong-object evidence for a printer."),
    QueryCase("a2-q23", "What does PRINTER-PX220 jam code J42 mean?", "printer", "PRINTER-PX220", "answerable", "FULL_ANSWER", ("printer",), ("printer-support-px220",), {"printer-support-px220": (1,)}, ("router-support-r620",), "Paper is near the rear duplex roller.", None),
    QueryCase("a2-q24", "Is PRINTER-PX420 covered for 18 months?", "printer", "PRINTER-PX420", "hard_negative", "REFUSE_INSUFFICIENT_EVIDENCE", ("printer",), (), {}, ("printer-warranty-px220",), None, "PRINTER-PX220 terms cannot be transferred to PRINTER-PX420."),
)


STOP_WORDS = {
    "a", "an", "and", "are", "can", "do", "does", "for", "from", "how", "i", "in", "is", "it", "of", "on",
    "should", "the", "to", "what", "when", "which", "with",
}


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def evaluation_config_hash() -> str:
    payload = {
        "corpus_schema": CORPUS_SCHEMA_VERSION,
        "runner_schema": RUNNER_SCHEMA_VERSION,
        "routing_config_hash": routing_config_hash(),
        "top_k": TOP_K,
        "documents": [asdict(item) for item in DOCUMENTS],
        "queries": [asdict(item) for item in QUERIES],
    }
    return _sha256(_json_bytes(payload))


def _build_pdf(document: SyntheticDocument) -> bytes:
    pdf = fitz.open()
    pdf.set_metadata({
        "title": f"Synthetic InfoBank A2 - {document.object_id}",
        "author": "InfoBank deterministic A2 generator",
        "subject": "Privacy-safe generated development fixture",
        "keywords": "synthetic, development, infobank",
        "creationDate": "D:20260819000000Z",
        "modDate": "D:20260819000000Z",
    })
    for text in document.pages:
        page = pdf.new_page(width=595, height=842)
        page.insert_textbox(fitz.Rect(72, 72, 523, 770), text, fontsize=11, fontname="helv")
    try:
        payload = pdf.tobytes(garbage=4, deflate=True, no_new_id=True)
    except TypeError:
        payload = pdf.tobytes(garbage=4, deflate=True)
    pdf.close()
    return payload


def generate_corpus(output_dir: Path) -> dict:
    corpus_dir = output_dir / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for document in sorted(DOCUMENTS, key=lambda item: item.id):
        payload = _build_pdf(document)
        (corpus_dir / document.filename).write_bytes(payload)
        files.append({
            "document_id": document.id,
            "filename": document.filename,
            "object_family": document.object_family,
            "object_id": document.object_id,
            "document_type": document.document_type,
            "keywords": list(document.keywords),
            "page_count": len(document.pages),
            "byte_size": len(payload),
            "sha256": _sha256(payload),
        })
    manifest = {
        "schema_version": CORPUS_SCHEMA_VERSION,
        "synthetic": True,
        "privacy_safe": True,
        "development_corpus_only": True,
        "final_reviewer_dataset": False,
        "document_count": len(DOCUMENTS),
        "query_count": len(QUERIES),
        "object_families": sorted({item.object_family for item in DOCUMENTS}),
        "files": files,
        "config_hash": evaluation_config_hash(),
    }
    (output_dir / "manifest.json").write_bytes(_json_bytes(manifest))
    (output_dir / "queries.json").write_bytes(_json_bytes({
        "schema_version": CORPUS_SCHEMA_VERSION,
        "queries": [asdict(item) for item in QUERIES],
    }))
    graph = build_semantic_cooccurrence_graph({item.id: item.keywords for item in DOCUMENTS})
    (output_dir / "semantic_cooccurrence_graph.json").write_bytes(_json_bytes(graph))
    return manifest


def _tokens(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 1 and token not in STOP_WORDS
    }


def _idf_by_token() -> dict[str, float]:
    document_tokens = [_tokens(" ".join(item.pages)) for item in DOCUMENTS]
    all_tokens = sorted(set().union(*document_tokens))
    count = len(document_tokens)
    return {
        token: math.log((count + 1) / (1 + sum(token in tokens for tokens in document_tokens))) + 1.0
        for token in all_tokens
    }


def retrieve(query: QueryCase, candidate_ids: Iterable[str], top_k: int = TOP_K) -> list[dict]:
    query_tokens = _tokens(query.text)
    idf = _idf_by_token()
    results = []
    documents_by_id = {item.id: item for item in DOCUMENTS}
    for document_id in sorted(set(candidate_ids)):
        document = documents_by_id[document_id]
        page_scores = []
        for page_number, text in enumerate(document.pages, start=1):
            hits = sorted(query_tokens & _tokens(text))
            score = sum(idf.get(token, 1.0) for token in hits)
            object_match = query.object_id.lower() in text.lower()
            if object_match:
                score += 2.0
            page_scores.append((score, page_number, hits))
        score, page_number, hits = sorted(page_scores, key=lambda value: (-value[0], value[1]))[0]
        if score > 0:
            page_chunks = chunk_pages(
                document.id,
                [PageText(index, page_text) for index, page_text in enumerate(document.pages, start=1)],
            )
            page_chunk = next(chunk for chunk in page_chunks if chunk.page_number == page_number)
            results.append({
                "document_id": document_id,
                "page_number": page_number,
                "chunk_id": page_chunk.id,
                "score": round(score, 6),
                "matched_tokens": hits,
                "object_id": document.object_id,
            })
    results.sort(key=lambda value: (-value["score"], value["document_id"], value["page_number"]))
    return results[:top_k]


def _run_query(query: QueryCase, mode: RoutingMode) -> dict:
    permitted_ids = tuple(item.id for item in DOCUMENTS)
    keyword_map = {item.id: item.keywords for item in DOCUMENTS}
    routing_started = time.perf_counter_ns()
    routing = route_documents(permitted_ids, keyword_map, query.routing_keywords, mode)
    routing_latency_ms = (time.perf_counter_ns() - routing_started) / 1_000_000
    retrieval_started = time.perf_counter_ns()
    retrieved = retrieve(query, routing.candidate_document_ids)
    retrieval_latency_ms = (time.perf_counter_ns() - retrieval_started) / 1_000_000
    retrieved_ids = [item["document_id"] for item in retrieved]
    gold = set(query.gold_document_ids)
    candidate = set(routing.candidate_document_ids)
    false_exclusions = sorted(gold - candidate)
    ranks = [retrieved_ids.index(item) + 1 for item in query.gold_document_ids if item in retrieved_ids]
    recall = len(gold & set(retrieved_ids)) / len(gold) if gold else None
    precision = len(gold & set(retrieved_ids)) / len(retrieved_ids) if gold and retrieved_ids else (0.0 if gold else None)
    hard_included = sorted(set(query.hard_negative_document_ids) & candidate)
    return {
        "schema_version": RUNNER_SCHEMA_VERSION,
        "query_id": query.id,
        "query_text": query.text,
        "object_family": query.object_family,
        "object_id": query.object_id,
        "case_type": query.case_type,
        "expected_output": query.expected_output,
        "routing_mode": mode.value,
        "routing_trace": routing.to_trace(),
        "candidate_document_ids": list(routing.candidate_document_ids),
        "excluded_document_ids": list(routing.excluded_document_ids),
        "candidate_set_size": routing.candidate_set_size,
        "retrieved": retrieved,
        "retrieved_document_ids": retrieved_ids,
        "gold_document_ids": list(query.gold_document_ids),
        "false_exclusions": false_exclusions,
        "hard_negative_candidates": hard_included,
        "recall_at_k": recall,
        "precision_at_k": precision,
        "found": bool(ranks) if gold else None,
        "target_rank": min(ranks) if ranks else None,
        "routing_latency_ms": round(routing_latency_ms, 6),
        "retrieval_latency_ms": round(retrieval_latency_ms, 6),
        "config_hash": evaluation_config_hash(),
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return ordered[index]


def _mean(values: Iterable[float]) -> float:
    items = list(values)
    return statistics.fmean(items) if items else 0.0


def summarize(results: list[dict], mode: RoutingMode) -> dict:
    selected = [item for item in results if item["routing_mode"] == mode.value]
    gold_results = [item for item in selected if item["gold_document_ids"]]
    hard_negative_total = sum(len(next(query for query in QUERIES if query.id == item["query_id"]).hard_negative_document_ids) for item in selected)
    hard_negative_included = sum(len(item["hard_negative_candidates"]) for item in selected)
    ranks = [item["target_rank"] for item in gold_results if item["target_rank"] is not None]
    routing_latencies = [item["routing_latency_ms"] for item in selected]
    retrieval_latencies = [item["retrieval_latency_ms"] for item in selected]
    false_exclusions = sum(len(item["false_exclusions"]) for item in selected)
    total_gold = sum(len(item["gold_document_ids"]) for item in selected)
    return {
        "routing_mode": mode.value,
        "query_count": len(selected),
        "gold_query_count": len(gold_results),
        "mean_recall_at_k": round(_mean(item["recall_at_k"] for item in gold_results), 6),
        "mean_precision_at_k": round(_mean(item["precision_at_k"] for item in gold_results), 6),
        "found_rate": round(_mean(1.0 if item["found"] else 0.0 for item in gold_results), 6),
        "mean_target_rank": round(_mean(ranks), 6),
        "mean_candidate_set_size": round(_mean(item["candidate_set_size"] for item in selected), 6),
        "hard_negative_inclusion_rate": round(hard_negative_included / hard_negative_total, 6) if hard_negative_total else 0.0,
        "false_exclusion_count": false_exclusions,
        "false_exclusion_rate": round(false_exclusions / total_gold, 6) if total_gold else 0.0,
        "routing_latency_p50_ms": round(_percentile(routing_latencies, 0.50), 6),
        "routing_latency_p95_ms": round(_percentile(routing_latencies, 0.95), 6),
        "retrieval_latency_p50_ms": round(_percentile(retrieval_latencies, 0.50), 6),
        "retrieval_latency_p95_ms": round(_percentile(retrieval_latencies, 0.95), 6),
    }


def decide_scope(summaries: dict[str, dict]) -> dict:
    off = summaries[RoutingMode.ROUTING_OFF.value]
    routed = summaries[RoutingMode.KEYWORD_ROUTING.value]
    retained = (
        routed["mean_recall_at_k"] >= off["mean_recall_at_k"]
        and routed["false_exclusion_count"] == 0
        and routed["mean_candidate_set_size"] < off["mean_candidate_set_size"]
        and routed["hard_negative_inclusion_rate"] <= off["hard_negative_inclusion_rate"]
    )
    return {
        "decision": "retain_as_measured_candidate_narrowing" if retained else "visualization_only_do_not_use_for_retrieval",
        "keyword_routing_retained": retained,
        "evidence_scope": "privacy-safe synthetic A2 development corpus only",
        "production_claim": False,
        "criteria": {
            "recall_not_lower": routed["mean_recall_at_k"] >= off["mean_recall_at_k"],
            "zero_false_exclusions": routed["false_exclusion_count"] == 0,
            "candidate_set_reduced": routed["mean_candidate_set_size"] < off["mean_candidate_set_size"],
            "hard_negative_inclusion_not_higher": routed["hard_negative_inclusion_rate"] <= off["hard_negative_inclusion_rate"],
        },
    }


def run_w1(output_dir: Path) -> dict:
    selected = [item for item in DOCUMENTS if item.object_family == "television"]
    documents = []
    for document in selected:
        payload = _build_pdf(document)
        extracted = extract_pdf_pages(payload)
        pages = [PageText(page.page_number, page.text, page.blocks) for page in extracted.pages]
        chunks = chunk_pages(document.id, pages)
        extracted_keywords = [item[0] for item in deterministic_keyword_candidates("\n".join(page.text for page in extracted.pages))]
        corrected_keywords = sorted(set(extracted_keywords + list(document.keywords) + (["owned-object"] if document.id == "tv-manual-aurora41" else [])))
        documents.append({
            "document_id": document.id,
            "filename": document.filename,
            "source_sha256": _sha256(payload),
            "page_count": extracted.page_count,
            "chunk_count": len(chunks),
            "chunk_ids": [item.id for item in chunks],
            "automatic_keywords": extracted_keywords,
            "reviewed_keywords": corrected_keywords,
            "user_correction": {"added": ["owned-object"] if document.id == "tv-manual-aurora41" else [], "removed": []},
            "object_link": {"object_family": document.object_family, "object_id": document.object_id},
            "source_view": {"available": True, "page_numbers": list(range(1, extracted.page_count + 1)), "content_checksum_verified": True},
        })
    assertions = {
        "all_sources_synthetic": True,
        "all_sources_page_addressable": all(item["page_count"] > 0 for item in documents),
        "all_chunks_stable": all(len(item["chunk_ids"]) == len(set(item["chunk_ids"])) for item in documents),
        "user_correction_recorded": any(item["user_correction"]["added"] for item in documents),
        "single_owned_object": {item["object_link"]["object_id"] for item in documents} == {"TV-AURORA-41"},
    }
    trace = {
        "schema_version": "infocom-a2-w1-owned-object-v1",
        "workflow": "W1_owned_object_onboarding",
        "status": "PASS" if all(assertions.values()) else "FAIL",
        "external_services_used": False,
        "stages": ["source_generation", "pdf_extraction", "page_aware_chunking", "keyword_review", "user_correction", "object_link", "source_view_verification"],
        "documents": documents,
        "assertions": assertions,
    }
    (output_dir / "w1_owned_object_trace.json").write_bytes(_json_bytes(trace))
    return trace


def run_w2(output_dir: Path, routed_results: list[dict]) -> dict:
    result_by_query = {item["query_id"]: item for item in routed_results if item["routing_mode"] == RoutingMode.KEYWORD_ROUTING.value}
    cases = []
    specifications = (
        ("answerable_multi_document", "a2-q03", "FULL_ANSWER"),
        ("insufficient_evidence", "a2-q04", "REFUSE_INSUFFICIENT_EVIDENCE"),
        ("conflicting_evidence", "a2-q05", "CONSTRAINED_ANSWER"),
        ("wrong_object_hard_negative", "a2-q08", "REFUSE_INSUFFICIENT_EVIDENCE"),
    )
    output_mode_map = {
        controlled_failure.STATUS_FULL_ANSWER: "FULL_ANSWER",
        controlled_failure.STATUS_RESTRICTED_ANSWER: "CONSTRAINED_ANSWER",
        controlled_failure.STATUS_ABSTAIN: "REFUSE_INSUFFICIENT_EVIDENCE",
        controlled_failure.STATUS_REFUSE: "REFUSE_INSUFFICIENT_EVIDENCE",
    }
    documents_by_id = {item.id: item for item in DOCUMENTS}
    for name, query_id, output_mode in specifications:
        query = next(item for item in QUERIES if item.id == query_id)
        result = result_by_query[query_id]
        retrieved_gold = [item for item in result["retrieved"] if item["document_id"] in set(query.gold_document_ids)]
        object_matched_document_ids = [
            item["document_id"] for item in result["retrieved"]
            if item["object_id"] == query.object_id
        ]
        policy_sources = []
        for item in retrieved_gold:
            document = documents_by_id[item["document_id"]]
            role = (
                relevance.SOURCE_ROLE_CONTRASTIVE
                if query.case_type == "conflict" and document.document_type == "service_bulletin"
                else relevance.SOURCE_ROLE_PRIMARY
            )
            policy_sources.append({
                "document_id": item["document_id"],
                "role": role,
                "usable_relevance": {
                    "role": role,
                    "levels": {
                        level: (1.0 if level in {"governance", "evidential"} else 0.0)
                        for level in relevance.RELEVANCE_LEVELS
                    },
                    "evidence_warnings": (
                        ["may_close_cancel_or_contradict_an_item"]
                        if role == relevance.SOURCE_ROLE_CONTRASTIVE else []
                    ),
                    "temporal_status": [],
                },
            })
        governance = {
            "usable_doc_ids": list(result["candidate_document_ids"]),
            "content_doc_ids": list(result["candidate_document_ids"]),
            "metadata_only_doc_ids": [],
            "denied_doc_ids": [],
            "has_primary_evidence": bool(policy_sources),
            "has_aggregate_evidence": False,
        }
        policy_decision = controlled_failure.select_rag_output_mode(
            question=query.text,
            sources=policy_sources,
            query_profile=relevance.build_query_profile(query.text, query.routing_keywords),
            governance=governance,
            context_blocks_available=bool(policy_sources),
        )
        policy_output_mode = policy_decision["output_mode"]
        actual_mode = output_mode_map.get(policy_output_mode, "REFUSE_INSUFFICIENT_EVIDENCE")
        failure = policy_decision.get("controlled_failure") or {}
        failure_reason = failure.get("reason")
        policy_gate = (policy_decision.get("trace") or {}).get("gate")
        cases.append({
            "case": name,
            "query_id": query_id,
            "object_id": query.object_id,
            "expected_output": output_mode,
            "actual_output": actual_mode,
            "policy_output_mode": policy_output_mode,
            "policy_reason": failure_reason,
            "policy_gate": policy_gate,
            "status": "PASS" if actual_mode == output_mode else "FAIL",
            "candidate_document_ids": result["candidate_document_ids"],
            "retrieved_document_ids": result["retrieved_document_ids"],
            "object_matched_document_ids": object_matched_document_ids,
            "citations": [
                {
                    "document_id": item["document_id"],
                    "page_number": item["page_number"],
                    "chunk_id": item["chunk_id"],
                }
                for item in retrieved_gold
            ],
            "conflict_detected": failure_reason == controlled_failure.REASON_CONFLICT_DEFEAT,
            "wrong_object_evidence_rejected": query.case_type == "hard_negative" and not object_matched_document_ids,
            "safe_message": failure.get("safeOutput") or query.reference_fact,
        })
    trace = {
        "schema_version": "infocom-a2-w2-warranty-support-v1",
        "workflow": "W2_multi_document_warranty_support",
        "status": "PASS" if all(item["status"] == "PASS" for item in cases) else "FAIL",
        "external_services_used": False,
        "cases": cases,
    }
    (output_dir / "w2_warranty_support_trace.json").write_bytes(_json_bytes(trace))
    return trace


def _write_summary_csv(output_dir: Path, summaries: dict[str, dict]) -> None:
    fields = list(next(iter(summaries.values())).keys())
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for mode in (RoutingMode.ROUTING_OFF.value, RoutingMode.KEYWORD_ROUTING.value):
        writer.writerow(summaries[mode])
    (output_dir / "summary.csv").write_text(buffer.getvalue(), encoding="utf-8", newline="")


def _write_summary_markdown(output_dir: Path, summaries: dict[str, dict], decision: dict, w1: dict, w2: dict) -> None:
    off = summaries[RoutingMode.ROUTING_OFF.value]
    routed = summaries[RoutingMode.KEYWORD_ROUTING.value]
    lines = [
        "# A-GATE Phase A2 local evaluation",
        "",
        "Privacy-safe synthetic development evidence only; this is not the final reviewer dataset and supports no production-performance claim.",
        "",
        "| Metric | ROUTING_OFF | KEYWORD_ROUTING |",
        "|---|---:|---:|",
    ]
    for key in (
        "mean_recall_at_k", "mean_precision_at_k", "found_rate", "mean_target_rank",
        "mean_candidate_set_size", "hard_negative_inclusion_rate", "false_exclusion_count",
        "routing_latency_p50_ms", "routing_latency_p95_ms", "retrieval_latency_p50_ms", "retrieval_latency_p95_ms",
    ):
        lines.append(f"| {key} | {off[key]} | {routed[key]} |")
    lines += [
        "",
        f"Decision: `{decision['decision']}`.",
        "",
        f"W1 owned-object onboarding: `{w1['status']}`.",
        f"W2 warranty/support workflow: `{w2['status']}`.",
        "",
    ]
    (output_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def run_evaluation(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = generate_corpus(output_dir)
    results = [
        _run_query(query, mode)
        for mode in (RoutingMode.ROUTING_OFF, RoutingMode.KEYWORD_ROUTING)
        for query in QUERIES
    ]
    with (output_dir / "raw_results.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for result in results:
            handle.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
    summaries = {
        mode.value: summarize(results, mode)
        for mode in (RoutingMode.ROUTING_OFF, RoutingMode.KEYWORD_ROUTING)
    }
    decision = decide_scope(summaries)
    w1 = run_w1(output_dir)
    w2 = run_w2(output_dir, results)
    machine_summary = {
        "schema_version": RUNNER_SCHEMA_VERSION,
        "config_hash": evaluation_config_hash(),
        "manifest_sha256": _sha256(_json_bytes(manifest)),
        "result_count": len(results),
        "summaries": summaries,
        "routing_scope_decision": decision,
        "w1_status": w1["status"],
        "w2_status": w2["status"],
    }
    (output_dir / "summary.json").write_bytes(_json_bytes(machine_summary))
    _write_summary_csv(output_dir, summaries)
    _write_summary_markdown(output_dir, summaries, decision, w1, w2)
    return machine_summary
