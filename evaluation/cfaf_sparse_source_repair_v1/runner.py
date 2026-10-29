"""Frozen exact exposed-ten paired run; no gold or scorer import."""
import json,time,sys,xml.etree.ElementTree as ET
from .artifacts import *
from .deadline import ensure,elapsed
from . import integration as impl
from .provider import BoundedProvider
from .cached import PREVIOUS
from .gate_controls import assess
from .sparse_source_assessment import parse_sparse
from .source_inventory import build_inventory
from .public_grounding_trace import build_public_grounding_trace
from evaluation.cfaf_target_claim_alignment_v1 import integration as old
from evaluation.cfaf_target_claim_alignment_v1.integration_controls import assess as old_assess
from evaluation.cfaf_request_evidence_verification_v1.runner import request_for
from evaluation.cfaf_request_evidence_verification_v1.prepare import selector
from evaluation.cfaf_request_evidence_verification_v1.source_capability_rules import trusted_provenance

def verify_frozen():
 m=read(ROOT/'experiment_manifest.json')
 for p,h in m['frozen_source_sha256'].items():
  if sha(REPO/p)!=h:raise RuntimeError('FROZEN_SOURCE_CHANGED:'+p)
 if sha(ROOT/'runtime_inputs.jsonl')!=m['runtime_sha256']:raise RuntimeError('FROZEN_RUNTIME_CHANGED')
 return m

def freeze():
 if (ROOT/'experiment_manifest.json').exists():raise RuntimeError('Already frozen')
 ensure('freeze',30,large_work=True)
 state=read(ROOT/'task_state.json');assert all(sha(REPO/p)==h for p,h in state['protected_files'].items())
 for name in ['unit_tests.xml','regression_tests.xml','final_regression_tests.xml','historical_hash_tests.xml']:
  suites=list(ET.parse(ROOT/name).getroot().iter('testsuite'));assert all(int(s.get('failures',0))+int(s.get('errors',0))==0 for s in suites),name
 cached=read(ROOT/'cached_ablation_results.json');assert cached['summary']['A0']['valid']==1 and cached['summary']['A3']['valid']==9;assert len(rows(ROOT/'runtime_inputs.jsonl'))==10
 assert (ROOT/'runtime_inputs.jsonl').read_bytes()==(PREVIOUS/'runtime_inputs.jsonl').read_bytes()
 cached_raw=rows(ROOT/'cached_ablation_raw.jsonl');runtime=rows(ROOT/'runtime_inputs.jsonl');previous=rows(PREVIOUS/'results.jsonl')
 for cached_row,inp,prior in zip(cached_raw,runtime,previous):
  request=request_for(inp['case'],prior['outcome']);inventory=build_inventory(request,inp['mapping'])
  for config in ['A1','A2','A3']:
   a,data,audit=parse_sparse(cached_row['raw_semantic_response'],request,inventory,allow_repair=config!='A1');v=assess(request,a,data,'T3',trusted_provenance(request,False));expected=cached_row['variants'][config];assert a.valid==expected['semantic_valid'] and selector(v,request,data)==expected['mode'];assert audit['errors']==expected['validation_errors']
 write(ROOT/'cached_final_source_verification.json',{'status':'PASS','cases':10,'configurations':['A1','A2','A3'],'model_calls':0,'final_sources_reproduce_saved_cached_results':True})
 for name in ['GOVERNED_PROMPT','CFAF_PROMPT','CONTROL_PROMPT','ANALYSIS_SCHEMA','GENERATION_SCHEMA']:assert getattr(impl,name)==getattr(old,name)
 own=[p.relative_to(REPO).as_posix() for p in ROOT.glob('*.py') if p.name not in {'score.py','report.py','audit.py','finalize.py','regression.py'}];dependencies=read(PREVIOUS/'experiment_manifest.json')['frozen_source_sha256'];files=sorted(set(own)|set(dependencies))
 write(ROOT/'experiment_manifest.json',{'baseline_commit':state['baseline_commit'],'branch':'experiment/cfaf-sparse-source-repair-v1','frozen_epoch':time.time(),'elapsed_at_freeze_seconds':elapsed(),'frozen_source_sha256':{p:sha(REPO/p) for p in files},'runtime_sha256':sha(ROOT/'runtime_inputs.jsonl'),'selection_sha256':sha(ROOT/'selection_manifest.json'),'cached_ablation_sha256':sha(ROOT/'cached_ablation_results.json'),'previous_raw_analysis_events_sha256':sha(PREVIOUS/'api_events.jsonl'),'old_dataset_source_commit':'2b7264f5d4e066affbe4b67b7d3b9cffeff98ede','old_dataset_sha256':'419e3941f6e8eb4082a74ca2140c1f9337f8b467ff76656a6b8b0290ca3f3a72','previous_selected_ids':[r['sample_id'] for r in read(ROOT/'selection_manifest.json')['records']],'new_dataset_records':0,'model':'gpt-4o-mini','temperature':0,'repetitions':1,'analysis_max_tokens':1500,'generation_max_tokens':512,'profile_max_tokens':500,'attempt_cap':75,'input_budget':60000,'input_budget_method':'Unchanged conservative serialized-UTF8-byte upper bound +128','model_visible_prompts_and_schemas_unchanged':True,'primary_change':'Deterministic sparse contract, exact reference normalization, operational status/reasons and strict post-response canonical vocabulary validation','new_public_reason_category':False,'public_reason_vocabulary_version':'existing-ReasonClass-v1-strict-validation','same_fresh_upstream_for_both_generators':True,'control_receives_gate_or_private_inventory':False,'sidecar_phase':'C; deterministic experimental analysis only after B completes; no verified claim citations without independent mapping','no_second_verifier_or_embeddings':True,'original_selector_and_eight_stages_unchanged':True,'tests_before_API':True,'cached_before_API':True,'original_benchmark_gold_in_runtime':False,'independent_validation':False})
 print('FROZEN',len(files),'sources; 57 synthetic tests and final historical regression prerequisites passed')

