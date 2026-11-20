"""Tests for ReferenceSupportChecker and offline evidence validation (PR 1).

Covers:
1. Valid citation verification (exact unique quote in permitted document).
2. Rejection of hallucinated quote (quote not found in source).
3. Rejection of unauthorized / unsupplied source citation.
4. Public response invariance (pipeline produces identical PublicResponseContract with and without checker).
5. Enforcement of local_only constraint (rejecting non-local checkers).
6. Multi-claim verification: all citations valid.
7. Multi-claim verification: partial failure (one valid, one hallucinated).
8. Composite citations: single claim supported by multiple distinct quotes.
9. Multi-document citations: citations resolving across distinct governed views.
10. Ambiguous quote rejection: non-unique quote appearing multiple times.
11. Empty quote rejection: whitespace or empty quote string.
12. Span-based citation verification: resolving valid catalog span_id.
13. Invalid span ID rejection: non-existent span reference.
14. Missing evidence rejection: claim with empty evidence references.
15. Ambiguous reference representation rejection: both quote and span_id provided.
"""
import pytest
from component_cfaf.contracts import (
    Authority,
    Claim,
    EvidenceRef,
    LLMProposal,
    ProviderResult,
    RawSource,
    RequirementSupport,
    SourceAssessment,
    ValueType,
)
from component_cfaf.pipeline import Pipeline
from component_cfaf.support_checker import ReferenceSupportChecker


# ==============================================================================
# Base PR 1 Acceptance Tests (1 - 5)
# ==============================================================================

def test_checker_valid_citation(authority, governance):
    """Test that valid exact citations are accepted with verified document snippets."""
    doc = RawSource(
        private_id='doc-vessel-01',
        content='The expedition vessel is blue. It was launched in 2024.',
        metadata={'title': 'Expedition Log'},
        public_metadata={'title': 'Expedition Log'}
    )
    query = 'What color is the expedition vessel?'

    class ValidProvider:
        def propose(self, request, evidence):
            view = evidence.views[0]
            quote = 'The expedition vessel is blue.'
            ref = EvidenceRef(source_id=view.source_id, quote=quote)
            claim = Claim(
                claim_id='c1',
                requirement_ids=[request.requirements[0].requirement_id],
                text='The expedition vessel is blue.',
                value_type=ValueType.TEXT,
                value='blue',
                subject_key=None,
                dependencies=[],
                evidence=[ref]
            )
            assessment = SourceAssessment(
                source_id=view.source_id,
                role='PRIMARY',
                relation='SUPPORTS',
                grounding_quotes=[quote],
                grounding_span_ids=[],
                note='Exact quote support'
            )
            support = RequirementSupport(
                requirement_id=request.requirements[0].requirement_id,
                status='SUFFICIENT',
                claim_ids=['c1'],
                missing=''
            )
            proposal = LLMProposal(
                requirements=request.requirements,
                source_assessments=[assessment],
                claims=[claim],
                requirement_support=[support],
                interpretation_limit=''
            )
            return ProviderResult(
                proposal=proposal,
                status='SUCCESS',
                usage={'attempts': 1, 'input_tokens': 10, 'output_tokens': 10},
                raw=None
            )

    checker = ReferenceSupportChecker()
    pipeline = Pipeline(governance, ValidProvider(), support_checker=checker)
    result = pipeline.run(query, [doc], authority)

    # 1. Pipeline result checks
    assert result.response.mode == 'FULL'

    # 2. Shadow audit trace checks
    shadow = result.private_trace.get('local_support_shadow')
    assert shadow is not None
    assert shadow['status'] == 'ACCEPTED'
    assert shadow['local_only'] is True
    assert shadow['claims_checked'] == 1
    assert shadow['references_valid'] == 1
    assert shadow['references_invalid'] == 0
    assert len(shadow['rejections']) == 0

    # 3. Verify snippet matches source exactly
    detail = shadow['details'][0]
    assert detail['claim_id'] == 'c1'
    assert detail['references'][0]['valid'] is True
    assert detail['references'][0]['matched_snippet'] == 'The expedition vessel is blue.'


