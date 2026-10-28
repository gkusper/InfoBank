"""Authorized exposed-input preparation and frozen-upstream deterministic ablation."""
import copy,hashlib,json
from .artifacts import *
from .deadline import ensure
from . import integration as impl
from .rec_v2 import assess
from evaluation.cfaf_request_evidence_verification_v1.prepare import selector
from evaluation.cfaf_request_evidence_verification_v1.runner import request_for
from evaluation.cfaf_request_evidence_verification_v1.source_capability_rules import trusted_provenance
from evaluation.refusalbench_noncontradiction_v1.public_adapter import public_case

def prepare():
 ensure('cached RDA ablation',90)
 if (ROOT/'cached_ablation.jsonl').exists():raise RuntimeError('Preparation already exists')
 previous=REPO/'evaluation/cfaf_request_evidence_verification_v1';prior=rows(previous/'cached_ablation_final.jsonl');ledger_path=REPO/'evaluation/refusalbench_iterative_dev_v1/exposure_ledger.json';ledger=read(ledger_path);known={r['id'] for r in ledger['entries']};cached=[];focus=[]
 for old in prior:
  directory=REPO/'evaluation/refusalbench_iterative_dev_v1'/old['origin'];i=old['origin_index'];rawcase=rows(directory/'selected_cases.jsonl')[i];out=rows(directory/'worker_results.jsonl')[i]['outcome'];assert rawcase['id'] in known
  runtime=public_case({'perturbed_query':rawcase['perturbed_query'],'perturbed_context':rawcase['perturbed_context']},i);request=request_for(runtime,out);data=out['semantic_assessment'];frozen=canonical(data);a,_,audit=impl.parse_analysis(json.dumps(data),request);assert a.valid
  results={c:assess(request,a,data,c,trusted_provenance(request,False)) for c in ['A0','B1','B2','B3']};predictions={c:selector(v,request,data) for c,v in results.items()};assert predictions['A0']==old['predictions']['A0'] and predictions['B1']==old['predictions']['B'];assert canonical(data)==frozen
  record={'index':len(cached),'origin':old['origin'],'origin_index':i,'expected_mode':old['expected_mode'],'expected_label':old['expected_label'],'predictions':predictions,'results':results,'frozen_assessment_sha256':hashlib.sha256(frozen.encode()).hexdigest(),'raw_source':str((directory/'worker_results.jsonl').relative_to(REPO)),'api_calls':0};append(ROOT/'cached_ablation.jsonl',record);cached.append(record)
  if old['origin']=='round_03' and i==11:
   alignment=results['B3']['alignment']['requirements'];check={'diagnostic':'Previously exposed compound identity/count regression','requirement_count':len(alignment),'fragment_types_compatible':[r['type_compatible'] for r in alignment],'fragments':[r['candidate_fragment'] for r in alignment],'A0':predictions['A0'],'B1':predictions['B1'],'B3':predictions['B3']};assert len(alignment)==2 and all(r['type_compatible'] is True for r in alignment) and predictions['B3']=='FULL';focus.append(check)
  if old['origin']=='paired_regression' and i==5:
   check={'diagnostic':'Previously exposed historical-priority uncertainty','A0':predictions['A0'],'B1':predictions['B1'],'B3':predictions['B3'],'soft_qualifier_warning':any(w['code']=='SOFT_QUALIFIER_UNVERIFIED' for w in results['B3']['soft_warnings'])};assert check['soft_qualifier_warning'];focus.append(check)
 # Retain all ten InfoBank cases and a fixed balanced exposed RefusalBench subset.
 runtime_old=rows(previous/'pilot_runtime.jsonl');gold_old={g['runtime_index']:g for g in rows(previous/'pilot_scorer_only.jsonl')};selected_old=list(range(10))+[10+i for i in [0,1,3,4,5,6,8,9,10,11,12,15,16]]
 runtime=[];gold=[]
 for oldindex in selected_old:
  r=copy.deepcopy(runtime_old[oldindex]);g=copy.deepcopy(gold_old[oldindex]);i=len(runtime);r['runtime_index']=i;r['case']['case_id']=f'runtime-{i:04d}';g['runtime_index']=i;runtime.append(r);gold.append(g)
 directory=REPO/'evaluation/refusalbench_iterative_dev_v1/paired_regression';c=rows(directory/'selected_cases.jsonl')[5];assert c['id'] in known;i=len(runtime);case=public_case({'perturbed_query':c['perturbed_query'],'perturbed_context':c['perturbed_context']},5);case['case_id']=f'runtime-{i:04d}';runtime.append({'runtime_index':i,'trusted_fixture_ingestion':False,'case':case});gold.append({'runtime_index':i,'dataset':'RefusalBench-NQ','original_id':c['id'],'expected_mode':'CFAF','expected_label':c['expected_rag_behavior'],'matched_pair':None,'family':'RefusalBench'})
 assert len(runtime)==24
 for r in runtime:append(ROOT/'pilot_runtime.jsonl',r)
 for g in gold:append(ROOT/'pilot_scorer_only.jsonl',g)
 write(ROOT/'preflight_structural_regressions.json',{'status':'PASS','focus_diagnostics':focus,'frozen_semantic_fields_unchanged':True,'model_calls':0,'no_case_specific_runtime_rule':True})
 write(ROOT/'selection_manifest.json',{'case_count':24,'infobank':10,'refusalbench':14,'expected_full':sum(g['expected_mode']=='FULL' for g in gold),'expected_cfaf':sum(g['expected_mode']=='CFAF' for g in gold),'selection_policy':'All ten prior InfoBank cases; predeclared round_03 indices 0,1,3,4,5,6,8,9,10,11,12,15,16; paired_regression index5 for historical priority. Selection is evaluator-only, not runtime rules.','runtime_sha256':sha(ROOT/'pilot_runtime.jsonl'),'scorer_sha256':sha(ROOT/'pilot_scorer_only.jsonl'),'exposure_ledger_sha256':sha(ledger_path),'new_exposures':0,'eligible_exposed':130,'eligible_unseen':1104,'reserved_groups':30,'untouched_groups':18,'students_accessed':False,'source_registry_sha256':sha(REPO/'evaluation/cfaf_request_evidence_verification_v1/source_capability_rules.py'),'gold_annotations_unchanged':True})
 for config in ['A0','B1','B2','B3']:print(config,sum(r['predictions'][config]==r['expected_mode'] for r in cached),'/',len(cached),flush=True)
 print('Pilot inputs frozen:24; no structural blocker; no new exposure',flush=True)
if __name__=='__main__':prepare()
