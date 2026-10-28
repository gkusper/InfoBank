"""Frozen same-assessment RDA comparisons; no evaluator data enter runtime."""
import argparse,json,time
from .artifacts import *
from .deadline import ensure,elapsed
from . import integration as impl
from .rec_v2 import assess
from .provider import BoundedProvider
from evaluation.cfaf_request_evidence_verification_v1.runner import request_for
from evaluation.cfaf_request_evidence_verification_v1.prepare import selector
from evaluation.cfaf_request_evidence_verification_v1.source_capability_rules import trusted_provenance

def verify_frozen():
 m=read(ROOT/'experiment_manifest.json')
 for p,h in m['frozen_source_sha256'].items():
  if sha(REPO/p)!=h:raise RuntimeError('Frozen RDA source changed:'+p)
 if sha(ROOT/'pilot_runtime.jsonl')!=m['runtime_sha256']:raise RuntimeError('Frozen runtime changed')
 return m

def preflight_pilot():
 oldrows=rows(REPO/'evaluation/cfaf_request_evidence_verification_v1/pilot_observations.jsonl');oldout=[r['outcomes']['A0'] for r in oldrows];oldout.append(rows(REPO/'evaluation/refusalbench_iterative_dev_v1/paired_regression/worker_results.jsonl')[5]['outcome']);checks=[]
 for row in rows(ROOT/'pilot_runtime.jsonl'):
  case=row['case'];matched=None
  for out in oldout:
   if out['permitted_request']['query']!=case['query']:continue
   try:request=request_for(case,out);matched=out;break
   except ValueError:continue
  if matched is None:raise RuntimeError('No authorized cached projection for preflight')
  if request.documents:a,data,audit=impl.parse_analysis(json.dumps(matched['semantic_assessment']),request)
  else:a=None;data={}
  result=assess(request,a,data,'B3',trusted_provenance(request,row['trusted_fixture_ingestion']));mode=selector(result,request,data);checks.append({'runtime_index':row['runtime_index'],'cached_A0':matched['selected_mode'],'RDA_B3':mode,'no_new_correct_full_loss':not(matched['selected_mode']=='FULL' and mode!='FULL'),'semantic_valid':a.valid if a else None})
 if not all(r['no_new_correct_full_loss'] for r in checks):raise RuntimeError('Structural blocker in selected pilot')
 write(ROOT/'pilot_preflight.json',{'status':'PASS','checks':checks,'api_calls':0});return checks

