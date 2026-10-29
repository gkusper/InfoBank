"""Materialize only preregistered rows AFTER the measured code/protocol freeze."""
import json,hashlib,datetime
from .artifacts import *
from .selection import D1,D2_LEDGER,D2_RESERVED,D3
from evaluation.cfaf_dataset3_garage_pilot_v1.adapter import runtime_projection,RUNTIME_KEYS
from evaluation.refusalbench_noncontradiction_v1.prepare_dataset import SOURCE as D2_SOURCE,eligible
from evaluation.infobank_semantic_regression_v1.policy_projection import ORACLE_KEYS

def selected_rows(path,indices):
 wanted=set(indices);found={}
 with Path(path).open('rb') as f:
  for i,line in enumerate(f):
   if i in wanted:found[i]=(json.loads(line),hashlib.sha256(line.rstrip(b'\r\n')).hexdigest())
 if set(found)!=wanted:raise ValueError('PREREGISTERED_ROW_MISSING')
 return [found[i] for i in indices]

def standard_case(query,context,index,dataset):
 return {'case_id':f'private-study-{dataset}-{index:04d}','pair_id':'unpaired','family':'study-input','variant':'neutral','query':query,'sources':[{'source_id':'private-study-source','title':'private-study-catalogue-title','source_type':'Document','content':context,'metadata':{},'retrieved':True,'access_mode':'FULL','existence_visibility':'PUBLIC','purpose_compatibility':'compatible','security_status':'clean'}]}

def materialize():
 from .runner import verify_frozen
 verify_frozen();plan=read(ROOT/'selection_plan.json')
 if (ROOT/'dataset3_runtime.jsonl').exists():raise RuntimeError('Selection already materialized; never resample')
 d1cases=rows(D1/'cases.jsonl');d1gold=rows(D1/'gold.jsonl');d1gold={g['case_id']:g for g in d1gold};assert len(d1cases)==40
 allowed={'source_id','title','source_type','retrieved','access_mode','existence_visibility','purpose_compatibility','security_status','content','aggregate_view','metadata','allowed_metadata_fields','protected_markers','policy_rule_id','retrieval_aliases'}
 for i,c in enumerate(d1cases):
  g=d1gold[c['case_id']]
  sources=[{k:({mk:mv for mk,mv in v.items() if mk not in ORACLE_KEYS} if k=='metadata' and isinstance(v,dict) else v) for k,v in s.items() if k in allowed} for s in c['sources']]
  case={'case_id':f'private-study-d1-{i:04d}','pair_id':'unpaired','family':'governed-synthetic','variant':'neutral','query':c['query'],'sources':sources}
  for key in ['protected_markers','forbidden_disclosures','protected_markers_used_only_by_validator','forbidden_disclosures_used_only_by_validator']:
   if key in c:case[key]=c[key]
  append(ROOT/'dataset1_runtime.jsonl',{'runtime_index':i,'case':case,'query_context':{},'mapping':[],'trusted_fixture_ingestion':True,'altered_context':False});append(ROOT/'dataset1_gold.jsonl',{'runtime_index':i,**g})
 d2indices=[r['dataset_index'] for r in plan['dataset2']['records']];assert sha(D2_SOURCE)==read(D2_LEDGER)['official_source_sha256'];selected=selected_rows(D2_SOURCE,d2indices);groups=set()
 for i,((r,h),meta) in enumerate(zip(selected,plan['dataset2']['records'])):
  assert r['id']==meta['id'] and str(r['source_id'])==meta['source_id'] and eligible(r);assert hashlib.sha256(r['id'].encode()).hexdigest()==meta['record_hash'];groups.add(str(r['source_id']))
  append(ROOT/'dataset2_runtime.jsonl',{'runtime_index':i,'case':standard_case(r['perturbed_query'],r['perturbed_context'],i,'d2'),'query_context':{},'mapping':[],'trusted_fixture_ingestion':False,'altered_context':False});append(ROOT/'dataset2_gold.jsonl',{'runtime_index':i,'id':r['id'],'source_group':str(r['source_id']),'expected_rag_behavior':r['expected_rag_behavior'],'expected_mode':'FULL' if r['expected_rag_behavior']=='ANSWER_CORRECTLY' else 'CFAF','original_answers':r['original_answers'],'implementation_reasoning':r['implementation_reasoning'],'raw_record_sha256':h})
 assert not groups&set(plan['dataset2']['unchanged_reserved_groups']);assert not groups&set(plan['dataset2']['unchanged_other_untouched_groups'])
 source=D3/'datasets/GaRAGe_benchmark.jsonl';assert sha(source)==plan['dataset3']['source_sha256'];fresh=selected_rows(source,plan['dataset3']['selected_indices_zero_based']);metadata=[]
 # Charge the entire selected sample before constructing any model request.
 for i,((record,h),index) in enumerate(zip(fresh,plan['dataset3']['selected_indices_zero_based'])):metadata.append({'runtime_index':i,'row_zero_based':index,'sample_id':record['sample_id'],'raw_record_sha256':h,'grounding_count':len(record['grounding'])})
 write(ROOT/'dataset3_selection_manifest.json',{'seed':20261029,'selected_after_code_freeze':True,'code_manifest_sha256':sha(ROOT/'experiment_manifest.json'),'selection_algorithm':plan['dataset3']['algorithm'],'records':metadata})
 write(ROOT/'dataset3_exposure_ledger.json',{'prior_exposed':10,'new_selected_charged':80,'cumulative_exposed':90,'remaining_unused':2276,'new_ids':[r['sample_id'] for r in metadata],'prior_exposure_manifest_sha256':sha(D3/'dataset3_exposure_ledger.json'),'charged_before_API_calls':True,'no_tuning_after_exposure':True})
 for i,(r,h) in enumerate(fresh):
  runtime=runtime_projection({k:r[k] for k in RUNTIME_KEYS});runtime['runtime_index']=i;runtime['trusted_fixture_ingestion']=False;append(ROOT/'dataset3_runtime.jsonl',runtime);append(ROOT/'dataset3_gold.jsonl',{'runtime_index':i,'sample_id':r['sample_id'],**{k:v for k,v in r.items() if k not in RUNTIME_KEYS and k!='sample_id'}})
 write(ROOT/'dataset1_selection_manifest.json',plan['dataset1']);write(ROOT/'dataset2_selection_manifest.json',{**plan['dataset2'],'distinct_selected_source_groups':len(groups),'all_40_previously_exposed':True,'legacy_record_hash_meaning':'SHA256(original ID), not full record contents; full row SHA256 is in ignored scorer artifact'})
 write(ROOT/'dataset2_exposure_ledger.json',{'new_records':0,'cumulative_eligible_exposed':130,'reused_records':40,'reserved_groups_consumed':0,'other_untouched_groups_consumed':0,'prior_ledger_sha256':sha(D2_LEDGER),'fallback_reason':plan['dataset2']['reason']})
 write(ROOT/'runtime_manifest.json',{'prepared_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'code_frozen_before_fresh_text':True,'runtime_sha256':{name:sha(ROOT/(name+'_runtime.jsonl')) for name in ['dataset1','dataset2','dataset3']},'gold_sha256':{name:sha(ROOT/(name+'_gold.jsonl')) for name in ['dataset1','dataset2','dataset3']},'counts':{'dataset1':40,'dataset2':40,'dataset3':80},'altered_context_cases':sum(r['altered_context'] for r in rows(ROOT/'dataset3_runtime.jsonl'))})
 print('MATERIALIZED exactly 40 exposed D1 + 40 exposed D2 + 80 fresh D3; no unselected record text parsed')
if __name__=='__main__':materialize()
