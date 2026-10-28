"""Uniform primary scoring for every version; annotations are scorer-only."""
import argparse,collections,json,re
from pathlib import Path
from evaluation.refusalbench_semantic_dev.scoring import metrics,expected_binary,refusal_category
from evaluation.refusalbench_span_fix_v1.contracts import validate_response
from evaluation.refusalbench_span_fix_v1.api_budget import read_jsonl,write_json
from .deadline import ensure,snapshot
ROOT=Path(__file__).resolve().parent
SYSTEMS=['semantic_cfaf','shared_control']

def common_errors(raw):
 errors=validate_response(raw)
 if errors:return errors
 d=json.loads(raw)
 if d['top_level_mode']=='FULL' and d['fulfilment_status']!='FULL':errors.append('FULL_REQUIRES_FULL_STATUS')
 if d['top_level_mode']=='CFAF' and d['fulfilment_status']=='FULL':errors.append('CFAF_CANNOT_CLAIM_FULL_STATUS')
 return errors

def reason_category(text):
 if re.search(r'unsupported premise|premise.{0,35}(?:not established|not supported)',text,re.I):return 'REFUSE_FALSE_PREMISE_IN_QUERY'
 return refusal_category(text)

def score_round(out):
 ensure('round scoring/report',30);out=Path(out);cases=read_jsonl(out/'selected_cases.jsonl');manifest=json.loads((out/'selection_manifest.json').read_text());worker=read_jsonl(out/'worker_results.jsonl');by={w['runtime_index']:w for w in worker};flat=[];results=[];errors=[]
 for i,case in enumerate(cases):
  w=by.get(i);a=w.get('outcome') if w else None;truth=expected_binary(case['expected_rag_behavior']);record={**manifest['records'][i],'expected_mode':truth,'systems':{},'worker_status':w.get('execution_status') if w else 'NOT_EXECUTED','outcome':a}
  for system in SYSTEMS:
   response=(a or {}).get('responses',{}).get(system);raw=(a or {}).get('raw_generations',{}).get(system)
   call=next((c for c in (w or {}).get('calls',[]) if c['kind']==system),{})
   if raw is None:raw=call.get('raw_content') or (json.dumps(response) if response else None)
   invalid=common_errors(raw) if raw else ['MISSING_GENERATION']
   if (a or {}).get('semantic_valid') is False:invalid+=['INVALID_SEMANTIC_ANALYSIS']
   invalid+=list((a or {}).get('system_errors',{}).get(system,[]))
   prediction=response.get('top_level_mode') if response and not invalid else None
   if not response and raw and not invalid:response=json.loads(raw);prediction=response['top_level_mode']
   reason=reason_category(response['answer']) if response and prediction=='CFAF' else None
   correct=prediction==truth;sc={'expected_label':case['expected_rag_behavior'],'expected_binary':truth,'prediction':prediction,'classification_correct':correct,'refusal_category':reason,'exact_answer_substring':response['answer'].strip() in case['perturbed_context'] if response and prediction=='FULL' else None,'mode_prose_agreement':None,'independent_response_review':None}
   row={'index':i,'mode_name':system,'execution_status':'SUCCESS' if prediction else 'ERROR','scoring':sc,'raw_model_output':raw,'input_tokens':call.get('input_tokens',0),'output_tokens':call.get('output_tokens',0),'actual_generation_attempts':1 if call else 0,'end_to_end_ms':call.get('latency_ms')};flat.append(row)
   record['systems'][system]={'prediction':prediction,'raw_response':response,'raw_output':raw,'correct':correct,'validation_errors':invalid,'refusal_category':reason,'specific_reason_correct':reason==case['expected_rag_behavior'] if truth=='CFAF' else None,'original_mode_for_diagnostic':response.get('top_level_mode') if response else None}
   if not correct:errors.append({'runtime_index':i,'dataset_index':manifest['records'][i]['dataset_index'],'record_hash':manifest['records'][i]['record_hash'],'system':system,'expected':truth,'prediction':prediction,'validation_errors':invalid,'issues':(a or {}).get('fulfilment_issues',[]),'query_profile':(a or {}).get('query_profile'),'assessment':(a or {}).get('semantic_assessment')})
  results.append(record)
 systems={system:metrics([r for r in flat if r['mode_name']==system]) for system in SYSTEMS}
 for name,prediction in [('always_full','FULL'),('always_cfaf','CFAF')]:
  refs=[{'execution_status':'REFERENCE','is_zero_cost_reference':True,'scoring':{'expected_label':c['expected_rag_behavior'],'expected_binary':expected_binary(c['expected_rag_behavior']),'prediction':prediction,'classification_correct':prediction==expected_binary(c['expected_rag_behavior'])}} for c in cases];systems[name]=metrics(refs)
 events=read_jsonl(out/'api_events.jsonl') if (out/'api_events.jsonl').exists() else [];requests=read_jsonl(out/'api_requests.jsonl') if (out/'api_requests.jsonl').exists() else []
 usage={'attempts':len(requests),'successes':sum(e['status']=='SUCCESS' for e in events),'errors':sum(e['status']=='ERROR' for e in events),'by_kind':dict(collections.Counter(e['kind'] for e in events)),'input_tokens':sum((e.get('usage') or {}).get('prompt_tokens',0) for e in events),'output_tokens':sum((e.get('usage') or {}).get('completion_tokens',0) for e in events),'latency_sum_ms':sum(e.get('latency_ms',0) for e in events),'model_versions':dict(collections.Counter(e.get('model','unknown') for e in events)),'retries':0}
 (out/'results.jsonl').write_text(''.join(json.dumps(r,sort_keys=True,ensure_ascii=True)+'\n' for r in results),encoding='utf-8');write_json(out/'api_usage.json',usage);write_json(out/'error_analysis.json',errors)
 validrefs=sum((w.get('outcome') or {}).get('reference_audit',{}).get('validated_reference_count',0) for w in worker);invalidrefs=sum((w.get('outcome') or {}).get('reference_audit',{}).get('reference_valid') is False for w in worker)
 summary={'round':manifest.get('round'),'version':json.loads((out/'source_version.json').read_text())['version'],'cases':20,'recorded_cases':len(worker),'completed':len(worker)==20,'systems':systems,'specific_reason_coverage':{s:sum(r['systems'][s]['specific_reason_correct'] is True for r in results)/10 for s in SYSTEMS},'invalid_output_count':{s:sum(bool(r['systems'][s]['validation_errors']) for r in results) for s in SYSTEMS},'evidence_references_validated':validrefs,'evidence_reference_failures':invalidrefs,'query_profiles_unresolved':sum((w.get('outcome') or {}).get('query_profile',{}).get('resolution')=='UNRESOLVED' for w in worker),'api_usage':usage,'scoring':'Same frozen cross-field/strict-output rules and specific reason recognizer across all versions; invalid outputs are ERROR.','time':snapshot(),'independent_validation':False}
 write_json(out/'summary.json',summary)
 lines=['# Round error analysis','','All official labels are unchanged. Error attributions below are provisional mechanistic flags, not independent human adjudication.','']
 for e in errors:
  causes=[]
  if e['validation_errors']:causes.append('Output schema inconsistency')
  if any('SCOPE' in x for x in e['issues']):causes.append('Query profiling')
  if any('IDENTITY' in x or 'COMPLETE' in x for x in e['issues']):causes.append('Requested-identity completeness')
  if any('PRIMARY' in x for x in e['issues']):causes.append('Entity/relation interpretation')
  if not causes:causes=['Evidence sufficiency / answer generation; contextual review needed']
  lines += [f"## Case {e['runtime_index']} / {e['system']}",'',f"Dataset index {e['dataset_index']}; record hash `{e['record_hash']}`. Expected {e['expected']}; observed {e['prediction'] or 'ERROR'}.",'',f"Attribution: {', '.join(causes)}. Issues: {', '.join(e['issues']) or 'none'}. Validation: {', '.join(e['validation_errors']) or 'none'}.",'']
 (out/'error_analysis.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');print(json.dumps({'directory':out.name,'completed':summary['completed'],'metrics':{s:{k:systems[s][k] for k in ['accuracy','full_recall','cfaf_recall','balanced_accuracy']} for s in SYSTEMS},'usage':usage,'unresolved':summary['query_profiles_unresolved']}),flush=True)
 return summary
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory');args=p.parse_args();score_round(ROOT/args.directory)
