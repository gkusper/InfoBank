"""Frozen paired study; no scorer/gold import in the inference path."""
import json,time,sys,hashlib,xml.etree.ElementTree as ET
from .artifacts import *
from .deadline import ensure,elapsed
from . import measured_c as impl
from .provider import StudyProvider
from .systems import STANDARD_PROMPT,guarded_a
from .contracts import RequestContract,PermittedEvidenceContract,FulfilmentDecision,PublicResponseContract
from evaluation.cfaf_sparse_source_repair_v1.operational_failure_codes import safe_operational_response
from evaluation.cfaf_request_evidence_verification_v1.source_capability_rules import trusted_provenance

def verify_frozen():
 m=read(ROOT/'experiment_manifest.json')
 for path,h in m['frozen_source_sha256'].items():
  if sha(REPO/path)!=h:raise RuntimeError('MEASURED_SOURCE_CHANGED:'+path)
 assert sha(ROOT/'selection_plan.json')==m['selection_plan_sha256'];assert sha(ROOT/'PREREGISTRATION.md')==m['preregistration_sha256']
 return m

def freeze():
 ensure('code/protocol freeze',30,large_work=True)
 if (ROOT/'experiment_manifest.json').exists():raise RuntimeError('Already frozen')
 state=read(ROOT/'task_state.json');assert all(sha(REPO/p)==h for p,h in state['protected_files'].items());assert read(ROOT/'selection_plan.json')['dataset3']['fresh_text_opened'] is False
 for name in ['unit_tests.xml','regression_tests.xml','historical_hash_tests.xml']:
  suites=list(ET.parse(ROOT/name).getroot().iter('testsuite'));assert all(int(s.get('failures',0))+int(s.get('errors',0))==0 for s in suites),name
 own=[p.relative_to(REPO).as_posix() for p in ROOT.glob('*.py') if p.name not in {'audit.py','report.py','finalize.py','regression.py','architecture_audit.py'}];prior=read(REPO/'evaluation/cfaf_sparse_source_repair_v1/experiment_manifest.json')['frozen_source_sha256'];files=sorted(set(own)|set(prior)|{'evaluation/cfaf_sparse_source_repair_v1/integration.py'})
 write(ROOT/'experiment_manifest.json',{'frozen_at_epoch':time.time(),'elapsed_at_freeze_seconds':elapsed(),'starting_commit':state['baseline_commit'],'branch':'experiment/cfaf-contract-driven-v1','freeze_tag':read(ROOT/'git_freeze_manifest.json')['annotated_tag'],'frozen_source_sha256':{p:sha(REPO/p) for p in files},'selection_plan_sha256':sha(ROOT/'selection_plan.json'),'preregistration_sha256':sha(ROOT/'PREREGISTRATION.md'),'model':'gpt-4o-mini','temperature':0,'repetitions':1,'analysis_max_tokens':1500,'generation_max_tokens':512,'profile_max_tokens':500,'attempt_cap':480,'hard_time_seconds':7200,'new_API_stop_seconds':6300,'systems':{'A':'Standard selective RAG, policy-safe shared evidence and query profile, self-reported common six-field mode; no semantic assessment or application fulfilment selector','B':'Same A generation deterministically postprocessed for existing output/policy contract and safe operational fallback; no second model call and no CFAF fulfilment gate','C':'Frozen sparse-source semantic analysis + existing request-relative gate + exact contract realization; only unused older shared-control generation removed'},'shared_components':['Authorized evidence snapshots','governance-before-model projection','initial deterministic query profile and legitimate opaque view bindings','question-date context','model ID/temperature/generation budget'],'C_additional_components':['Semantic model assessment','RDA/RECV and original selector','Response contract realization','Operational assessment/reference failure semantics'],'compact_architecture':'Four dataclass boundary skeletons exercised, no replacement RAG framework or eight-stage rewrite','one_call_structured_output':'FUTURE_ABLATION_NOT_EXECUTED','new_embeddings_or_judges':0,'no_reruns_or_retries':True,'gold_join':'scorer only after saved observations','dataset2':'Fallback40 exposed development due explicit heldout content prohibition','dataset3_fresh_inputs_opened_before_freeze':False,'C_analysis_and_generation_prompts_unchanged':True,'C_reference_alias_R1':'NOT_ENABLED; remains separately tested earlier experimental ablation','citation_rendering':'No unverified sidecar claim association rendered','error_policy':'Keep every planned case; ERROR/operational fallback never credited substantive correct refusal; no resampling'})
 print('CODE/PROTOCOL FROZEN',len(files),'sources; no fresh D3 text opened')