def freeze():
 ensure('RDA experiment freeze',60)
 if (ROOT/'experiment_manifest.json').exists():raise RuntimeError('Already frozen')
 import xml.etree.ElementTree as ET
 unit=ET.parse(ROOT/'unit_tests.xml').getroot();assert not any(int(s.get('errors',0))+int(s.get('failures',0)) for s in unit.iter('testsuite'))
 preflight_pilot()
 for old in rows(ROOT/'cached_ablation.jsonl'):
  source=REPO/old['raw_source'];out=rows(source)[old['origin_index']]['outcome'];directory=source.parent;case=rows(directory/'selected_cases.jsonl')[old['origin_index']]
  from evaluation.refusalbench_noncontradiction_v1.public_adapter import public_case
  runtime=public_case({'perturbed_query':case['perturbed_query'],'perturbed_context':case['perturbed_context']},old['origin_index']);request=request_for(runtime,out);a,data,audit=impl.parse_analysis(json.dumps(out['semantic_assessment']),request)
  results={c:assess(request,a,data,c,trusted_provenance(request,False)) for c in ['A0','B1','B2','B3']};pred={c:selector(v,request,data) for c,v in results.items()};assert pred==old['predictions'];append(ROOT/'cached_ablation_final.jsonl',{**old,'results':results,'predictions':pred})
 own=['requirement_decomposition.py','requirement_alignment.py','rec_v2.py','integration.py','provider.py','runner.py','artifacts.py','deadline.py','prepare.py'];dependencies=['evaluation/cfaf_request_evidence_verification_v1/'+n for n in ['source_capability_rules.py','request_evidence_coverage.py','decision.py']]+['evaluation/refusalbench_iterative_dev_v1/versions/v02/'+n for n in ['implementation.py','query_profile.py','metadata_binding.py','contracts.py']]+['evaluation/wolala2026/'+n for n in ['pipeline.py','labels.py','semantic_evidence.py','real_api.py']]+['evaluation/refusalbench_span_fix_v1/span_references.py','evaluation/infobank_semantic_regression_v1/policy_projection.py','evaluation/infobank_semantic_integration_v2/query_profile.py']
 files=[(ROOT/n).relative_to(REPO).as_posix() for n in own]+dependencies
 write(ROOT/'experiment_manifest.json',{'baseline_commit':read(ROOT/'task_state.json')['baseline_commit'],'branch':'experiment/cfaf-requirement-alignment-v1','model':'gpt-4o-mini','temperature':0,'repetitions':1,'generation_limit':160,'analysis_limit':1500,'query_profile_limit':500,'external_attempt_cap':120,'frozen_at_epoch':time.time(),'elapsed_at_freeze':elapsed(),'frozen_source_sha256':{p:sha(REPO/p) for p in files},'runtime_sha256':sha(ROOT/'pilot_runtime.jsonl'),'scorer_sha256':sha(ROOT/'pilot_scorer_only.jsonl'),'analysis_prompt':impl.GOVERNED_PROMPT,'cfaf_prompt':impl.CFAF_PROMPT,'control_prompt':impl.CONTROL_PROMPT,'analysis_schema':impl.ANALYSIS_SCHEMA,'generation_schema':impl.GENERATION_SCHEMA,'source_registry_unchanged':True,'optional_second_verifier':'DISABLED','B4':'NOT_EXECUTED; no soft veto justified on development results','live_generated_configurations':['A0','B1','B3','shared_control'],'deterministic_configurations':['A0','B1','B2','B3'],'semantic_assessments_shared':True,'frozen_versus_recomputed':{'frozen':'original legacy profile, complete semantic JSON, answer_candidate, source roles, supporting/counter span IDs, model properties','recomputed':'RDA output obligations/query spans, explicit dependencies/qualifiers, candidate-fragment offsets and type proposals, per-child source capability, hard/soft classification and shadow coverage'},'soft_policy':'New semantic warnings are shadow-only; original v02 sufficiency and permissions remain mandatory. B2/B3 never promote an A0 refusal. B1 preserves the prior strict enforcement comparator.','selection':read(ROOT/'selection_manifest.json'),'upstream_prompt_unchanged':True,'not_independent_validation':True})
 print('RDA frozen; cached40 and selected24 preflight PASS')

def pilot():
 verify_frozen();ensure('RDA paired live pilot',360)
 if elapsed()>=3000:raise RuntimeError('50-minute reporting priority')
 if (ROOT/'pilot_observations.jsonl').exists():raise RuntimeError('Live results already frozen')
 provider=BoundedProvider();consecutive=0
 for row in rows(ROOT/'pilot_runtime.jsonl'):
  ensure('paired case',100,new_api=True);verify_frozen();case=row['case'];i=row['runtime_index'];provider.index=i;provider.cache={};provider.case_calls=[];outcomes={};start=time.perf_counter();record={'runtime_index':i}
  try:
   request=impl.project_case(case);provenance=trusted_provenance(request,row['trusted_fixture_ingestion'])
   for config in ['A0','B1','B3']:
    provider.system=config;outcomes[config]=impl.run_governed(case,provider,config,provenance)
   a0=outcomes['A0'];assert all(o['semantic_assessment']==a0['semantic_assessment'] and o['permitted_request']==a0['permitted_request'] for o in outcomes.values())
   request=request_for(case,a0)
   if request.documents:a,data,audit=impl.parse_analysis(json.dumps(a0['semantic_assessment']),request)
   else:a=None;data={}
   variants={c:assess(request,a,data,c,provenance) for c in ['A0','B1','B2','B3']};pred={c:selector(v,request,data) for c,v in variants.items()};assert all(pred[c]==o['selected_mode'] for c,o in outcomes.items());assert pred['B2']==pred['B3']
   record.update(status='SUCCESS',outcomes=outcomes,ablations=variants,gate_predictions=pred,semantic_assessment_identical=True);consecutive=0
  except Exception as exc:
   from evaluation.refusalbench_span_fix_v1.api_budget import redact
   record.update(status='ERROR',error=redact(str(exc)),partial_outcomes=outcomes);consecutive+=1
  record.update(api_calls=provider.case_calls,elapsed_ms=(time.perf_counter()-start)*1000);append(ROOT/'pilot_observations.jsonl',record);print('RDA pilot',i+1,record['status'],record.get('gate_predictions'),flush=True)
  if consecutive>=3 or record.get('error') and any(x in record['error'] for x in ['HTTP 401','HTTP 403','HTTP 429','network error','cap exhausted']):break
 verify_frozen()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['freeze','pilot']);a=p.parse_args();{'freeze':freeze,'pilot':pilot}[a.action]()
