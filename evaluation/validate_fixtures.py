from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .fixture_schema import EvaluationFixture, FixtureCase, load_fixture


EXPECTED_FAMILY_COUNTS = {
    "full_access_direct_qa": 8,
    "metadata_only": 8,
    "deny_private_no_permission": 8,
    "aggregate_only": 8,
    "mixed_or_insufficient_primary_evidence": 8,
}

ALLOWED_FIXTURE_IDS = {"document_rag_v1", "document_rag_v2", "document_rag_v3"}

ALLOWED_BEHAVIOR_CLASSES = {
    "answer_allowed",
    "metadata_only_answer",
    "deny_refuse_or_abstain",
    "aggregate_answer",
    "aggregate_only_restriction",
    "controlled_failure",
}

AGGREGATE_MARKERS = [
    "average",
    "mean",
    "median",
    "count",
    "total",
    "statistics",
    "statistic",
    "aggregate",
    "pilot",
    "approval time",
    "rate",
    "percentage",
    "percent",
    "days",
    "hours",
    "items",
    "documents",
    "users",
]


class FixtureValidationError(ValueError):
    pass


def validate_fixture(fixture: EvaluationFixture) -> list[str]:
    errors: list[str] = []
    docs = fixture.document_by_alias()
    users = fixture.user_by_alias()
    case_ids = [case.case_id for case in fixture.cases]
    doc_aliases = [document.alias for document in fixture.documents]

    _expect(fixture.schema_version == "1.0", "schema_version must be 1.0", errors)
    _expect(fixture.fixture_id in ALLOWED_FIXTURE_IDS, f"fixture_id must be one of {sorted(ALLOWED_FIXTURE_IDS)}", errors)
    _expect(fixture.benchmark_family == "document_rag", "benchmark_family must be document_rag", errors)
    if fixture.fixture_id == "document_rag_v3":
        validate_fixture_v3(fixture, docs, users, case_ids, doc_aliases, errors)
        if errors:
            raise FixtureValidationError("\n".join(errors))
        return []
    _expect(len(fixture.cases) == 40, f"fixture must contain exactly 40 cases, found {len(fixture.cases)}", errors)
    _expect(fixture.case_count == 40, f"case_count must be 40, found {fixture.case_count}", errors)
    _expect(len(case_ids) == len(set(case_ids)), "case IDs must be unique", errors)
    _expect(len(doc_aliases) == len(set(doc_aliases)), "document aliases must be unique", errors)

    counts = Counter(case.scenario_family for case in fixture.cases)
    for family, expected in EXPECTED_FAMILY_COUNTS.items():
        _expect(counts.get(family, 0) == expected, f"{family} count must be {expected}, found {counts.get(family, 0)}", errors)
    for user in fixture.users:
        domain = user.email.rsplit("@", 1)[-1]
        _expect(domain == "example.test" or domain.endswith(".example.test"), f"user {user.alias} must use .example.test email", errors)

    for case in fixture.cases:
        validate_case_references(case, docs, users, errors)
        validate_case_markers(case, docs, fixture.cases, errors)
        validate_behavior_class(case, errors)
        validate_secret_patterns(case, docs, errors)

    validate_triplets(fixture, docs, errors)
    validate_aggregate_pairs(fixture, docs, errors)
    validate_contextual_only(fixture, errors)

    if errors:
        raise FixtureValidationError("\n".join(errors))
    return []


def validate_fixture_v3(
    fixture: EvaluationFixture,
    docs: dict[str, Any],
    users: dict[str, Any],
    case_ids: list[str],
    doc_aliases: list[str],
    errors: list[str],
) -> None:
    _expect(len(fixture.cases) == 400, f"document_rag_v3 must contain exactly 400 cases, found {len(fixture.cases)}", errors)
    _expect(fixture.case_count == 400, f"document_rag_v3 case_count must be 400, found {fixture.case_count}", errors)
    _expect(len(case_ids) == len(set(case_ids)), "case IDs must be unique", errors)
    _expect(len(doc_aliases) == len(set(doc_aliases)), "document aliases must be unique", errors)
    counts = Counter(case.metadata.get("scenario") for case in fixture.cases)
    for scenario, expected in {"D1": 80, "D2": 80, "D3": 80, "D4": 80, "D5": 80}.items():
        _expect(counts.get(scenario, 0) == expected, f"{scenario} count must be {expected}, found {counts.get(scenario, 0)}", errors)
    for user in fixture.users:
        domain = user.email.rsplit("@", 1)[-1]
        _expect(domain == "example.test" or domain.endswith(".example.test"), f"user {user.alias} must use .example.test email", errors)
    for case in fixture.cases:
        validate_case_references(case, docs, users, errors)
        validate_case_markers_v3(case, docs, fixture.cases, errors)
        validate_behavior_class(case, errors)
        validate_secret_patterns(case, docs, errors)
        for alias in case.scope:
            _expect(alias in case.document_access, f"{case.case_id}: document_access missing scoped alias {alias}", errors)
    validate_v3_triplets(fixture, docs, errors)
    validate_v3_aggregate_pairs(fixture, docs, errors)
    validate_v3_d5_pairs(fixture, docs, errors)
    validate_v3_leakage(fixture, docs, errors)