def live():
 m=verify_frozen();ensure('paired ten-case development regression',120)
 if (ROOT/'live_paired_results.jsonl').exists():raise RuntimeError('No repeated live run')
 provider=BoundedProvider()
 for row in rows(ROOT/'runtime_inputs.jsonl'):
  ensure('next exposed case',90,new_api=True);verify_frozen();i=row['runtime_index'];provider.index=i;provider.case_calls=[];provider.query_context=row['query_context'];provider.private_mapping=row['mapping'];start=time.perf_counter();record={'runtime_index':i,'status':'ERROR'}
  try:
   case=row['case'];request=impl.project_case(case);outcome=impl.run_governed(case,provider,'T3',trusted_provenance(request,False));request=request_for(case,outcome);inventory=build_inventory(request,row['mapping']);raw=next(c['content'] for c in provider.case_calls if c['kind']=='semantic_analysis');a,data,audit=parse_sparse(raw,request,inventory);provenance=trusted_provenance(request,False);a0=assess(request,a,data,'A0',provenance);strict,strict_data,strict_audit=old.parse_analysis(raw,request);strict_gate=old_assess(request,strict,strict_data,'T3',provenance)
   record.update(status='COMPLETED',outcome=outcome,original_A0_gate_on_new_sparse=selector(a0,request,data),strict_original_gate_on_same_fresh_analysis=selector(strict_gate,request,strict_data),strict_original_semantic_valid=strict.valid,strict_original_errors=strict_audit.get('errors',[]))
  except Exception as exc:
   from evaluation.refusalbench_span_fix_v1.api_budget import redact
   record['error']=redact(str(exc))
  record.update(api_calls=provider.case_calls,end_to_end_ms=(time.perf_counter()-start)*1000);record['deterministic_and_local_overhead_ms']=max(0,record['end_to_end_ms']-sum(c['latency_ms'] for c in provider.case_calls));append(ROOT/'live_paired_results.jsonl',record)
  o=record.get('outcome',{});print('LIVE',i+1,record['status'],'valid',o.get('semantic_valid'),'gate',o.get('selected_mode'),'status',o.get('verification_outcome',{}).get('status'),'served',{k:v.get('top_level_mode') for k,v in o.get('responses',{}).items()},record.get('error',''),flush=True)
  if record.get('error') and any(v in record['error'] for v in ['HTTP 401','HTTP 403','HTTP 429','network error','cap exhausted']):break
 verify_frozen()

def citations():
 verify_frozen();results=rows(ROOT/'live_paired_results.jsonl');runtime=rows(ROOT/'runtime_inputs.jsonl')
 if len(results)!=10 or any(r['status']!='COMPLETED' for r in results):raise RuntimeError('Phase C deferred: primary phase incomplete')
 if (ROOT/'citation_diagnostics.jsonl').exists():raise RuntimeError('Citation diagnostics already saved')
 for r,inp in zip(results,runtime):
  o=r['outcome'];request=request_for(inp['case'],o);inventory=build_inventory(request,inp['mapping']);traces={name:build_public_grounding_trace(request,o.get('semantic_assessment') or {},response,o['semantic_valid'],inventory,name) for name,response in o['responses'].items()};append(ROOT/'citation_diagnostics.jsonl',{'runtime_index':r['runtime_index'],'phase':'C deterministic experimental sidecar; no new API calls','systems':traces})
 print('PHASE C completed; no unverified claim-group mapping rendered as a verified citation')
if __name__=='__main__':{'freeze':freeze,'live':live,'citations':citations}[sys.argv[1]]()
