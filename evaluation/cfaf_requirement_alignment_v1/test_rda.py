import copy,hashlib,json,time
from types import SimpleNamespace
from pathlib import Path
import pytest
from .requirement_decomposition import decompose,validate
from .requirement_alignment import align
from .rec_v2 import assess
from . import integration as impl
from evaluation.refusalbench_iterative_dev_v1.functional_support import FunctionalProvider
from evaluation.infobank_semantic_integration_v2.synthetic_cases import source
from evaluation.cfaf_request_evidence_verification_v1.source_capability_rules import RULES,capability,trusted_provenance
from evaluation.refusalbench_iterative_dev_v1.versions.v02 import implementation as old

def case(query='Who painted the mural?',text='Nera painted the mural.'):
 return {'case_id':'local-unit','pair_id':'unpaired','family':'synthetic','variant':'none','query':query,'sources':[{**source('garden record','FULL'),'content':text}]}

def sample(query='Who painted the mural?',candidate='Nera',text='Nera painted the mural.',entities=None):
 c=case(query,text);request=impl.project_case(c);p=FunctionalProvider({'expected':{'answer':candidate},'controlled_semantic_supported':True},impl);data=json.loads(p.call(request,'semantic_analysis','',request.public(),1500).content);data['entities']=['Nera'] if entities is None else entities
 return c,request,data

def evaluated(request,data,config='B3'):
 a,_,_=impl.parse_analysis(json.dumps(data),request);assert a.valid
 return assess(request,a,data,config,trusted_provenance(request,True))

@pytest.mark.parametrize('query,kinds',[
 ('Who designed the lantern?',['NAMED_IDENTITY']),('When did the expedition depart?',['DATE_TIME']),
 ('Who collected the most coins, and how many coins did she collect?',['NAMED_IDENTITY','COUNT']),
 ('Who founded the institute and when was it founded?',['NAMED_IDENTITY','DATE_TIME']),
 ('Report the count and average processing time.',['COUNT','QUANTITY']),
 ('What are the height and color of the tower?',['QUANTITY','FACT']),
 ('List all members of the expedition.',['DESCRIPTION']),
 ('Who was the first captain?',['NAMED_IDENTITY']),
 ('Where did it happen?',['LOCATION']),
 ('Who wrote the note and when was it sent and how many copies were made?',['NAMED_IDENTITY','DATE_TIME','COUNT']),
 ('What year was the university founded?',['DATE_TIME'])])
def test_output_obligation_decomposition(query,kinds):
 p=decompose(query);assert [r['answer_type'] for r in p['requirements']]==kinds;assert validate(p);assert all(query[r['query_span']['start']:r['query_span']['end']]==r['request_text'] for r in p['requirements'])

def test_pronoun_dependency_and_no_extra_user_output():
 p=decompose('Who scored the most points and how many points did he score?');assert p['requirements'][1]['depends_on']==['request-1'];assert len(p['requirements'])==2
 p=decompose('What year was the university founded?');assert len(p['requirements'])==1;assert p['requirements'][0]['requested_precision']=='YEAR'

def test_no_invented_qualifier_and_stable_ids():
 q='When was the bridge opened?';a=decompose(q);assert not a['requirements'][0]['qualifiers'];assert a==decompose(q)
 b=decompose('When was the last bridge opened?');assert b['requirements'][0]['qualifiers'][0]['value']=='LAST';assert b['original_query']!=''

def test_unresolved_pronoun_is_internal_uncertainty():
 p=decompose('Where did it happen?');assert len(p['requirements'])==1;assert p['requirements'][0]['internal_dependencies'][0]['status']=='UNRESOLVED'

def test_metadata_components_keep_metadata_permission():
 p=decompose('What file type and creation date are recorded for garden record?');assert len(p['requirements'])==2;assert all(r['request_type']=='METADATA_LOOKUP' for r in p['requirements']);assert p['requirements'][1]['metadata_fields']==['created_at']

@pytest.mark.parametrize('query,relation',[
 ('What is the average duration?','AVERAGE'),('Give the sum of amounts.','SUM'),('How many visits occurred?','COUNT')])
def test_aggregate_operators_are_distinct(query,relation):assert decompose(query)['requirements'][0]['relation_or_operation']==relation

