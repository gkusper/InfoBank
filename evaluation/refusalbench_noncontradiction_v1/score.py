"""Trusted post-generation scorer; official annotations never reach execution."""
from __future__ import annotations
import collections,hashlib,json,re
from pathlib import Path
from evaluation.refusalbench_semantic_dev.scoring import metrics,refusal_category,expected_binary
from evaluation.wolala2026.semantic_evidence import strict_output
from evaluation.refusalbench_span_fix_v1.contracts import validate_response
from evaluation.refusalbench_span_fix_v1.api_budget import read_jsonl,write_json
ROOT=Path(__file__).resolve().parent;SYSTEMS=['semantic_cfaf','shared_control']


def infer_analyzer_causes(assessment):
 if not assessment:return []
 causes=set(assessment.get('uncertainty_causes',[]));codes=[]
 if assessment.get('query_status')=='NONFACTUAL' or 'nonfactual_request' in causes:codes.append('REFUSE_NONFACTUAL_QUERY')
 if assessment.get('query_status')=='AMBIGUOUS' or 'ambiguous_reference' in causes:codes.append('REFUSE_AMBIGUOUS_QUERY')
 if assessment.get('premise_status')=='REFUTED' or 'false_premise' in causes:codes.append('REFUSE_FALSE_PREMISE_IN_QUERY')
 if not assessment.get('granularity_matches',True) or 'granularity_gap' in causes:codes.append('REFUSE_GRANULARITY_MISMATCH')
 if assessment.get('support_status') in ['MISSING','PARTIAL'] or 'evidence_missing' in causes:codes.append('REFUSE_INFO_MISSING_IN_CONTEXT')
 return codes


def score(cases,worker):
 by={w['runtime_index']:w for w in worker};flat=[];case_results=[]
 for i,case in enumerate(cases):
  expected=expected_binary(case['expected_rag_behavior']);w=by.get(i);outcome=w.get('outcome') if w else None;record={'runtime_index':i,'id':case['id'],'source_id':str(case['source_id']),'official_expected_behavior':case['expected_rag_behavior'],'expected_mode':expected,'worker_status':w['execution_status'] if w else 'NOT_EXECUTED','systems':{}}
  if outcome:record.update(query_profile=outcome['query_profile'],semantic_assessment=outcome['semantic_assessment'],fulfilment_issues=outcome['fulfilment_issues'],reference_audit=outcome['reference_audit'],analyzer_cause_categories=infer_analyzer_causes(outcome['semantic_assessment']))
  for system in SYSTEMS:
   response=outcome['responses'][system] if outcome else None;raw=outcome.get('raw_generations',{}).get(system) if outcome else None
   if response and raw is None:raw=json.dumps(response)
   parsed,error=strict_output(raw or '')
   schema_errors=validate_response(raw) if raw is not None else ['MISSING_GENERATION']
   status='SUCCESS' if w and w['execution_status']=='SUCCESS' and parsed and not schema_errors else 'ERROR'
   prediction=parsed['top_level_mode'] if status=='SUCCESS' else None
   reason=refusal_category(parsed['answer']) if parsed and parsed['top_level_mode']=='CFAF' else None
   answer=parsed['answer'] if parsed else None
   abstention=bool(re.search(r'\bI (?:cannot|can.t)\b|cannot (?:answer|determine|provide)|not enough (?:information|evidence)|insufficient (?:information|evidence)',answer,re.I)) if answer else None
   agreement=(not abstention if prediction=='FULL' else True if abstention else None) if prediction else None
   sc={'original_id':case['id'],'expected_label':case['expected_rag_behavior'],'expected_binary':expected,'prediction':prediction,'raw_declared_mode':parsed['top_level_mode'] if parsed else None,'classification_correct':prediction==expected,'parser_error':error,'schema_errors':schema_errors,'refusal_category':reason,'reason_category_correct':reason==case['expected_rag_behavior'] if reason and expected=='CFAF' else None,'exact_answer_substring':answer.strip() in case['perturbed_context'] if answer and prediction=='FULL' else None,'mode_prose_agreement':agreement,'independent_response_review':None,'support_warning':'Candidate copying, exact spans and original_answers do not establish perturbed-answer completeness.'}
   call=next((c for c in w.get('calls',[]) if c['kind']==system),{}) if w else {}
   item={'index':i,'mode_name':system,'execution_status':status,'raw_model_output':raw,'scoring':sc,'input_tokens':call.get('input_tokens',0),'output_tokens':call.get('output_tokens',0),'actual_generation_attempts':1 if call else 0,'end_to_end_ms':w.get('end_to_end_ms') if w else None};flat.append(item)
   record['systems'][system]={'prediction':prediction,'correct':prediction==expected,'response':parsed,'schema_errors':schema_errors,'refusal_category':reason,'reason_category_correct':sc['reason_category_correct'],'exact_answer_substring':sc['exact_answer_substring'],'mode_prose_agreement_lexical_only':agreement,'answer_support':None,'complete_fulfilment':None,'support_status':'REQUIRES_POSTRUN_REVIEW'}
  case_results.append(record)
 systems={s:metrics([r for r in flat if r['mode_name']==s]) for s in SYSTEMS}
 for system,pred in [('always_full','FULL'),('always_cfaf','CFAF')]:
  references=[]
  for i,case in enumerate(cases):
   truth=expected_binary(case['expected_rag_behavior']);references.append({'index':i,'mode_name':system,'is_zero_cost_reference':True,'execution_status':'REFERENCE','reference_prediction':pred,'scoring':{'expected_label':case['expected_rag_behavior'],'expected_binary':truth,'prediction':pred,'classification_correct':pred==truth}})
  systems[system]=metrics(references)
 return case_results,systems


