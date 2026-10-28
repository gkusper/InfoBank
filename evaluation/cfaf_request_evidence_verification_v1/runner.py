"""Freeze, deterministic replay, and paired live execution. Scorer is separate."""
import argparse,json,time
from .artifacts import *
from .deadline import ensure,elapsed
from . import integration as impl
from .decision import assess
from .prepare import selector
from .source_capability_rules import trusted_provenance
from .provider import BoundedProvider
from .focused_verification import triggers,payload as focused_payload,parse as parse_focused,PROMPT,TRIGGER_CODES
from evaluation.refusalbench_iterative_dev_v1.versions.v02.query_profile import parse_profile

def request_for(case,outcome):
 fallback=outcome.get('query_profile_fallback');att=parse_profile(case['query'],fallback['raw']) if fallback else None
 req=impl.project_case(case,att)
 if req.public()!=outcome['permitted_request']:raise ValueError('FROZEN_PROJECTION_MISMATCH')
 return req

def verify_frozen():
 m=read(ROOT/'experiment_manifest.json')
 for name,h in m['frozen_source_sha256'].items():
  if sha(REPO/name)!=h:raise RuntimeError('Frozen source changed: '+name)
 if sha(ROOT/'pilot_runtime.jsonl')!=m['runtime_sha256']:raise RuntimeError('Runtime changed')
 return m

def freeze():
 ensure('experiment freeze',15)
 if (ROOT/'experiment_manifest.json').exists():raise RuntimeError('Already frozen')
 # Recompute final Phase-1 diagnostics after test-driven trace corrections.
 for record in rows(ROOT/'cached_ablation.jsonl'):
  history=REPO/'evaluation/refusalbench_iterative_dev_v1'/record['origin'];w=rows(history/'worker_results.jsonl')[record['origin_index']];original=rows(history/'selected_cases.jsonl')[record['origin_index']]
  from evaluation.refusalbench_noncontradiction_v1.public_adapter import public_case
  case=public_case({'perturbed_query':original['perturbed_query'],'perturbed_context':original['perturbed_context']},record['origin_index']);req=request_for(case,w['outcome']);a,data,audit=impl.parse_analysis(json.dumps(w['outcome']['semantic_assessment']),req)
  record['results']={c:assess(req,a,data,c,trusted_provenance(req,False)) for c in ['A0','A1','A2','B']};record['predictions']={c:selector(v,req,data) for c,v in record['results'].items()};append(ROOT/'cached_ablation_final.jsonl',record)
 import xml.etree.ElementTree as ET
 unit=ET.parse(ROOT/'unit_tests.xml').getroot()
 if any(int(s.get('failures',0))+int(s.get('errors',0)) for s in unit.iter('testsuite')):raise RuntimeError('Unit tests not passed')
 own=['integration.py','decision.py','request_evidence_coverage.py','source_capability_rules.py','focused_verification.py','provider.py','runner.py','deadline.py','artifacts.py','prepare.py']
 dependent=['evaluation/wolala2026/'+n for n in ['pipeline.py','labels.py','semantic_evidence.py','real_api.py']]+['evaluation/refusalbench_span_fix_v1/'+n for n in ['span_references.py','contracts.py','api_budget.py']]+['evaluation/refusalbench_iterative_dev_v1/versions/v02/'+n for n in ['implementation.py','query_profile.py','metadata_binding.py','contracts.py']]+['evaluation/infobank_semantic_regression_v1/'+n for n in ['policy_projection.py','integration_v2.py']]+['evaluation/infobank_semantic_integration_v2/query_profile.py']
 paths=[(ROOT/n).relative_to(REPO).as_posix() for n in own]+dependent
 selection=read(ROOT/'selection_manifest.json');write(ROOT/'experiment_manifest.json',{'baseline_commit':read(ROOT/'task_state.json')['baseline_commit'],'branch':'experiment/cfaf-request-evidence-verification-v1','model':'gpt-4o-mini','temperature':0,'repetitions':1,'analysis_max_tokens':1500,'generation_max_tokens':160,'query_profile_max_tokens':500,'focused_verification_max_tokens':500,'external_attempt_cap':170,'frozen_at_epoch':time.time(),'elapsed_seconds_at_freeze':elapsed(),'frozen_source_sha256':{p:sha(REPO/p) for p in paths},'runtime_sha256':sha(ROOT/'pilot_runtime.jsonl'),'scorer_sha256':sha(ROOT/'pilot_scorer_only.jsonl'),'selection':selection,'phase1_api_calls':0,'phase2_systems':['A0','B','shared_control'],'all_ablations':['A0','A1','A2','B'],'upstream_assessments_shared':True,'unchanged_upstream_prompt':impl.GOVERNED_PROMPT,'unchanged_control_prompt':impl.CONTROL_PROMPT,'unchanged_cfaf_prompt':impl.CFAF_PROMPT,'analysis_schema':impl.ANALYSIS_SCHEMA,'generation_schema':impl.GENERATION_SCHEMA,'optional_trigger_codes':sorted(TRIGGER_CODES),'optional_trigger_policy':'Only B UNKNOWN with A0 fully supportable, no source veto, no failed deterministic check, and exclusively the declared unresolved semantic codes; one focused call per triggered requirement, no retries or trigger changes','source_provenance':'Original synthetic source_type supplied by trusted fixture ingestion; no claim of production connector validation. RefusalBench document provenance unattested. Restricted view provenance follows policy projection.','not_independent_validation':True,'new_refusalbench_records':0})
 print('Frozen sources and final cached ablation; Phase 1 passed')

