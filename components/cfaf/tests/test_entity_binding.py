"""Tests for PR 2: Query anchoring, document reference linking, and trusted entity binding.

Covers:
1. Matching trusted entity IDs across multiple sources and dependent claims (MATCHED -> SUPPORTED).
2. Mismatched entity IDs combined in a single composite claim (MISMATCHED -> UNRESOLVED).
3. Mismatched entity IDs across dependent claims even when LLM subject_key strings match (MISMATCHED -> UNRESOLVED + public invariance).
4. Mismatched entity IDs across independent claims sharing the same subject_key (MISMATCHED -> UNRESOLVED).
5. Missing entity ID when combining multiple sources (MISSING -> UNRESOLVED).
6. Missing entity ID on a single source when claim is subject-bound or checker requires entity binding (MISSING -> UNRESOLVED).
7. Policy-supplied AccessDecision entity_id precedence and DENY source entity_id blocking.
8. Contradictory source assessment on the same trusted entity (MATCHED -> CONTRADICTED).
9. Contradictory source assessment on a different trusted entity does not taint matched claim (MATCHED -> SUPPORTED).
10. Insufficient evidence handling: abstention with zero claims and non-primary source role (INSUFFICIENT).
11. Tamper detection on stale entity_bindings signature (STALE_ENTITY_BINDING).
12. End-to-end verification of both reference kinds (query anchor + quote/span document refs) and ClaimAuditRecord schema compliance.
13. Regression (Finding 1): Omitting claim dependencies and subject_key cannot bypass mandatory request depends_on entity checks.
14. Regression (Finding 2): Contradiction on one requirement/claim does not taint an independently supported claim about the same entity.
15. Regression (Finding 2 edge): Unscoped multi-requirement contradiction is rejected without poisoning valid claims.
16. Regression (Finding 3): Replaying old view-0001 entity_bindings + entity_signature onto a new document is rejected as STALE_ENTITY_BINDING.
"""
from component_cfaf.adapters.local import LegacyGovernance
from component_cfaf.contracts import (
    AccessDecision,
    Authority,
    Claim,
    ClaimAuditRecord,
    DependencyBinding,
    EntityBindingStatus,
    EvidenceRef,
    LLMProposal,
    ProviderResult,
    RawSource,
    RequirementSupport,
    SourceAssessment,
    SourceEntityBinding,
    SupportStatus,
    ValueType,
)
from component_cfaf.pipeline import Pipeline
from component_cfaf.support_checker import ReferenceSupportChecker


def test_matching_entity_ids_across_two_sources_supported(authority, governance):
    """Test 1: Two sources with identical trusted entity_id produce MATCHED and SUPPORTED."""
    doc1 = RawSource(
        private_id='doc-ada-bio',
        content='Ada Lovelace leads Lab Alpha.',
        metadata={},
        public_metadata={'title': 'Staff Directory'},
        entity_id='person-ada-01',
    )
    doc2 = RawSource(
        private_id='doc-ada-pub',
        content='Ada Lovelace published the report in 2024.',
        metadata={},
        public_metadata={'title': 'Publication Log'},
        entity_id='person-ada-01',
    )
    query = 'Who leads Lab Alpha and when did she publish?'

    class MatchingEntityProvider:
        def propose(self, request, evidence):
            v1, v2 = evidence.views[0], evidence.views[1]
            r1, r2 = request.requirements[0], request.requirements[1]
            q1 = 'Ada Lovelace leads Lab Alpha.'
            q2 = 'Ada Lovelace published the report in 2024.'

            c1 = Claim(
                claim_id='c1',
                requirement_ids=[r1.requirement_id],
                text=q1,
                value_type=ValueType.ENTITY,
                value='Ada Lovelace',
                subject_key='Ada Lovelace',
                dependencies=[],
                evidence=[EvidenceRef(source_id=v1.source_id, quote=q1)],
            )
            c2 = Claim(
                claim_id='c2',
                requirement_ids=[r2.requirement_id],
                text=q2,
                value_type=ValueType.DATE_TIME,
                value='2024',
                subject_key='Ada Lovelace',
                dependencies=[
                    DependencyBinding(
                        parent_requirement_id=r1.requirement_id,
                        parent_claim_id='c1',
                        subject_key='Ada Lovelace',
                    )
                ],
                evidence=[EvidenceRef(source_id=v2.source_id, quote=q2)],
            )
            assessments = [
                SourceAssessment(
                    source_id=v1.source_id,
                    role='PRIMARY',
                    relation='SUPPORTS',
                    grounding_quotes=[q1],
                    grounding_span_ids=[],
                    note='Identifies lab lead',
                ),
                SourceAssessment(
                    source_id=v2.source_id,
                    role='PRIMARY',
                    relation='SUPPORTS',
                    grounding_quotes=[q2],
                    grounding_span_ids=[],
                    note='Identifies publication year',
                ),
            ]
            supports = [
                RequirementSupport(requirement_id=r1.requirement_id, status='SUFFICIENT', claim_ids=['c1'], missing=''),
                RequirementSupport(requirement_id=r2.requirement_id, status='SUFFICIENT', claim_ids=['c2'], missing=''),
            ]
            return ProviderResult(
                proposal=LLMProposal(
                    requirements=request.requirements,
                    source_assessments=assessments,
                    claims=[c1, c2],
                    requirement_support=supports,
                    interpretation_limit='',
                ),
                status='SUCCESS',
                usage={'attempts': 1, 'input_tokens': 20, 'output_tokens': 20},
                raw=None,
            )

    result = Pipeline(governance, MatchingEntityProvider(), support_checker=ReferenceSupportChecker()).run(
        query, [doc1, doc2], authority
    )

    assert result.response.mode == 'FULL'
    shadow = result.private_trace['local_support_shadow']
    assert shadow['status'] == 'ACCEPTED'
    assert shadow['support_status'] == 'SUPPORTED'
    assert shadow['entity_binding_summary']['matched'] == 2
    assert shadow['entity_binding_summary']['mismatched'] == 0
    assert shadow['entity_binding_summary']['missing'] == 0

    records = [ClaimAuditRecord.model_validate(r) for r in shadow['records']]
    assert len(records) == 2
    assert records[0].query_anchor.snippet == 'Who leads Lab Alpha'
    assert records[1].query_anchor.snippet == 'when did she publish?'
    for rec in records:
        assert rec.query_anchor.valid is True
        assert rec.document_refs[0].valid is True
        assert rec.entity_binding.status == EntityBindingStatus.MATCHED
        assert rec.entity_binding.claim_entity_id == 'person-ada-01'
        assert rec.support_status == SupportStatus.SUPPORTED
        assert rec.runtime_error is None


