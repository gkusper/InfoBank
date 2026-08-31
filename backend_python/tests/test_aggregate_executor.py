from __future__ import annotations

import json

import pytest

import models
import relevance
from document_processing import sha256_text
from aggregate_executor import (
    AGGREGATE_RESULT,
    REFUSE_AGGREGATION_THRESHOLD,
    AggregateConfig,
    AggregateContribution,
    execute_aggregate,
    extract_unambiguous_numeric_value,
)
from routers import chat


def contributions():
    return [
        AggregateContribution("source-a", "person-a", 10.0),
        AggregateContribution("source-a-duplicate", "person-a", 999.0),
        AggregateContribution("source-b", "person-b", 20.0),
        AggregateContribution("source-c", "person-c", 30.0),
        AggregateContribution("source-denied", "person-denied", 5000.0),
        AggregateContribution("source-metadata", "person-metadata", 7000.0),
    ]


def decisions():
    return {
        "source-a": relevance.USE_FULL,
        "source-a-duplicate": relevance.USE_AGGREGATE,
        "source-b": relevance.USE_AGGREGATE,
        "source-c": relevance.USE_FULL,
        "source-denied": relevance.USE_DENY,
        "source-metadata": relevance.USE_METADATA,
    }


def test_mixed_policy_aggregate_is_correct_deduplicated_and_non_disclosing() -> None:
    result = execute_aggregate(contributions(), decisions(), AggregateConfig(k_threshold=3, operation="mean"))
    assert result["output_class"] == AGGREGATE_RESULT
    assert result["aggregate"] == {"operation": "mean", "value": 20.0, "contributor_count": 3, "k_threshold": 3}
    serialized = json.dumps(result, sort_keys=True)
    for prohibited in ("source-a", "person-a", "999", "5000", "7000"):
        assert prohibited not in serialized
    assert "distinct contributors" not in result["safe_output"]
    assert "contributor_count" not in result["public_trace"]
    assert "deduplicated_count" not in result["public_trace"]
    assert result["citations"] == []
    assert json.loads(result["generator_context"])["governed_aggregate"]["value"] == 20.0


def test_equal_threshold_is_allowed_without_public_count() -> None:
    result = execute_aggregate(contributions()[:3], decisions(), AggregateConfig(k_threshold=2, operation="sum"))
    assert result["output_class"] == AGGREGATE_RESULT
    assert result["aggregate"]["value"] == 30.0
    assert result["aggregate"]["contributor_count"] == 2
    assert "contributor_count" not in result["public_trace"]
    assert "2" not in result["safe_output"]


def test_above_threshold_is_allowed_without_source_or_component_disclosure() -> None:
    result = execute_aggregate(contributions()[:4], decisions(), AggregateConfig(k_threshold=2, operation="mean"))
    assert result["output_class"] == AGGREGATE_RESULT
    assert result["aggregate"]["contributor_count"] == 3
    serialized_public = json.dumps(
        {
            "safe_output": result["safe_output"],
            "public_trace": result["public_trace"],
            "citations": result["citations"],
        },
        sort_keys=True,
    )
    for prohibited in ("source-a", "person-a", "10.0", "20.0", "30.0"):
        assert prohibited not in serialized_public


def test_threshold_is_runtime_configuration_not_a_global_constant() -> None:
    permitted = [AggregateContribution("entry-a", "group-a", 4.0), AggregateContribution("entry-b", "group-b", 8.0)]
    policy = {"entry-a": relevance.USE_AGGREGATE, "entry-b": relevance.USE_AGGREGATE}
    assert execute_aggregate(permitted, policy, AggregateConfig(k_threshold=2))["output_class"] == AGGREGATE_RESULT
    assert (
        execute_aggregate(permitted, policy, AggregateConfig(k_threshold=3))["output_class"]
        == REFUSE_AGGREGATION_THRESHOLD
    )


def test_below_threshold_refusal_does_not_disclose_source_existence_or_count() -> None:
    restricted = decisions() | {"source-c": relevance.USE_DENY}
    result = execute_aggregate(contributions(), restricted, AggregateConfig(k_threshold=3))
    assert result["output_class"] == REFUSE_AGGREGATION_THRESHOLD
    assert result["aggregate"] is None
    assert result["generator_context"] == ""
    assert result["citations"] == []
    assert "2" not in result["safe_output"]
    assert "source" not in result["safe_output"].lower()
    assert "excluded_by_policy" not in json.dumps(result)


def test_permission_counterfactual_changes_only_policy_and_never_leaks() -> None:
    allowed = execute_aggregate(contributions(), decisions(), AggregateConfig(k_threshold=3))
    denied = execute_aggregate(
        contributions(), decisions() | {"source-c": relevance.USE_DENY}, AggregateConfig(k_threshold=3)
    )
    assert allowed["output_class"] == AGGREGATE_RESULT
    assert denied["output_class"] == REFUSE_AGGREGATION_THRESHOLD
    assert "30" not in json.dumps(denied)