def validate_case_markers_v3(case: FixtureCase, docs: dict[str, Any], all_cases: list[FixtureCase], errors: list[str]) -> None:
    scoped_docs = [docs[alias] for alias in case.scope if alias in docs]
    scoped_text = "\n".join(document.content for document in scoped_docs)
    same_family_aliases = {
        alias
        for other in all_cases
        if other.pair_id == case.pair_id
        for alias in other.scope
    }
    unrelated_text = "\n".join(
        document.content for alias, document in docs.items() if alias not in same_family_aliases
    )
    metadata_surface = " ".join(
        [item.question for item in all_cases]
        + [document.file_name for document in docs.values()]
        + [keyword for document in docs.values() for keyword in document.keywords]
    )
    for marker in case.protected:
        _expect(marker in scoped_text, f"{case.case_id}: protected marker {marker!r} missing from scoped protected content", errors)
        _expect(marker not in metadata_surface, f"{case.case_id}: protected marker {marker!r} leaks into question/filename/keywords", errors)
        _expect(marker not in unrelated_text, f"{case.case_id}: protected marker {marker!r} leaks outside matched family", errors)
    if case.canonical_answer is None:
        _expect(not case.acceptable_answer_markers, f"{case.case_id}: null canonical_answer should not have acceptable markers", errors)
    else:
        _expect(bool(case.acceptable_answer_markers), f"{case.case_id}: canonical answer requires acceptable markers", errors)
        for marker in case.acceptable_answer_markers:
            _expect(marker in case.canonical_answer, f"{case.case_id}: acceptable marker {marker!r} must appear in canonical answer", errors)


def validate_v3_triplets(fixture: EvaluationFixture, docs: dict[str, Any], errors: list[str]) -> None:
    by_pair: dict[str, list[FixtureCase]] = defaultdict(list)
    for case in fixture.cases:
        if case.metadata.get("scenario") in {"D1", "D2", "D4"}:
            by_pair[case.pair_id or ""].append(case)
    _expect(len(by_pair) == 80 and "" not in by_pair, f"v3 D1/D2/D4 must form 80 triplets, found {len(by_pair)}", errors)
    for pair_id, family in by_pair.items():
        scenarios = sorted(case.metadata.get("scenario") for case in family)
        _expect(scenarios == ["D1", "D2", "D4"], f"{pair_id}: triplet scenarios must be D1/D2/D4, found {scenarios}", errors)
        texts = {docs[case.scope[0]].content for case in family if case.scope and case.scope[0] in docs}
        questions = {case.question for case in family}
        _expect(len(texts) == 1, f"{pair_id}: D1/D2/D4 source content must be identical", errors)
        _expect(len(questions) == 1, f"{pair_id}: D1/D2/D4 question must be identical", errors)


def validate_v3_aggregate_pairs(fixture: EvaluationFixture, docs: dict[str, Any], errors: list[str]) -> None:
    by_pair: dict[str, list[FixtureCase]] = defaultdict(list)
    for case in fixture.cases:
        if case.metadata.get("scenario") == "D3":
            by_pair[case.pair_id or ""].append(case)
    _expect(len(by_pair) == 40 and "" not in by_pair, f"v3 D3 must form 40 pairs, found {len(by_pair)}", errors)
    for pair_id, family in by_pair.items():
        subtypes = sorted(case.case_subtype for case in family)
        _expect(subtypes == ["aggregate_safe", "individual_restricted"], f"{pair_id}: D3 pair subtype mismatch {subtypes}", errors)
        aliases = {tuple(case.scope) for case in family}
        _expect(len(aliases) == 1, f"{pair_id}: D3 pair must share the same scoped aggregate document", errors)
        for case in family:
            scoped_text = "\n".join(docs[alias].content for alias in case.scope if alias in docs)
            _expect(bool(extract_aggregate_safe_facts_compatible(scoped_text)), f"{case.case_id}: aggregate text lacks numeric aggregate fact", errors)


