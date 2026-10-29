"""Scorer-only joins and preregistered metrics. No inference or gold-driven tuning."""
import json,collections,csv,statistics,re,random
from .artifacts import *
from .statistics import bootstrap_groups,paired_counts
from . import measured_c as impl
from .selection import D1
from evaluation.cfaf_sparse_source_repair_v1.operational_failure_codes import validate_response
from evaluation.cfaf_sparse_source_repair_v1.public_grounding_trace import build_public_grounding_trace
from evaluation.cfaf_sparse_source_repair_v1.source_inventory import build_inventory
from evaluation.cfaf_request_evidence_verification_v1.runner import request_for
from evaluation.cfaf_dataset3_garage_pilot_v1.score import selection_metric,aggregate,answer_citations
from evaluation.refusalbench_span_fix_v1.span_references import build_catalogue,resolve_span

def code_only(errors):return sorted(set(str(x).split(':',1)[0] for x in errors))
def write_rows(path,rs):Path(path).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rs),encoding='utf-8')
def empty_response_status():return {'response':None,'status':'NOT_EXECUTED','operational_failure':True}
def compute_mode_metrics(records,golds,system):
 counts=collections.Counter();observed=collections.Counter();failures=collections.Counter();fulln=cfn=correct=observedcorrect=0;reason_correct=reason_available=status_correct=marker_match=marker_available=0;fp=fn=op_answerable=0
 for r,g in zip(records,golds):
  entry=r['systems'][system];response=r.get('_responses',{}).get(system);actual=response.get('top_level_mode') if isinstance(response,dict) else 'ERROR';expected=g['expected_mode'];op=entry['operational_failure'];policy=entry.get('policy_violation',False);correct_here=actual==expected and not op and not policy;correct+=correct_here;observedcorrect+=actual==expected;observed[expected+'_as_'+str(actual)]+=1;counts[expected+'_as_'+('OPERATIONAL' if op else 'POLICY_VIOLATION' if policy else str(actual))]+=1;fulln+=expected=='FULL';cfn+=expected=='CFAF';fp+=expected=='CFAF' and actual=='FULL';fn+=expected=='FULL' and actual=='CFAF' and not op;op_answerable+=expected=='FULL' and op
  if op:failures[entry['status']]+=1
  if g.get('reason_available',False):reason_available+=1;reason_correct+=isinstance(response,dict) and not op and not policy and response.get('public_reason_class')==g.get('expected_reason')
  if isinstance(response,dict) and 'expected_fulfilment_status' in g:status_correct+=not op and response.get('fulfilment_status')==g['expected_fulfilment_status']
  if g.get('expected_mode')=='FULL' and g.get('canonical_answer_markers'):
   marker_available+=1;marker_match+=isinstance(response,dict) and not op and not policy and all(str(m).casefold() in response.get('answer','').casefold() for m in g['canonical_answer_markers'])
 full_correct=sum(r['systems'][system]['mode_correct_nonoperational'] for r,g in zip(records,golds) if g['expected_mode']=='FULL');cf_correct=correct-full_correct
 return {'N_planned':len(records),'correct_mode_nonoperational':correct,'mode_accuracy_nonoperational':correct/len(records) if records else None,'observed_output_mode_agreement':observedcorrect/len(records) if records else None,'observed_mode_confusion':dict(observed),'nonoperational_confusion':dict(counts),'FULL_gold':fulln,'CFAF_gold':cfn,'FULL_recall':full_correct/fulln if fulln else None,'CFAF_recall':cf_correct/cfn if cfn else None,'balanced_accuracy':(full_correct/fulln+cf_correct/cfn)/2 if fulln and cfn else None,'failure_to_restrict_observed_FULL':fp,'unnecessary_nonoperational_CFAF':fn,'operational_withholding_on_gold_FULL':op_answerable,'operational_failures':dict(failures),'operational_failure_count':sum(failures.values()),'policy_violation_count':sum(r['systems'][system].get('policy_violation',False) for r in records),'reason_class_agreement':reason_correct/reason_available if reason_available else None,'reason_class_denominator':reason_available,'fulfilment_status_agreement':status_correct/len(records) if any('expected_fulfilment_status' in g for g in golds) else None,'gold_marker_presence_FULL_cases':marker_match/marker_available if marker_available else None,'gold_marker_denominator':marker_available,'answer_factual_accuracy':'NOT independently measured; mode and marker agreement do not prove entailment'}

