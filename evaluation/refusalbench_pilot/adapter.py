"""Non-oracle input bridge to unchanged WoLaLa adapters. No benchmark labels."""
from __future__ import annotations
from typing import Any

RUNTIME_FIELDS = frozenset({'perturbed_query', 'perturbed_context'})
ADAPTER_VERSION = 'refusalbench-unknown-role-v1'


def validate_runtime(record: dict[str, Any]) -> None:
    if set(record) != RUNTIME_FIELDS:
        raise ValueError('Runtime record must contain exactly the two allowed text fields.')
    if not all(isinstance(record[key], str) for key in RUNTIME_FIELDS):
        raise ValueError('Both runtime fields must be strings.')


def adapt_runtime(record: dict[str, str], index: int) -> dict[str, Any]:
    validate_runtime(record)
    if not 0 <= index < 10:
        raise ValueError('Pilot indices are restricted to 0 through 9.')
    query = record['perturbed_query']
    return {
        # Original IDs encode perturbation metadata and MUST NOT enter the system.
        'case_id': f'runtime-{index:02d}', 'query_id': f'query-{index:02d}', 'query': query,
        'task': 'grounded_question_answering', 'purpose': 'answer_from_supplied_context',
        'requested_content': 'content', 'requested_granularity': 'direct',
        'requested_action': 'answer_question', 'time_horizon': 'unspecified',
        'required_evidence_strength': 'direct_support', 'source_scope': 'supplied_context_only',
        'required_claims': [{'claim_id': 'claim-1', 'requested_content': query}],
        'sources': [{
            'source_id': 'provided-context', 'candidate_id': 'provided-context-1',
            'source_type': 'Document', 'title': 'Provided context',
            'content': record['perturbed_context'], 'retrieved': True,
            'retrieval_rank': 1, 'retrieval_score': 1.0,
            'retriever_name': 'benchmark_provided_context',
            'retrieval_reason': 'provided_without_reranking_or_chunking',
            # Public text supplied for this experiment is permitted in full.
            'access_mode': 'FULL', 'existence_visibility': 'PUBLIC',
            'policy_rule_id': 'REFUSALBENCH-PROVIDED-PUBLIC-TEXT', 'policy_version': ADAPTER_VERSION,
            # UNKNOWN denotes missing semantic annotation, not an inferred refusal.
            'evidential_role': 'UNKNOWN',
            # CURRENT is the existing default, not a recency judgement.
            'evidence_state': 'CURRENT', 'relation': 'NONE', 'claim_id': 'claim-1', 'metadata': {},
        }],
    }
