from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class FixtureUser(BaseModel):
    user_alias: str | None = None
    user_id: str | None = None
    username: str
    email: str

    @property
    def alias(self) -> str:
        return self.user_alias or self.user_id or self.username


class FixturePermission(BaseModel):
    user_id: str | None = None
    user_alias: str | None = None
    permission_type: str


class FixturePolicyRule(BaseModel):
    target_type: str
    target_id: str
    purpose: str = "any"
    access_mode: str
    valid_from: str | None = None
    valid_until: str | None = None


class FixtureDocument(BaseModel):
    document_alias: str | None = None
    document_id: str | None = None
    file_name: str
    visibility: str = "Private"
    owner_user_id: str | None = None
    owner_user_alias: str | None = None
    content_format: str = "text"
    content: str
    permissions: list[FixturePermission] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    policy_rules: list[FixturePolicyRule] = Field(default_factory=list)
    protected_content_markers: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def alias(self) -> str:
        return self.document_alias or self.document_id or self.file_name


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
    pair_id: str | None = None
    scenario_family: str
    description: str | None = None
    user_id: str | None = None
    user_alias: str | None = None
    question: str
    document_scope: list[str] = Field(default_factory=list)
    expected_behavioral_class: str | None = None
    accepted_behavioral_classes: list[str] = Field(default_factory=list)
    expected_policy_decision: str | None = None
    document_access: dict[str, dict[str, Any]] = Field(default_factory=dict)
    canonical_answer: str | None = None
    acceptable_answer_markers: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    protected_content_markers: list[str] = Field(default_factory=list)
    protected_markers: list[str] = Field(default_factory=list)
    forbidden_answer_markers: list[str] = Field(default_factory=list)
    content_disclosure_allowed: bool | None = None
    aggregate_disclosure_allowed: bool | None = None
    individual_disclosure_allowed: bool | None = None
    answerable_from_raw_context: bool | None = None
    answerable_under_policy: bool | None = None
    answerable_with_primary_evidence: bool | None = None
    expected_role_aware_source_roles: list[str] = Field(default_factory=list)
    expected_supporting_document_aliases: list[str] = Field(default_factory=list)
    expected_contextual_document_aliases: list[str] = Field(default_factory=list)
    aggregate_pair_id: str | None = None
    case_subtype: str | None = None
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def scope(self) -> list[str]:
        return self.document_scope or self.document_ids

    @property
    def protected(self) -> list[str]:
        return self.protected_markers or self.protected_content_markers


class EvaluationFixture(BaseModel):
    schema_version: str | None = None
    fixture_id: str
    description: str | None = None
    benchmark_family: str | None = None
    case_count: int | None = None
    users: list[FixtureUser] = Field(default_factory=list)
    documents: list[FixtureDocument] = Field(default_factory=list)
    permissions: list[FixturePermission] = Field(default_factory=list)
    policy_rules: list[FixturePolicyRule] = Field(default_factory=list)
    evidence_units: list[FixtureEvidenceUnit] = Field(default_factory=list)
    cases: list[FixtureCase] = Field(default_factory=list)
    ground_truth: dict[str, Any] = Field(default_factory=dict)

    def document_by_alias(self) -> dict[str, FixtureDocument]:
        return {document.alias: document for document in self.documents}

    def user_by_alias(self) -> dict[str, FixtureUser]:
        return {user.alias: user for user in self.users}


def load_fixture(path: str | Path) -> EvaluationFixture:
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(raw) or {}
    else:
        data = json.loads(raw)
    return EvaluationFixture.parse_obj(data)
