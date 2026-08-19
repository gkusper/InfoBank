from __future__ import annotations

import models
import policy_engine
from routers.analytics import _build_governed_graph
from semantic_graph import GRAPH_SCHEMA_VERSION, build_semantic_cooccurrence_graph, stable_node_id


USER_ID = "00000000-0000-0000-0000-000000000201"


def test_semantic_graph_is_deterministic_and_counts_each_keyword_once_per_document() -> None:
    first = build_semantic_cooccurrence_graph({
        "doc-b": ["Router", "support", "support"],
        "doc-a": ["television", "Support"],
    })
    second = build_semantic_cooccurrence_graph({
        "doc-a": ["Support", "television"],
        "doc-b": ["support", "Router"],
    })
    assert first == second
    assert first["schema_version"] == GRAPH_SCHEMA_VERSION
    support = next(node for node in first["nodes"] if node["keyword"] == "support")
    assert support["id"] == stable_node_id("SUPPORT")
    assert support["document_frequency"] == 2
    assert first["links"] == sorted(first["links"], key=lambda item: (item["source_keyword"], item["target_keyword"]))
    assert all(set(link) >= {"shared_document_count", "source", "target"} for link in first["links"])


def test_semantic_graph_export_contains_no_document_ids_paths_or_source_text() -> None:
    graph = build_semantic_cooccurrence_graph({"private-document-id": ["television", "warranty"]})
    serialized = str(graph)
    assert "private-document-id" not in serialized
    assert "\\" not in serialized
    assert "/home/" not in serialized


def test_database_graph_applies_governance_before_export(db_session) -> None:
    db_session.add(models.User(id=USER_ID, email="graph@example.invalid", username="graph-user", password_hash="unused"))
    db_session.flush()
    fixtures = (
        ("full-doc", models.PermissionType.Owner, "visible-full"),
        ("metadata-doc", models.PermissionType.Metadata, "visible-metadata"),
        ("aggregate-doc", models.PermissionType.Aggregate, "hidden-aggregate"),
        ("denied-doc", models.PermissionType.Owner, "hidden-denied"),
    )
    for index, (document_id, permission, keyword) in enumerate(fixtures, start=1):
        db_session.add(models.Document(id=document_id, file_path=f"{document_id}.pdf", visibility="Private", source_status="ACTIVE"))
        db_session.add(models.Keyword(id=index, word=keyword))
    db_session.flush()
    for index, (document_id, permission, _keyword) in enumerate(fixtures, start=1):
        db_session.add(models.DocumentKeyword(document_id=document_id, keyword_id=index))
        db_session.add(models.UserDocumentPermission(
            id=f"permission-{document_id}", user_id=USER_ID, document_id=document_id, permission_type=permission,
        ))
    db_session.add(models.PolicyRule(
        id="deny-graph-rule",
        owner_user_id=USER_ID,
        target_type=policy_engine.TARGET_DOCUMENT,
        target_id="denied-doc",
        purpose="semantic_graph_visualization",
        access_mode=models.PolicyAccessMode.Deny,
    ))
    db_session.flush()

    graph = _build_governed_graph(USER_ID, db_session)
    keywords = {node["keyword"] for node in graph["nodes"]}
    assert keywords == {"visible-full", "visible-metadata"}
    assert graph["governance"]["aggregate_excluded_count"] == 1
    assert graph["governance"]["denied_document_count"] == 1
    assert graph["governance"]["policy_order"] == "governance_before_graph_export"