def test_checker_rejects_hallucinated_quote(authority, governance):
    """Test that a quote absent from the source is rejected in the shadow audit."""
    doc = RawSource(
        private_id='doc-vessel-01',
        content='The expedition vessel is blue. It was launched in 2024.',
        metadata={'title': 'Expedition Log'},
        public_metadata={'title': 'Expedition Log'}
    )
    query = 'What color is the expedition vessel?'

    class HallucinatingQuoteProvider:
        def propose(self, request, evidence):
            view = evidence.views[0]
            # Quote not in doc content
            quote = 'The expedition vessel is red.'
            ref = EvidenceRef(source_id=view.source_id, quote=quote)
            claim = Claim(
                claim_id='c1',
                requirement_ids=[request.requirements[0].requirement_id],
                text='The expedition vessel is red.',
                value_type=ValueType.TEXT,
                value='red',
                subject_key=None,
                dependencies=[],
                evidence=[ref]
            )
            assessment = SourceAssessment(
                source_id=view.source_id,
                role='PRIMARY',
                relation='SUPPORTS',
                grounding_quotes=[quote],
                grounding_span_ids=[],
                note='Hallucinated quote'
            )
            support = RequirementSupport(
                requirement_id=request.requirements[0].requirement_id,
                status='SUFFICIENT',
                claim_ids=['c1'],
                missing=''
            )
            proposal = LLMProposal(
                requirements=request.requirements,
                source_assessments=[assessment],
                claims=[claim],
                requirement_support=[support],
                interpretation_limit=''
            )
            return ProviderResult(
                proposal=proposal,
                status='SUCCESS',
                usage={'attempts': 1, 'input_tokens': 10, 'output_tokens': 10},
                raw=None
            )

    checker = ReferenceSupportChecker()
    pipeline = Pipeline(governance, HallucinatingQuoteProvider(), support_checker=checker)
    result = pipeline.run(query, [doc], authority)

    # Shadow audit must reject the invalid quote
    shadow = result.private_trace.get('local_support_shadow')
    assert shadow is not None
    assert shadow['status'] == 'REJECTED'
    assert shadow['references_invalid'] == 1
    assert len(shadow['rejections']) == 1
    assert shadow['rejections'][0]['reason'] == 'QUOTE_NOT_FOUND'


def test_checker_rejects_unauthorized_source(authority, governance):
    """Test that citing an unauthorized source_id is rejected in the shadow audit."""
    doc = RawSource(
        private_id='doc-vessel-01',
        content='The expedition vessel is blue. It was launched in 2024.',
        metadata={'title': 'Expedition Log'},
        public_metadata={'title': 'Expedition Log'}
    )
    query = 'What color is the expedition vessel?'

    class UnauthorizedSourceProvider:
        def propose(self, request, evidence):
            # Citing an unknown/unauthorized source ID
            ref = EvidenceRef(source_id='unauthorized-secret-doc-99', quote='The secret plan.')
            claim = Claim(
                claim_id='c1',
                requirement_ids=[request.requirements[0].requirement_id],
                text='The secret plan.',
                value_type=ValueType.TEXT,
                value='secret',
                subject_key=None,
                dependencies=[],
                evidence=[ref]
            )
            assessment = SourceAssessment(
                source_id='unauthorized-secret-doc-99',
                role='PRIMARY',
                relation='SUPPORTS',
                grounding_quotes=['The secret plan.'],
                grounding_span_ids=[],
                note='Unauthorized citation'
            )
            support = RequirementSupport(
                requirement_id=request.requirements[0].requirement_id,
                status='SUFFICIENT',
                claim_ids=['c1'],
                missing=''
            )
            proposal = LLMProposal(
                requirements=request.requirements,
                source_assessments=[assessment],
                claims=[claim],
                requirement_support=[support],
                interpretation_limit=''
            )
            return ProviderResult(
                proposal=proposal,
                status='SUCCESS',
                usage={'attempts': 1, 'input_tokens': 10, 'output_tokens': 10},
                raw=None
            )

    checker = ReferenceSupportChecker()
    pipeline = Pipeline(governance, UnauthorizedSourceProvider(), support_checker=checker)
    result = pipeline.run(query, [doc], authority)

    shadow = result.private_trace.get('local_support_shadow')
    assert shadow is not None
    assert shadow['status'] == 'REJECTED'
    assert shadow['references_invalid'] == 1
    assert len(shadow['rejections']) == 1
    assert shadow['rejections'][0]['reason'] == 'UNKNOWN_OR_UNSUPPLIED_SOURCE'