def validate_v3_d5_pairs(fixture: EvaluationFixture, docs: dict[str, Any], errors: list[str]) -> None:
    by_pair: dict[str, list[FixtureCase]] = defaultdict(list)
    for case in fixture.cases:
        if case.metadata.get("scenario") == "D5":
            by_pair[case.pair_id or ""].append(case)
    _expect(len(by_pair) == 40 and "" not in by_pair, f"v3 D5 must form 40 pairs, found {len(by_pair)}", errors)
    for pair_id, family in by_pair.items():
        subtypes = sorted(case.case_subtype for case in family)
        _expect(subtypes == ["contextual_only", "mixed_primary"], f"{pair_id}: D5 pair subtype mismatch {subtypes}", errors)
        mixed = next(case for case in family if case.case_subtype == "mixed_primary")
        context = next(case for case in family if case.case_subtype == "contextual_only")
        _expect(bool(mixed.expected_supporting_document_aliases), f"{mixed.case_id}: mixed case must have primary support", errors)
        _expect(not context.expected_supporting_document_aliases, f"{context.case_id}: contextual-only case must not have primary support", errors)
        _expect(set(context.scope).issubset(set(mixed.scope)), f"{pair_id}: contextual-only scope must be subset of mixed scope", errors)


def validate_v3_leakage(fixture: EvaluationFixture, docs: dict[str, Any], errors: list[str]) -> None:
    prohibited = [
        "primary evidence",
        "contextual evidence",
        "authoritative source",
        "not authoritative",
        "cannot prove",
        "insufficient evidence",
        "background only",
        "does not include a signed confirmation",
        "final assignment notice",
        "this source must not be used",
    ]
    for document in docs.values():
        lowered = document.content.lower()
        for phrase in prohibited:
            _expect(phrase not in lowered, f"{document.alias}: D5/source role leakage phrase {phrase!r}", errors)


def validate_case_references(case: FixtureCase, docs: dict[str, Any], users: dict[str, Any], errors: list[str]) -> None:
    _expect(case.user_alias in users or case.user_id in users, f"{case.case_id}: referenced user does not exist", errors)
    _expect(bool(case.scope), f"{case.case_id}: document_scope must be nonempty", errors)
    for alias in case.scope:
        _expect(alias in docs, f"{case.case_id}: document_scope references missing document {alias}", errors)
    for alias in case.document_access:
        _expect(alias in docs, f"{case.case_id}: document_access references missing document {alias}", errors)


def validate_case_markers(case: FixtureCase, docs: dict[str, Any], all_cases: list[FixtureCase], errors: list[str]) -> None:
    scoped_docs = [docs[alias] for alias in case.scope if alias in docs]
    scoped_text = "\n".join(document.content for document in scoped_docs)
    unrelated_text = "\n".join(
        document.content for alias, document in docs.items() if alias not in set(case.scope)
    )
    metadata_surface = " ".join(
        [item.question for item in all_cases]
        + [document.file_name for document in docs.values()]
        + [keyword for document in docs.values() for keyword in document.keywords]
    )
    for marker in case.protected:
        _expect(marker in scoped_text, f"{case.case_id}: protected marker {marker!r} missing from scoped protected content", errors)
        _expect(marker not in metadata_surface, f"{case.case_id}: protected marker {marker!r} leaks into question/filename/keywords", errors)
        _expect(marker not in unrelated_text, f"{case.case_id}: protected marker {marker!r} leaks into unrelated document", errors)
    if case.canonical_answer is None:
        _expect(not case.acceptable_answer_markers, f"{case.case_id}: null canonical_answer should not have acceptable markers", errors)
    else:
        _expect(bool(case.acceptable_answer_markers), f"{case.case_id}: canonical answer requires acceptable markers", errors)
        for marker in case.acceptable_answer_markers:
            _expect(marker in case.canonical_answer, f"{case.case_id}: acceptable marker {marker!r} must appear in canonical answer", errors)


def validate_behavior_class(case: FixtureCase, errors: list[str]) -> None:
    if case.expected_behavioral_class:
        _expect(case.expected_behavioral_class in ALLOWED_BEHAVIOR_CLASSES, f"{case.case_id}: invalid behavioral class", errors)
    for value in case.accepted_behavioral_classes:
        _expect(value in ALLOWED_BEHAVIOR_CLASSES, f"{case.case_id}: invalid accepted class {value}", errors)


