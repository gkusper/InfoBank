"""Versioned, label-blind round runner with persistent deadline and task budget."""
import argparse,hashlib,importlib,json,subprocess,time
from pathlib import Path
from evaluation.refusalbench_noncontradiction_v1.public_adapter import public_case,authorize_runtime
from evaluation.refusalbench_span_fix_v1.api_budget import read_jsonl,write_json,append_jsonl
from .deadline import ensure,elapsed,snapshot,DeadlineReached
from .provider_v2 import BoundedProvider
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1]
SHARED=['deadline.py','exposure.py','provider_v2.py','runner_v2.py','scoring.py']
BASE=['evaluation/infobank_semantic_integration_v2/'+n for n in ['query_profile.py','metadata_binding.py','integration.py','provider.py']]+['evaluation/wolala2026/pipeline.py','evaluation/wolala2026/semantic_evidence.py','evaluation/refusalbench_span_fix_v1/contracts.py','evaluation/refusalbench_span_fix_v1/span_references.py']

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load_version(version):return importlib.import_module('evaluation.refusalbench_iterative_dev_v1.versions.'+version+'.implementation')
def source_version(version):
 impl=load_version(version);paths=[ROOT/n for n in SHARED]+list((ROOT/'versions'/version).glob('*.py'))+[REPO/n for n in BASE]
 hashes={p.relative_to(REPO).as_posix():sha(p) for p in paths}
 return {'version':version,'implementation_name':impl.VERSION,'frozen_at':snapshot(),'code_sha256':hashes,'analysis_prompt':impl.GOVERNED_PROMPT,'cfaf_prompt':impl.CFAF_PROMPT,'control_prompt':impl.CONTROL_PROMPT,'analysis_schema':impl.ANALYSIS_SCHEMA,'generation_schema':impl.GENERATION_SCHEMA,'model':'gpt-4o-mini','temperature':0,'analysis_max_tokens':1500,'generation_max_tokens':160,'repetitions':1,'task_api_attempt_cap':360,'no_fallback_classifier_calls':not hasattr(impl,'PROFILE_SCHEMA'),'query_only_fallback_schema':getattr(impl,'PROFILE_SCHEMA',None),'query_only_fallback_prompt':getattr(impl,'PROFILE_PROMPT',None),'query_only_fallback_max_tokens':500}

def verify_source(frozen):
 if any(sha(REPO/n)!=h for n,h in frozen['code_sha256'].items()):raise RuntimeError('Frozen round source changed')

def prepare(number,version):
 ensure('new round preparation',240)
 if elapsed()>=3000:raise DeadlineReached('50-minute reporting priority prevents another new experiment')
 from .exposure import sample
 frozen=source_version(version);out=sample(number,frozen)
 archive=out/'frozen_source';archive.mkdir()
 for name in frozen['code_sha256']:
  path=archive/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((REPO/name).read_bytes())
 return out

def paired(version,baseline):
 ensure('paired regression preparation',240)
 if elapsed()>=3000:raise DeadlineReached('50-minute cutoff: no new paired experiment')
 out=ROOT/'paired_regression';out.mkdir(exist_ok=False);base=ROOT/baseline
 for name in ['selected_cases.jsonl','runtime_inputs.jsonl','runtime_authorization.json','selection_manifest.json']:(out/name).write_bytes((base/name).read_bytes())
 frozen=source_version(version);frozen['paired_baseline']=baseline;frozen['no_new_exposure']=True;write_json(out/'source_version.json',frozen)
 return out

def generate(directory):
 out=ROOT/directory;ensure('round generation',240);frozen=json.loads((out/'source_version.json').read_text());verify_source(frozen);impl=load_version(frozen['version'])
 if (out/'worker_results.jsonl').exists():raise RuntimeError('Frozen observations already exist')
 runtime=read_jsonl(out/'runtime_inputs.jsonl');auth=json.loads((out/'runtime_authorization.json').read_text());authorize_runtime(runtime,auth)
 if sha(out/'runtime_inputs.jsonl')!=auth['runtime_sha256']:raise RuntimeError('Runtime checksum mismatch')
 provider=BoundedProvider(out,impl);failures=[];consecutive=0;blocker=None;start=time.perf_counter()
 for i,row in enumerate(runtime):
  try:ensure('case generation',50,new_api=True)
  except DeadlineReached as exc:blocker=str(exc);break
  provider.index=i;provider.case_calls=[];before=time.perf_counter();attempts=provider.attempts
  try:
   outcome=impl.run_governed(public_case(row,i),provider)
   if outcome.get('semantic_valid') is False:raise RuntimeError('INVALID_SEMANTIC_ANALYSIS')
   result={'runtime_index':i,'execution_status':'SUCCESS' if not outcome.get('system_errors') else 'OUTPUT_ERRORS','outcome':outcome};consecutive=0
  except Exception as exc:
   result={'runtime_index':i,'execution_status':'ERROR','outcome':None,'error':str(exc)};failures.append({'runtime_index':i,'error':str(exc)});consecutive+=1
   if isinstance(exc,DeadlineReached) or consecutive>=3 or any(s in str(exc) for s in ['HTTP 401','HTTP 403','HTTP 429','network error','budget exhausted']):blocker=str(exc)
  result.update(calls=provider.case_calls,actual_api_attempts=provider.attempts-attempts,end_to_end_ms=(time.perf_counter()-before)*1000)
  append_jsonl(out/'worker_results.jsonl',result)
  print(out.name,i+1,result['execution_status'],{s:(result['outcome'].get('responses',{}).get(s) or {}).get('top_level_mode') for s in ['semantic_cfaf','shared_control']} if result['outcome'] else result.get('error'),flush=True)
  if blocker:break
 write_json(out/'generation_manifest.json',{'completed_cases':len(read_jsonl(out/'worker_results.jsonl')) if (out/'worker_results.jsonl').exists() else 0,'failures':failures,'blocker':blocker,'frozen_source_unchanged':True,'wall_clock_ms':(time.perf_counter()-start)*1000,'end_time':snapshot()})
 verify_source(frozen)
 from .scoring import score_round
 return score_round(out)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','generate','paired']);p.add_argument('--round',type=int);p.add_argument('--version');p.add_argument('--directory');p.add_argument('--baseline',default='round_01');a=p.parse_args()
 if a.action=='prepare':prepare(a.round,a.version)
 elif a.action=='paired':paired(a.version,a.baseline)
 else:generate(a.directory)