def test_public_response_identical_with_and_without_checker(authority, source, governance):
    """Test that public responses are identical bit-by-bit whether the checker is present or not."""
    class ValidProvider:
        def propose(self, request, evidence):
            view = evidence.views[0]
            quote = 'The vessel is blue.'
            ref = EvidenceRef(source_id=view.source_id, quote=quote)
            claim = Claim(
                claim_id='c1',
                requirement_ids=[request.requirements[0].requirement_id],
                text='The vessel is blue.',
                value_type=ValueType.TEXT,
                value='blue',
                subject_key=None,
                dependencies=[],
                evidence=[ref]
            )
            assessment = SourceAssessment(
                source_id=view.source_id,
                role='PRIMARY',
                relation='SUPPORTS',
                grounding_quotes=[quote],
                grounding_span_ids=[],
                note='Exact quote'
            )
            support = RequirementSupport(
                requirement_id=request.requirements[0].requirement_id,
                status='SUFFICIENT',
                claim_ids=['c1'],
                missing=''
            )
            proposal = LLMProposal(
                requirements=request.requirements,
                source_assessments=[assessment],
                claims=[claim],
                requirement_support=[support],
                interpretation_limit=''
            )
            return ProviderResult(
                proposal=proposal,
                status='SUCCESS',
                usage={'attempts': 1, 'input_tokens': 10, 'output_tokens': 10},
                raw=None
            )

    query = 'What color is the vessel?'

    # 1. Run without checker
    pipeline_no_checker = Pipeline(governance, ValidProvider(), support_checker=None)
    result_no_checker = pipeline_no_checker.run(query, [source], authority)

    # 2. Run with checker
    pipeline_with_checker = Pipeline(governance, ValidProvider(), support_checker=ReferenceSupportChecker())
    result_with_checker = pipeline_with_checker.run(query, [source], authority)

    # 3. Public response must be identical
    assert result_no_checker.response == result_with_checker.response
    assert result_no_checker.response.text == result_with_checker.response.text
    assert result_no_checker.response.mode == result_with_checker.response.mode
    assert result_no_checker.response.citations == result_with_checker.response.citations

    # 4. Checker only affects private trace
    assert 'local_support_shadow' not in result_no_checker.private_trace
    assert 'local_support_shadow' in result_with_checker.private_trace
    assert result_with_checker.private_trace['local_support_shadow']['status'] == 'ACCEPTED'


def test_checker_requires_local_only(governance):
    """Test that Pipeline strictly rejects any checker without local_only=True."""
    class NonLocalChecker:
        local_only = False
        def check(self, request, evidence, proposal):
            return {}

    with pytest.raises(ValueError, match='ONLY_EXPLICIT_LOCAL_SHADOW_CHECKER_ALLOWED'):
        Pipeline(governance, None, support_checker=NonLocalChecker())


# ==============================================================================
# Extended Deep Verification Tests (6 - 15)
# ==============================================================================