def score():
 plan=read(ROOT/'selection_plan.json');summary={};allpaired={};grounding={};operational={};rawall={};safeall={};goldall={};flatcsv=[];review=[];reviewkey=[]
 for dataset,N in plan['planned_case_counts'].items():
  path=ROOT/(dataset+'_results_raw.jsonl');raw={r['runtime_index']:r for r in rows(path)} if path.exists() else {};rawall[dataset]=raw;runtime=rows(ROOT/(dataset+'_runtime.jsonl'));gold=rows(ROOT/(dataset+'_gold.jsonl'));goldall[dataset]=gold;records=[];grouped=[];d3layers={'raw_C':[],'validated_C':[],'A_actual_citations':[],'B_actual_citations':[],'C_actual_citations':[]};d3cases=[]
  for i,(inp,g) in enumerate(zip(runtime,gold)):
   rr=raw.get(i,{'dataset':dataset,'runtime_index':i,'status':'NOT_EXECUTED','systems':{}});source_request=impl.project_case(inp['case']);out=rr.get('C_outcome',{});sid=g.get('sample_id',g.get('id',g.get('case_id')));safe={'dataset':dataset,'runtime_index':i,'sample_id':sid,'execution_status':rr['status'],'systems':{},'altered_context':inp.get('altered_context',False),'_responses':{k:rr.get('systems',{}).get(k,{}).get('response') for k in ['A','B','C']},'C_semantic_valid':out.get('semantic_valid'),'C_verification_outcome':out.get('verification_outcome'),'C_validation_error_codes':code_only(out.get('reference_audit',{}).get('errors',[])),'case_elapsed_ms':rr.get('elapsed_ms'),'local_overhead_ms':rr.get('local_overhead_ms'),'B_postprocess_ms':rr.get('B_postprocess_ms'),'query_profile_fallback':bool(out.get('query_profile_fallback'))}
   if dataset=='dataset1':g['expected_mode']=g['expected_top_level_mode'];g['expected_reason']=g['expected_public_reason_class'];g['reason_available']=True
   for system in ['A','B','C']:
    e=rr.get('systems',{}).get(system,empty_response_status());response=e.get('response');op=bool(e.get('operational_failure',True));errors=validate_response(json.dumps(response));policy=False
    if isinstance(response,dict):
     try:impl.assert_safe_payload(source_request,{**source_request.public(),'response':response})
     except ValueError:policy=True
    if system=='A' and errors:op=True
    mode=response.get('top_level_mode') if isinstance(response,dict) else 'ERROR';status='INVALID_OUTPUT_CONTRACT' if system=='A' and errors and e.get('status')!='NOT_EXECUTED' else e.get('status','NOT_EXECUTED');text=response.get('answer','') if isinstance(response,dict) else '';text=text if isinstance(text,str) else ''
    safe['systems'][system]={'mode':mode,'status':status,'operational_failure':op,'policy_violation':policy,'output_validation_codes':code_only(errors),'response_characters':len(text),'response_words':len(text.split()),'mode_correct_nonoperational':mode==g.get('expected_mode') and not op and not policy if dataset!='dataset3' else None,'observed_mode_agreement':mode==g.get('expected_mode') if dataset!='dataset3' else None,'public_reason_class':response.get('public_reason_class') if isinstance(response,dict) and not errors else None,'fulfilment_status':response.get('fulfilment_status') if isinstance(response,dict) and not errors else None,'model_response_available':isinstance(response,dict)}
   if dataset!='dataset3':
    group=g['pair_id'] if dataset=='dataset1' else g['source_group'];grouped.append({'group':group,**{s:safe['systems'][s]['mode_correct_nonoperational'] for s in ['A','B','C']}})
   else:
    d=out.get('semantic_assessment') or {};docs={v['source_id']:v['context'] for v in out.get('permitted_request',{}).get('documents',source_request.documents)};cat=build_catalogue(docs);vmap={m['source_id']:m['original_marker'] for m in inp['mapping']};rawsources=set();validated=set();roles={r['source_id']:r for r in d.get('source_assessments',[])}
    for ref in d.get('supporting_spans',[]):
     try:
      span=resolve_span(ref,docs,cat);rawsources.add(vmap[span['source_id']]);role=roles.get(span['source_id'],{})
      if out.get('semantic_valid') and role.get('role')=='PRIMARY' and role.get('relation_label')=='SUPPORTS':validated.add(vmap[span['source_id']])
     except (ValueError,KeyError):pass
    rm=selection_metric(rawsources,g['evidence_relevant'],g['evidence_correct']);vm=selection_metric(validated,g['evidence_relevant'],g['evidence_correct']);d3layers['raw_C'].append(rm);d3layers['validated_C'].append(vm);caseground={'sample_id':sid,'runtime_index':i,'semantic_valid':out.get('semantic_valid'),'altered_context':inp.get('altered_context',False),'original_passages':inp.get('original_grounding_count'),'included_passages':inp.get('included_count'),'raw_C':rm,'validated_C':vm,'original_relevance_distribution':dict(collections.Counter(g['evidence_relevant'])),'original_correctness_distribution':dict(collections.Counter(g['evidence_correct'])),'systems':{}}
    for system in ['A','B','C']:
     response=rr.get('systems',{}).get(system,{}).get('response') or {};citations,invalid=answer_citations(response.get('answer',''),inp['mapping'],cat);cm=selection_metric(citations,g['evidence_relevant'],g['evidence_correct']);d3layers[system+'_actual_citations'].append(cm);nassoc=0
     if system=='C' and out:
      try:
       req=request_for(inp['case'],out);trace=build_public_grounding_trace(req,d,response,out.get('semantic_valid') is True,build_inventory(req,inp['mapping']));nassoc=len(trace['unverified_associations'])
      except ValueError:pass
     caseground['systems'][system]={'actual_citation_metric':cm,'invalid_public_citations':len(invalid),'mechanically_valid_unverified_associations':nassoc,'rendered_verified_sidecar_citations':0,'citationless_FULL':safe['systems'][system]['mode']=='FULL' and not citations}
    d3cases.append(caseground)
    # Blinded packet contains only authorized evidence and randomized system aliases.
    labels=['A','B','C'];random.Random(20261029+i).shuffle(labels);blind={f'R{j+1}':rr.get('systems',{}).get(label,{}).get('response') for j,label in enumerate(labels)};review.append({'sample_id':sid,'question':inp['case']['query'],'question_context':inp['query_context'],'authorized_documents':source_request.documents,'responses':blind});reviewkey.append({'sample_id':sid,'system_key':{f'R{j+1}':label for j,label in enumerate(labels)}})
   records.append(safe)
  safeall[dataset]=records
  complete=sum(r['execution_status']=='COMPLETED' for r in records);cohort={'dataset':'Original 40 exposed development' if dataset=='dataset1' else 'Fixed40 exposed development fallback; reserved30 untouched' if dataset=='dataset2' else 'Fresh80 code-frozen held-out rows; source grounding only','planned':N,'paired_executions_completed':complete,'incomplete':N-complete,'systems':{}}
  if dataset!='dataset3':
   boot=bootstrap_groups(grouped);allpaired[dataset]={'bootstrap':boot,'C_vs_B':paired_counts(grouped),'C_vs_A':paired_counts(grouped,'C','A'),'B_vs_A':paired_counts(grouped,'B','A')}
   for system in ['A','B','C']:
    m=compute_mode_metrics(records,gold,system);m['mode_accuracy_cluster_interval95']=boot['intervals'][system];m['observed_modes']=dict(collections.Counter(r['systems'][system]['mode'] for r in records));cohort['systems'][system]=m
    if dataset=='dataset1':
     groups=collections.defaultdict(list)
     for r,g in zip(records,gold):groups[g['pair_id']].append(r)
     m['matched_pair_joint_mode_accuracy']=sum(len(rs)==2 and all(r['systems'][system]['mode_correct_nonoperational'] for r in rs) for rs in groups.values())/len(groups)
  else:
   for system in ['A','B','C']:cohort['systems'][system]={'planned':N,'mode_accuracy':None,'reason':'No native FULL/CFAF or independent claim gold','observed_modes':dict(collections.Counter(r['systems'][system]['mode'] for r in records)),'operational_failure_count':sum(r['systems'][system]['operational_failure'] for r in records),'policy_violation_count':sum(r['systems'][system]['policy_violation'] for r in records),'mean_response_words':statistics.mean(r['systems'][system]['response_words'] for r in records)}
   grounding={'dataset':'Original GaRAGe fresh80','definition':'Original source relevance YES/NO, correctness categories retained; no answer completeness or entailment score','layers':{k:aggregate(v) for k,v in d3layers.items()},'C_valid_assessment_only':aggregate([r['validated_C'] for r in d3cases if r['semantic_valid']]),'C_unchanged_context_only':aggregate([r['validated_C'] for r in d3cases if not r['altered_context']]),'semantic_valid_cases':sum(bool(r['semantic_valid']) for r in d3cases),'altered_context_cases':sum(r['altered_context'] for r in d3cases),'original_label_distributions':{'relevance':dict(sum((collections.Counter(r['original_relevance_distribution']) for r in d3cases),collections.Counter())),'correctness':dict(sum((collections.Counter(r['original_correctness_distribution']) for r in d3cases),collections.Counter()))},'systems':{s:{'actual_public_citations':sum(r['systems'][s]['actual_citation_metric']['selected_count'] for r in d3cases),'invalid_public_citations':sum(r['systems'][s]['invalid_public_citations'] for r in d3cases),'mechanically_valid_unverified_associations':sum(r['systems'][s]['mechanically_valid_unverified_associations'] for r in d3cases),'rendered_verified_citations':0,'citationless_FULL':sum(r['systems'][s]['citationless_FULL'] for r in d3cases)} for s in ['A','B','C']},'cases':d3cases,'independent_adjudication':'PENDING'}
  operational[dataset]={'per_system':{s:dict(collections.Counter(r['systems'][s]['status'] for r in records)) for s in ['A','B','C']},'C_gate_outcomes':dict(collections.Counter((r['C_verification_outcome'] or {}).get('status','NOT_EXECUTED') for r in records)),'C_validation_error_codes':dict(collections.Counter(e for r in records for e in r['C_validation_error_codes'])),'query_only_fallbacks':sum(r['query_profile_fallback'] for r in records),'not_executed_indices':[r['runtime_index'] for r in records if r['execution_status']=='NOT_EXECUTED'],'execution_error_indices':[r['runtime_index'] for r in records if r['execution_status']=='ERROR']}
  summary[dataset]=cohort
  for system,m in cohort['systems'].items():flatcsv.append({'dataset':dataset,'cohort':cohort['dataset'],'system':system,'N_planned':N,'N_paired_complete':complete,'mode_accuracy_nonoperational':m.get('mode_accuracy_nonoperational'),'balanced_accuracy':m.get('balanced_accuracy'),'FULL_recall':m.get('FULL_recall'),'CFAF_recall':m.get('CFAF_recall'),'operational_failures':m.get('operational_failure_count'),'FULL_outputs':m['observed_modes'].get('FULL',0),'CFAF_outputs':m['observed_modes'].get('CFAF',0),'source_grounding_scope':'actual citations only' if system in ['A','B'] else 'separate raw/validated support and actual citations'})
  write_rows(ROOT/(dataset+'_results.jsonl'),[{k:v for k,v in r.items() if k!='_responses'} for r in records])
 write(ROOT/'comparison_summary.json',summary);write(ROOT/'paired_mode_confusions.json',allpaired);write(ROOT/'grounding_metrics.json',grounding);write(ROOT/'operational_failures.json',operational)
 with (ROOT/'comparison_summary.csv').open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(flatcsv[0]));w.writeheader();w.writerows(flatcsv)
 events=rows(ROOT/'api_events.jsonl') if (ROOT/'api_events.jsonl').exists() else [];requests=rows(ROOT/'api_requests.jsonl') if (ROOT/'api_requests.jsonl').exists() else [];bydataset={}
 for dataset in ['dataset1','dataset2','dataset3']:
  es=[e for e in events if e['dataset']==dataset];reqs=[r for r in requests if r['dataset']==dataset];split={}
  for who in ['A_shared_with_B','C']:
   ss=[e for e in es if (e['kind']=='standard_rag')==(who=='A_shared_with_B')];split[who]={'calls':len(ss),'input_tokens':sum((e.get('usage') or {}).get('prompt_tokens',0) for e in ss),'output_tokens':sum((e.get('usage') or {}).get('completion_tokens',0) for e in ss),'summed_provider_ms':sum(e['latency_ms'] for e in ss)}
  bydataset[dataset]={'attempts':len(reqs),'successful':sum(e['status']=='SUCCESS' for e in es),'errors':sum(e['status']!='SUCCESS' for e in es),'input_tokens':sum((e.get('usage') or {}).get('prompt_tokens',0) for e in es),'output_tokens':sum((e.get('usage') or {}).get('completion_tokens',0) for e in es),'kind_counts':dict(collections.Counter(e['kind'] for e in es)),'allocation':split,'B_extra_model_calls':0,'B_total_postprocess_ms':sum(r.get('B_postprocess_ms',0) for r in rawall[dataset].values()),'local_overhead_ms':sum(r.get('local_overhead_ms',0) for r in rawall[dataset].values())}
 usage={'attempts':len(requests),'cap':480,'successes':sum(e['status']=='SUCCESS' for e in events),'errors':sum(e['status']!='SUCCESS' for e in events),'unsettled_attempts':len(requests)-len(events),'input_tokens':sum(v['input_tokens'] for v in bydataset.values()),'output_tokens':sum(v['output_tokens'] for v in bydataset.values()),'mean_latency_ms':statistics.mean(e['latency_ms'] for e in events) if events else None,'max_latency_ms':max((e['latency_ms'] for e in events),default=None),'provider_latency_seconds':sum(e['latency_ms'] for e in events)/1000,'models_observed':sorted(set(e.get('model','unknown') for e in events)),'by_dataset':bydataset,'finish_reasons':dict(collections.Counter(e.get('finish_reason','ERROR') for e in events)),'retries':0,'embeddings':0,'external_judges':0,'one_call_ablation_executed':False,'monetary_cost':None,'pricing_verified':False};write(ROOT/'api_usage.json',usage)
 write_rows(ROOT/'local/dataset3_blinded_review_packet.jsonl',review);write(ROOT/'local/dataset3_blinding_key.json',reviewkey)
 with (ROOT/'DATASET3_ADJUDICATION_TEMPLATE.csv').open('w',newline='',encoding='utf-8') as f:
  fields=['sample_id','response_alias','annotator','essential_requirements','complete_supported_answer_possible','factual_claims_supported','missing_requirements','temporal_scope','citation_entailment','appropriate_refusal','notes','status'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for packet in review:
   for alias in ['R1','R2','R3']:w.writerow({'sample_id':packet['sample_id'],'response_alias':alias,'status':'PENDING'})
 print(json.dumps({'cohorts':{k:{'planned':v['planned'],'complete':v['paired_executions_completed'],'mode_accuracy':{s:m.get('mode_accuracy_nonoperational') for s,m in v['systems'].items()}} for k,v in summary.items()},'API_attempts':usage['attempts'],'input_tokens':usage['input_tokens'],'output_tokens':usage['output_tokens']},indent=2))
if __name__=='__main__':score()