def main():
 frozen=json.loads((ROOT/'experiment_manifest.json').read_text())
 for name,expected_hash in frozen['preparation_sha256'].items():
  if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected_hash:raise RuntimeError('Trusted scoring input changed after freeze: '+name)
 cases=read_jsonl(ROOT/'selected_cases.jsonl');worker=read_jsonl(ROOT/'worker_results.jsonl');records,systems=score(cases,worker)
 (ROOT/'results.jsonl').write_text(''.join(json.dumps(r,sort_keys=True,ensure_ascii=True,separators=(',',':'))+'\n' for r in records),encoding='utf-8')
 events=read_jsonl(ROOT/'api_events.jsonl');requests=read_jsonl(ROOT/'api_requests.jsonl');usage={'actual_attempts':len(requests),'successes':sum(e['status']=='SUCCESS' for e in events),'errors':sum(e['status']=='ERROR' for e in events),'kind_counts':dict(collections.Counter(e['kind'] for e in events)),'input_tokens':sum((e.get('usage') or {}).get('prompt_tokens',0) for e in events),'output_tokens':sum((e.get('usage') or {}).get('completion_tokens',0) for e in events),'summed_call_latency_ms':sum(e.get('latency_ms',0) for e in events),'model_versions':dict(collections.Counter(e.get('model','unknown') for e in events)),'retries':0,'embeddings':0,'shared_analysis_double_counted':False}
 write_json(ROOT/'api_usage.json',usage)
 summary={'cases':20,'expected_FULL':10,'expected_CFAF':10,'systems':systems,'api_usage':usage,'official_labels_unchanged':True,'independent_validation':False,'domain':'Non-contradiction-filtered records within previously exposed development source groups only','inference_significance':False,'refusal_reason_metric':'Same pre-existing frozen lexical category recognizer for both systems; generic/unknown explanations not credited as specific categories.','answer_correctness':'No perturbed-answer gold; support/completeness require contextual review, copying and span existence alone are insufficient.','schema_failures':{s:sum(bool(r['systems'][s]['schema_errors']) for r in records) for s in SYSTEMS},'analyzer_failures':sum(w['execution_status']!='SUCCESS' for w in worker),'unexecuted_cases':20-len(worker)}
 write_json(ROOT/'summary.json',summary);print(json.dumps({s:{k:m[k] for k in ['accuracy','balanced_accuracy','full_recall','cfaf_recall','specific_refusal_reason_correct','specific_refusal_reason_predictions']} for s,m in systems.items()},indent=2));print(json.dumps(usage))
if __name__=='__main__':main()
