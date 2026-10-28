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
