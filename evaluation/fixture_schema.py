from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class FixtureUser(BaseModel):
    user_id: str
    username: str
    email: str


class FixturePermission(BaseModel):
    user_id: str
    permission_type: str


class FixturePolicyRule(BaseModel):
    target_type: str
    target_id: str
    purpose: str = "any"
    access_mode: str
    valid_from: str | None = None
    valid_until: str | None = None


class FixtureDocument(BaseModel):
    document_id: str
    file_name: str
    visibility: str = "Private"
    owner_user_id: str | None = None
    content_format: str = "text"
    content: str
    permissions: list[FixturePermission] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    policy_rules: list[FixturePolicyRule] = Field(default_factory=list)
    protected_content_markers: list[str] = Field(default_factory=list)


class FixtureEvidenceUnit(BaseModel):
    evidence_unit_id: str
    user_id: str
    source_type: str = "Other"
    title: str
    content: str
    source_timestamp: str | None = None
    thread_id: str | None = None
    relation_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    policy_rules: list[FixturePolicyRule] = Field(default_factory=list)


class FixtureCase(BaseModel):
    case_id: str
    scenario_family: str
    user_id: str
    question: str
    expected_behavioral_class: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    protected_content_markers: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationFixture(BaseModel):
    fixture_id: str
    description: str | None = None
    users: list[FixtureUser] = Field(default_factory=list)
    documents: list[FixtureDocument] = Field(default_factory=list)
    permissions: list[FixturePermission] = Field(default_factory=list)
    policy_rules: list[FixturePolicyRule] = Field(default_factory=list)
    evidence_units: list[FixtureEvidenceUnit] = Field(default_factory=list)
    cases: list[FixtureCase] = Field(default_factory=list)


def load_fixture(path: str | Path) -> EvaluationFixture:
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(raw) or {}
    else:
        data = json.loads(raw)
    return EvaluationFixture.parse_obj(data)