def pilot():
 manifest=verify_frozen();ensure('paired development pilot',360)
 if elapsed()>=3000:raise RuntimeError('50-minute reporting priority prevents new pilot')
 if (ROOT/'pilot_observations.jsonl').exists():raise RuntimeError('Observations already frozen')
 provider=BoundedProvider();runtime=rows(ROOT/'pilot_runtime.jsonl');consecutive=0
 for row in runtime:
  ensure('paired case',90,new_api=True);verify_frozen();i=row['runtime_index'];case=row['case'];provider.index=i;provider.system='A0';provider.cache={};provider.case_calls=[];start=time.perf_counter()
  record={'runtime_index':i}
  try:
   req=impl.project_case(case);provenance=trusted_provenance(req,row['trusted_fixture_ingestion'])
   a0=impl.run_governed(case,provider,'A0',provenance);provider.system='B';b=impl.run_governed(case,provider,'B',provenance)
   if a0['semantic_assessment']!=b['semantic_assessment'] or a0['permitted_request']!=b['permitted_request']:raise ValueError('SHARED_ASSESSMENT_OR_INPUT_DRIFT')
   req=request_for(case,a0)
   if req.documents:a,data,audit=impl.parse_analysis(json.dumps(a0['semantic_assessment']),req)
   else:a=None;data={}
   variants={c:assess(req,a,data,c,provenance) for c in ['A0','A1','A2','B']};pred={c:selector(v,req,data) for c,v in variants.items()};assert pred['A0']==a0['selected_mode'] and pred['B']==b['selected_mode']
   record.update(status='SUCCESS',outcomes={'A0':a0,'B':b},ablations=variants,gate_predictions=pred,semantic_assessment_identical=True,optional_trigger_requirements=[x['requirement_id'] for x in triggers(b)]);consecutive=0
  except Exception as exc:
   from evaluation.refusalbench_span_fix_v1.api_budget import redact
   record.update(status='ERROR',error=redact(str(exc)));consecutive+=1
  record.update(api_calls=provider.case_calls,elapsed_ms=(time.perf_counter()-start)*1000);append(ROOT/'pilot_observations.jsonl',record)
  print('pilot',i+1,record['status'],record.get('gate_predictions'),flush=True)
  if consecutive>=3 or record.get('error') and any(x in record['error'] for x in ['HTTP 401','HTTP 403','HTTP 429','network error','cap exhausted']):break
 verify_frozen()

def optional():
 verify_frozen();ensure('optional selective pilot',120)
 if elapsed()>=3000:raise RuntimeError('50-minute reporting priority omits optional phase')
 if (ROOT/'optional_observations.jsonl').exists():raise RuntimeError('Optional observations already exist')
 provider=BoundedProvider();runtime={r['runtime_index']:r for r in rows(ROOT/'pilot_runtime.jsonl')}
 for r in rows(ROOT/'pilot_observations.jsonl'):
  if r['status']!='SUCCESS':continue
  i=r['runtime_index'];entry=runtime[i];case=entry['case'];b=r['outcomes']['B'];triggered=triggers(b);record={'runtime_index':i,'triggered_requirements':[x['requirement_id'] for x in triggered],'status':'REUSED_B','outcome':b,'focused_verdicts':[],'additional_calls':[]}
  if triggered:
   ensure('focused verification',100,new_api=True);req=request_for(case,b);data=b['semantic_assessment'];provider.index=i;provider.system='C';provider.cache={};provider.case_calls=[];attestations=[]
   # Replay all upstream calls and independent control without network.
   for call in r['api_calls']:
    if call['kind'] in {'semantic_analysis','query_profile','shared_control'}:
     request_record=next(x for x in rows(ROOT/'api_requests.jsonl') if x['runtime_index']==i and x['kind']==call['kind']);msgs=request_record['payload']['messages'];provider.cache[call['kind']]={'prompt':msgs[0]['content'],'payload':json.loads(msgs[1]['content']),'result':{k:call[k] for k in ['content','model','input_tokens','output_tokens','latency_ms','response_id']}}
   try:
    for requirement in triggered:
     call=provider.call(req,'focused_verification',PROMPT,focused_payload(req,data,requirement),500);att=parse_focused(req,data,call.content);attestations.append(att);record['focused_verdicts'].append(json.loads(call.content))
    a,_,_=impl.parse_analysis(json.dumps(data),req);provenance=trusted_provenance(req,entry['trusted_fixture_ingestion']);verified=assess(req,a,data,'C',provenance,attestations);prediction=selector(verified,req,data)
    if prediction!=b['selected_mode']:record['outcome']=impl.run_governed(case,provider,'C',provenance,attestations)
    else:record['outcome']={**b,'configuration':'C','verification':verified}
    record['status']='SUCCESS';record['additional_calls']=provider.case_calls
   except Exception as exc:
    from evaluation.refusalbench_span_fix_v1.api_budget import redact
    record.update(status='ERROR',error=redact(str(exc)),additional_calls=provider.case_calls)
  append(ROOT/'optional_observations.jsonl',record);print('optional',i+1,record['status'],record['triggered_requirements'],flush=True)
 verify_frozen()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['freeze','pilot','optional']);a=p.parse_args();{'freeze':freeze,'pilot':pilot,'optional':optional}[a.action]()