def test_person_count_pairing_new_entities_and_numbers():
 c,r,d=sample('Who collected the most coins and how many coins did she collect?','Nera collected eleven coins.','Nera collected eleven coins.',['Nera']);profile=decompose(r.query,r.query_profile);a=align(profile,d['answer_candidate'],d,r.documents)
 assert [x['candidate_fragment']['text'] for x in a['requirements']]==['Nera','eleven'];assert all(x['type_compatible'] for x in a['requirements']);assert a['requirements'][1]['dependency_association']['status']=='PROPOSED_SAME_ENTITY_ASSOCIATION';assert not a['independent_entailment_proof']

def test_entity_quantity_mismatch_is_soft_not_policy_proof():
 c,r,d=sample('Who collected the most coins and how many coins did she collect?','Nera collected eleven coins.','Nera collected four coins; Oris collected eleven coins.',['Nera','Oris']);result=evaluated(r,d)
 assert any(w['code']=='SOFT_POTENTIAL_ENTITY_QUANTITY_MISMATCH' for w in result['soft_warnings']);assert not result['hard_failures']

def test_missing_structured_second_requirement_is_hard():
 c,r,d=sample('Who sent the parcel and when was it sent?','Nera sent it in 2038.');p=decompose(r.query,r.query_profile);a=align(p,{'request-1':'Nera'},d,r.documents);assert a['requirements'][1]['explicit_component_missing'];assert not a['requirements'][0]['explicit_component_missing']
 a0,_,_=impl.parse_analysis(json.dumps(d),r);d['answer_candidate']={'request-1':'Nera'};result=assess(r,a0,d,'B3');assert not result['validated_request_fulfilment'];assert any(h['code']=='HARD_MISSING_EXPLICIT_COMPONENT' for h in result['hard_failures'])

def test_mixed_answer_types_do_not_veto_complete_full():
 c,r,d=sample('Who collected the most coins and how many coins did she collect?','Nera collected eleven coins.','Nera collected eleven coins.',['Nera']);v=evaluated(r,d);assert v['validated_request_fulfilment'];assert len(v['coverage']['requirements'])==2;assert v['soft_warnings']

def test_incomplete_list_remains_semantic_and_cannot_promote():
 c,r,d=sample('List all members of the team.','Nera',entities=['Nera']);d['requirement_support'][0]['complete_answer']=False;v=evaluated(r,d);assert any(w['code']=='SOFT_LIST_EXHAUSTIVENESS' for w in v['soft_warnings']);assert not v['validated_request_fulfilment'];assert not v['hard_failures']

@pytest.mark.parametrize('query,candidate,text',[
 ('When was the vaccine introduced?','in the 1950s','It was introduced in the 1950s.'),
 ('What year was the observatory founded?','2037','The observatory was founded in 2037.')])
def test_approximate_precision_does_not_require_exact_day(query,candidate,text):
 c,r,d=sample(query,candidate,text,[]);d['requirement_support'][0]['answer_form']='DATE_TIME';v=evaluated(r,d);assert v['validated_request_fulfilment'];assert not v['hard_failures']

def test_uncertain_first_event_shadow_full():
 c,r,d=sample('Who was the first captain?','Nera','Nera captained the ship in 2037.',['Nera']);v=evaluated(r,d);assert v['validated_request_fulfilment'];assert any(w['code']=='SOFT_QUALIFIER_UNVERIFIED' for w in v['soft_warnings']);assert not v['hard_failures']

def test_inferred_wrong_prose_type_is_soft():
 c,r,d=sample('Who painted the mural?','eleven',entities=['eleven']);v=evaluated(r,d);assert not v['hard_failures'] # no deterministic claim that an LLM entity classification is truth

def test_native_wrong_value_type_is_hard():
 c,r,d=sample('Who painted the mural?');a=align(decompose(r.query,r.query_profile),{'request-1':8},d,r.documents);assert a['requirements'][0]['type_compatible'] is False

@pytest.mark.parametrize('text,entities',[
 ('Nera was the captain; Nera was also the engineer.',['Nera']),
 ('Nera and Oris both designed a mural.',['Nera','Oris'])])
def test_roles_and_multiple_referents_not_string_entailment(text,entities):
 c,r,d=sample('Who designed the mural?','Nera and Oris',text,entities);v=evaluated(r,d);assert not v['coverage']['requirements'][0]['deterministic_entailment_proof'];assert v['soft_warnings']

