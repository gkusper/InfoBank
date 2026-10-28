import copy,json,hashlib
from pathlib import Path
import pytest
from .query_profile import profile_query
from .metadata_binding import project_case,assert_safe_payload
from .synthetic_cases import make_cases,source,ControlledProvider
from .integration import run_governed,parse_analysis

SCENARIOS=make_cases()
@pytest.mark.parametrize('scenario',SCENARIOS,ids=lambda s:s['runtime_case']['case_id'])
def test_new_construction_rule_cases(scenario):
 provider=ControlledProvider(scenario);row=run_governed(scenario['runtime_case'],provider)
 assert {r['request_type'] for r in row['query_profile']['requirements']}==set(scenario['expected']['request_types'])
 assert row['selected_mode']==scenario['expected']['top_level_mode']
 assert len(row['internal_trace']['stage_sequence'])==8
 assert all(isinstance(r['answer'],str) and r['answer'] for r in row['responses'].values())
 if provider.calls:
  cf=next(p for k,p in provider.calls if k=='semantic_cfaf');control=next(p for k,p in provider.calls if k=='shared_control')
  assert cf['semantic_assessment']==control['semantic_assessment'];assert cf['documents']==control['documents'];assert cf['query_profile']==control['query_profile'];assert cf['view_bindings']==control['view_bindings'];assert 'response_contract' not in control

@pytest.mark.parametrize('question,expected',[
 ('How many invoices arrived?',{'AGGREGATE_COUNT'}),('What is the count of open entries?',{'AGGREGATE_COUNT'}),
 ('Give the total amount spent.',{'AGGREGATE_SUM'}),('What is the mean waiting period?',{'AGGREGATE_AVERAGE'}),
 ('Which transaction lasted eight days?',{'INDIVIDUAL_RECORD'}),('List the records and report their average duration.',{'INDIVIDUAL_RECORD','AGGREGATE_AVERAGE'}),
 ('Give the format and creation date for jade dome.',{'METADATA_LOOKUP'}),('What does the body say about jade dome?',{'DOCUMENT_CONTENT'}),
 ('Which next action was recorded for jade dome?',{'ACTION_LOOKUP'}),('Tell me more.',{'UNRESOLVED'}),
 ('How many individual invoices arrived?',{'AGGREGATE_COUNT'}),('What is the sum of individual payments?',{'AGGREGATE_SUM'}),
 ('List individual payments and their sum.',{'INDIVIDUAL_RECORD','AGGREGATE_SUM'}),('What is the percentage of failures?',{'AGGREGATE_OTHER'})])
def test_paraphrases_and_near_scope_controls(question,expected):
 assert {r['request_type'] for r in profile_query(question)['requirements']}==expected


def metadata_case():return {'query':'What file type and creation date are recorded for green conservatory?','sources':[source('green conservatory','METADATA',fields={'file_type':'blueprint','created_at':'2039-11-22'})]}
def test_scope_independent_of_access():
 case=metadata_case();before=profile_query(case['query']);case['sources'][0]['access_mode']='DENY';assert project_case(case).query_profile==before

def test_private_binding_never_discloses_name_or_id():
 case=metadata_case();request=project_case(case)
 assert request.view_bindings==[{'source_id':'view-0001','binding_status':'TRUSTED_QUERY_TARGET'}]
 visible=json.dumps(request.public());assert case['sources'][0]['title'] not in visible;assert case['sources'][0]['source_id'] not in visible;assert case['sources'][0]['content'] not in visible;assert 'ORACLE_NOT_FOR_RUNTIME' not in visible

def test_wrong_target_unresolved():
 case=metadata_case();case['query']='What file type is recorded for unknown courthouse?';assert project_case(case).view_bindings[0]['binding_status']=='UNRESOLVED'
def test_multiple_targets_ambiguous():
 case=metadata_case();another=copy.deepcopy(case['sources'][0]);another['source_id']='private-other';case['sources'].append(another);assert all(b['binding_status']=='AMBIGUOUS' for b in project_case(case).view_bindings)
def test_forbidden_binding_rejected():
 request=project_case(metadata_case());payload=request.public();payload['view_bindings']=[{'source_id':'hidden-private','binding_status':'TRUSTED_QUERY_TARGET'}]
 with pytest.raises(ValueError,match='UNTRUSTED_PROFILE_OR_BINDING'):assert_safe_payload(request,payload)
def test_policy_change_invalidates_binding():
 case=metadata_case();request=project_case(case);case['sources'][0]['access_mode']='DENY'
 with pytest.raises(ValueError,match='STALE_POLICY_OR_BINDING'):assert_safe_payload(request,request.public())
