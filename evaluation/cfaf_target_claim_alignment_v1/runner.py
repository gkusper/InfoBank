"""Freeze all target/claim mechanisms and run only shared-upstream comparisons."""
import argparse,json,time
from .artifacts import *
from .deadline import ensure,elapsed
from . import integration as impl
from .integration_controls import assess
from .provider import BoundedProvider
from .prepare import CONFIGS
from evaluation.cfaf_request_evidence_verification_v1.runner import request_for
from evaluation.cfaf_request_evidence_verification_v1.prepare import selector
from evaluation.cfaf_request_evidence_verification_v1.source_capability_rules import trusted_provenance

def verify_frozen():
 m=read(ROOT/'experiment_manifest.json')
 for n,h in m['frozen_source_sha256'].items():
  if sha(REPO/n)!=h:raise RuntimeError('Frozen target/claim source changed:'+n)
 if sha(ROOT/'pilot_runtime.jsonl')!=m['runtime_sha256']:raise RuntimeError('Frozen runtime changed')
 return m

def freeze():
 ensure('target-claim freeze',90,large_work=True)
 if (ROOT/'experiment_manifest.json').exists():raise RuntimeError('Already frozen')
 import xml.etree.ElementTree as ET
 for name in ['unit_tests.xml','final_regression_tests.xml','current_worktree_hash_tests.xml']:
  root=ET.parse(ROOT/name).getroot();assert not any(int(s.get('failures',0))+int(s.get('errors',0)) for s in root.iter('testsuite'))
 assert read(ROOT/'metadata_type_summary.json')['original_type_sequences_correct']==17
 oldobs=rows(REPO/'evaluation/cfaf_requirement_alignment_v1/pilot_observations.jsonl');runtime=rows(ROOT/'pilot_runtime.jsonl');preflight=[]
 for row,previous in zip(runtime,oldobs):
  assert row['runtime_index']==previous['runtime_index'];out=previous['outcomes']['A0'];request=request_for(row['case'],out)
  if request.documents:a,data,audit=impl.parse_analysis(json.dumps(out['semantic_assessment']),request)
  else:a=None;data={}
  provenance=trusted_provenance(request,row['trusted_fixture_ingestion']);variants={c:assess(request,a,data,c,provenance) for c in CONFIGS};pred={c:selector(v,request,data) for c,v in variants.items()};assert all(pred[c]==pred['B3'] for c in ['T1','T2','T3']);assert pred['A0']==previous['gate_predictions']['A0'];preflight.append({'runtime_index':row['runtime_index'],'predictions':pred,'semantic_valid':a.valid if a else None})
 write(ROOT/'pilot_preflight.json',{'status':'PASS','rows':preflight,'model_calls':0})
 # Recompute cached diagnostics after all test-driven fixes; original inputs stay frozen.
 for old in rows(ROOT/'cached_ablation.jsonl'):
  src=REPO/old['raw_source'];out=rows(src)[old['origin_index']]['outcome'];case=rows(src.parent/'selected_cases.jsonl')[old['origin_index']]
  from evaluation.refusalbench_noncontradiction_v1.public_adapter import public_case
  c=public_case({'perturbed_query':case['perturbed_query'],'perturbed_context':case['perturbed_context']},old['origin_index']);request=request_for(c,out);a,data,audit=impl.parse_analysis(json.dumps(out['semantic_assessment']),request);variants={n:assess(request,a,data,n,trusted_provenance(request,False)) for n in CONFIGS};pred={n:selector(v,request,data) for n,v in variants.items()};assert pred==old['predictions'];append(ROOT/'cached_ablation_final.jsonl',{**old,'results':variants})
 own=['trusted_target_resolution.py','claim_evidence_alignment.py','metadata_value_typing.py','integration_controls.py','integration.py','provider.py','runner.py','deadline.py','artifacts.py','prepare.py','aggregate_smoke_adapter.py']
 files=[(ROOT/n).relative_to(REPO).as_posix() for n in own]+[p.relative_to(REPO).as_posix() for p in (ROOT/'vendor').glob('*.py')]+['evaluation/cfaf_requirement_alignment_v1/'+n for n in ['requirement_decomposition.py','requirement_alignment.py','rec_v2.py']]+['evaluation/cfaf_request_evidence_verification_v1/source_capability_rules.py']+['evaluation/refusalbench_iterative_dev_v1/versions/v02/'+n for n in ['implementation.py','metadata_binding.py','query_profile.py','contracts.py']]+['evaluation/wolala2026/'+n for n in ['pipeline.py','labels.py','semantic_evidence.py','real_api.py']]+['evaluation/refusalbench_span_fix_v1/span_references.py','evaluation/infobank_semantic_regression_v1/policy_projection.py']
 write(ROOT/'experiment_manifest.json',{'baseline_commit':read(ROOT/'task_state.json')['baseline_commit'],'branch':'experiment/cfaf-target-claim-alignment-v1','main_source_commit':read(ROOT/'remote_source_manifest.json')['source_commit'],'remote_main_merged':False,'frozen_at_epoch':time.time(),'elapsed_at_freeze':elapsed(),'frozen_source_sha256':{n:sha(REPO/n) for n in files},'runtime_sha256':sha(ROOT/'pilot_runtime.jsonl'),'scorer_sha256':sha(ROOT/'pilot_scorer_only.jsonl'),'model':'gpt-4o-mini','temperature':0,'repetitions':1,'analysis_limit':1500,'generation_limit':160,'profile_limit':500,'attempt_cap':120,'generated_configurations':['A0','T3','shared_control'],'gate_only_configurations':['B3','T1','T2'],'configurations':CONFIGS,'analysis_prompt':impl.GOVERNED_PROMPT,'cfaf_prompt':impl.CFAF_PROMPT,'control_prompt':impl.CONTROL_PROMPT,'analysis_schema':impl.ANALYSIS_SCHEMA,'generation_schema':impl.GENERATION_SCHEMA,'upstream_shared':True,'new_target_claim_data_sent_to_model':False,'shadow_mechanisms':['T1','T2','T3'],'T4':'NOT_EXECUTED; no post-label semantic veto enabled','optional_verifier':'DISABLED','metadata_type_fix':'New access/attribute/value-type representation in T1-T3; baseline B3 retained as reference; no gate change','evidence_pruning':'DIAGNOSTIC_ONLY; original permitted model views/counterevidence unchanged','selection':read(ROOT/'selection_manifest.json'),'not_independent_validation':True})
 print('Target/claim frozen: cached40, mixed24, metadata17/17, shadow-only T1-T3')

