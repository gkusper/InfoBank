import copy,json
import pytest
from .query_profile import profile_query
from . import implementation as impl
from ...functional_support import FunctionalProvider
from evaluation.infobank_semantic_integration_v2.synthetic_cases import make_cases,source
from evaluation.refusalbench_noncontradiction_v1.public_adapter import public_case

@pytest.mark.parametrize('q,kind',[('Who sculpted the fountain?','NAMED_IDENTITY'),('Where was the meteorite found?','LOCATION'),('When did the gallery open?','DATE_TIME'),('What is a semaphore?','FACT'),('Which team won the cup?','SELECTION'),('How much does the vase cost?','QUANTITY'),('How long did the voyage last?','DURATION'),('Who received the medal?','NAMED_IDENTITY')])
def test_general_factual_types(q,kind):
 p=profile_query(q);assert p['resolution']=='RESOLVED';assert p['answer_kind']==kind;assert p['requirements'][0]['request_type']=='FACT_LOOKUP'

def test_compositional_query():
 p=profile_query('Who designed the tower and when did it open?');assert len(p['requirements'])==2;assert [r['answer_kind'] for r in p['requirements']]==['NAMED_IDENTITY','DATE_TIME']

def test_explicit_ambiguity_preserved():assert profile_query('Tell me what is available.')['resolution']=='UNRESOLVED'

@pytest.mark.parametrize('scenario',make_cases(),ids=lambda s:s['runtime_case']['case_id'])
def test_infobank_governance_regressions(scenario):
 row=impl.run_governed(scenario['runtime_case'],FunctionalProvider(scenario,impl));assert row['selected_mode']==scenario['expected']['top_level_mode'];assert len(row['internal_trace']['stage_sequence'])==8

@pytest.mark.parametrize('assessment,code',[
 ({'query_status':'NONFACTUAL'},'NONFACTUAL_REQUEST'),({'query_status':'AMBIGUOUS'},'AMBIGUOUS_REQUEST'),({'premise_status':'REFUTED'},'UNSUPPORTED_PREMISE'),({'uncertainty_causes':['granularity_gap']},'UNSUPPORTED_GRANULARITY'),({},'MISSING')])
def test_specific_reason_categories(assessment,code):
 req=impl.project_case(public_case({'perturbed_query':'Who designed it?','perturbed_context':'No designer is recorded.'},0));result=impl.refusal_details(['MISSING'],req,assessment);assert result[1]==code

def test_permission_change_invalidates_new_profile_binding():
 case={'query':'What file type is recorded for ochre observatory?','sources':[source('ochre observatory','METADATA',fields={'file_type':'plan'})]};req=impl.project_case(case);case['sources'][0]['access_mode']='DENY'
 with pytest.raises(ValueError):impl.assert_safe_payload(req,req.public())

def test_zero_view_source_existence_unchanged():
 empty=public_case({'perturbed_query':'Who designed it?','perturbed_context':''},0);hidden=copy.deepcopy(empty);hidden['sources'][0].update(content='SECRET',access_mode='DENY',existence_visibility='INTERNAL_ONLY')
 class Never:
  def call(self,*args):raise AssertionError('No model call')
 a=impl.run_governed(empty,Never());b=impl.run_governed(hidden,Never());assert a['public_traces']==b['public_traces']

def test_cross_field_error_is_not_repaired_or_shared_with_valid_system():
 scenario=make_cases()[0]
 class BadControl(FunctionalProvider):
  def call(self,request,kind,prompt,payload,limit):
   r=super().call(request,kind,prompt,payload,limit)
   if kind=='shared_control':
    d=json.loads(r.content);d['fulfilment_status']='FULL';r.content=json.dumps(d)
   return r
 row=impl.run_governed(scenario['runtime_case'],BadControl(scenario,impl));assert 'shared_control' in row['system_errors'];assert 'semantic_cfaf' not in row['system_errors'];assert row['responses']['shared_control']['fulfilment_status']=='FULL'

@pytest.mark.parametrize('q,kind',[('In the revised edition, what is a semaphore?','FACT'),('Is the bridge open?','BOOLEAN'),('Why was the station closed?','EXPLANATION'),('Could you tell me where the monument is?','LOCATION'),('What is a concrete example of a mineral?','INSTANCE')])
def test_prefaces_boolean_and_instance_types(q,kind):assert profile_query(q)['answer_kind']==kind