def test_metadata_whitelist_change_invalidates_binding():
 case=metadata_case();request=project_case(case);case['sources'][0]['allowed_metadata_fields']=['file_type']
 with pytest.raises(ValueError):assert_safe_payload(request,request.public())
def test_retarget_invalidates_binding():
 case=metadata_case();request=project_case(case);case['query']='What file type is recorded for other target?'
 with pytest.raises(ValueError):assert_safe_payload(request,request.public())
def test_p5_no_binding_or_count_signal():
 case=metadata_case();case['sources'][0].update(access_mode='DENY',existence_visibility='INTERNAL_ONLY');a=project_case(case);empty=copy.deepcopy(case);empty['sources']=[];b=project_case(empty)
 assert a.public()==b.public();assert not a.view_bindings;assert not a.documents

def test_hidden_distractor_cannot_change_public_binding():
 case=metadata_case();before=project_case(case).public();hidden=copy.deepcopy(case['sources'][0]);hidden.update(source_id='private-hidden',access_mode='DENY',existence_visibility='INTERNAL_ONLY');case['sources'].append(hidden);assert project_case(case).public()==before

def test_binding_does_not_establish_sufficiency():
 case=metadata_case();case['sources'][0]['metadata'].pop('created_at');request=project_case(case);assert request.view_bindings[0]['binding_status']=='TRUSTED_QUERY_TARGET'
 scenario={'expected':{'answer':'blueprint'},'controlled_semantic_supported':True};case.update(case_id='new-local',pair_id='pair-local',family='synthetic',variant='test');row=run_governed(case,ControlledProvider(scenario));assert row['selected_mode']=='CFAF';assert 'REQUESTED_METADATA_MISSING' in row['fulfilment_issues']

def test_authorized_alias_interface():
 case=metadata_case();case['sources'][0]['title']='private uninformative title';case['sources'][0]['retrieval_aliases']=['green conservatory'];assert project_case(case).view_bindings[0]['binding_status']=='TRUSTED_QUERY_TARGET'
def test_no_single_retrieval_fallback_binding():
 case=metadata_case();case['sources'][0]['title']='private uninformative title';assert project_case(case).view_bindings[0]['binding_status']=='UNRESOLVED'
def test_invalid_evidence_reference_rejected():
 scenario=SCENARIOS[0];request=project_case(scenario['runtime_case']);provider=ControlledProvider(scenario);raw=json.loads(provider.call(request,'semantic_analysis','',request.public(),1500).content);raw['requirement_support'][0]['supporting_span_ids']=['forbidden:span-0000'];a,data,audit=parse_analysis(json.dumps(raw),request);assert not a.valid;assert any('UNKNOWN_SPAN_ID' in x for x in audit['errors'])
def test_oracle_semantics_mutation_cannot_affect_projection():
 case=metadata_case();before=project_case(case).public();case.update(gold_answer='oracle',requested_granularity='individual',family='P999',pair_id='oracle');case['sources'][0].update(evidential_role='PRIMARY',relation='SUPPORTS',evidence_state='CURRENT');case['sources'][0]['metadata']['runtime_answer']='new oracle';assert project_case(case).public()==before

def test_profile_tamper_rejected():
 request=project_case(metadata_case());request.query_profile['requirements'][0]['request_type']='AGGREGATE_COUNT'
 with pytest.raises(ValueError,match='UNTRUSTED_QUERY_PROFILE'):assert_safe_payload(request,request.public())

def test_mutating_binding_object_cannot_forge_trust():
 case=metadata_case();case['sources'][0]['title']='wrong catalogue target';request=project_case(case);request.view_bindings[0]['binding_status']='TRUSTED_QUERY_TARGET'
 with pytest.raises(ValueError,match='INVALID_BINDING'):assert_safe_payload(request,request.public())

def test_unauthorized_metadata_field_is_not_in_view_or_full_answer():
 case=metadata_case();case['query']='Who is the owner for green conservatory?';case['sources'][0]['metadata']['owner']='Confidential Curator';case['sources'][0]['allowed_metadata_fields']=['file_type','created_at']
 request=project_case(case);assert 'Confidential Curator' not in json.dumps(request.public())
 case.update(case_id='new-local-owner',pair_id='pair-owner',family='synthetic',variant='test')
 row=run_governed(case,ControlledProvider({'expected':{'answer':'Unknown owner'},'controlled_semantic_supported':True}))
 assert row['selected_mode']=='CFAF';assert 'REQUESTED_METADATA_MISSING' in row['fulfilment_issues'];assert 'Confidential Curator' not in json.dumps(row['responses'])

def test_missing_metadata_scope_stays_unresolved():
 profile=profile_query('Show metadata for green conservatory.')
 assert profile['resolution']=='UNRESOLVED';assert profile['requirements'][0]['metadata_fields']==[]