def pilot():
 verify_frozen();ensure('target claim live pilot',300)
 if elapsed()>=3000:raise RuntimeError('50-minute reporting priority')
 if (ROOT/'pilot_observations.jsonl').exists():raise RuntimeError('Live results already frozen')
 provider=BoundedProvider();consecutive=0
 for row in rows(ROOT/'pilot_runtime.jsonl'):
  ensure('paired case',90,new_api=True);verify_frozen();case=row['case'];i=row['runtime_index'];provider.index=i;provider.cache={};provider.case_calls=[];outcomes={};start=time.perf_counter();record={'runtime_index':i}
  try:
   request=impl.project_case(case);provenance=trusted_provenance(request,row['trusted_fixture_ingestion'])
   for config in ['A0','T3']:
    provider.system=config;outcomes[config]=impl.run_governed(case,provider,config,provenance)
   a0=outcomes['A0'];t3=outcomes['T3'];assert a0['semantic_assessment']==t3['semantic_assessment'] and a0['permitted_request']==t3['permitted_request'];request=request_for(case,a0)
   if request.documents:a,data,audit=impl.parse_analysis(json.dumps(a0['semantic_assessment']),request)
   else:a=None;data={}
   variants={c:assess(request,a,data,c,provenance) for c in CONFIGS};pred={c:selector(v,request,data) for c,v in variants.items()};assert pred['A0']==a0['selected_mode'] and pred['T3']==t3['selected_mode'];assert all(pred[c]==pred['B3'] for c in ['T1','T2','T3']);record.update(status='SUCCESS',outcomes=outcomes,ablations=variants,gate_predictions=pred,semantic_assessment_identical=True);consecutive=0
  except Exception as exc:
   from evaluation.refusalbench_span_fix_v1.api_budget import redact
   record.update(status='ERROR',error=redact(str(exc)),partial_outcomes=outcomes);consecutive+=1
  record.update(api_calls=provider.case_calls,elapsed_ms=(time.perf_counter()-start)*1000);append(ROOT/'pilot_observations.jsonl',record);print('target-claim pilot',i+1,record['status'],record.get('gate_predictions'),flush=True)
  if consecutive>=3 or record.get('error') and any(s in record['error'] for s in ['HTTP 401','HTTP 403','HTTP 429','network error','cap exhausted']):break
 verify_frozen()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['freeze','pilot']);a=p.parse_args();{'freeze':freeze,'pilot':pilot}[a.action]()