def test_mismatched_entity_ids_composite_claim_unresolved(authority, governance):
    """Test 2: Combining two verbatim quotes from different trusted entities yields MISMATCHED and UNRESOLVED."""
    doc1 = RawSource(
        private_id='doc-john-a',
        content='John Smith leads Lab Alpha.',
        metadata={},
        public_metadata={},
        entity_id='person-john-alpha',
    )
    doc2 = RawSource(
        private_id='doc-john-b',
        content='John Smith retired in 2021.',
        metadata={},
        public_metadata={},
        entity_id='person-john-beta',
    )
    pipeline = Pipeline(governance, None)
    request, evidence, _ = pipeline.prepare('Describe John Smith.', [doc1, doc2], authority)
    v1, v2 = evidence.views[0], evidence.views[1]

    q1 = 'John Smith leads Lab Alpha.'
    q2 = 'John Smith retired in 2021.'
    claim = Claim(
        claim_id='c1',
        requirement_ids=[request.requirements[0].requirement_id],
        text='John Smith leads Lab Alpha and retired in 2021.',
        value_type=ValueType.TEXT,
        value='John Smith',
        subject_key='John Smith',
        dependencies=[],
        evidence=[
            EvidenceRef(source_id=v1.source_id, quote=q1),
            EvidenceRef(source_id=v2.source_id, quote=q2),
        ],
    )
    proposal = LLMProposal(
        requirements=request.requirements,
        source_assessments=[
            SourceAssessment(source_id=v1.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=[q1], grounding_span_ids=[], note=''),
            SourceAssessment(source_id=v2.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=[q2], grounding_span_ids=[], note=''),
        ],
        claims=[claim],
        requirement_support=[
            RequirementSupport(requirement_id=request.requirements[0].requirement_id, status='SUFFICIENT', claim_ids=['c1'], missing='')
        ],
        interpretation_limit='',
    )

    shadow = ReferenceSupportChecker().check(request, evidence, proposal)
    assert shadow['status'] == 'REJECTED'
    assert shadow['support_status'] == 'UNRESOLVED'
    assert shadow['references_valid'] == 2
    assert shadow['references_invalid'] == 0
    assert shadow['rejections'][0]['reason'] == 'ENTITY_ID_MISMATCH'

    rec = ClaimAuditRecord.model_validate(shadow['records'][0])
    assert rec.query_anchor.valid is True
    assert all(ref.valid for ref in rec.document_refs)
    assert rec.entity_binding.status == EntityBindingStatus.MISMATCHED
    assert rec.entity_binding.error == 'ENTITY_ID_MISMATCH'
    assert rec.support_status == SupportStatus.UNRESOLVED


def test_mismatched_entity_ids_across_dependent_claims_and_public_invariance(authority, governance):
    """Test 3: Dependent claims citing homonymous entities with distinct trusted IDs are caught as MISMATCHED/UNRESOLVED while public output stays invariant."""
    doc1 = RawSource(
        private_id='doc-homonym-1',
        content='John Smith leads Lab Alpha.',
        metadata={},
        public_metadata={},
        entity_id='person-john-001',
    )
    doc2 = RawSource(
        private_id='doc-homonym-2',
        content='John Smith joined in 2019.',
        metadata={},
        public_metadata={},
        entity_id='person-john-002',
    )
    query = 'Who leads Lab Alpha and when did he join?'

    class HomonymMixupProvider:
        def propose(self, request, evidence):
            v1, v2 = evidence.views[0], evidence.views[1]
            r1, r2 = request.requirements[0], request.requirements[1]
            q1 = 'John Smith leads Lab Alpha.'
            q2 = 'John Smith joined in 2019.'

            c1 = Claim(
                claim_id='c1',
                requirement_ids=[r1.requirement_id],
                text=q1,
                value_type=ValueType.ENTITY,
                value='John Smith',
                subject_key='John Smith',
                dependencies=[],
                evidence=[EvidenceRef(source_id=v1.source_id, quote=q1)],
            )
            c2 = Claim(
                claim_id='c2',
                requirement_ids=[r2.requirement_id],
                text=q2,
                value_type=ValueType.DATE_TIME,
                value='2019',
                subject_key='John Smith',
                dependencies=[
                    DependencyBinding(
                        parent_requirement_id=r1.requirement_id,
                        parent_claim_id='c1',
                        subject_key='John Smith',
                    )
                ],
                evidence=[EvidenceRef(source_id=v2.source_id, quote=q2)],
            )
            return ProviderResult(
                proposal=LLMProposal(
                    requirements=request.requirements,
                    source_assessments=[
                        SourceAssessment(source_id=v1.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=[q1], grounding_span_ids=[], note=''),
                        SourceAssessment(source_id=v2.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=[q2], grounding_span_ids=[], note=''),
                    ],
                    claims=[c1, c2],
                    requirement_support=[
                        RequirementSupport(requirement_id=r1.requirement_id, status='SUFFICIENT', claim_ids=['c1'], missing=''),
                        RequirementSupport(requirement_id=r2.requirement_id, status='SUFFICIENT', claim_ids=['c2'], missing=''),
                    ],
                    interpretation_limit='',
                ),
                status='SUCCESS',
                usage={'attempts': 1, 'input_tokens': 20, 'output_tokens': 20},
                raw=None,
            )

    res_without = Pipeline(governance, HomonymMixupProvider(), support_checker=None).run(query, [doc1, doc2], authority)
    res_with = Pipeline(governance, HomonymMixupProvider(), support_checker=ReferenceSupportChecker()).run(
        query, [doc1, doc2], authority
    )

    assert res_without.response == res_with.response
    shadow = res_with.private_trace['local_support_shadow']
    assert shadow['status'] == 'REJECTED'
    assert shadow['support_status'] == 'UNRESOLVED'
    assert shadow['entity_binding_summary']['mismatched'] == 2