def factual_case(query='Who painted the mural?',context='An unnamed painter made the mural.'):
 return public_case({'perturbed_query':query,'perturbed_context':context},0)
class ChangedRequirement(FunctionalProvider):
 changes={}
 def call(self,request,kind,prompt,payload,limit):
  r=super().call(request,kind,prompt,payload,limit)
  if kind=='semantic_analysis':
   a=json.loads(r.content);a['requirement_support'][0].update(self.changes);r.content=json.dumps(a)
  return r

def test_unnamed_description_cannot_fulfil_name_request():
 class P(ChangedRequirement):changes={'answer_form':'DESCRIPTION','identity_identified':False,'complete_answer':False}
 row=impl.run_governed(factual_case(),P({'expected':{'answer':'The unnamed painter.'},'controlled_semantic_supported':True},impl));assert row['selected_mode']=='CFAF';assert 'REQUESTED_IDENTITY_INCOMPLETE' in row['fulfilment_issues']

def test_associated_person_without_role_link_is_not_complete():
 class P(ChangedRequirement):changes={'relation_and_qualifiers_supported':False,'complete_answer':False}
 row=impl.run_governed(factual_case(context='Lea is mentioned as a cast member.'),P({'expected':{'answer':'Lea'},'controlled_semantic_supported':True},impl));assert row['selected_mode']=='CFAF';assert 'REQUEST_RELATION_UNSUPPORTED' in row['fulfilment_issues']

def test_definition_cannot_replace_requested_instance():
 class P(ChangedRequirement):changes={'answer_form':'DEFINITION'}
 row=impl.run_governed(factual_case('What is a concrete example of a mineral?','A mineral is naturally occurring.'),P({'expected':{'answer':'A mineral.'},'controlled_semantic_supported':True},impl));assert row['selected_mode']=='CFAF';assert 'REQUESTED_INSTANCE_INCOMPLETE' in row['fulfilment_issues']

def test_multiple_referents_cannot_be_made_full_by_listing_answers():
 class P(ChangedRequirement):changes={'referent_resolved':False,'complete_answer':False}
 row=impl.run_governed(factual_case('Who wrote this novel?','There are two novels with that title.'),P({'expected':{'answer':'Both writers.'},'controlled_semantic_supported':True},impl));assert row['selected_mode']=='CFAF';assert row['internal_reason']['code']=='AMBIGUOUS_REQUEST'

def test_query_only_fallback_rejects_context_and_answers():
 request=impl.QueryOnlyRequest('maker of the monument')
 with pytest.raises(ValueError):impl.assert_safe_payload(request,{'query':request.query,'context':'forbidden'})
 from .query_profile import parse_profile
 data={'resolution':'RESOLVED','query_target':None,'requirements':[{'requirement_id':'request-1','request_type':'FACT_LOOKUP','metadata_fields':[],'answer_kind':'NAMED_IDENTITY','request_text':request.query}]}
 assert parse_profile(request.query,json.dumps(data))
 data['requirements'][0]['request_text']='The answer is Lea'
 with pytest.raises(ValueError):parse_profile(request.query,json.dumps(data))

def test_telegraphic_query_only_fallback_and_bound_guard():
 class P(FunctionalProvider):
  def call(self,request,kind,prompt,payload,limit):
   if kind=='query_profile':
    assert set(payload)=={'query'}
    from types import SimpleNamespace
    data={'resolution':'RESOLVED','query_target':None,'requirements':[{'requirement_id':'request-1','request_type':'FACT_LOOKUP','metadata_fields':[],'answer_kind':'NAMED_IDENTITY','request_text':request.query}]}
    return SimpleNamespace(content=json.dumps(data),model='controlled-query-only')
   return super().call(request,kind,prompt,payload,limit)
 row=impl.run_governed(factual_case('sculptor of the monument','Lea sculpted the monument.'),P({'expected':{'answer':'Lea'},'controlled_semantic_supported':True},impl));assert row['selected_mode']=='FULL';assert row['query_profile_fallback']['valid'];assert row['query_profile']['method']=='validated_query_only_llm_fallback'
