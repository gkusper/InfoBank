"""Label-blind live worker. Reads only authorized two-field runtime rows."""
from __future__ import annotations
import argparse,hashlib,json,subprocess,time
from pathlib import Path
from .public_adapter import PilotProvider,authorize_runtime,public_case,run_governed
from evaluation.refusalbench_span_fix_v1.api_budget import write_json,append_jsonl,read_jsonl,utc
from evaluation.infobank_semantic_integration_v2.integration import GOVERNED_PROMPT,CFAF_PROMPT,CONTROL_PROMPT,ANALYSIS_SCHEMA
from evaluation.refusalbench_span_fix_v1.contracts import GENERATION_SCHEMA
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1]
FROZEN_FILES=['public_adapter.py','execute.py','score.py','test_pilot.py']
BASE_FILES=['evaluation/infobank_semantic_integration_v2/'+name for name in ['query_profile.py','metadata_binding.py','integration.py','provider.py']]+['evaluation/refusalbench_span_fix_v1/span_references.py','evaluation/refusalbench_span_fix_v1/contracts.py','evaluation/wolala2026/pipeline.py','evaluation/wolala2026/semantic_evidence.py']

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def freeze_hashes():return {**{name:sha(ROOT/name) for name in FROZEN_FILES},**{name:sha(REPO/name) for name in BASE_FILES}}


def freeze():
 if (ROOT/'prerun_protocol.json').exists():raise RuntimeError('Frozen run already exists.')
 rows=read_jsonl(ROOT/'runtime_inputs.jsonl');auth=json.loads((ROOT/'runtime_authorization.json').read_text());authorize_runtime(rows,auth)
 if sha(ROOT/'runtime_inputs.jsonl')!=auth['runtime_sha256']:raise RuntimeError('Runtime file checksum mismatch.')
 write_json(ROOT/'prerun_protocol.json',{'version':'refusalbench-noncontradiction-v1','frozen_at_utc':utc(),'runtime_sha256':sha(ROOT/'runtime_inputs.jsonl'),'runtime_authorization_sha256':sha(ROOT/'runtime_authorization.json'),'code_sha256':freeze_hashes(),'model':'gpt-4o-mini','temperature':0,'analysis_max_tokens':1500,'generation_max_tokens':160,'repetitions':1,'hard_attempt_cap':75,'planned_calls':60,'systems':['semantic_cfaf','shared_control'],'counterfactual_constant_systems':'Zero-cost reference predictions only','implementation':'Finalized semantic-integration-v2.1 imported unchanged. No query-classifier or contradiction tuning.','data_flow':'Worker reads runtime_inputs and runtime_authorization only; no selection/gold/preparation imports or reads.'})
 write_json(ROOT/'frozen_prompts.json',{'analysis':GOVERNED_PROMPT,'semantic_cfaf':CFAF_PROMPT,'shared_control':CONTROL_PROMPT,'analysis_schema':ANALYSIS_SCHEMA,'generation_schema':GENERATION_SCHEMA})
 print('Protocol frozen; 20 authorized two-field rows; current InfoBank v2.1 unchanged.')


def generate():
 protocol=json.loads((ROOT/'prerun_protocol.json').read_text())
 if (ROOT/'worker_results.jsonl').exists() or (ROOT/'api_requests.jsonl').exists():raise RuntimeError('Refusing to overwrite/replay frozen observations.')
 if protocol['code_sha256']!=freeze_hashes():raise RuntimeError('Frozen implementation changed.')
 rows=read_jsonl(ROOT/'runtime_inputs.jsonl');auth=json.loads((ROOT/'runtime_authorization.json').read_text());authorize_runtime(rows,auth)
 if sha(ROOT/'runtime_inputs.jsonl')!=protocol['runtime_sha256'] or sha(ROOT/'runtime_authorization.json')!=protocol['runtime_authorization_sha256']:raise RuntimeError('Unauthorized runtime file change.')
 provider=PilotProvider(ROOT);start=time.perf_counter();failures=[];consecutive=0;blocker=None
 for i,row in enumerate(rows):
  provider.index=i;provider.case_calls=[];before=time.perf_counter();first_attempt=provider.attempts
  try:
   outcome=run_governed(public_case(row,i),provider)
   if outcome['semantic_valid'] is False:raise RuntimeError('SEMANTIC_ANALYSIS_SCHEMA_OR_REFERENCE_INVALID')
   result={'runtime_index':i,'execution_status':'SUCCESS','outcome':outcome};consecutive=0
  except Exception as exc:
   result={'runtime_index':i,'execution_status':'ERROR','error':str(exc),'outcome':None};failures.append({'runtime_index':i,'error':str(exc)});consecutive+=1
   # No fabricated refusal output. Schema/semantic errors remain errors, and the
   # remaining independent selected cases may still run under unchanged code.
   if any(marker in str(exc) for marker in ['HTTP 401','HTTP 403','HTTP 429','network error']) or consecutive>=3:blocker=str(exc)
  result.update(calls=provider.case_calls,actual_api_attempts=provider.attempts-first_attempt,end_to_end_ms=(time.perf_counter()-before)*1000)
  append_jsonl(ROOT/'worker_results.jsonl',result)
  print(i+1,result['execution_status'],{s:result['outcome']['responses'][s]['top_level_mode'] for s in ['semantic_cfaf','shared_control']} if result['outcome'] else result.get('error'),flush=True)
  if blocker:break
 status='COMPLETED' if len(read_jsonl(ROOT/'worker_results.jsonl'))==20 else 'BLOCKED'
 write_json(ROOT/'generation_manifest.json',{'status':status,'actual_api_attempts':provider.attempts,'hard_attempt_cap':75,'worker_cases_recorded':len(read_jsonl(ROOT/'worker_results.jsonl')),'failures':failures,'blocker':blocker,'code_unchanged':protocol['code_sha256']==freeze_hashes(),'runtime_unchanged':sha(ROOT/'runtime_inputs.jsonl')==protocol['runtime_sha256'],'wall_clock_ms':(time.perf_counter()-start)*1000,'finished_at_utc':utc(),'no_auto_retries':True})
 print(json.dumps({'status':status,'attempts':provider.attempts,'case_errors':len(failures)}),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['freeze','generate']);args=parser.parse_args();freeze() if args.action=='freeze' else generate()