def test_checker_multiple_claims_all_valid(authority, governance):
    """Test 6: Multiple claims with valid citations are all verified and accepted."""
    doc = RawSource(
        private_id='doc-vessel-02',
        content='The expedition vessel is blue. It was launched in 2024.',
        metadata={'title': 'Expedition Log'},
        public_metadata={'title': 'Expedition Log'}
    )
    query = 'What color is the vessel, and when was it launched?'

    class MultiClaimValidProvider:
        def propose(self, request, evidence):
            view = evidence.views[0]
            req1 = request.requirements[0]
            req2 = request.requirements[1] if len(request.requirements) > 1 else req1

            ref1 = EvidenceRef(source_id=view.source_id, quote='The expedition vessel is blue.')
            ref2 = EvidenceRef(source_id=view.source_id, quote='It was launched in 2024.')

            c1 = Claim(
                claim_id='c1',
                requirement_ids=[req1.requirement_id],
                text='The expedition vessel is blue.',
                value_type=ValueType.TEXT,
                value='blue',
                subject_key=None,
                dependencies=[],
                evidence=[ref1]
            )
            c2 = Claim(
                claim_id='c2',
                requirement_ids=[req2.requirement_id],
                text='It was launched in 2024.',
                value_type=ValueType.TEXT,
                value='2024',
                subject_key=None,
                dependencies=[],
                evidence=[ref2]
            )
            assessment = SourceAssessment(
                source_id=view.source_id,
                role='PRIMARY',
                relation='SUPPORTS',
                grounding_quotes=['The expedition vessel is blue.', 'It was launched in 2024.'],
                grounding_span_ids=[],
                note='Dual claim support'
            )
            supports = [
                RequirementSupport(requirement_id=req1.requirement_id, status='SUFFICIENT', claim_ids=['c1'], missing=''),
            ]
            if req2 != req1:
                supports.append(RequirementSupport(requirement_id=req2.requirement_id, status='SUFFICIENT', claim_ids=['c2'], missing=''))

            proposal = LLMProposal(
                requirements=request.requirements,
                source_assessments=[assessment],
                claims=[c1, c2],
                requirement_support=supports,
                interpretation_limit=''
            )
            return ProviderResult(
                proposal=proposal,
                status='SUCCESS',
                usage={'attempts': 1, 'input_tokens': 15, 'output_tokens': 15},
                raw=None
            )

    checker = ReferenceSupportChecker()
    pipeline = Pipeline(governance, MultiClaimValidProvider(), support_checker=checker)
    result = pipeline.run(query, [doc], authority)

    shadow = result.private_trace.get('local_support_shadow')
    assert shadow is not None
    assert shadow['status'] == 'ACCEPTED'
    assert shadow['claims_checked'] == 2
    assert shadow['references_valid'] == 2
    assert shadow['references_invalid'] == 0
    assert len(shadow['details']) == 2
    assert shadow['details'][0]['references'][0]['matched_snippet'] == 'The expedition vessel is blue.'
    assert shadow['details'][1]['references'][0]['matched_snippet'] == 'It was launched in 2024.'