def test_unknown_semantics_do_not_promote_original_refusal():
 c,r,d=sample();d['requirement_support'][0]['support_status']='UNKNOWN';v=evaluated(r,d);assert not v['validated_request_fulfilment'];assert v['baseline_issues'];assert not v['hard_failures']

def test_invalid_span_is_hard_and_never_exposed():
 c,r,d=sample();d['requirement_support'][0]['supporting_span_ids']=['private:span-9'];a,_,_=impl.parse_analysis(json.dumps(d),r);v=assess(r,a,d);assert not v['validated_request_fulfilment'];assert any(h['code']=='HARD_INVALID_SPAN' for h in v['hard_failures'])

@pytest.mark.parametrize('query,access',[
 ('Which individual transaction took four days?','AGGREGATE'),('What does the body of garden record say?','METADATA')])
def test_authoritative_scope_is_hard(query,access):
 c,r,d=sample(query);c['sources'][0].update(access_mode=access,aggregate_view='There were four transactions.',metadata={'file_type':'PDF'},allowed_metadata_fields=['file_type']);r=impl.project_case(c);a,_,_=impl.parse_analysis(json.dumps(d),r);v=assess(r,a,d);assert any('VIEW' in h['code'] or 'SCOPE' in h['code'] for h in v['hard_failures']);assert not v['validated_request_fulfilment']

@pytest.mark.parametrize('config',['A0','B1','B2','B3'])
def test_eight_stages_and_original_selector(config):
 c=case();p=FunctionalProvider({'expected':{'answer':'Nera'},'controlled_semantic_supported':True},impl);o=impl.run_governed(c,p,config);assert len(o['internal_trace']['stage_sequence'])==8;assert impl.TopLevelModeSelectionStage is old.TopLevelModeSelectionStage;assert not o['system_errors'];assert 'rda_profile' in o['internal_trace'];assert set(o['public_traces']['semantic_cfaf'])==set(impl.GENERATION_SCHEMA['required'])

@pytest.mark.parametrize('access',['DENY','AGGREGATE','METADATA'])
def test_protected_raw_never_reaches_llm(access):
 c=case(text='PRIVATE_RDA_CANARY');c['sources'][0].update(access_mode=access,aggregate_view='Count 4',metadata={'file_type':'PDF'},allowed_metadata_fields=['file_type']);p=FunctionalProvider({'expected':{'answer':'four'},'controlled_semantic_supported':True},impl);o=impl.run_governed(c,p);assert 'PRIVATE_RDA_CANARY' not in json.dumps(p.calls);assert 'PRIVATE_RDA_CANARY' not in json.dumps(o['public_traces'])

def test_p5_identical_traces_and_no_calls():
 c=case();c['sources'][0].update(access_mode='DENY',existence_visibility='INTERNAL_ONLY');p=FunctionalProvider({'expected':{'answer':'Nera'}},impl);a=impl.run_governed(c,p);c['sources']=[];b=impl.run_governed(c,p);assert a['public_traces']==b['public_traces'];assert not p.calls

def test_gold_fields_do_not_reach_runtime():
 c=case();c.update(gold_answer='ORACLE_SECRET',expected_top_level_mode='CFAF');p=FunctionalProvider({'expected':{'answer':'Nera'},'controlled_semantic_supported':True},impl);impl.run_governed(c,p);assert 'ORACLE_SECRET' not in json.dumps(p.calls);assert 'expected_top_level_mode' not in json.dumps(p.calls)

@pytest.mark.parametrize('rule',RULES,ids=lambda r:r.rule_id)
def test_source_registry_preserved_and_claim_relative(rule):
 c,r,d=sample();r.documents[0]['source_type']=rule.source_type;p=trusted_provenance(r,True);assert capability(r.documents[0],rule.relation_family,p['view-0001'])['capability_state']==rule.state

def test_unknown_source_does_not_reject_supported_full():
 c,r,d=sample();v=evaluated(r,d);assert v['validated_request_fulfilment']

def test_b2_b3_same_gate_b3_has_shadow_diagnostics():
 c,r,d=sample('Who was the earliest captain?');b2=evaluated(r,d,'B2');b3=evaluated(r,d,'B3');assert b2['validated_request_fulfilment']==b3['validated_request_fulfilment'];assert not b2['soft_warnings'];assert b3['soft_warnings']

