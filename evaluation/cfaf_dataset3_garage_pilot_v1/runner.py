"""Frozen ten-case run. Does not load original records, gold or scorer outputs."""
import json,time,sys
from .artifacts import *
from .deadline import ensure,elapsed
from .provider import BoundedProvider
from .adapter import CONTEXT_POLICY,INPUT_BUDGET
from evaluation.cfaf_target_claim_alignment_v1 import integration as impl
from evaluation.cfaf_target_claim_alignment_v1.integration_controls import assess
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
 s=read(ROOT/'task_state.json');bad=[p for p,h in s['protected_files'].items() if sha(REPO/p)!=h]
 assert not bad,bad
 current=[p.relative_to(REPO).as_posix() for p in ROOT.glob('*.py') if p.name not in {'score.py','report.py','audit.py','finalize.py','regression.py'}]
 prior=read(REPO/'evaluation/cfaf_target_claim_alignment_v1/experiment_manifest.json')['frozen_source_sha256']
 hashes={p:sha(REPO/p) for p in sorted(set(current)|set(prior))}
 write(ROOT/'experiment_manifest.json',{'baseline_commit':s['baseline_commit'],'branch':'experiment/cfaf-garage-pilot-v1','frozen_utc_epoch':time.time(),'elapsed_at_freeze_seconds':elapsed(),'frozen_source_sha256':hashes,'runtime_sha256':sha(ROOT/'runtime_inputs.jsonl'),'selection_manifest_sha256':sha(ROOT/'dataset3_selection_manifest.json'),'dataset_sha256':read(ROOT/'source_audit.json')['sha256'],'model':'gpt-4o-mini','temperature':0,'repetitions':1,'analysis_limit':1500,'generation_limit':512,'profile_limit':500,'attempt_cap':60,'input_token_upper_bound':INPUT_BUDGET,'input_budget_method':'Serialized ASCII JSON UTF-8 byte count +128; conservative token upper bound; no tokenizer package required','context_policy':CONTEXT_POLICY,'generated_systems':['T3 semantic_cfaf','shared_control'],'gate_only':['A0'],'A0_generated':False,'shared_upstream':True,'prompt_schema_changes':False,'eight_stage_selector_unchanged':True,'gold_fields_to_model':False,'web_ent_permissions':'All supplied passages have explicit task authorization for FULL access; provider does not imply authority or trust','provenance_attested':False,'runtime_date_context':'Original question_date supplied equally to analysis and both generators; query-only fallback remains query-only','additional_verifier':False,'embeddings':False,'external_case_fact_retrieval':False,'binary_full_cfaf_accuracy':'NOT_MEASURABLE without independent complete-request sufficiency labels','independent_validation':False,'python':sys.version,'protected_count':len(s['protected_files'])})
 print('FROZEN',len(hashes),'sources; runtime cases',len(rows(ROOT/'runtime_inputs.jsonl')))

def pilot():
 verify_frozen();ensure('ten-case pilot',120)
 if (ROOT/'results.jsonl').exists():raise RuntimeError('No repeated pilot or rescore with changed implementation')
 provider=BoundedProvider()
 for row in rows(ROOT/'runtime_inputs.jsonl'):
  verify_frozen();ensure('next selected case',90,new_api=True);i=row['runtime_index'];provider.index=i;provider.case_calls=[];provider.query_context=row['query_context'];record={'runtime_index':i,'status':'ERROR'};start=time.perf_counter()
  try:
   case=row['case'];request=impl.project_case(case);provenance=trusted_provenance(request,False)
   outcome=impl.run_governed(case,provider,'T3',provenance);request=request_for(case,outcome)
   a,data,audit=impl.parse_analysis(json.dumps(outcome['semantic_assessment']),request)
   a0=assess(request,a,data,'A0',provenance);a0mode=selector(a0,request,data)
   record.update(status='COMPLETED',outcome=outcome,A0_gate=a0mode,A0_assessment=a0)
  except Exception as exc:
   from evaluation.refusalbench_span_fix_v1.api_budget import redact
   record['error']=redact(str(exc))
  record.update(api_calls=provider.case_calls,elapsed_ms=(time.perf_counter()-start)*1000);append(ROOT/'results.jsonl',record)
  print('CASE',i+1,record['status'],'T3',record.get('outcome',{}).get('selected_mode'),'A0',record.get('A0_gate'),'errors',record.get('outcome',{}).get('system_errors',{}),record.get('error',''),flush=True)
  if record.get('error') and any(v in record['error'] for v in ['HTTP 401','HTTP 403','HTTP 429','network error','cap exhausted']):break
 verify_frozen()
if __name__=='__main__':{'freeze':freeze,'pilot':pilot}[sys.argv[1]]()