def run():
 verify_frozen();rm=read(ROOT/'runtime_manifest.json');provider=StudyProvider()
 for dataset in ['dataset1','dataset2','dataset3']:
  assert sha(ROOT/(dataset+'_runtime.jsonl'))==rm['runtime_sha256'][dataset]
  output=ROOT/(dataset+'_results_raw.jsonl')
  if output.exists():raise RuntimeError('No repeated execution of a cohort')
  for row in rows(ROOT/(dataset+'_runtime.jsonl')):
   ensure('next paired case',120,new_api=True);verify_frozen();i=row['runtime_index'];provider.dataset=dataset;provider.index=i;provider.case_calls=[];provider.query_context=row['query_context'];provider.private_mapping=row['mapping'];case=row['case'];request=impl.project_case(case);start=time.perf_counter();record={'dataset':dataset,'runtime_index':i,'status':'ERROR','systems':{}}
   try:
    RequestContract.from_request(request);PermittedEvidenceContract.from_request(request)
    if request.documents:
     a_call=provider.call(request,'standard_rag',STANDARD_PROMPT,request.public(),512)
     try:a=json.loads(a_call.content)
     except (TypeError,ValueError):a=None
     a_status='MODEL_SELF_REPORTED_MODE' if isinstance(a,dict) else 'OPERATIONAL_FAILURE'
    else:a=impl.deterministic_response();a_status='VALIDATED_RESTRICTED_NO_VIEW'
    b_start=time.perf_counter();b,b_status=guarded_a(a,request);record['B_postprocess_ms']=(time.perf_counter()-b_start)*1000;record['systems'].update(A={'response':a,'status':a_status,'operational_failure':a_status=='OPERATIONAL_FAILURE'},B={'response':b,'status':b_status['status'],'operational_failure':b_status['status']=='OPERATIONAL_FAILURE','validation':b_status,'derived_from':'A same exact generation'})
    out=impl.run_governed(case,provider,'T3',trusted_provenance(request,row['trusted_fixture_ingestion']));c=out['responses']['semantic_cfaf'];status=out['response_verification']['semantic_cfaf'];gate=out['verification_outcome'];PublicResponseContract.from_response(c);FulfilmentDecision(out['selected_mode'],gate['status'],gate.get('reason'))
    record['systems']['C']={'response':c,'status':status['status'],'operational_failure':status['status']=='OPERATIONAL_FAILURE','verification_outcome':gate};record.update(status='COMPLETED',C_outcome=out,altered_context=row.get('altered_context',False))
   except Exception as exc:
    from evaluation.refusalbench_span_fix_v1.api_budget import redact
    record['error']=redact(str(exc))
   record.update(api_calls=provider.case_calls,elapsed_ms=(time.perf_counter()-start)*1000);record['local_overhead_ms']=max(0,record['elapsed_ms']-sum(c['latency_ms'] for c in provider.case_calls));append(output,record)
   print(dataset,i+1,record['status'],{k:(v.get('response') or {}).get('top_level_mode') for k,v in record['systems'].items()},'op',{k:v['operational_failure'] for k,v in record['systems'].items()},flush=True)
   if record.get('error') and any(x in record['error'] for x in ['HTTP 401','HTTP 403','HTTP 429','network error','CAP_EXHAUSTED']):return
 verify_frozen()
if __name__=='__main__':{'freeze':freeze,'run':run}[sys.argv[1]]()
