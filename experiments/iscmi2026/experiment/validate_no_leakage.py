from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any

from experiment_core import (
    ANSWER_TYPES,
    BASELINE_DOCUMENT_KEYS,
    CONDITIONS,
    EXPERIMENT_DIR,
    FORBIDDEN_GOLD_FIELDS,
    build_oracle_documents,
    build_prompt,
    contexts_for_condition,
    deterministic_mock_embedding,
    ensure_no_forbidden_fields,
    inference_question,
    load_benchmark,
    load_configs,
    parse_corrected_packet,
    parse_model_output,
    read_jsonl,
    resolve_packet_dir,
    sha256_file,
)


SEMANTIC_TASK_KEYS = {
    "task_id",
    "final_state",
    "last_transition",
    "transition",
    "resulting_state",
    "requester",
    "actor",
    "deadline",
    "waiting_for",
    "blocked_by",
    "closure_reason",
    "history",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def assert_prompt_has_no_target_field_labels(system_prompt: str, user_prompt: str) -> None:
    combined = system_prompt + "\n" + user_prompt
    for field in FORBIDDEN_GOLD_FIELDS:
        pattern = rf"(?i)(?:\"|')?{re.escape(field)}(?:\"|')?\s*:"
        if re.search(pattern, combined):
            fail(f"Forbidden target field label appears in model prompt: {field}")


def validate_packet_hashes(packet_dir: Path, manifest: dict[str, Any]) -> None:
    expected = manifest["pilot_packet"]["file_sha256"]
    for file_name, expected_hash in expected.items():
        actual = sha256_file(packet_dir / "threads" / file_name)
        if actual != expected_hash:
            fail(f"Corrected packet hash mismatch for {file_name}")


def validate_corpora(benchmark: dict[str, Any], packet_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    validate_packet_hashes(packet_dir, benchmark["manifest"])
    emails = parse_corrected_packet(packet_dir, benchmark["evidence"])
    oracle = build_oracle_documents(benchmark["histories"], benchmark["snapshots"])
    ensure_no_forbidden_fields(emails, "baseline_corpus")
    ensure_no_forbidden_fields(oracle, "oracle_corpus")
    for document in emails:
        if set(document) != BASELINE_DOCUMENT_KEYS:
            fail(f"Unexpected baseline document keys in {document['document_id']}")
        leaked_keys = set(document) & SEMANTIC_TASK_KEYS
        if leaked_keys:
            fail(f"Semantic task keys in baseline document {document['document_id']}: {sorted(leaked_keys)}")
        if "### Original MailEx annotations" in document["text"]:
            fail(f"Original MailEx annotations entered baseline document {document['document_id']}")
    required_oracle_keys = {
        "task_id",
        "final_state",
        "history",
        "evidence_message_ids",
        "thread_id",
    }
    if not oracle or any(not required_oracle_keys <= set(document) for document in oracle):
        fail("Oracle corpus does not contain the required task representation")
    if len(emails) != 195:
        fail(f"Expected 195 corrected email documents, found {len(emails)}")
    if len(oracle) != 236:
        fail(f"Expected 236 oracle task documents, found {len(oracle)}")
    return emails, oracle


def validate_target_independence(
    questions: list[dict[str, Any]],
    emails: list[dict[str, Any]],
    oracle: list[dict[str, Any]],
    configs: dict[str, dict[str, Any]],
) -> None:
    email_embeddings = {
        row["document_id"]: deterministic_mock_embedding(row["text"]) for row in emails
    }
    for raw_question in questions:
        inference = inference_question(raw_question)
        mutated = copy.deepcopy(raw_question)
        mutated["gold_answer"] = "FORBIDDEN_SENTINEL_72d1a8"
        mutated["gold_structured"] = {
            "expected_answer": "FORBIDDEN_SENTINEL_0f649e",
            "score": 999,
            "is_correct": True,
        }
        if inference_question(mutated) != inference:
            fail(f"Inference projection depends on benchmark target for {raw_question['question_id']}")
        question_embedding = deterministic_mock_embedding(inference["question"])
        for condition in CONDITIONS:
            contexts, _scores = contexts_for_condition(
                condition=condition,
                question=inference,
                email_documents=emails,
                oracle_documents=oracle,
                question_embedding=question_embedding,
                document_embeddings=email_embeddings,
                config=configs[condition],
            )
            ensure_no_forbidden_fields(contexts, f"{condition}.contexts")
            original_prompt = build_prompt(inference["question"], contexts)
            mutated_prompt = build_prompt(inference_question(mutated)["question"], contexts)
            if original_prompt != mutated_prompt:
                fail(f"Prompt changes when gold is mutated for {raw_question['question_id']}")
            assert_prompt_has_no_target_field_labels(*original_prompt)


def validate_evidence(benchmark: dict[str, Any]) -> None:
    message_ids = {row["message_id"] for row in benchmark["evidence"]}
    for collection_name in ("histories", "snapshots", "questions"):
        for row in benchmark[collection_name]:
            missing = set(row.get("evidence_message_ids", [])) - message_ids
            if missing:
                fail(f"Unresolved evidence IDs in {collection_name}: {sorted(missing)}")


def validate_result_file(path: Path, benchmark: dict[str, Any]) -> None:
    rows = read_jsonl(path)
    if not rows:
        fail(f"Result file is empty: {path}")
    pairs = [(row["question_id"], row["condition"]) for row in rows]
    if len(pairs) != len(set(pairs)):
        fail("Duplicate condition-question result pair")
    if {row["condition"] for row in rows} != set(CONDITIONS):
        fail("Result file does not contain all three conditions")
    by_condition = {
        condition: {row["question_id"] for row in rows if row["condition"] == condition}
        for condition in CONDITIONS
    }
    if len({frozenset(ids) for ids in by_condition.values()}) != 1:
        fail("Conditions do not contain identical question IDs")
    recognized_ids = {row["question_id"] for row in benchmark["questions"]}
    if set().union(*by_condition.values()) - recognized_ids:
        fail("Result file contains unknown question IDs")
    all_message_ids = {row["message_id"] for row in benchmark["evidence"]}
    for row in rows:
        ensure_no_forbidden_fields(row, f"result.{row['question_id']}.{row['condition']}")
        answer_type = (row.get("parsed_output") or {}).get("answer_type")
        if answer_type not in ANSWER_TYPES:
            fail(f"Unrecognized parsed answer type: {answer_type}")
        unresolved = set(row.get("retrieved_message_ids", [])) - all_message_ids
        if unresolved:
            fail(f"Unresolved retrieved message IDs: {sorted(unresolved)}")
        if "output_status" in row and row["output_status"] not in {
            "complete",
            "truncated_by_output_limit",
            "invalid_json",
            "unparsable",
        }:
            fail(f"Unrecognized output status: {row['output_status']}")
    if rows[0].get("run_mode") == "real_api":
        if len(by_condition[CONDITIONS[0]]) != 271 or len(rows) != 813:
            fail("A real API result must contain exactly 271 questions x 3 conditions")


def validate(args: argparse.Namespace) -> int:
    benchmark = load_benchmark()
    configs = load_configs()
    configured_limits = {config["max_output_tokens"] for config in configs.values()}
    if configured_limits != {2000}:
        fail(f"Expected uniform max_output_tokens=2000, found {sorted(configured_limits)}")
    configured_generators = {config["generator_model"] for config in configs.values()}
    if configured_generators != {"gpt-4.1-2025-04-14"}:
        fail(
            "Expected pinned generator gpt-4.1-2025-04-14, found "
            f"{sorted(configured_generators)}"
        )
    packet_dir = resolve_packet_dir(args.packet_dir)
    if len(benchmark["questions"]) != 271:
        fail("Exactly 271 benchmark questions were not loaded")
    question_ids = [row["question_id"] for row in benchmark["questions"]]
    if len(question_ids) != len(set(question_ids)):
        fail("Question IDs are not unique")
    emails, oracle = validate_corpora(benchmark, packet_dir)
    validate_evidence(benchmark)
    validate_target_independence(benchmark["questions"], emails, oracle, configs)
    sample, parse_error = parse_model_output(
        "prefix ```json\n"
        + json.dumps(
            {
                "answer_type": "TASK_SET",
                "tasks": [],
                "none": True,
                "evidence_message_ids": [],
                "controlled_failure": False,
                "failure_reason": None,
            }
        )
        + "\n``` suffix"
    )
    if parse_error or sample["answer_type"] != "TASK_SET":
        fail("Noise-tolerant deterministic response parser failed")
    if args.results:
        validate_result_file(Path(args.results).resolve(), benchmark)
    print("Leakage validation: PASS")
    print("Questions: 271; corrected email documents: 195; oracle task documents: 236")
    print("Gold-target mutation leaves every condition prompt unchanged")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate corpus separation and question-gold isolation for the ISCMI experiment."
    )
    parser.add_argument("--packet-dir", help="Corrected external MailEx packet directory.")
    parser.add_argument("--results", help="Optional gold-free inference JSONL to validate.")
    return parser


if __name__ == "__main__":
    raise SystemExit(validate(build_parser().parse_args()))
