import json,copy,pytest
from . import measured_c as impl
from .contracts import *
from .systems import guarded_a
from evaluation.cfaf_sparse_source_repair_v1.operational_failure_codes import safe_operational_response
from evaluation.cfaf_target_claim_alignment_v1.test_target_claim import case,doc
from evaluation.cfaf_sparse_source_repair_v1 import integration as previous
from evaluation.refusalbench_iterative_dev_v1.functional_support import FunctionalProvider

def test_c_is_existing_pipeline_without_unmeasured_control_generation():
 c=case();p=FunctionalProvider({'expected':{'answer':'Avel'}},impl);out=impl.run_governed(c,p);assert [k for k,payload in p.calls]==['semantic_analysis','semantic_cfaf'];assert set(out['responses'])=={'semantic_cfaf'};assert out['selected_mode']=='FULL';assert len(out['internal_trace']['stage_sequence'])==8;assert impl.TopLevelModeSelectionStage is previous.TopLevelModeSelectionStage
 for key in ['GOVERNED_PROMPT','CFAF_PROMPT','ANALYSIS_SCHEMA','GENERATION_SCHEMA']:assert getattr(impl,key)==getattr(previous,key)
def test_minimal_contracts_reuse_authorized_inventory():
 r=impl.project_case(case());a=RequestContract.from_request(r);b=PermittedEvidenceContract.from_request(r);assert a.projection_signature==b.request_signature;assert len(b.view_hashes)==1
 with pytest.raises(ValueError):FulfilmentDecision('FULL','OPERATIONAL_FAILURE','INVALID')
def test_b_reuses_a_without_mode_gate():
 r=impl.project_case(case());raw={'answer':'Avel','top_level_mode':'FULL','fulfilment_status':'FULL','realization':None,'public_reason_class':None,'next_step_codes':[]};out,status=guarded_a(raw,r);assert out is raw;assert status['status']=='VALID_CONTRACT_SELF_REPORTED_MODE';assert PublicResponseContract.from_response(out)
def test_b_rejects_noncanonical_reason():
 r=impl.project_case(case());raw=safe_operational_response();raw['public_reason_class']='MISSING_EVIDENCE';out,status=guarded_a(raw,r);assert status['status']=='OPERATIONAL_FAILURE';assert out['top_level_mode']=='CFAF'
def test_p5_hidden_absent_all_contract_outputs_indistinguishable():
 p=FunctionalProvider({'expected':{'answer':'Avel'}},impl);c=case(sources=[doc(access='DENY',existence_visibility='INTERNAL_ONLY')]);a=impl.run_governed(c,p);c['sources']=[];b=impl.run_governed(c,p);assert a['public_traces']==b['public_traces'];assert not p.calls

def test_clustered_paired_statistics_preserve_pairs():
 from .statistics import bootstrap_groups,paired_counts
 rs=[{'group':'one','A':0,'B':0,'C':1},{'group':'one','A':1,'B':1,'C':0},{'group':'two','A':1,'B':1,'C':1},{'group':'two','A':0,'B':0,'C':0}];b=bootstrap_groups(rs,repetitions=20);assert b['groups']==2;assert b['paired_delta_intervals']['C-B']==[0,0];assert paired_counts(rs)['left_only']==1 and paired_counts(rs)['right_only']==1

def test_provider_baseline_boundary_before_network(monkeypatch):
 from .provider import StudyProvider
 monkeypatch.setenv('OPENAI_API_KEY','fictional-unit-key');p=StudyProvider();r=impl.project_case(case())
 with pytest.raises(ValueError,match='BENCHMARK_FIELD'):p.call(r,'standard_rag','',dict(r.public(),sample_id='forbidden-id'),512)
 with pytest.raises(ValueError,match='STANDARD_RAG_CONTAMINATION'):p.call(r,'standard_rag','',dict(r.public(),semantic_assessment={}),512)

def test_operational_refusal_not_credited_as_substantive_mode_accuracy():
 from .score import compute_mode_metrics
 r={'systems':{'C':{'operational_failure':True,'policy_violation':False,'status':'OPERATIONAL_FAILURE','mode_correct_nonoperational':False}},'_responses':{'C':{'top_level_mode':'CFAF','answer':'Could not verify','public_reason_class':'EPISTEMIC'}}};g={'expected_mode':'CFAF','reason_available':True,'expected_reason':'EPISTEMIC'};m=compute_mode_metrics([r],[g],'C');assert m['observed_output_mode_agreement']==1;assert m['mode_accuracy_nonoperational']==0;assert m['reason_class_agreement']==0

def test_missing_execution_stays_in_reason_denominator():
 from .score import compute_mode_metrics
 r={'systems':{'C':{'operational_failure':True,'policy_violation':False,'status':'NOT_EXECUTED','mode_correct_nonoperational':False}},'_responses':{'C':None}};g={'expected_mode':'CFAF','reason_available':True,'expected_reason':'EVIDENTIAL'};m=compute_mode_metrics([r],[g],'C');assert m['mode_accuracy_nonoperational']==0;assert m['reason_class_denominator']==1
