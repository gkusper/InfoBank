"""Security and request-relative integration regressions; no external calls."""
import copy,json,hashlib
from pathlib import Path
from types import SimpleNamespace
import pytest
from .policy_projection import *
from .integration_v2 import *
from .run_experiment_v2 import score,ROOT,DATA,read_jsonl

CASES=read_jsonl(DATA/'cases.jsonl')
def c(name):return copy.deepcopy(next(x for x in CASES if x['case_id']==name))

@pytest.mark.parametrize('case',CASES,ids=lambda x:x['case_id'])
def test_projection_oracle_exclusion(case):
 request=project_case(case);assert_safe_payload(request,request.public())
 assert not set(_all_keys(request.public()))&ORACLE_KEYS

def _all_keys(x):
 if isinstance(x,dict):
  for k,v in x.items():yield k;yield from _all_keys(v)
 elif isinstance(x,list):
  for v in x:yield from _all_keys(v)

def test_full():
 case=c('HELD3_P1_01A');r=project_case(case)
 assert r.documents[0]['context']==case['sources'][0]['content'];assert r.documents[0]['source_id']=='view-0001'
 assert 'runtime_answer' not in canonical(r.public())
def test_aggregate():
 case=c('HELD3_P2_01A');r=project_case(case)
 assert r.documents[0]['context']==case['sources'][0]['aggregate_view'];assert case['sources'][0]['content'] not in canonical(r.public())
def test_metadata():
 r=project_case(c('HELD3_P3_01A'));assert set(json.loads(r.documents[0]['context']))=={'file_type','created_at'}
def test_deny_no_count_or_identifier():
 a=project_case(c('HELD3_P5_01A'));b=project_case(c('HELD3_P5_01B'));assert a.public()==b.public();assert a.signature()==b.signature()
def test_deny_does_not_shift_ids():
 case=c('HELD3_P1_01A');case['sources'].insert(0,c('HELD3_P5_01B')['sources'][0]);assert project_case(case).documents[0]['source_id']=='view-0001'
@pytest.mark.parametrize('key',['runtime_answer','evidential_role','relation','case_id','pair_id','gold_answer'])
def test_guard_rejects_oracles(key):
 request=project_case(c('HELD3_P1_01A'))
 with pytest.raises(ValueError):assert_safe_payload(request,{**request.public(),key:'leak'})
def test_guard_rejects_raw_restricted_content():
 case=c('HELD3_P2_01A');request=project_case(case)
 with pytest.raises(ValueError):assert_safe_payload(request,{**request.public(),'extra':case['sources'][0]['content']})
def test_spans_bind_permitted_view():
 for name in ['HELD3_P2_01A','HELD3_P3_01A']:
  r=project_case(c(name));docs={d['source_id']:d['context'] for d in r.documents};cat=build_catalogue(docs)
  for ref in cat.spans:assert resolve_span(ref,docs,cat)['quote']==docs['view-0001']
  with pytest.raises(ValueError):resolve_span('hidden:span-0000',docs,cat)
class Never:
 def call(self,*a,**k):raise AssertionError('No model call permitted')
def test_p5_public_trace_identical_no_model():
 a=run_governed(c('HELD3_P5_01A'),Never());b=run_governed(c('HELD3_P5_01B'),Never());assert a['public_traces']==b['public_traces'];assert a['internal_trace']['policy']!=b['internal_trace']['policy']
def test_nonempty_contract():
 assert not validate_response(json.dumps(deterministic_response()))
 response=deterministic_response();response['answer']=None;assert validate_response(json.dumps(response))
def test_control_has_no_gate_instruction():
 assert 'response_contract' not in CONTROL_PROMPT;assert 'can_fulfil_request' not in CONTROL_PROMPT

def test_historical_files_unchanged():
 protected=json.loads((ROOT/'protected_files.json').read_text())
 if isinstance(protected,dict) and 'files' in protected:protected=protected['files']
 assert isinstance(protected,dict)
 for name,expected in protected.items():assert hashlib.sha256((ROOT.parents[1]/name).read_bytes()).hexdigest()==expected,name

def test_matched_pair_scorer():
 rows=[]
 for case in [c('HELD3_P5_01A'),c('HELD3_P5_01B')]:rows.append(run_governed(case,Never()))
 summary,pairs,errors=score(rows);assert summary['systems']['semantic_cfaf']['matched_pair_accuracy']==1;assert not errors

def test_request_scope_sufficiency():
 # Actual inference stays the model's task; this checks the deterministic permission boundary.
 from evaluation.wolala2026.semantic_evidence import SemanticAssessment
 base={'query_status':'SPECIFIED','uncertainty_causes':[],'premise_status':'NOT_APPLICABLE','support_status':'SUFFICIENT','granularity_matches':True,'confidence':1,'supporting_spans':[{'source_id':'view-0001'}],'contradicting_spans':[],'answer_candidate':'11 tickets'}
 a=SemanticAssessment(base,True,[],'test');r=project_case(c('HELD3_P2_01A'))
 data={'request_scope':'AGGREGATE','source_assessments':[{'source_id':'view-0001','role':'PRIMARY','relation_label':'SUPPORTS'}]}
 assert not support_issues(a,data,r)
 data['request_scope']='INDIVIDUAL';assert 'REQUEST_EXCEEDS_PERMITTED_VIEW' in support_issues(a,data,r)
 data['request_scope']='AGGREGATE';data['source_assessments'][0]['role']='CONTEXTUAL';assert 'SUPPORT_NOT_PRIMARY' in support_issues(a,data,r)


def test_semantic_role_inconsistency_is_diagnostic_not_schema_failure():
 from evaluation.infobank_semantic_regression_v1.integration_v2 import parse_analysis,support_issues
 rows=read_jsonl(ROOT/'pilot_10_attempt1/pilot_10_results.jsonl')
 row=rows[-1];request=project_case(c(row['case_id']))
 assessment,data,audit=parse_analysis(json.dumps(row['semantic_assessment']),request)
 assert assessment.valid and audit['reference_valid']
 assert 'SUPPORT_NOT_PRIMARY' in support_issues(assessment,data,request)
 assert data['source_assessments'][0]['role']=='PRIMARY'  # Preserve the model error.

def test_v3_shared_control_has_identical_assessment_and_documents():
 path=ROOT/'pilot_10/api_requests.jsonl'
 if not path.exists():pytest.skip('Real pilot ledger not yet available')
 grouped={}
 for record in read_jsonl(path):
  grouped.setdefault(record['request_signature'],{})[record['kind']]=json.loads(record['payload']['messages'][1]['content'])
 for calls in grouped.values():
  if 'semantic_cfaf' not in calls or 'shared_control' not in calls:continue
  cf=calls['semantic_cfaf'];control=calls['shared_control']
  assert cf['semantic_assessment']==control['semantic_assessment']
  assert cf['documents']==control['documents'];assert cf['query']==control['query']
  assert 'response_contract' in cf and 'response_contract' not in control