def test_historical_files_immutable():
 from .artifacts import ROOT,REPO,read,sha
 s=read(ROOT/'task_state.json');assert all(sha(REPO/n)==h for n,h in s['protected_files'].items())

def test_proper_name_qualifier_is_not_a_required_priority_output():
 p=decompose('What color is the First National Bank logo?');r=p['requirements'][0];assert not r['qualifiers'];assert r['inferred_qualifiers'][0]['required'] is False

def test_source_capabilities_applied_per_requirement():
 c,r,d=sample('Which page was visited and what obligation was accepted?','The visit and obligation.');c['sources'][0]['source_type']='BrowserHistory';r=impl.project_case(c);v=evaluated(r,d);families={x['relation_family'] for x in v['source_capabilities']};assert families=={'PAGE_VISIT','OBLIGATION'}
 assert any(w['code']=='SOFT_SOURCE_ADDITIONAL_EVIDENCE' for w in v['soft_warnings'])

def test_authoritative_forbidden_capability_is_hard():
 c,r,d=sample('Which individual transaction took four days?');c['sources'][0]['source_type']='AggregateReport';r=impl.project_case(c);v=evaluated(r,d);assert any(h['code']=='HARD_TRUSTED_SOURCE_USE_FORBIDDEN' for h in v['hard_failures'])

def test_current_task_deadline_uses_test_clock(monkeypatch):
 from . import deadline
 s=deadline.state();wall=time.time();mono=time.monotonic();monkeypatch.setattr(deadline,'state',lambda:{**s,'start_epoch':wall,'start_monotonic':mono});assert deadline.ensure('unit')>0
 monkeypatch.setattr(deadline,'state',lambda:{**s,'start_epoch':wall-3301,'start_monotonic':mono-3301})
 with pytest.raises(deadline.DeadlineReached,match='55-minute'):deadline.ensure('api',new_api=True)

def test_task_cap_120_counts_before_network(tmp_path,monkeypatch):
 from . import provider
 monkeypatch.setattr(provider,'ROOT',tmp_path);(tmp_path/'api_requests.jsonl').write_text(''.join(json.dumps({'attempt':i})+'\n' for i in range(120)));p=provider.BoundedProvider.__new__(provider.BoundedProvider)
 with pytest.raises(RuntimeError,match='120 API attempt'):p._post_json('/chat/completions',{})

def test_optional_verifier_disabled_without_external_attempt(tmp_path,monkeypatch):
 from . import provider
 monkeypatch.setattr(provider,'ROOT',tmp_path);monkeypatch.setattr(provider,'ensure',lambda *args,**kwargs:1000);p=provider.BoundedProvider.__new__(provider.BoundedProvider);p.kind='focused_verification'
 with pytest.raises(ValueError,match='FROZEN_MODEL_SETTINGS'):p._post_json('/chat/completions',{'model':'gpt-4o-mini','temperature':0,'max_tokens':500})
 assert not (tmp_path/'api_requests.jsonl').exists()

def test_upstream_prompts_and_schema_unchanged():
 assert impl.GOVERNED_PROMPT==old.GOVERNED_PROMPT;assert impl.ANALYSIS_SCHEMA==old.ANALYSIS_SCHEMA;assert impl.CONTROL_PROMPT==old.CONTROL_PROMPT;assert impl.GENERATION_SCHEMA==old.GENERATION_SCHEMA

def test_hard_permission_reason_overrides_soft_ambiguity():
 from .rec_v2 import reason_details
 c,r,d=sample('What does the body of garden record say?');c['sources'][0].update(access_mode='METADATA',metadata={'file_type':'PDF'},allowed_metadata_fields=['file_type']);r=impl.project_case(c);d['query_status']='AMBIGUOUS';d['analysis_refusal_cause']='AMBIGUOUS_REQUEST';a,_,_=impl.parse_analysis(json.dumps(d),r);v=assess(r,a,d,'B3');assert reason_details(v,r,d)[0].value=='GOVERNANCE_PRIVACY'

def test_explicit_counterevidence_still_blocks_full():
 c,r,d=sample();d['contradicting_spans']=d['supporting_spans'];a,_,_=impl.parse_analysis(json.dumps(d),r);assert a.valid
 v=assess(r,a,d,'B3');assert not v['validated_request_fulfilment'];assert 'INCOMPATIBLE_EVIDENCE' in v['baseline_issues']