def test_checker_multiple_claims_partial_failure(authority, governance):
    """Test 7: If one claim has a valid quote and another has a hallucinated quote,
    the shadow audit marks overall status REJECTED and details show each claim's status."""
    doc = RawSource(
        private_id='doc-vessel-03',
        content='The expedition vessel is blue. It was launched in 2024.',
        metadata={'title': 'Expedition Log'},
        public_metadata={'title': 'Expedition Log'}
    )
    query = 'What color is the vessel, and when was it launched?'

    class PartialFailureProvider:
        def propose(self, request, evidence):
            view = evidence.views[0]
            req1 = request.requirements[0]
            req2 = request.requirements[1] if len(request.requirements) > 1 else req1

            ref1 = EvidenceRef(source_id=view.source_id, quote='The expedition vessel is blue.')
            ref2 = EvidenceRef(source_id=view.source_id, quote='It was launched in 1990.')

            c1 = Claim(
                claim_id='c1',
                requirement_ids=[req1.requirement_id],
                text='The expedition vessel is blue.',
                value_type=ValueType.TEXT,
                value='blue',
                subject_key=None,
                dependencies=[],
                evidence=[ref1]
            )
            c2 = Claim(
                claim_id='c2',
                requirement_ids=[req2.requirement_id],
                text='It was launched in 1990.',
                value_type=ValueType.TEXT,
                value='1990',
                subject_key=None,
                dependencies=[],
                evidence=[ref2]
            )
            assessment = SourceAssessment(
                source_id=view.source_id,
                role='PRIMARY',
                relation='SUPPORTS',
                grounding_quotes=['The expedition vessel is blue.'],
                grounding_span_ids=[],
                note='Partial support'
            )
            supports = [
                RequirementSupport(requirement_id=req1.requirement_id, status='SUFFICIENT', claim_ids=['c1'], missing=''),
            ]
            if req2 != req1:
                supports.append(RequirementSupport(requirement_id=req2.requirement_id, status='SUFFICIENT', claim_ids=['c2'], missing=''))

            proposal = LLMProposal(
                requirements=request.requirements,
                source_assessments=[assessment],
                claims=[c1, c2],
                requirement_support=supports,
                interpretation_limit=''
            )
            return ProviderResult(
                proposal=proposal,
                status='SUCCESS',
                usage={'attempts': 1, 'input_tokens': 15, 'output_tokens': 15},
                raw=None
            )

    checker = ReferenceSupportChecker()
    pipeline = Pipeline(governance, PartialFailureProvider(), support_checker=checker)
    result = pipeline.run(query, [doc], authority)

    shadow = result.private_trace.get('local_support_shadow')
    assert shadow is not None
    assert shadow['status'] == 'REJECTED'
    assert shadow['claims_checked'] == 2
    assert shadow['references_valid'] == 1
    assert shadow['references_invalid'] == 1
    assert shadow['details'][0]['valid'] is True
    assert shadow['details'][1]['valid'] is False
    assert len(shadow['rejections']) == 1
    assert shadow['rejections'][0]['claim_id'] == 'c2'
    assert shadow['rejections'][0]['reason'] == 'QUOTE_NOT_FOUND'


def test_checker_composite_evidence_for_single_claim(authority, governance):
    """Test 8: A single claim supported by two distinct valid quotes resolves both."""
    doc = RawSource(
        private_id='doc-vessel-04',
        content='The expedition vessel is blue. It was launched in 2024.',
        metadata={},
        public_metadata={}
    )
    pipeline = Pipeline(governance, None)
    request, evidence, _ = pipeline.prepare('Status?', [doc], authority)
    view = evidence.views[0]

    ref1 = EvidenceRef(source_id=view.source_id, quote='The expedition vessel is blue.')
    ref2 = EvidenceRef(source_id=view.source_id, quote='It was launched in 2024.')
    claim = Claim(
        claim_id='c1',
        requirement_ids=[request.requirements[0].requirement_id],
        text='The blue vessel was launched in 2024.',
        value_type=ValueType.TEXT,
        value='blue 2024',
        subject_key=None,
        dependencies=[],
        evidence=[ref1, ref2]
    )
    proposal = LLMProposal(
        requirements=request.requirements,
        source_assessments=[SourceAssessment(
            source_id=view.source_id,
            role='PRIMARY',
            relation='SUPPORTS',
            grounding_quotes=['The expedition vessel is blue.', 'It was launched in 2024.'],
            grounding_span_ids=[],
            note=''
        )],
        claims=[claim],
        requirement_support=[RequirementSupport(
            requirement_id=request.requirements[0].requirement_id,
            status='SUFFICIENT',
            claim_ids=['c1'],
            missing=''
        )],
        interpretation_limit=''
    )

    checker = ReferenceSupportChecker()
    shadow = checker.check(request, evidence, proposal)

    assert shadow['status'] == 'ACCEPTED'
    assert shadow['claims_checked'] == 1
    assert shadow['references_valid'] == 2
    assert shadow['references_invalid'] == 0
    assert len(shadow['details'][0]['references']) == 2
    assert shadow['details'][0]['references'][0]['valid'] is True
    assert shadow['details'][0]['references'][1]['valid'] is True