def test_mismatched_entity_ids_shared_subject_key_without_dependency(authority, governance):
    """Test 4: Independent claims sharing the same subject_key but backed by distinct entity_ids are flagged MISMATCHED."""
    doc1 = RawSource(private_id='d1', content='Dr. Taylor works in Rome.', metadata={}, public_metadata={}, entity_id='ent-taylor-1')
    doc2 = RawSource(private_id='d2', content='Dr. Taylor won the prize.', metadata={}, public_metadata={}, entity_id='ent-taylor-2')

    pipeline = Pipeline(governance, None)
    request, evidence, _ = pipeline.prepare('Tell me about Dr. Taylor.', [doc1, doc2], authority)
    v1, v2 = evidence.views[0], evidence.views[1]
    rid = request.requirements[0].requirement_id

    c1 = Claim(
        claim_id='c1',
        requirement_ids=[rid],
        text='Dr. Taylor works in Rome.',
        value_type=ValueType.TEXT,
        value='Rome',
        subject_key='Dr. Taylor',
        dependencies=[],
        evidence=[EvidenceRef(source_id=v1.source_id, quote='Dr. Taylor works in Rome.')],
    )
    c2 = Claim(
        claim_id='c2',
        requirement_ids=[rid],
        text='Dr. Taylor won the prize.',
        value_type=ValueType.TEXT,
        value='prize',
        subject_key='Dr. Taylor',
        dependencies=[],
        evidence=[EvidenceRef(source_id=v2.source_id, quote='Dr. Taylor won the prize.')],
    )
    proposal = LLMProposal(
        requirements=request.requirements,
        source_assessments=[
            SourceAssessment(source_id=v1.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=['Dr. Taylor works in Rome.'], grounding_span_ids=[], note=''),
            SourceAssessment(source_id=v2.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=['Dr. Taylor won the prize.'], grounding_span_ids=[], note=''),
        ],
        claims=[c1, c2],
        requirement_support=[RequirementSupport(requirement_id=rid, status='SUFFICIENT', claim_ids=['c1', 'c2'], missing='')],
        interpretation_limit='',
    )

    shadow = ReferenceSupportChecker().check(request, evidence, proposal)
    assert shadow['status'] == 'REJECTED'
    assert shadow['support_status'] == 'UNRESOLVED'
    assert all(r['entity_binding']['status'] == 'MISMATCHED' for r in shadow['records'])


def test_missing_entity_id_across_two_sources_unresolved(authority, governance):
    """Test 5: Combining two sources when at least one lacks a trusted entity_id produces MISSING and UNRESOLVED."""
    doc1 = RawSource(
        private_id='doc-known-entity',
        content='Ada Lovelace leads Lab Alpha.',
        metadata={},
        public_metadata={},
        entity_id='person-ada-01',
    )
    doc2 = RawSource(
        private_id='doc-missing-entity',
        content='She completed 5 milestones.',
        metadata={},
        public_metadata={},
        entity_id=None,
    )
    pipeline = Pipeline(governance, None)
    request, evidence, _ = pipeline.prepare('Milestones of Lab Alpha lead?', [doc1, doc2], authority)
    v1, v2 = evidence.views[0], evidence.views[1]
    rid = request.requirements[0].requirement_id

    claim = Claim(
        claim_id='c1',
        requirement_ids=[rid],
        text='Ada Lovelace completed 5 milestones.',
        value_type=ValueType.TEXT,
        value='5',
        subject_key='Ada Lovelace',
        dependencies=[],
        evidence=[
            EvidenceRef(source_id=v1.source_id, quote='Ada Lovelace leads Lab Alpha.'),
            EvidenceRef(source_id=v2.source_id, quote='She completed 5 milestones.'),
        ],
    )
    proposal = LLMProposal(
        requirements=request.requirements,
        source_assessments=[
            SourceAssessment(source_id=v1.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=['Ada Lovelace leads Lab Alpha.'], grounding_span_ids=[], note=''),
            SourceAssessment(source_id=v2.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=['She completed 5 milestones.'], grounding_span_ids=[], note=''),
        ],
        claims=[claim],
        requirement_support=[RequirementSupport(requirement_id=rid, status='SUFFICIENT', claim_ids=['c1'], missing='')],
        interpretation_limit='',
    )

    shadow = ReferenceSupportChecker().check(request, evidence, proposal)
    assert shadow['status'] == 'REJECTED'
    assert shadow['support_status'] == 'UNRESOLVED'
    assert shadow['rejections'][0]['reason'] == 'MISSING_SOURCE_ENTITY_ID'

    rec = ClaimAuditRecord.model_validate(shadow['records'][0])
    assert rec.entity_binding.status == EntityBindingStatus.MISSING
    assert rec.entity_binding.source_entity_ids[v1.source_id] == 'person-ada-01'
    assert rec.entity_binding.source_entity_ids[v2.source_id] is None
    assert rec.support_status == SupportStatus.UNRESOLVED


def test_missing_entity_id_single_source_when_subject_bound_or_required(authority, governance):
    """Test 6: Single source without entity_id is flagged MISSING when claim has subject_key or checker requires binding."""
    doc = RawSource(
        private_id='doc-no-eid',
        content='Ada Lovelace leads Lab Alpha.',
        metadata={},
        public_metadata={},
        entity_id=None,
    )
    pipeline = Pipeline(governance, None)
    request, evidence, _ = pipeline.prepare('Who leads Lab Alpha?', [doc], authority)
    view = evidence.views[0]
    rid = request.requirements[0].requirement_id
    quote = 'Ada Lovelace leads Lab Alpha.'

    claim_with_subject = Claim(
        claim_id='c1',
        requirement_ids=[rid],
        text=quote,
        value_type=ValueType.ENTITY,
        value='Ada Lovelace',
        subject_key='Ada Lovelace',
        dependencies=[],
        evidence=[EvidenceRef(source_id=view.source_id, quote=quote)],
    )
    proposal = LLMProposal(
        requirements=request.requirements,
        source_assessments=[SourceAssessment(source_id=view.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=[quote], grounding_span_ids=[], note='')],
        claims=[claim_with_subject],
        requirement_support=[RequirementSupport(requirement_id=rid, status='SUFFICIENT', claim_ids=['c1'], missing='')],
        interpretation_limit='',
    )

    shadow = ReferenceSupportChecker().check(request, evidence, proposal)
    assert shadow['status'] == 'REJECTED'
    assert shadow['support_status'] == 'UNRESOLVED'
    assert shadow['records'][0]['entity_binding']['status'] == 'MISSING'

    claim_no_subject = claim_with_subject.model_copy(update={'subject_key': None, 'value_type': ValueType.TEXT})
    proposal_plain = proposal.model_copy(update={'claims': [claim_no_subject]})
    shadow_strict = ReferenceSupportChecker(require_entity_binding=True).check(request, evidence, proposal_plain)
    assert shadow_strict['status'] == 'REJECTED'
    assert shadow_strict['records'][0]['entity_binding']['status'] == 'MISSING'