def validate_secret_patterns(case: FixtureCase, docs: dict[str, Any], errors: list[str]) -> None:
    combined = "\n".join([case.question] + [doc.content for doc in docs.values()])
    _expect(not re.search(r"sk-[A-Za-z0-9]", combined), "fixture must not contain OpenAI-style API keys", errors)
    _expect("password" not in combined.lower(), "fixture must not contain password-like text", errors)


def validate_triplets(fixture: EvaluationFixture, docs: dict[str, Any], errors: list[str]) -> None:
    cases_by_id = {case.case_id: case for case in fixture.cases}
    for index in range(1, 9):
        suffix = f"{index:02d}"
        expected_ids = [f"FULL_{suffix}", f"METADATA_{suffix}", f"DENY_{suffix}"]
        missing = [case_id for case_id in expected_ids if case_id not in cases_by_id]
        _expect(not missing, f"PAIR_{suffix}: missing triplet cases {missing}", errors)
        if missing:
            continue
        full, metadata, deny = [cases_by_id[case_id] for case_id in expected_ids]
        baseline = _triplet_invariant(full, docs)
        for case in [metadata, deny]:
            _expect(_triplet_invariant(case, docs) == baseline, f"{case.case_id}: triplet invariant differs from FULL_{suffix}", errors)
        _expect([full.expected_policy_decision, metadata.expected_policy_decision, deny.expected_policy_decision] == ["full", "metadata", "deny"], f"PAIR_{suffix}: policy sequence must be full/metadata/deny", errors)


def _triplet_invariant(case: FixtureCase, docs: dict[str, Any]) -> tuple[Any, ...]:
    scoped_text = "\n".join(docs[alias].content for alias in case.scope if alias in docs)
    return (
        case.pair_id,
        tuple(case.scope),
        scoped_text,
        case.question,
        case.canonical_answer,
        tuple(case.acceptable_answer_markers),
        tuple(case.protected),
        tuple(case.forbidden_answer_markers),
        case.answerable_from_raw_context,
    )


def validate_aggregate_pairs(fixture: EvaluationFixture, docs: dict[str, Any], errors: list[str]) -> None:
    aggregate_cases = [case for case in fixture.cases if case.scenario_family == "aggregate_only"]
    by_pair: dict[str, list[FixtureCase]] = defaultdict(list)
    for case in aggregate_cases:
        by_pair[case.aggregate_pair_id or ""].append(case)
    _expect(len(by_pair) == 4 and "" not in by_pair, f"aggregate cases must form four named pairs, found {sorted(by_pair)}", errors)
    for pair_id, cases in by_pair.items():
        subtypes = sorted(case.case_subtype for case in cases)
        _expect(subtypes == ["aggregate_safe", "individual_disclosure"], f"{pair_id}: aggregate pair must contain safe and individual cases", errors)
        for case in cases:
            scoped_text = "\n".join(docs[alias].content for alias in case.scope if alias in docs)
            if case.case_subtype == "aggregate_safe":
                _expect(bool(extract_aggregate_safe_facts_compatible(scoped_text)), f"{case.case_id}: aggregate-safe text is incompatible with current extraction pattern", errors)


def validate_contextual_only(fixture: EvaluationFixture, errors: list[str]) -> None:
    context_cases = [case for case in fixture.cases if case.case_subtype == "contextual_only"]
    _expect(len(context_cases) == 4, f"contextual_only case count must be 4, found {len(context_cases)}", errors)
    for case in context_cases:
        _expect(not case.expected_supporting_document_aliases, f"{case.case_id}: contextual-only case must not declare primary support", errors)
        _expect(case.expected_role_aware_source_roles == ["contextual"], f"{case.case_id}: contextual-only role expectation must be contextual", errors)
        _expect(case.answerable_with_primary_evidence is False, f"{case.case_id}: must not be answerable with primary evidence", errors)


def extract_aggregate_safe_facts_compatible(text: str) -> list[str]:
    clean = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    facts: list[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        has_marker = any(marker in lowered for marker in AGGREGATE_MARKERS)
        has_number = bool(re.search(r"\b\d+(?:\.\d+)?\b", sentence))
        if has_marker and has_number:
            facts.append(sentence)
    return facts


def _expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate InfoBank evaluation fixtures")
    parser.add_argument("fixture", help="Fixture YAML/JSON path")
    args = parser.parse_args(argv)
    try:
        validate_fixture(load_fixture(args.fixture))
    except FixtureValidationError as exc:
        print(f"VALIDATION: FAIL\n{exc}")
        return 1
    print("VALIDATION: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