def test_checker_multi_document_evidence(authority, governance):
    """Test 9: Verification across multiple distinct governed evidence documents."""
    doc1 = RawSource(
        private_id='doc-color',
        content='The expedition vessel is blue.',
        metadata={},
        public_metadata={}
    )
    doc2 = RawSource(
        private_id='doc-captain',
        content='Captain Alice navigates the vessel.',
        metadata={},
        public_metadata={}
    )
    pipeline = Pipeline(governance, None)
    request, evidence, _ = pipeline.prepare('Query?', [doc1, doc2], authority)
    assert len(evidence.views) == 2
    v1, v2 = evidence.views[0], evidence.views[1]

    ref1 = EvidenceRef(source_id=v1.source_id, quote='The expedition vessel is blue.')
    ref2 = EvidenceRef(source_id=v2.source_id, quote='Captain Alice navigates the vessel.')

    c1 = Claim(
        claim_id='c1',
        requirement_ids=[request.requirements[0].requirement_id],
        text='The vessel is blue.',
        value_type=ValueType.TEXT,
        value='blue',
        subject_key=None,
        dependencies=[],
        evidence=[ref1]
    )
    c2 = Claim(
        claim_id='c2',
        requirement_ids=[request.requirements[0].requirement_id],
        text='Captain Alice is the navigator.',
        value_type=ValueType.TEXT,
        value='Alice',
        subject_key=None,
        dependencies=[],
        evidence=[ref2]
    )
    proposal = LLMProposal(
        requirements=request.requirements,
        source_assessments=[
            SourceAssessment(source_id=v1.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=['The expedition vessel is blue.'], grounding_span_ids=[], note=''),
            SourceAssessment(source_id=v2.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=['Captain Alice navigates the vessel.'], grounding_span_ids=[], note=''),
        ],
        claims=[c1, c2],
        requirement_support=[RequirementSupport(requirement_id=request.requirements[0].requirement_id, status='SUFFICIENT', claim_ids=['c1', 'c2'], missing='')],
        interpretation_limit=''
    )

    checker = ReferenceSupportChecker()
    shadow = checker.check(request, evidence, proposal)

    assert shadow['status'] == 'ACCEPTED'
    assert shadow['claims_checked'] == 2
    assert shadow['references_valid'] == 2
    assert shadow['details'][0]['references'][0]['source_id'] == v1.source_id
    assert shadow['details'][1]['references'][0]['source_id'] == v2.source_id


def test_checker_rejects_ambiguous_quote(authority, governance):
    """Test 10: A non-unique substring appearing multiple times is rejected as AMBIGUOUS_EVIDENCE_QUOTE."""
    doc = RawSource(
        private_id='doc-ambiguous',
        content='The hull is blue. The mast is also blue.',
        metadata={},
        public_metadata={}
    )
    pipeline = Pipeline(governance, None)
    request, evidence, _ = pipeline.prepare('Color?', [doc], authority)
    view = evidence.views[0]

    # 'blue.' appears twice in doc.content!
    ambiguous_quote = 'blue.'
    ref = EvidenceRef(source_id=view.source_id, quote=ambiguous_quote)
    claim = Claim(
        claim_id='c1',
        requirement_ids=[request.requirements[0].requirement_id],
        text='The color is blue.',
        value_type=ValueType.TEXT,
        value='blue',
        subject_key=None,
        dependencies=[],
        evidence=[ref]
    )
    proposal = LLMProposal(
        requirements=request.requirements,
        source_assessments=[SourceAssessment(source_id=view.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=[], grounding_span_ids=[], note='')],
        claims=[claim],
        requirement_support=[RequirementSupport(requirement_id=request.requirements[0].requirement_id, status='SUFFICIENT', claim_ids=['c1'], missing='')],
        interpretation_limit=''
    )

    checker = ReferenceSupportChecker()
    shadow = checker.check(request, evidence, proposal)

    assert shadow['status'] == 'REJECTED'
    assert shadow['references_invalid'] == 1
    assert len(shadow['rejections']) == 1
    assert shadow['rejections'][0]['reason'] == 'AMBIGUOUS_EVIDENCE_QUOTE'