def test_access_decision_entity_id_precedence_and_denied_source_blocking(authority):
    """Test 7: Authenticated AccessDecision.entity_id overrides RawSource.entity_id and denied entity_ids are blocked."""
    permitted_doc = RawSource(
        private_id='doc-permitted',
        content='The project lead is Ada.',
        metadata={},
        public_metadata={},
        entity_id='raw-fallback-id',
    )
    denied_doc = RawSource(
        private_id='doc-denied',
        content='Secret record.',
        metadata={},
        public_metadata={},
        entity_id='secret-denied-entity-99',
    )

    def policy_resolver(src, auth):
        if src.private_id == 'doc-denied':
            return AccessDecision(access='DENY', existence_public=False)
        return AccessDecision(access='FULL', entity_id='authoritative-policy-entity-01')

    gov = LegacyGovernance(policy_resolver)
    pipeline = Pipeline(gov, None)
    _, evidence, private = pipeline.prepare('Who is the project lead?', [permitted_doc, denied_doc], authority)

    assert len(evidence.entity_bindings) == 1
    assert evidence.entity_bindings[0].entity_id == 'authoritative-policy-entity-01'
    assert 'secret-denied-entity-99' in private['blocked_values']


def test_same_entity_source_contradiction_returns_contradicted(authority, governance):
    """Test 8: Contradictory source assessment on the same trusted entity produces CONTRADICTED."""
    doc1 = RawSource(
        private_id='doc-status-1',
        content='Ada Lovelace is an active researcher.',
        metadata={},
        public_metadata={},
        entity_id='person-ada-01',
    )
    doc2 = RawSource(
        private_id='doc-status-2',
        content='Ada Lovelace retired from all research duties.',
        metadata={},
        public_metadata={},
        entity_id='person-ada-01',
    )
    pipeline = Pipeline(governance, None)
    request, evidence, _ = pipeline.prepare('Is Ada Lovelace an active researcher?', [doc1, doc2], authority)
    v1, v2 = evidence.views[0], evidence.views[1]
    rid = request.requirements[0].requirement_id
    q1 = 'Ada Lovelace is an active researcher.'

    claim = Claim(
        claim_id='c1',
        requirement_ids=[rid],
        text=q1,
        value_type=ValueType.TEXT,
        value='active',
        subject_key='Ada Lovelace',
        dependencies=[],
        evidence=[EvidenceRef(source_id=v1.source_id, quote=q1)],
    )
    proposal = LLMProposal(
        requirements=request.requirements,
        source_assessments=[
            SourceAssessment(source_id=v1.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=[q1], grounding_span_ids=[], note='States active'),
            SourceAssessment(source_id=v2.source_id, role='CONTRASTIVE', relation='CONTRADICTS', grounding_quotes=['Ada Lovelace retired from all research duties.'], grounding_span_ids=[], note='Directly contradicts active status'),
        ],
        claims=[claim],
        requirement_support=[RequirementSupport(requirement_id=rid, status='SUFFICIENT', claim_ids=['c1'], missing='')],
        interpretation_limit='',
    )

    shadow = ReferenceSupportChecker().check(request, evidence, proposal)
    assert shadow['status'] == 'REJECTED'
    assert shadow['support_status'] == 'CONTRADICTED'
    assert shadow['rejections'][0]['reason'] == 'SOURCE_CONTRADICTION'

    rec = ClaimAuditRecord.model_validate(shadow['records'][0])
    assert rec.entity_binding.status == EntityBindingStatus.MATCHED
    assert rec.entity_binding.claim_entity_id == 'person-ada-01'
    assert rec.support_status == SupportStatus.CONTRADICTED


def test_different_entity_contradiction_does_not_taint_matched_entity(authority, governance):
    """Test 9: A CONTRADICTS assessment on a source bound to a DIFFERENT entity does not taint a matched claim."""
    doc_ada = RawSource(
        private_id='doc-ada',
        content='Ada Lovelace is an active researcher.',
        metadata={},
        public_metadata={},
        entity_id='person-ada-01',
    )
    doc_bob = RawSource(
        private_id='doc-bob',
        content='Bob Martin retired in 2020.',
        metadata={},
        public_metadata={},
        entity_id='person-bob-02',
    )
    pipeline = Pipeline(governance, None)
    request, evidence, _ = pipeline.prepare('Is Ada Lovelace active?', [doc_ada, doc_bob], authority)
    v_ada, v_bob = evidence.views[0], evidence.views[1]
    rid = request.requirements[0].requirement_id
    q_ada = 'Ada Lovelace is an active researcher.'

    claim = Claim(
        claim_id='c1',
        requirement_ids=[rid],
        text=q_ada,
        value_type=ValueType.TEXT,
        value='active',
        subject_key='Ada Lovelace',
        dependencies=[],
        evidence=[EvidenceRef(source_id=v_ada.source_id, quote=q_ada)],
    )
    proposal = LLMProposal(
        requirements=request.requirements,
        source_assessments=[
            SourceAssessment(source_id=v_ada.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=[q_ada], grounding_span_ids=[], note=''),
            SourceAssessment(source_id=v_bob.source_id, role='CONTRASTIVE', relation='CONTRADICTS', grounding_quotes=['Bob Martin retired in 2020.'], grounding_span_ids=[], note='About Bob, not Ada'),
        ],
        claims=[claim],
        requirement_support=[RequirementSupport(requirement_id=rid, status='SUFFICIENT', claim_ids=['c1'], missing='')],
        interpretation_limit='',
    )

    shadow = ReferenceSupportChecker().check(request, evidence, proposal)
    assert shadow['status'] == 'ACCEPTED'
    assert shadow['support_status'] == 'SUPPORTED'
    assert shadow['records'][0]['support_status'] == 'SUPPORTED'
    assert shadow['records'][0]['entity_binding']['status'] == 'MATCHED'


