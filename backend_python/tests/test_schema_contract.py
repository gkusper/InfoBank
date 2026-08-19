from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import Enum, String, UniqueConstraint

import models


REPO_ROOT = Path(__file__).resolve().parents[2]
SQL_PATH = REPO_ROOT / "infobank_db.sql"


def sql_text() -> str:
    return SQL_PATH.read_text(encoding="utf-8-sig")


def test_required_runtime_tables_exist_in_sql_and_models() -> None:
    required = {"evidence_units", "policy_rules", "connector_accounts", "audit_logs"}
    sql = sql_text().lower()
    for table in required:
        assert re.search(rf"create\s+table\s+if\s+not\s+exists\s+{table}\b", sql)
        assert table in models.Base.metadata.tables


def test_sql_and_sqlalchemy_enum_values_agree() -> None:
    sql = sql_text()
    evidence_match = re.search(r"source_type\s+ENUM\(([^)]+)\)", sql, re.IGNORECASE)
    policy_match = re.search(r"access_mode\s+ENUM\(([^)]+)\)", sql, re.IGNORECASE)
    assert evidence_match and policy_match
    sql_evidence = set(re.findall(r"'([^']+)'", evidence_match.group(1)))
    sql_policy = set(re.findall(r"'([^']+)'", policy_match.group(1)))
    assert sql_evidence == {item.value for item in models.EvidenceSourceType}
    assert sql_policy == {item.value for item in models.PolicyAccessMode}
    assert isinstance(models.EvidenceUnit.__table__.c.source_type.type, Enum)
    assert isinstance(models.PolicyRule.__table__.c.access_mode.type, Enum)


def test_key_field_lengths_and_foreign_keys_are_compatible() -> None:
    assert isinstance(models.EvidenceUnit.__table__.c.id.type, String)
    assert models.EvidenceUnit.__table__.c.id.type.length == 36
    assert models.EvidenceUnit.__table__.c.user_id.type.length == 36
    assert models.PolicyRule.__table__.c.id.type.length == 36
    assert models.PolicyRule.__table__.c.owner_user_id.type.length == 36
    assert models.ConnectorAccount.__table__.c.id.type.length == 36
    assert models.ConnectorAccount.__table__.c.user_id.type.length == 36
    assert models.AuditLog.__table__.c.id.type.length == 50
    targets = {
        foreign_key.target_fullname
        for table in (models.EvidenceUnit.__table__, models.PolicyRule.__table__, models.ConnectorAccount.__table__)
        for column in table.columns
        for foreign_key in column.foreign_keys
    }
    assert targets == {"users.id"}


def test_known_sql_only_permission_unique_constraint_is_explicitly_recorded() -> None:
    assert re.search(r"UNIQUE\s*\(\s*user_id\s*,\s*document_id\s*\)", sql_text(), re.IGNORECASE)
    model_uniques = [
        constraint
        for constraint in models.UserDocumentPermission.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    assert model_uniques == []
