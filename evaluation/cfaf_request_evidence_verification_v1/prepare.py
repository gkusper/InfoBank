"""Preparations use exclusively committed, already-exposed material. Zero network."""
import copy,hashlib,json
from .artifacts import *
from .deadline import ensure
from . import integration as impl
from .decision import assess,reason_details
from .source_capability_rules import trusted_provenance
from evaluation.infobank_semantic_regression_v1.policy_projection import ORACLE_KEYS
from evaluation.refusalbench_noncontradiction_v1.public_adapter import public_case
from evaluation.refusalbench_iterative_dev_v1.versions.v02.query_profile import parse_profile
from evaluation.wolala2026.labels import PipelineState,ClaimAssessment
from evaluation.wolala2026.pipeline import TopLevelModeSelectionStage,RunContext

def selector(result,request,data):
 full=result['validated_request_fulfilment'];reason,code,realization,text=reason_details(result,request,data)
 st=PipelineState(case_id='local',query_id='query',query=request.query)
 st.claim_assessments=[ClaimAssessment('claim-1','SUPPORTED' if full else 'INSUFFICIENT',[],list(data.get('contradicting_spans',[])),full,'REQUESTED_OUTPUT' if full else 'NONE',data.get('available_granularity','unknown'),data.get('requested_granularity','unknown'),full,data.get('answer_candidate') if full else None,None if full else reason,None if full else code,None if full else realization)]
 return TopLevelModeSelectionStage().run(st,RunContext(case={'query':request.query},trace_id='internal')).mode_decision.mode.value

def sanitize(case,index):
 source_fields=['source_type','title','retrieval_aliases','content','access_mode','aggregate_view','allowed_metadata_fields','retrieved','existence_visibility','purpose_compatibility','security_status']
 sources=[]
 for n,s in enumerate(case['sources']):
  out={k:copy.deepcopy(s[k]) for k in source_fields if k in s};out['source_id']=f'local-ingested-{n:04d}'
  out['metadata']={k:v for k,v in s.get('metadata',{}).items() if k in s.get('allowed_metadata_fields',[]) and k not in ORACLE_KEYS}
  sources.append(out)
 return {'case_id':f'runtime-{index:04d}','pair_id':'unpaired','family':'local','variant':'none','query':case['query'],'sources':sources}

def prepare():
 ensure('API-free preparation',60)
 if (ROOT/'pilot_runtime.jsonl').exists():raise RuntimeError('Preparation artifacts already frozen')
 ledger_path=REPO/'evaluation/refusalbench_iterative_dev_v1/exposure_ledger.json';ledger=read(ledger_path);known={r['id'] for r in ledger['entries']}
 phase=[];rb_selected=[];rb_gold=[];history=REPO/'evaluation/refusalbench_iterative_dev_v1'
 for name in ['round_03','paired_regression']:
  cases=rows(history/name/'selected_cases.jsonl');workers=rows(history/name/'worker_results.jsonl')
  assert len(cases)==len(workers)==20
  for i,(case,w) in enumerate(zip(cases,workers)):
   assert case['id'] in known;out=w['outcome'];runtime=public_case({'perturbed_query':case['perturbed_query'],'perturbed_context':case['perturbed_context']},i)
   profile=parse_profile(runtime['query'],out['query_profile_fallback']['raw']) if out.get('query_profile_fallback') else None
   req=impl.project_case(runtime,profile);assert req.public()==out['permitted_request']
   a,data,audit=impl.parse_analysis(json.dumps(out['semantic_assessment']),req);assert a.valid
   results={};predictions={}
   for config in ['A0','A1','A2','B']:
    results[config]=assess(req,a,data,config,trusted_provenance(req,False));predictions[config]=selector(results[config],req,data)
   assert predictions['A0']==out['selected_mode']
   truth='FULL' if case['expected_rag_behavior']=='ANSWER_CORRECTLY' else 'CFAF'
   record={'phase':'cached','index':len(phase),'origin':name,'origin_index':i,'expected_mode':truth,'expected_label':case['expected_rag_behavior'],'predictions':predictions,'results':results,'semantic_assessment_sha256':hashlib.sha256(canonical(data).encode()).hexdigest(),'raw_assessment_source':str((history/name/'worker_results.jsonl').relative_to(REPO)),'no_api_calls':True}
   phase.append(record);append(ROOT/'cached_ablation.jsonl',record)
   if name=='round_03':rb_selected.append(runtime);rb_gold.append({'dataset':'RefusalBench-NQ','original_id':case['id'],'expected_mode':truth,'expected_label':case['expected_rag_behavior'],'matched_pair':None,'family':'RefusalBench'})
 cases=rows(REPO/'evaluation/wolala2026/data/heldout_pilot_v3/cases.jsonl');gold={g['case_id']:g for g in rows(REPO/'evaluation/wolala2026/data/heldout_pilot_v3/gold.jsonl')}
 chosen=[c for c in cases if c['pair_id'] in {f'H3PAIR_P{f}_01' for f in range(1,6)}];assert len(chosen)==10
 runtime=[];scorer=[];origins=[]
 for c in chosen:
  idx=len(runtime);clean=sanitize(c,idx);g=gold[c['case_id']];runtime.append({'runtime_index':idx,'trusted_fixture_ingestion':True,'case':clean});scorer.append({'runtime_index':idx,'dataset':'InfoBank-original-40','original_id':c['case_id'],'expected_mode':g['expected_top_level_mode'],'expected_label':g['expected_top_level_mode'],'expected_public_reason_class':g['expected_public_reason_class'],'matched_pair':c['pair_id'],'family':c['family']});origins.append(c['case_id'])
 for c,g in zip(rb_selected,rb_gold):
  idx=len(runtime);c['case_id']=f'runtime-{idx:04d}';runtime.append({'runtime_index':idx,'trusted_fixture_ingestion':False,'case':c});scorer.append({'runtime_index':idx,**g});origins.append(g['original_id'])
 for r in runtime:append(ROOT/'pilot_runtime.jsonl',r)
 for g in scorer:append(ROOT/'pilot_scorer_only.jsonl',g)
 write(ROOT/'selection_manifest.json',{'selection':'First existing InfoBank pair in each of P1-P5 plus all twenty committed iterative round_03 cases; predeclared before any new API execution','case_count':30,'infobank':10,'refusalbench':20,'full':sum(g['expected_mode']=='FULL' for g in scorer),'cfaf':sum(g['expected_mode']=='CFAF' for g in scorer),'selected_original_ids_scorer_only':origins,'runtime_sha256':sha(ROOT/'pilot_runtime.jsonl'),'scorer_sha256':sha(ROOT/'pilot_scorer_only.jsonl'),'cached_observations':40,'newly_exposed_records':0,'exposure_ledger_sha256':sha(ledger_path),'cumulative_exposed_eligible_records':130,'remaining_unseen_eligible_records':1104,'reserved_groups':30,'additional_untouched_groups':18,'maximum_exposed_eligible_records':617,'no_official_source_or_holdout_file_opened':True,'no_student_cases_opened':True})
 print('Prepared: cached40, pilot30 (InfoBank10 + RefusalBench20), zero new exposures')
if __name__=='__main__':prepare()