def test_insufficient_evidence_missing_claims_and_non_primary_role(authority, governance):
    """Test 10: Abstention with empty claims or non-PRIMARY source role yields INSUFFICIENT."""
    doc = RawSource(
        private_id='doc-partial',
        content='The expedition vessel departed at dawn.',
        metadata={},
        public_metadata={},
        entity_id='vessel-01',
    )
    pipeline = Pipeline(governance, None)
    request, evidence, _ = pipeline.prepare('What color is the expedition vessel?', [doc], authority)
    view = evidence.views[0]
    rid = request.requirements[0].requirement_id

    # Case A: Empty claims (honest abstention due to missing evidence)
    empty_proposal = LLMProposal(
        requirements=request.requirements,
        source_assessments=[
            SourceAssessment(source_id=view.source_id, role='IRRELEVANT', relation='NONE', grounding_quotes=[], grounding_span_ids=[], note='No color mentioned')
        ],
        claims=[],
        requirement_support=[RequirementSupport(requirement_id=rid, status='MISSING', claim_ids=[], missing='Vessel color not stated')],
        interpretation_limit='',
    )
    shadow_empty = ReferenceSupportChecker().check(request, evidence, empty_proposal)
    assert shadow_empty['status'] == 'EMPTY_PROPOSAL'
    assert shadow_empty['support_status'] == 'INSUFFICIENT'
    assert len(shadow_empty['records']) == 1
    rec_empty = ClaimAuditRecord.model_validate(shadow_empty['records'][0])
    assert rec_empty.claim_id is None
    assert rec_empty.query_anchor.valid is True
    assert rec_empty.support_status == SupportStatus.INSUFFICIENT

    # Case B: Claim backed only by a CONTEXTUAL (non-PRIMARY) source
    quote = 'The expedition vessel departed at dawn.'
    weak_claim = Claim(
        claim_id='c1',
        requirement_ids=[rid],
        text=quote,
        value_type=ValueType.TEXT,
        value='dawn',
        subject_key=None,
        dependencies=[],
        evidence=[EvidenceRef(source_id=view.source_id, quote=quote)],
    )
    weak_proposal = LLMProposal(
        requirements=request.requirements,
        source_assessments=[
            SourceAssessment(source_id=view.source_id, role='CONTEXTUAL', relation='SUPPORTS', grounding_quotes=[quote], grounding_span_ids=[], note='Contextual only')
        ],
        claims=[weak_claim],
        requirement_support=[RequirementSupport(requirement_id=rid, status='PARTIAL', claim_ids=['c1'], missing='Color missing')],
        interpretation_limit='',
    )
    shadow_weak = ReferenceSupportChecker().check(request, evidence, weak_proposal)
    assert shadow_weak['status'] == 'REJECTED'
    assert shadow_weak['support_status'] == 'INSUFFICIENT'
    assert shadow_weak['rejections'][0]['reason'] == 'INSUFFICIENT_EVIDENCE_SUPPORT'
    assert shadow_weak['records'][0]['support_status'] == 'INSUFFICIENT'


def test_stale_entity_signature_tampering_detected(authority, governance):
    """Test 11: Modifying entity_bindings without updating entity_signature is rejected as STALE_ENTITY_BINDING."""
    doc = RawSource(
        private_id='doc-tamper',
        content='The expedition vessel is blue.',
        metadata={},
        public_metadata={},
        entity_id='vessel-01',
    )
    pipeline = Pipeline(governance, None)
    request, evidence, _ = pipeline.prepare('What color is the expedition vessel?', [doc], authority)
    view = evidence.views[0]
    rid = request.requirements[0].requirement_id
    quote = 'The expedition vessel is blue.'

    tampered_evidence = evidence.model_copy(
        update={'entity_bindings': [SourceEntityBinding(source_id=view.source_id, entity_id='spoofed-vessel-99')]}
    )
    proposal = LLMProposal(
        requirements=request.requirements,
        source_assessments=[SourceAssessment(source_id=view.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=[quote], grounding_span_ids=[], note='')],
        claims=[
            Claim(
                claim_id='c1',
                requirement_ids=[rid],
                text=quote,
                value_type=ValueType.TEXT,
                value='blue',
                subject_key=None,
                dependencies=[],
                evidence=[EvidenceRef(source_id=view.source_id, quote=quote)],
            )
        ],
        requirement_support=[RequirementSupport(requirement_id=rid, status='SUFFICIENT', claim_ids=['c1'], missing='')],
        interpretation_limit='',
    )

    shadow = ReferenceSupportChecker().check(request, tampered_evidence, proposal)
    assert shadow['status'] == 'REJECTED'
    assert shadow['support_status'] == 'UNRESOLVED'
    assert any(r.get('reason') == 'STALE_ENTITY_BINDING' for r in shadow['rejections'])


def test_both_reference_kinds_and_record_contract_compliance(authority, governance):
    """Test 12: Verifies both query-snippet anchoring and quote + span_id document references in ClaimAuditRecord."""
    doc = RawSource(
        private_id='doc-both-refs',
        content='Captain Alice commands Vessel Echo. Vessel Echo is docked at Pier 4.',
        metadata={},
        public_metadata={'title': 'Harbor Registry'},
        entity_id='vessel-echo-01',
    )
    query = 'Who commands Vessel Echo and where is it docked?'
    pipeline = Pipeline(governance, None)
    request, evidence, _ = pipeline.prepare(query, [doc], authority)
    view = evidence.views[0]
    r1, r2 = request.requirements[0], request.requirements[1]

    c1 = Claim(
        claim_id='c-quote',
        requirement_ids=[r1.requirement_id],
        text='Captain Alice commands Vessel Echo.',
        value_type=ValueType.ENTITY,
        value='Captain Alice',
        subject_key='Vessel Echo',
        dependencies=[],
        evidence=[EvidenceRef(source_id=view.source_id, quote='Captain Alice commands Vessel Echo.')],
    )
    c2 = Claim(
        claim_id='c-span',
        requirement_ids=[r2.requirement_id],
        text='Vessel Echo is docked at Pier 4.',
        value_type=ValueType.TEXT,
        value='Pier 4',
        subject_key='Vessel Echo',
        dependencies=[],
        evidence=[EvidenceRef(source_id=view.source_id, span_id=view.spans[0].span_id, quote=None)],
    )
    proposal = LLMProposal(
        requirements=request.requirements,
        source_assessments=[
            SourceAssessment(
                source_id=view.source_id,
                role='PRIMARY',
                relation='SUPPORTS',
                grounding_quotes=['Captain Alice commands Vessel Echo.'],
                grounding_span_ids=[view.spans[0].span_id],
                note='Supports both claims',
            )
        ],
        claims=[c1, c2],
        requirement_support=[
            RequirementSupport(requirement_id=r1.requirement_id, status='SUFFICIENT', claim_ids=['c-quote'], missing=''),
            RequirementSupport(requirement_id=r2.requirement_id, status='SUFFICIENT', claim_ids=['c-span'], missing=''),
        ],
        interpretation_limit='',
    )

    shadow = ReferenceSupportChecker().check(request, evidence, proposal, case_id='harbor-case-01')
    assert shadow['status'] == 'ACCEPTED'
    assert shadow['support_status'] == 'SUPPORTED'

    rec_quote, rec_span = [ClaimAuditRecord.model_validate(r) for r in shadow['records']]
    assert rec_quote.case_id == 'harbor-case-01'
    assert rec_quote.query_anchor.snippet == 'Who commands Vessel Echo'
    assert rec_quote.document_refs[0].matched_snippet == 'Captain Alice commands Vessel Echo.'
    assert rec_quote.entity_binding.status == EntityBindingStatus.MATCHED

    assert rec_span.case_id == 'harbor-case-01'
    assert rec_span.query_anchor.snippet == 'where is it docked?'
    assert rec_span.document_refs[0].span_id == view.spans[0].span_id
    assert rec_span.document_refs[0].matched_snippet == doc.content
    assert rec_span.entity_binding.status == EntityBindingStatus.MATCHED