def test_checker_rejects_empty_quote(authority, governance):
    """Test 11: Empty or whitespace-only quotes are rejected as EMPTY_EVIDENCE_QUOTE."""
    doc = RawSource(
        private_id='doc-empty-quote',
        content='The vessel is blue.',
        metadata={},
        public_metadata={}
    )
    pipeline = Pipeline(governance, None)
    request, evidence, _ = pipeline.prepare('Color?', [doc], authority)
    view = evidence.views[0]

    ref = EvidenceRef(source_id=view.source_id, quote='   ')
    claim = Claim(
        claim_id='c1',
        requirement_ids=[request.requirements[0].requirement_id],
        text='The vessel is blue.',
        value_type=ValueType.TEXT,
        value='blue',
        subject_key=None,
        dependencies=[],
        evidence=[ref]
    )
    proposal = LLMProposal(
        requirements=request.requirements,
        source_assessments=[SourceAssessment(source_id=view.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=[], grounding_span_ids=[], note='')],
        claims=[claim],
        requirement_support=[RequirementSupport(requirement_id=request.requirements[0].requirement_id, status='SUFFICIENT', claim_ids=['c1'], missing='')],
        interpretation_limit=''
    )

    checker = ReferenceSupportChecker()
    shadow = checker.check(request, evidence, proposal)

    assert shadow['status'] == 'REJECTED'
    assert shadow['references_invalid'] == 1
    assert shadow['rejections'][0]['reason'] == 'EMPTY_EVIDENCE_QUOTE'


def test_checker_valid_span_reference(authority, governance):
    """Test 12: A citation referencing a valid catalog span_id is accepted."""
    doc = RawSource(
        private_id='doc-span-valid',
        content='The vessel is blue. Launched in 2024.',
        metadata={},
        public_metadata={}
    )
    pipeline = Pipeline(governance, None)
    request, evidence, _ = pipeline.prepare('Color?', [doc], authority)
    view = evidence.views[0]
    assert len(view.spans) > 0
    valid_span = view.spans[0]

    ref = EvidenceRef(source_id=view.source_id, span_id=valid_span.span_id, quote=None)
    claim = Claim(
        claim_id='c1',
        requirement_ids=[request.requirements[0].requirement_id],
        text='The vessel is blue.',
        value_type=ValueType.TEXT,
        value='blue',
        subject_key=None,
        dependencies=[],
        evidence=[ref]
    )
    proposal = LLMProposal(
        requirements=request.requirements,
        source_assessments=[SourceAssessment(source_id=view.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=[], grounding_span_ids=[valid_span.span_id], note='')],
        claims=[claim],
        requirement_support=[RequirementSupport(requirement_id=request.requirements[0].requirement_id, status='SUFFICIENT', claim_ids=['c1'], missing='')],
        interpretation_limit=''
    )

    checker = ReferenceSupportChecker()
    shadow = checker.check(request, evidence, proposal)

    assert shadow['status'] == 'ACCEPTED'
    assert shadow['references_valid'] == 1
    assert shadow['details'][0]['references'][0]['span_id'] == valid_span.span_id
    assert shadow['details'][0]['references'][0]['matched_snippet'] == view.text[valid_span.start:valid_span.end]


def test_checker_rejects_invalid_span_id(authority, governance):
    """Test 13: Citing a non-existent span_id is rejected as INVALID_SPAN_REFERENCE."""
    doc = RawSource(
        private_id='doc-span-invalid',
        content='The vessel is blue.',
        metadata={},
        public_metadata={}
    )
    pipeline = Pipeline(governance, None)
    request, evidence, _ = pipeline.prepare('Color?', [doc], authority)
    view = evidence.views[0]

    fake_span_id = f'{view.source_id}:span-9999'
    ref = EvidenceRef(source_id=view.source_id, span_id=fake_span_id, quote=None)
    claim = Claim(
        claim_id='c1',
        requirement_ids=[request.requirements[0].requirement_id],
        text='The vessel is blue.',
        value_type=ValueType.TEXT,
        value='blue',
        subject_key=None,
        dependencies=[],
        evidence=[ref]
    )
    proposal = LLMProposal(
        requirements=request.requirements,
        source_assessments=[SourceAssessment(source_id=view.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=[], grounding_span_ids=[], note='')],
        claims=[claim],
        requirement_support=[RequirementSupport(requirement_id=request.requirements[0].requirement_id, status='SUFFICIENT', claim_ids=['c1'], missing='')],
        interpretation_limit=''
    )

    checker = ReferenceSupportChecker()
    shadow = checker.check(request, evidence, proposal)

    assert shadow['status'] == 'REJECTED'
    assert shadow['references_invalid'] == 1
    assert shadow['rejections'][0]['reason'] == 'INVALID_SPAN_REFERENCE'


