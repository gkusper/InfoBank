"""One saved paired execution; scorer/gold has no inference import path."""
import json,time,sys,subprocess,xml.etree.ElementTree as ET
from .artifacts import *
from . import measured_c as impl
from .provider import StudyProvider
from .systems import STANDARD_PROMPT,guarded_a
from evaluation.cfaf_sparse_source_repair_v1.operational_failure_codes import safe_operational_response
from evaluation.cfaf_request_evidence_verification_v1.source_capability_rules import trusted_provenance
from evaluation.refusalbench_span_fix_v1.api_budget import redact

def verify_frozen():
 m=read(ROOT/'EXPERIMENT_MANIFEST.json')
 for p,h in m['frozen_source_sha256'].items():
  if sha(REPO/p)!=h:raise RuntimeError('FROZEN_SOURCE_CHANGED:'+p)
 assert sha(ROOT/'DATASET3_SELECTION_MANIFEST.json')==m['selection_manifest_sha256']
 assert sha(ROOT/'local/runtime_inputs.jsonl')==m['private_runtime_sha256']
 return m

def freeze():
 ensure();assert not (ROOT/'EXPERIMENT_MANIFEST.json').exists()
 state=read(ROOT/'task_state.json');assert all(sha(REPO/p)==h for p,h in state['protected_files'].items())
 for name in ['unit_tests.xml','regression_tests.xml','historical_hash_tests.xml']:
  ss=list(ET.parse(ROOT/name).getroot().iter('testsuite'));assert all(int(s.get('failures',0))+int(s.get('errors',0))==0 for s in ss),name
 own=[p.relative_to(REPO).as_posix() for p in ROOT.glob('*.py') if p.name not in {'score.py','report.py','audit.py','finalize.py','regression.py'}]
 prior=read(REPO/'evaluation/cfaf_contract_driven_2h_v1/experiment_manifest.json')['frozen_source_sha256'];files=sorted(set(own)|set(prior))
 write(ROOT/'EXPERIMENT_MANIFEST.json',{'dataset':'Dataset3-QASPER-v2-candidate','starting_commit':state['starting_commit'],'branch':'experiment/cfaf-qasper-pilot-v1','frozen_at_epoch':time.time(),'elapsed_at_freeze_seconds':ensure(),'frozen_source_sha256':{p:sha(REPO/p) for p in files},'selection_manifest_sha256':sha(ROOT/'DATASET3_SELECTION_MANIFEST.json'),'private_runtime_sha256':sha(ROOT/'local/runtime_inputs.jsonl'),'model':'gpt-4o-mini','temperature':0,'repetitions':1,'analysis_max_tokens':1500,'generation_max_tokens':512,'query_profile_max_tokens':500,'attempt_cap':50,'hard_time_seconds':3600,'new_api_stop_seconds':3000,'input_serialized_byte_upper_bound':120000,'retrieval_context_target_upper_bound':110000,'context_budget_change':'Predeclared before API: old GaRAGe 60000 bound raised for long research papers; entire serialized request bounded by 120000 ASCII bytes plus 1500 max output, conservatively below existing 128000 context. Paragraph selection target 110000 leaves profile overhead. No model-tokenizer approximation used.','retrieval':'Full paper if <=110000 analysis-envelope bytes; otherwise SQLite FTS5 unicode61 OR query terms BM25, ties original rowid; whole paragraphs greedily admitted then restored to original order. Title/abstract always included. No gold evidence or labels used.','systems':{'A':'Existing Standard RAG six-field self-report, only policy-projected question and common evidence','B':'Same exact A generation; existing deterministic output/policy contract validation; no extra generation','C':'Byte-identical copy of prior measured_c.py sparse source pipeline; current RDA/RECV, query-only optional fallback, unchanged original selector and response realization'},'B_extra_calls':0,'embeddings':0,'LLM_judges':0,'independent_verification_API':0,'retries':0,'citations':'No new public citation rendering or R1 experimental alias ablation enabled','measurement':'All ten selections retained; operational outputs and missing executions receive zero mode credit; model FULL is not factual correctness','qualitative_assessment':'Codex-produced non-independent manual review after execution only','implementation_change_after_outputs':'FORBIDDEN'})
 print('FROZEN',len(files),'source files; elapsed seconds',round(ensure()))

def run():
 verify_frozen();provider=StudyProvider();provider.dataset='Dataset3-QASPER-v2-candidate';outpath=ROOT/'local/results_raw.jsonl';assert not outpath.exists()
 for row in rows(ROOT/'local/runtime_inputs.jsonl'):
  try:ensure(new_api=True)
  except RuntimeError:break
  verify_frozen();provider.index=row['runtime_index'];provider.case_calls=[];provider.query_context={};provider.private_mapping=[];case=row['case'];request=impl.project_case(case);start=time.perf_counter();record={'runtime_index':provider.index,'status':'ERROR','systems':{}}
  try:
   a_call=provider.call(request,'standard_rag',STANDARD_PROMPT,request.public(),512)
   try:a=json.loads(a_call.content)
   except (TypeError,ValueError):a=None
   a_status='MODEL_SELF_REPORTED_MODE' if isinstance(a,dict) else 'OPERATIONAL_FAILURE';record['systems']['A']={'response':a,'status':a_status,'operational_failure':a_status=='OPERATIONAL_FAILURE'}
   before=time.perf_counter();b,bs=guarded_a(a,request);record['B_postprocess_ms']=(time.perf_counter()-before)*1000;record['systems']['B']={'response':b,'status':bs['status'],'operational_failure':bs['status']=='OPERATIONAL_FAILURE','validation':bs,'derived_from':'A same exact generation'}
   out=impl.run_governed(case,provider,'T3',trusted_provenance(request,False));c=out['responses']['semantic_cfaf'];status=out['response_verification']['semantic_cfaf'];record['systems']['C']={'response':c,'status':status['status'],'operational_failure':status['status']=='OPERATIONAL_FAILURE','verification_outcome':out['verification_outcome']};record.update(status='COMPLETED',C_outcome=out)
  except Exception as exc:record['error']=redact(str(exc))
  for system in ['A','B','C']:
   if system not in record['systems']:record['systems'][system]={'response':safe_operational_response(),'status':'OPERATIONAL_FAILURE','operational_failure':True,'error':record.get('error','NOT_COMPLETED')}
  record.update(api_calls=provider.case_calls,elapsed_ms=(time.perf_counter()-start)*1000);append(outpath,record)
  print(provider.index,record['status'],{s:v['response'].get('top_level_mode') if isinstance(v['response'],dict) else None for s,v in record['systems'].items()},'operational',{s:v['operational_failure'] for s,v in record['systems'].items()},flush=True)
  if record.get('error') and any(x in record['error'] for x in ['HTTP 401','HTTP 403','HTTP 429','network error','CAP_EXHAUSTED']):break
 verify_frozen()
if __name__=='__main__':{'freeze':freeze,'run':run}[sys.argv[1]]()
