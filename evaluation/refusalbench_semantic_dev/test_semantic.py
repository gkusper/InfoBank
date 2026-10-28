"""Offline acceptance and leakage tests using synthetic examples only."""
import copy
import json
from pathlib import Path
import pytest
from evaluation.wolala2026.labels import TopLevelMode, ValidationStatus
from evaluation.wolala2026.real_api import ProviderCallResult
from evaluation.wolala2026.semantic_evidence import (parse_assessment, fulfilment_issues,
    run_semantic_pipeline, unknown_assessment, ANALYSIS_PROMPT, ASSESSMENT_SCHEMA)
from evaluation.refusalbench_semantic_dev.semantic_adapter import runtime_case,validate_runtime


def answerable():
    return {
        'requested_information':'the color of the square','entities':['square'],'relations':['color'],
        'query_status':'SPECIFIED','interpretations':['color of the specified square'],
        'requested_granularity':'color','available_granularity':'color','premise_status':'SUPPORTED',
        'support_status':'SUFFICIENT','granularity_matches':True,'answer_candidate':'blue',
        'supporting_spans':[{'source_id':'context-1','quote':'The square is blue.'}],
        'contradicting_spans':[],'uncertainty_causes':[],'confidence':0.95,
        'rationale':'The passage explicitly states the color of the specified square.',
    }


def execute(data=None,context='The square is blue.',query='What color is the square?',provider=None):
    assessment=parse_assessment(json.dumps(data or answerable()),{'context-1':context},'synthetic-test')
    case=runtime_case({'perturbed_query':query,'perturbed_context':context},0)
    return (*run_semantic_pipeline(case,assessment,provider),assessment)


def test_clearly_answerable_full_without_any_gold_answer():
    state,realizer,assessment=execute()
    assert state.mode_decision.mode==TopLevelMode.FULL
    assert state.final_response=='blue'
    assert state.validation.status==ValidationStatus.PASS
    assert state.claim_assessments[0].answer=='blue'
    assert state.candidates[0].evidential_role.value=='PRIMARY'
    assert len(state.internal_trace['stage_sequence'])==8
    assert state.generator_context[0]['query']=='What color is the square?'


@pytest.mark.parametrize('change,context,expected',[
    ({'query_status':'AMBIGUOUS','interpretations':['square A','square B'],'answer_candidate':None,'uncertainty_causes':['ambiguous_reference']},'The square is blue. Another square is red.','AMBIGUOUS_REFERENCE'),
    ({'support_status':'MISSING','answer_candidate':None,'supporting_spans':[],'granularity_matches':False,'uncertainty_causes':['evidence_missing']},'The square exists.','ESSENTIAL_INFORMATION_MISSING'),
    ({'support_status':'CONFLICTING','answer_candidate':None,'contradicting_spans':[{'source_id':'context-1','quote':'The square is red.'}],'uncertainty_causes':['conflicting_evidence']},'The square is blue. The square is red.','INCOMPATIBLE_EVIDENCE'),
    ({'premise_status':'REFUTED','support_status':'PARTIAL','answer_candidate':None,'contradicting_spans':[{'source_id':'context-1','quote':'It is not a circle.'}],'uncertainty_causes':['false_premise']},'The square is blue. It is not a circle.','PREMISE_REFUTED'),
    ({'support_status':'PARTIAL','granularity_matches':False,'answer_candidate':None,'uncertainty_causes':['granularity_gap'],'requested_granularity':'exact wavelength','available_granularity':'color name'},'The square is blue.','GRANULARITY_NOT_SUPPORTED'),
    ({'query_status':'NONFACTUAL','answer_candidate':None,'uncertainty_causes':['nonfactual_request']},'The square is blue.','NONFACTUAL_REQUEST'),
    ({'support_status':'UNKNOWN','answer_candidate':None,'supporting_spans':[],'query_status':'UNKNOWN','uncertainty_causes':['analysis_uncertain'],'confidence':0.2},'The square exists.','SEMANTIC_UNCERTAIN'),
])
def test_distinct_synthetic_failure_causes(change,context,expected):
    data=answerable();data.update(change)
    state,_,assessment=execute(data,context)
    assert assessment.valid
    assert state.mode_decision.mode==TopLevelMode.CFAF
    assert state.mode_decision.reason_code==expected
    assert state.validation.status==ValidationStatus.PASS


@pytest.mark.parametrize('raw',['not JSON','{}','[]','{"top_level_mode":"FULL"}'])
def test_malformed_analysis_is_logged_and_cannot_admit_full(raw):
    assessment=parse_assessment(raw,{'context-1':'The square is blue.'})
    assert not assessment.valid
    assert fulfilment_issues(assessment)==['SEMANTIC_ASSESSMENT_INVALID']
    case=runtime_case({'perturbed_query':'color?','perturbed_context':'The square is blue.'},0)
    state,_=run_semantic_pipeline(case,assessment)
    assert state.mode_decision.mode==TopLevelMode.CFAF
    assert state.mode_decision.reason_code=='SEMANTIC_ASSESSMENT_INVALID'