# ==============================================================================
# PR 2 Code Review Regression Tests (13 - 16)
# ==============================================================================

def test_omitted_claim_dependencies_and_subject_key_still_enforces_request_depends_on(authority, governance):
    """Test 13: When request.requirements[1].depends_on points to req-1, omitting claim.dependencies
    and subject_key cannot sneak Ada's lead claim + Bob's task-count claim through as SUPPORTED."""
    doc_ada = RawSource(
        private_id='doc-ada-lead',
        content='Ada vezette a projektet.',
        metadata={},
        public_metadata={},
        entity_id='person-ada-01',
    )
    doc_bob = RawSource(
        private_id='doc-bob-tasks',
        content='Bob öt feladatot zárt le.',
        metadata={},
        public_metadata={},
        entity_id='person-bob-02',
    )
    query = 'Ki vezette a projektet és hány feladatot zárt le ő?'
    pipeline = Pipeline(governance, None)
    request, evidence, _ = pipeline.prepare(query, [doc_ada, doc_bob], authority)
    assert len(request.requirements) == 2
    r1, r2 = request.requirements[0], request.requirements[1]
    assert r2.depends_on == [r1.requirement_id]
    v_ada, v_bob = evidence.views[0], evidence.views[1]

    # Model deliberately omits dependencies=[] and subject_key=None on both claims
    c1 = Claim(
        claim_id='c1',
        requirement_ids=[r1.requirement_id],
        text='Ada vezette a projektet.',
        value_type=ValueType.ENTITY,
        value='Ada',
        subject_key=None,
        dependencies=[],
        evidence=[EvidenceRef(source_id=v_ada.source_id, quote='Ada vezette a projektet.')],
    )
    c2 = Claim(
        claim_id='c2',
        requirement_ids=[r2.requirement_id],
        text='Bob öt feladatot zárt le.',
        value_type=ValueType.NUMBER,
        value='5',
        subject_key=None,
        dependencies=[],
        evidence=[EvidenceRef(source_id=v_bob.source_id, quote='Bob öt feladatot zárt le.')],
    )
    proposal = LLMProposal(
        requirements=request.requirements,
        source_assessments=[
            SourceAssessment(source_id=v_ada.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=['Ada vezette a projektet.'], grounding_span_ids=[], note=''),
            SourceAssessment(source_id=v_bob.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=['Bob öt feladatot zárt le.'], grounding_span_ids=[], note=''),
        ],
        claims=[c1, c2],
        requirement_support=[
            RequirementSupport(requirement_id=r1.requirement_id, status='SUFFICIENT', claim_ids=['c1'], missing=''),
            RequirementSupport(requirement_id=r2.requirement_id, status='SUFFICIENT', claim_ids=['c2'], missing=''),
        ],
        interpretation_limit='',
    )

    shadow = ReferenceSupportChecker().check(request, evidence, proposal)
    assert shadow['status'] == 'REJECTED'
    assert shadow['support_status'] == 'UNRESOLVED'
    assert any(rej.get('claim_id') == 'c2' and rej.get('reason') == 'ENTITY_ID_MISMATCH' for rej in shadow['rejections'])

    rec1, rec2 = [ClaimAuditRecord.model_validate(r) for r in shadow['records']]
    assert rec1.claim_id == 'c1'
    assert rec1.entity_binding.status == EntityBindingStatus.MATCHED
    assert rec1.support_status == SupportStatus.SUPPORTED

    assert rec2.claim_id == 'c2'
    assert rec2.entity_binding.status == EntityBindingStatus.MISMATCHED
    assert rec2.support_status == SupportStatus.UNRESOLVED