def test_checker_rejects_claim_without_evidence(authority, governance):
    """Test 14: A claim completely lacking evidence references is flagged and rejected."""
    doc = RawSource(
        private_id='doc-no-evidence',
        content='The vessel is blue.',
        metadata={},
        public_metadata={}
    )
    pipeline = Pipeline(governance, None)
    request, evidence, _ = pipeline.prepare('Color?', [doc], authority)
    view = evidence.views[0]

    claim = Claim(
        claim_id='c1',
        requirement_ids=[request.requirements[0].requirement_id],
        text='The vessel is blue.',
        value_type=ValueType.TEXT,
        value='blue',
        subject_key=None,
        dependencies=[],
        evidence=[]
    )
    proposal = LLMProposal(
        requirements=request.requirements,
        source_assessments=[SourceAssessment(source_id=view.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=[], grounding_span_ids=[], note='')],
        claims=[claim],
        requirement_support=[RequirementSupport(requirement_id=request.requirements[0].requirement_id, status='SUFFICIENT', claim_ids=['c1'], missing='')],
        interpretation_limit=''
    )

    checker = ReferenceSupportChecker()
    shadow = checker.check(request, evidence, proposal)

    assert shadow['status'] == 'REJECTED'
    assert shadow['details'][0]['valid'] is False
    assert len(shadow['rejections']) == 1
    assert shadow['rejections'][0]['error_type'] == 'NO_EVIDENCE'
    assert shadow['rejections'][0]['reason'] == 'MISSING_EVIDENCE_REFERENCES'


def test_checker_rejects_ambiguous_reference_representation(authority, governance):
    """Test 15: Providing both quote and span_id raises AMBIGUOUS_REFERENCE_REPRESENTATION and is rejected."""
    doc = RawSource(
        private_id='doc-ambiguous-rep',
        content='The vessel is blue.',
        metadata={},
        public_metadata={}
    )
    pipeline = Pipeline(governance, None)
    request, evidence, _ = pipeline.prepare('Color?', [doc], authority)
    view = evidence.views[0]

    # Providing BOTH quote and span_id is forbidden by contract
    ref = EvidenceRef(source_id=view.source_id, quote='The vessel is blue.', span_id=view.spans[0].span_id)
    claim = Claim(
        claim_id='c1',
        requirement_ids=[request.requirements[0].requirement_id],
        text='The vessel is blue.',
        value_type=ValueType.TEXT,
        value='blue',
        subject_key=None,
        dependencies=[],
        evidence=[ref]
    )
    proposal = LLMProposal(
        requirements=request.requirements,
        source_assessments=[SourceAssessment(source_id=view.source_id, role='PRIMARY', relation='SUPPORTS', grounding_quotes=['The vessel is blue.'], grounding_span_ids=[], note='')],
        claims=[claim],
        requirement_support=[RequirementSupport(requirement_id=request.requirements[0].requirement_id, status='SUFFICIENT', claim_ids=['c1'], missing='')],
        interpretation_limit=''
    )

    checker = ReferenceSupportChecker()
    shadow = checker.check(request, evidence, proposal)

    assert shadow['status'] == 'REJECTED'
    assert shadow['references_invalid'] == 1
    assert shadow['rejections'][0]['reason'] == 'AMBIGUOUS_REFERENCE_REPRESENTATION'