def test_fabricated_quote_rejects_entire_assessment():
    data=answerable();data['supporting_spans'][0]['quote']='The square is green.'
    state,_,assessment=execute(data)
    assert not assessment.valid
    assert any('QUOTE' in x for x in assessment.validation_errors)
    assert state.mode_decision.mode==TopLevelMode.CFAF


def test_valid_quotes_have_exact_offsets():
    state,_,assessment=execute()
    span=assessment.data['supporting_spans'][0]
    assert 'The square is blue.'[span['start']:span['end']]==span['quote']
    assert state.response_contract.allowed_evidence_views[0]['content']==span['quote']


@pytest.mark.parametrize('field',['expected_rag_behavior','original_answers','original_context','original_query','perturbation_class','intensity','implementation_reasoning','verifier_votes','id','lever_selected'])
def test_forbidden_benchmark_fields_rejected(field):
    with pytest.raises(ValueError):validate_runtime({'perturbed_query':'q','perturbed_context':'c',field:'SECRET'})


def test_semantic_schema_cannot_choose_top_level_mode_or_refusal_code():
    assert 'top_level_mode' not in ASSESSMENT_SCHEMA['properties']
    assert 'REFUSE_' not in ANALYSIS_PROMPT
    data=answerable();data['top_level_mode']='FULL'
    assert not parse_assessment(json.dumps(data),{'context-1':'The square is blue.'}).valid


def test_primary_never_inferred_from_retrieval_alone():
    data=answerable();data.update({'supporting_spans':[],'confidence':0.5})
    state,_,_=execute(data)
    assert state.candidates[0].evidential_role.value=='UNKNOWN'
    assert state.mode_decision.mode.value=='CFAF'


class Generator:
    def __init__(self,mode='FULL',answer='blue'):self.mode=mode;self.answer=answer;self.requests=[]
    def generate_json(self,**kwargs):
        self.requests.append(kwargs)
        return ProviderCallResult(content=json.dumps({'top_level_mode':self.mode,'answer':self.answer}),model='synthetic-test',input_tokens=20,output_tokens=5,latency_ms=1)


def test_real_generation_interface_uses_question_and_derived_candidate():
    provider=Generator();state,realizer,_=execute(provider=provider)
    payload=provider.requests[0]['user_payload']
    assert payload['query']=='What color is the square?'
    assert payload['response_contract']['allowed_claims'][0]['answer']=='blue'
    assert state.model_call_count==1 and state.final_response=='blue'
    text=json.dumps(payload)
    assert 'gold_answer' not in text and 'runtime_answer' not in text and 'original_answers' not in text


@pytest.mark.parametrize('mode,answer,violation',[('CFAF','Cannot answer.','MODE_CONTRACT_MISMATCH'),('FULL','green','ANSWER_CONTRACT_MISMATCH')])
def test_generated_failure_not_silently_relabelled_as_successful_refusal(mode,answer,violation):
    state,realizer,_=execute(provider=Generator(mode,answer))
    assert state.mode_decision.mode==TopLevelMode.FULL
    assert state.validation.status==ValidationStatus.FAIL
    assert violation in state.validation.violation_codes
    assert state.validation.fallback_used
    assert json.loads(realizer.raw_output)['top_level_mode']==mode


def test_declared_gold_and_runtime_answers_blocked():
    case=runtime_case({'perturbed_query':'q','perturbed_context':'The square is blue.'},0)
    assessment=parse_assessment(json.dumps(answerable()),{'context-1':'The square is blue.'})
    for forbidden in ['gold_answer','runtime_answer']:
        bad=copy.deepcopy(case)
        if forbidden=='gold_answer':bad[forbidden]='SECRET'
        else:bad['sources'][0]['metadata'][forbidden]='SECRET'
        with pytest.raises(ValueError):run_semantic_pipeline(bad,assessment)


def test_denied_evidence_cannot_become_full():
    case=runtime_case({'perturbed_query':'q','perturbed_context':'The square is blue.'},0)
    case['sources'][0]['access_mode']='DENY'
    assessment=parse_assessment(json.dumps(answerable()),{'context-1':'The square is blue.'})
    state,_=run_semantic_pipeline(case,assessment)
    assert state.mode_decision.mode.value=='CFAF'
    assert not state.response_contract.allowed_evidence_views


@pytest.mark.parametrize('field,value', [('premise_status','REFUTED'),('support_status','CONFLICTING')])
def test_counterclaim_requires_verified_counterspan(field,value):
    data=answerable();data[field]=value
    assessment=parse_assessment(json.dumps(data),{'context-1':'The square is blue.'})
    assert not assessment.valid
    assert any('COUNTERSPAN' in message for message in assessment.validation_errors)
