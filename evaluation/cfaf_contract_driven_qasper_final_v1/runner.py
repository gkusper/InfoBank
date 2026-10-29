"""One frozen A/B/C dataset replacement run; no gold/scoring feedback in inference."""
import json,time,sys,xml.etree.ElementTree as ET
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
 assert sha(ROOT/'PREREGISTRATION.md')==m['preregistration_sha256'];assert sha(ROOT/'QASPER_GOLD_MAPPING.md')==m['mapping_sha256'];return m

def freeze():
 ensure();assert not (ROOT/'EXPERIMENT_MANIFEST.json').exists();assert not (ROOT/'SAMPLE_MANIFEST.json').exists();state=read(ROOT/'task_state.json');assert all(sha(REPO/p)==h for p,h in state['protected_files'].items())
 for name in ['unit_tests.xml','regression_tests.xml','historical_hash_tests.xml']:
  ss=list(ET.parse(ROOT/name).getroot().iter('testsuite'));assert all(int(s.get('failures',0))+int(s.get('errors',0))==0 for s in ss),name
 own=[p.relative_to(REPO).as_posix() for p in ROOT.glob('*.py') if p.name not in {'score.py','report.py','audit.py','finalize.py','regression.py','paper.py'}];prior=read(REPO/'evaluation/cfaf_contract_driven_2h_v1/experiment_manifest.json')['frozen_source_sha256'];files=sorted(set(own)|set(prior));source=read(ROOT/'SOURCE_PROVENANCE.json')
 write(ROOT/'EXPERIMENT_MANIFEST.json',{'branch':'experiment/cfaf-final-qasper-replacement-v1','starting_commit':state['starting_commit'],'frozen_at_epoch':time.time(),'elapsed_at_freeze_seconds':ensure(),'frozen_source_sha256':{p:sha(REPO/p) for p in files},'preregistration_sha256':sha(ROOT/'PREREGISTRATION.md'),'mapping_sha256':sha(ROOT/'QASPER_GOLD_MAPPING.md'),'source_test_sha256':source['test_member']['sha256'],'source_archive_sha256':source['downloads']['qasper-test-and-evaluator-v0.3.tgz']['sha256'],'source_revision':source['hf_revision'],'eligibility_counts_sha256':sha(ROOT/'QASPER_ELIGIBILITY_COUNTS.json'),'historical_import_audit_sha256':sha(ROOT/'HISTORICAL_IMPORT_AUDIT.json'),'algorithms':'Exact original 160-case Standard/Guarded/sparse CFAF functions and prompts; no one-call v2 or ComponentBasaedCFAF','model':'gpt-4o-mini','temperature':0,'repetitions':1,'analysis_max_tokens':1500,'generation_max_tokens':512,'profile_max_tokens':500,'attempt_cap':260,'target_calls_for_80':240,'hard_time_seconds':7200,'new_api_stop_seconds':6300,'pilot_retrieval_input_bound':110000,'actual_API_input_bound':120000,'B_new_generation_calls':0,'C_realization':'Frozen LLM realization, not deterministic renderer','retries':0,'embeddings':0,'external_judges':0,'independent_verifiers':0,'new_test_sample_text_opened_for_tuning':False,'schema_and_source_metadata_audited_only':True,'historical_D1_D2_rerun_calls':0})
 print('FROZEN',len(files),'sources; elapsed',round(ensure()))

def run():
 verify_frozen();run=read(ROOT/'RUN_MANIFEST.json');assert sha(ROOT/'local/runtime_inputs.jsonl')==run['runtime_inputs_sha256'];assert sha(ROOT/'SAMPLE_MANIFEST.json')==run['sample_manifest_sha256'];assert sha(ROOT/'EXPERIMENT_MANIFEST.json')==run['code_manifest_sha256'];outpath=ROOT/'local/results_raw.jsonl';assert not outpath.exists();provider=StudyProvider();provider.dataset='Dataset3 – QASPER test'
 for row in rows(ROOT/'local/runtime_inputs.jsonl'):
  try:ensure(new_api=True)
  except RuntimeError:break
  verify_frozen();provider.index=row['runtime_index'];provider.case_calls=[];provider.query_context={};provider.private_mapping=[];case=row['case'];request=impl.project_case(case);start=time.perf_counter();r={'runtime_index':provider.index,'status':'ERROR','systems':{}}
  try:
   call=provider.call(request,'standard_rag',STANDARD_PROMPT,request.public(),512)
   try:a=json.loads(call.content)
   except (TypeError,ValueError):a=None
   r['systems']['A']={'response':a,'status':'MODEL_SELF_REPORTED_MODE' if isinstance(a,dict) else 'OPERATIONAL_FAILURE','operational_failure':not isinstance(a,dict)};before=time.perf_counter();b,bs=guarded_a(a,request);r['B_postprocess_ms']=(time.perf_counter()-before)*1000;r['systems']['B']={'response':b,'status':bs['status'],'operational_failure':bs['status']=='OPERATIONAL_FAILURE','validation':bs,'derived_from':'A exact same generation'}
   out=impl.run_governed(case,provider,'T3',trusted_provenance(request,False));response=out['responses']['semantic_cfaf'];status=out['response_verification']['semantic_cfaf'];r['systems']['C']={'response':response,'status':status['status'],'operational_failure':status['status']=='OPERATIONAL_FAILURE','verification_outcome':out['verification_outcome']};r.update(status='COMPLETED',C_outcome=out)
  except Exception as exc:r['error']=redact(str(exc))
  for s in ['A','B','C']:
   if s not in r['systems']:r['systems'][s]={'response':safe_operational_response(),'status':'OPERATIONAL_FAILURE','operational_failure':True,'error':r.get('error','NOT_COMPLETED')}
  r.update(api_calls=provider.case_calls,elapsed_ms=(time.perf_counter()-start)*1000);r['processing_overhead_ms']=max(0,r['elapsed_ms']-sum(c['latency_ms'] for c in provider.case_calls));append(outpath,r)
  print(provider.index+1,r['status'],{s:(v['response'] or {}).get('top_level_mode') for s,v in r['systems'].items()},'operational',{s:v['operational_failure'] for s,v in r['systems'].items()},flush=True)
  if r.get('error') and any(v in r['error'] for v in ['HTTP 401','HTTP 403','HTTP 429','network error','CAP_EXHAUSTED']):break
 verify_frozen()
if __name__=='__main__':{'freeze':freeze,'run':run}[sys.argv[1]]()