def test_denied_and_metadata_contributions_are_publicly_indistinguishable_from_absence() -> None:
    all_inputs = execute_aggregate(contributions(), decisions(), AggregateConfig(k_threshold=3))
    permitted_only = execute_aggregate(
        contributions()[:4],
        {key: value for key, value in decisions().items() if key not in {"source-denied", "source-metadata"}},
        AggregateConfig(k_threshold=3),
    )
    assert all_inputs == permitted_only


def test_free_text_numeric_extraction_refuses_ambiguous_chunks() -> None:
    assert extract_unambiguous_numeric_value("Private contributor metric is 17.5 units.") == 17.5
    assert extract_unambiguous_numeric_value("Report 2026: metric 17.5 units.") is None
    assert extract_unambiguous_numeric_value("No numeric contribution is present.") is None


@pytest.mark.parametrize("k", [0, 1])
def test_unsafe_threshold_is_rejected(k: int) -> None:
    with pytest.raises(ValueError, match="at least 2"):
        AggregateConfig(k_threshold=k)


def test_production_retrieval_never_places_aggregate_chunk_in_generator_or_public_source(db_session, monkeypatch) -> None:
    document_id = "aggregate-production-doc"
    chunk_id = "aggregate-production-chunk"
    db_session.add(models.Document(
        id=document_id, file_path="private-aggregate.pdf", source_status="ACTIVE", visibility="Aggregate"
    ))
    db_session.add(models.DocumentChunk(
        id=chunk_id, document_id=document_id, chunk_index=0, page_number=1,
        char_start=0, char_end=57, text_content="Private contributor metric is 17.5 units.",
        content_sha256=sha256_text("Private contributor metric is 17.5 units."), vector_id=chunk_id,
    ))
    db_session.flush()

    class Collection:
        @staticmethod
        def query(**_kwargs):
            return {
                "ids": [[chunk_id]],
                "documents": [["Private contributor metric is 17.5 units."]],
                "metadatas": [[{"document_id": document_id, "chunk_id": chunk_id}]],
            }

    monkeypatch.setattr(chat.ai_service, "collection", Collection())
    governance = {
        "source_roles": {document_id: relevance.SOURCE_ROLE_AGGREGATE_ONLY},
        "use_decisions": {document_id: relevance.USE_AGGREGATE},
    }
    sources, blocks, contributions_found = chat.query_retrieved_sources(
        db_session,
        "What is the average metric?",
        [0.0],
        {"task_intent": "aggregate_statistics"},
        governance,
        [document_id],
    )
    assert blocks == []
    assert len(contributions_found) == 1
    assert contributions_found[0].value == 17.5
    assert "17.5" not in json.dumps(sources)
    assert "Private contributor" not in json.dumps(sources)
    assert sources[0]["citation"]["available"] is False


def test_production_retrieval_excludes_ambiguous_aggregate_chunk(db_session, monkeypatch) -> None:
    document_id = "aggregate-ambiguous-doc"
    chunk_id = "aggregate-ambiguous-chunk"
    content = "Report 2026: private contributor metric is 17.5 units."
    db_session.add(models.Document(
        id=document_id, file_path="private-ambiguous.pdf", source_status="ACTIVE", visibility="Aggregate"
    ))
    db_session.add(models.DocumentChunk(
        id=chunk_id, document_id=document_id, chunk_index=0, page_number=1,
        char_start=0, char_end=len(content), text_content=content,
        content_sha256=sha256_text(content), vector_id=chunk_id,
    ))
    db_session.flush()

    class Collection:
        @staticmethod
        def query(**_kwargs):
            return {
                "ids": [[chunk_id]],
                "documents": [[content]],
                "metadatas": [[{"document_id": document_id, "chunk_id": chunk_id}]],
            }

    monkeypatch.setattr(chat.ai_service, "collection", Collection())
    governance = {
        "source_roles": {document_id: relevance.SOURCE_ROLE_AGGREGATE_ONLY},
        "use_decisions": {document_id: relevance.USE_AGGREGATE},
    }
    sources, blocks, contributions_found = chat.query_retrieved_sources(
        db_session,
        "What is the average metric?",
        [0.0],
        {"task_intent": "aggregate_statistics"},
        governance,
        [document_id],
    )
    assert len(sources) == 1
    assert blocks == []
    assert contributions_found == []
    assert "17.5" not in json.dumps(sources)


def test_aggregate_generator_safe_chunk_is_content_independent() -> None:
    first = chat.make_generator_safe_chunk(relevance.SOURCE_ROLE_AGGREGATE_ONLY, "Secret 11", {})
    second = chat.make_generator_safe_chunk(relevance.SOURCE_ROLE_AGGREGATE_ONLY, "Different 99", {})
    assert first == second
    assert "11" not in first and "99" not in second