def test_scoped_contradiction_does_not_taint_independent_claim_on_same_entity(authority, governance):
    """Test 14: Conflict between 'Ada closed 3 tasks' and 'Ada closed 0 tasks' marks only the task-count
    claim/requirement CONTRADICTED while keeping 'Ada led the project' SUPPORTED."""
    doc_lead = RawSource(
        private_id='doc-ada-lead',
        content='Ada vezette a projektet.',
        metadata={},
        public_metadata={},
        entity_id='person-ada-01',
    )
    doc_three = RawSource(
        private_id='doc-ada-three',
        content='Ada három feladatot zárt le.',
        metadata={},
        public_metadata={},
        entity_id='person-ada-01',
    )
    doc_zero = RawSource(
        private_id='doc-ada-zero',
        content='Ada nulla feladatot zárt le.',
        metadata={},
        public_metadata={},
        entity_id='person-ada-01',
    )
    query = 'Ki vezette a projektet és hány feladatot zárt le ő?'
    pipeline = Pipeline(governance, None)
    request, evidence, _ = pipeline.prepare(query, [doc_lead, doc_three, doc_zero], authority)
    r1, r2 = request.requirements[0], request.requirements[1]
    v_lead, v_three, v_zero = evidence.views[0], evidence.views[1], evidence.views[2]

    c1 = Claim(
        claim_id='c-lead',
        requirement_ids=[r1.requirement_id],
        text='Ada vezette a projektet.',
        value_type=ValueType.ENTITY,
        value='Ada',
        subject_key='Ada',
        dependencies=[],
        evidence=[EvidenceRef(source_id=v_lead.source_id, quote='Ada vezette a projektet.')],
    )
    c2 = Claim(
        claim_id='c-tasks-3',
        requirement_ids=[r2.requirement_id],
        text='Ada három feladatot zárt le.',
        value_type=ValueType.NUMBER,
        value='3',
        subject_key='Ada',
        dependencies=[DependencyBinding(parent_requirement_id=r1.requirement_id, parent_claim_id='c-lead', subject_key='Ada')],
        evidence=[EvidenceRef(source_id=v_three.source_id, quote='Ada három feladatot zárt le.')],
    )

    # Variant A: Explicit target via contradicts_claim_ids / contradicts_requirement_ids
    proposal_targeted = LLMProposal(
        requirements=request.requirements,
        source_assessments=[
            SourceAssessment(source_id=v_lead.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=['Ada vezette a projektet.'], grounding_span_ids=[], note=''),
            SourceAssessment(source_id=v_three.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=['Ada három feladatot zárt le.'], grounding_span_ids=[], note=''),
            SourceAssessment(
                source_id=v_zero.source_id,
                role='CONTRASTIVE',
                relation='CONTRADICTS',
                grounding_quotes=['Ada nulla feladatot zárt le.'],
                grounding_span_ids=[],
                note='Conflicts on task count',
                contradicts_claim_ids=['c-tasks-3'],
                contradicts_requirement_ids=[r2.requirement_id],
            ),
        ],
        claims=[c1, c2],
        requirement_support=[
            RequirementSupport(requirement_id=r1.requirement_id, status='SUFFICIENT', claim_ids=['c-lead'], missing=''),
            RequirementSupport(requirement_id=r2.requirement_id, status='SUFFICIENT', claim_ids=['c-tasks-3'], missing=''),
        ],
        interpretation_limit='',
    )
    shadow_a = ReferenceSupportChecker().check(request, evidence, proposal_targeted)
    assert shadow_a['status'] == 'REJECTED'
    assert shadow_a['support_status'] == 'CONTRADICTED'
    recs_a = {r['claim_id']: ClaimAuditRecord.model_validate(r) for r in shadow_a['records']}
    assert recs_a['c-lead'].support_status == SupportStatus.SUPPORTED
    assert recs_a['c-tasks-3'].support_status == SupportStatus.CONTRADICTED

    # Variant B: c2 directly cites both v_three (SUPPORTS) and v_zero (CONTRADICTS) without explicit target list
    c2_both = c2.model_copy(
        update={
            'evidence': [
                EvidenceRef(source_id=v_three.source_id, quote='Ada három feladatot zárt le.'),
                EvidenceRef(source_id=v_zero.source_id, quote='Ada nulla feladatot zárt le.'),
            ]
        }
    )
    proposal_direct = proposal_targeted.model_copy(
        update={
            'claims': [c1, c2_both],
            'source_assessments': [
                proposal_targeted.source_assessments[0],
                proposal_targeted.source_assessments[1],
                SourceAssessment(
                    source_id=v_zero.source_id,
                    role='CONTRASTIVE',
                    relation='CONTRADICTS',
                    grounding_quotes=['Ada nulla feladatot zárt le.'],
                    grounding_span_ids=[],
                    note='Direct ref contradiction',
                ),
            ],
        }
    )
    shadow_b = ReferenceSupportChecker().check(request, evidence, proposal_direct)
    recs_b = {r['claim_id']: ClaimAuditRecord.model_validate(r) for r in shadow_b['records']}
    assert recs_b['c-lead'].support_status == SupportStatus.SUPPORTED
    assert recs_b['c-tasks-3'].support_status == SupportStatus.CONTRADICTED

    # Variant C: Competing scalar claims c-tasks-3 (value='3') and c-tasks-0 (value='0') on req-2
    c2_zero = Claim(
        claim_id='c-tasks-0',
        requirement_ids=[r2.requirement_id],
        text='Ada nulla feladatot zárt le.',
        value_type=ValueType.NUMBER,
        value='0',
        subject_key='Ada',
        dependencies=[DependencyBinding(parent_requirement_id=r1.requirement_id, parent_claim_id='c-lead', subject_key='Ada')],
        evidence=[EvidenceRef(source_id=v_zero.source_id, quote='Ada nulla feladatot zárt le.')],
    )
    proposal_competing = LLMProposal(
        requirements=request.requirements,
        source_assessments=[
            SourceAssessment(source_id=v_lead.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=['Ada vezette a projektet.'], grounding_span_ids=[], note=''),
            SourceAssessment(source_id=v_three.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=['Ada három feladatot zárt le.'], grounding_span_ids=[], note=''),
            SourceAssessment(source_id=v_zero.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=['Ada nulla feladatot zárt le.'], grounding_span_ids=[], note=''),
        ],
        claims=[c1, c2, c2_zero],
        requirement_support=[
            RequirementSupport(requirement_id=r1.requirement_id, status='SUFFICIENT', claim_ids=['c-lead'], missing=''),
            RequirementSupport(requirement_id=r2.requirement_id, status='SUFFICIENT', claim_ids=['c-tasks-3', 'c-tasks-0'], missing=''),
        ],
        interpretation_limit='',
    )
    shadow_c = ReferenceSupportChecker().check(request, evidence, proposal_competing)
    recs_c = {r['claim_id']: ClaimAuditRecord.model_validate(r) for r in shadow_c['records']}
    assert recs_c['c-lead'].support_status == SupportStatus.SUPPORTED
    assert recs_c['c-tasks-3'].support_status == SupportStatus.CONTRADICTED
    assert recs_c['c-tasks-0'].support_status == SupportStatus.CONTRADICTED


