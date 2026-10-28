"""Leakage-safe runtime projection into the reusable semantic CFAF component."""
from __future__ import annotations
from evaluation.wolala2026.semantic_evidence import (SemanticAssessment, analyze_evidence,
    parse_assessment, run_semantic_pipeline, unknown_assessment)

ALLOWED_FIELDS=frozenset({'perturbed_query','perturbed_context'})


def validate_runtime(record):
    if not isinstance(record,dict) or set(record)!=ALLOWED_FIELDS or not all(isinstance(record[k],str) for k in ALLOWED_FIELDS):
        raise ValueError('Runtime input must contain exactly perturbed_query and perturbed_context strings.')


def runtime_case(record,index):
    validate_runtime(record)
    if not isinstance(index,int) or index<0:raise ValueError('Neutral nonnegative index required.')
    return {
        'case_id':f'runtime-{index:03d}','query_id':f'query-{index:03d}',
        'query':record['perturbed_query'],'task':'grounded_question_answering',
        'purpose':'answer_from_supplied_context','requested_content':'content',
        'requested_granularity':'direct','requested_action':'answer_question',
        'time_horizon':'unspecified','required_evidence_strength':'direct_support','source_scope':'supplied_context_only',
        'sources':[{'source_id':'context-1','candidate_id':'context-1','source_type':'Document',
            'title':'Provided context','content':record['perturbed_context'],'retrieved':True,
            'retriever_name':'benchmark_provided_context','retrieval_reason':'provided_without_modification',
            'access_mode':'FULL','existence_visibility':'PUBLIC','evidential_role':'UNKNOWN','relation':'NONE',
            'evidence_state':'CURRENT','metadata':{},'policy_rule_id':'PUBLIC_RUNTIME_TEXT','policy_version':'semantic-dev-v1'}],
    }