def test_unscoped_multi_requirement_contradiction_rejected_without_poisoning_claims(authority, governance):
    """Test 15: An unlinked CONTRADICTS assessment in a multi-requirement proposal does not poison valid claims
    and is flagged as UNSCOPED_CONTRADICTION_ASSESSMENT."""
    doc1 = RawSource(private_id='d1', content='Ada vezette a projektet.', metadata={}, public_metadata={}, entity_id='person-ada-01')
    doc2 = RawSource(private_id='d2', content='Ada három feladatot zárt le.', metadata={}, public_metadata={}, entity_id='person-ada-01')
    doc3 = RawSource(private_id='d3', content='Ada nulla feladatot zárt le.', metadata={}, public_metadata={}, entity_id='person-ada-01')

    query = 'Ki vezette a projektet és hány feladatot zárt le ő?'
    pipeline = Pipeline(governance, None)
    request, evidence, _ = pipeline.prepare(query, [doc1, doc2, doc3], authority)
    r1, r2 = request.requirements[0], request.requirements[1]
    v1, v2, v3 = evidence.views[0], evidence.views[1], evidence.views[2]

    c1 = Claim(
        claim_id='c1',
        requirement_ids=[r1.requirement_id],
        text='Ada vezette a projektet.',
        value_type=ValueType.ENTITY,
        value='Ada',
        subject_key='Ada',
        dependencies=[],
        evidence=[EvidenceRef(source_id=v1.source_id, quote='Ada vezette a projektet.')],
    )
    c2 = Claim(
        claim_id='c2',
        requirement_ids=[r2.requirement_id],
        text='Ada három feladatot zárt le.',
        value_type=ValueType.NUMBER,
        value='3',
        subject_key='Ada',
        dependencies=[DependencyBinding(parent_requirement_id=r1.requirement_id, parent_claim_id='c1', subject_key='Ada')],
        evidence=[EvidenceRef(source_id=v2.source_id, quote='Ada három feladatot zárt le.')],
    )
    proposal = LLMProposal(
        requirements=request.requirements,
        source_assessments=[
            SourceAssessment(source_id=v1.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=['Ada vezette a projektet.'], grounding_span_ids=[], note=''),
            SourceAssessment(source_id=v2.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=['Ada három feladatot zárt le.'], grounding_span_ids=[], note=''),
            SourceAssessment(source_id=v3.source_id, role='CONTRASTIVE', relation='CONTRADICTS', grounding_quotes=['Ada nulla feladatot zárt le.'], grounding_span_ids=[], note='Unscoped contradiction'),
        ],
        claims=[c1, c2],
        requirement_support=[
            RequirementSupport(requirement_id=r1.requirement_id, status='SUFFICIENT', claim_ids=['c1'], missing=''),
            RequirementSupport(requirement_id=r2.requirement_id, status='SUFFICIENT', claim_ids=['c2'], missing=''),
        ],
        interpretation_limit='',
    )

    shadow = ReferenceSupportChecker().check(request, evidence, proposal)
    assert shadow['status'] == 'REJECTED'
    assert any(r.get('reason') == 'UNSCOPED_CONTRADICTION_ASSESSMENT' for r in shadow['rejections'])
    recs = {r['claim_id']: ClaimAuditRecord.model_validate(r) for r in shadow['records']}
    assert recs['c1'].support_status == SupportStatus.SUPPORTED


def test_replaying_old_view_0001_entity_binding_onto_new_document_is_rejected(authority, governance):
    """Test 16: Copying Ada's (entity_bindings, entity_signature) for view-0001 onto Bob's new view-0001
    document is rejected as STALE_ENTITY_BINDING."""
    doc_ada = RawSource(
        private_id='doc-run1-ada',
        content='Ada Lovelace leads Lab Alpha.',
        metadata={},
        public_metadata={},
        entity_id='person-ada-01',
    )
    doc_bob = RawSource(
        private_id='doc-run2-bob',
        content='Bob Martin leads Lab Beta.',
        metadata={},
        public_metadata={},
        entity_id='person-bob-02',
    )

    auth_run1 = authority.model_copy(update={'request_id': 'run-1'})
    auth_run2 = authority.model_copy(update={'request_id': 'run-2'})

    _, evidence_ada, _ = Pipeline(governance, None).prepare('Who leads the lab?', [doc_ada], auth_run1)
    request_bob, evidence_bob, _ = Pipeline(governance, None).prepare('Who leads the lab?', [doc_bob], auth_run2)

    # Both runs assign neutral ID 'view-0001' to their first authorized view
    assert evidence_ada.views[0].source_id == 'view-0001'
    assert evidence_bob.views[0].source_id == 'view-0001'

    # Attack A: Replay both entity_bindings and entity_signature from Ada's run onto Bob's document
    replayed_evidence = evidence_bob.model_copy(
        update={
            'entity_bindings': evidence_ada.entity_bindings,
            'entity_signature': evidence_ada.entity_signature,
        }
    )
    quote_bob = 'Bob Martin leads Lab Beta.'
    rid = request_bob.requirements[0].requirement_id
    proposal_bob = LLMProposal(
        requirements=request_bob.requirements,
        source_assessments=[
            SourceAssessment(
                source_id='view-0001',
                role='PRIMARY',
                relation='SUPPORTS',
                grounding_quotes=[quote_bob],
                grounding_span_ids=[],
                note='',
            )
        ],
        claims=[
            Claim(
                claim_id='c1',
                requirement_ids=[rid],
                text=quote_bob,
                value_type=ValueType.ENTITY,
                value='Bob Martin',
                subject_key='Bob Martin',
                dependencies=[],
                evidence=[EvidenceRef(source_id='view-0001', quote=quote_bob)],
            )
        ],
        requirement_support=[RequirementSupport(requirement_id=rid, status='SUFFICIENT', claim_ids=['c1'], missing='')],
        interpretation_limit='',
    )

    shadow_replay = ReferenceSupportChecker().check(request_bob, replayed_evidence, proposal_bob)
    assert shadow_replay['status'] == 'REJECTED'
    assert shadow_replay['support_status'] == 'UNRESOLVED'
    assert any(r.get('reason') == 'STALE_ENTITY_BINDING' for r in shadow_replay['rejections'])

    # Attack B: Forge content_sha256 on binding and wipe entity_signature=None to try bypassing signature check
    unsigned_forged = evidence_bob.model_copy(
        update={
            'entity_bindings': [
                SourceEntityBinding(
                    source_id='view-0001',
                    entity_id='person-ada-01',
                    content_sha256=evidence_bob.views[0].content_sha256,
                )
            ],
            'entity_signature': None,
        }
    )
    shadow_unsigned = ReferenceSupportChecker().check(request_bob, unsigned_forged, proposal_bob)
    assert shadow_unsigned['status'] == 'REJECTED'
    assert shadow_unsigned['support_status'] == 'UNRESOLVED'
    assert any(r.get('reason') == 'STALE_ENTITY_BINDING' for r in shadow_unsigned['rejections'])

