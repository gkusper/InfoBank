"""Source-label metrics, kept separate from complete-answer and entailment judgement."""
import re,collections,json,statistics
from .artifacts import *
from evaluation.refusalbench_span_fix_v1.span_references import build_catalogue,resolve_span

def selection_metric(selected,relevance,correctness):
 selected=set(selected);yes={f'cite_{i+1}' for i,v in enumerate(relevance) if v=='YES'};no={f'cite_{i+1}' for i,v in enumerate(relevance) if v=='NO'};tp=len(selected&yes);fp=len(selected&no);fn=len(yes-selected)
 precision=tp/(tp+fp) if tp+fp else None;recall=tp/(tp+fn) if tp+fn else None;den=2*tp+fp+fn
 return {'selected_markers':sorted(selected,key=lambda x:int(x.split('_')[1])),'selected_count':len(selected),'tp':tp,'fp':fp,'fn':fn,'precision':precision,'recall':recall,'f1':2*tp/den if den else None,'missing_relevant_markers':sorted(yes-selected),'irrelevant_selected_markers':sorted(selected&no),'selected_unknown_relevance':len(selected-yes-no),'correctness_distribution':dict(collections.Counter(correctness[int(x.split('_')[1])-1] for x in selected))}

def answer_citations(answer,mapping,catalogue):
 marker_map={m['original_marker']:m for m in mapping};viewmap={m['source_id']:m['original_marker'] for m in mapping};valid=[];invalid=[]
 for match in re.finditer(r'\[(cite_\d+|view-\d{4}(?::span-\d{4})?)\]',answer or ''):
  token=match.group(1)
  if token.startswith('cite_'):
   if token in marker_map:valid.append(token)
   else:invalid.append(token)
  else:
   sid=token.split(':')[0]
   if sid not in viewmap or ':' in token and token not in catalogue.spans:invalid.append(token)
   else:valid.append(viewmap[sid])
 return set(valid),invalid

def aggregate(metrics):
 tp=sum(m['tp'] for m in metrics);fp=sum(m['fp'] for m in metrics);fn=sum(m['fn'] for m in metrics);den=2*tp+fp+fn
 return {'case_count':len(metrics),'tp':tp,'fp':fp,'fn':fn,'micro_precision':tp/(tp+fp) if tp+fp else None,'micro_recall':tp/(tp+fn) if tp+fn else None,'micro_f1':2*tp/den if den else None,'macro_precision_defined_cases':sum(m['precision'] is not None for m in metrics),'macro_precision':statistics.mean(m['precision'] for m in metrics if m['precision'] is not None) if any(m['precision'] is not None for m in metrics) else None,'macro_recall':statistics.mean(m['recall'] for m in metrics if m['recall'] is not None) if any(m['recall'] is not None for m in metrics) else None,'macro_f1':statistics.mean(m['f1'] for m in metrics if m['f1'] is not None) if any(m['f1'] is not None for m in metrics) else None}

def score():
 original=rows(ROOT/'selected_records.jsonl');runtime=rows(ROOT/'runtime_inputs.jsonl');results={r['runtime_index']:r for r in rows(ROOT/'results.jsonl')};diagnostics=[];modes=[]
 for i,(r,inp) in enumerate(zip(original,runtime)):
  result=results.get(i,{'status':'NOT_EXECUTED'});out=result.get('outcome',{});semantic=out.get('semantic_assessment') or {};docs={d['source_id']:d['context'] for d in out.get('permitted_request',{}).get('documents',[])};cat=build_catalogue(docs);viewmap={m['source_id']:m['original_marker'] for m in inp['mapping']};global_selected=set();invalid_spans=[]
  for reference in semantic.get('supporting_spans',[]):
   try:global_selected.add(viewmap[resolve_span(reference,docs,cat)['source_id']])
   except (ValueError,KeyError,TypeError):invalid_spans.append(reference)
  role_selected={viewmap[s['source_id']] for s in semantic.get('source_assessments',[]) if s.get('source_id') in viewmap and s.get('role')=='PRIMARY' and s.get('relation_label')=='SUPPORTS'}
  requirement_selected=set();requirement_audit=[]
  for requirement in semantic.get('requirement_support',[]):
   chosen=set();errors=[]
   for reference in requirement.get('supporting_span_ids',[]):
    try:chosen.add(viewmap[resolve_span(reference,docs,cat)['source_id']])
    except (ValueError,KeyError,TypeError):errors.append(reference)
   requirement_selected|=chosen;requirement_audit.append({**requirement,'original_markers':sorted(chosen),'invalid_span_ids':errors,'source_label_metric':selection_metric(chosen,r['evidence_relevant'],r['evidence_correct'])})
  metrics={'analyzer_global_support':selection_metric(global_selected,r['evidence_relevant'],r['evidence_correct']),'analyzer_primary_supports_roles':selection_metric(role_selected,r['evidence_relevant'],r['evidence_correct']),'analyzer_requirement_support':selection_metric(requirement_selected,r['evidence_relevant'],r['evidence_correct'])};systems={}
  for name in ['semantic_cfaf','shared_control']:
   response=out.get('responses',{}).get(name);errors=out.get('system_errors',{}).get(name,[]);answer=response.get('answer','') if isinstance(response,dict) else '';citations,invalid=answer_citations(answer,inp['mapping'],cat);metric=selection_metric(citations,r['evidence_relevant'],r['evidence_correct']);metric.update(invalid_citation_count=len(invalid),invalid_citations=invalid,answer_citation_count=len(citations),unsupported_claim_count=None,undersupported_FULL=None,unnecessary_deflection=None,claim_judgement='Requires non-independent qualitative review and independent human confirmation')
   metrics[name+'_answer_citations']=metric;systems[name]={'response':response,'valid':isinstance(response,dict) and not errors,'validation_errors':errors,'mode':response.get('top_level_mode') if isinstance(response,dict) and not errors else 'ERROR','raw_declared_mode':response.get('top_level_mode') if isinstance(response,dict) else None,'answer_has_citations':bool(citations),'citation_metric':metric}
  record={'runtime_index':i,'sample_id':r['sample_id'],'status':result['status'],'semantic_valid':out.get('semantic_valid'),'reference_audit':out.get('reference_audit'),'invalid_global_span_ids':invalid_spans,'metrics':metrics,'systems':systems,'requirement_support':requirement_audit,'fulfilment_issues':out.get('fulfilment_issues',[]),'internal_reason':out.get('internal_reason'),'A0_gate':result.get('A0_gate'),'T3_gate':out.get('selected_mode'),'context_altered':inp['altered_context'],'question_date':r['question_date'],'gold_relevance_counts':dict(collections.Counter(r['evidence_relevant'])),'gold_correctness_counts':dict(collections.Counter(r['evidence_correct'])),'reference_answer_validated':r['answer_validate'],'latency_ms':result.get('elapsed_ms'),'api_usage':{'calls':len(result.get('api_calls',[])),'input_tokens':sum(c['input_tokens'] for c in result.get('api_calls',[])),'output_tokens':sum(c['output_tokens'] for c in result.get('api_calls',[]))},'gold_full_cfaf':None}
  diagnostics.append(record);modes.append({'runtime_index':i,'sample_id':r['sample_id'],'status':result['status'],'T3_gate':record['T3_gate'],'T3_generated':systems['semantic_cfaf']['mode'],'control_generated':systems['shared_control']['mode'],'A0_gate':record['A0_gate'],'semantic_valid':out.get('semantic_valid'),'context_altered':inp['altered_context']})
 with (ROOT/'per_case_diagnostics.jsonl').open('w',encoding='utf-8') as f:
  for d in diagnostics:f.write(json.dumps(d,ensure_ascii=False)+'\n')
 layers=list(diagnostics[0]['metrics']);aggregate_metrics={layer:aggregate([d['metrics'][layer] for d in diagnostics if d['status']=='COMPLETED']) for layer in layers}
 write(ROOT/'grounding_metrics.json',{'definition':'Source selection against original evidence_relevant YES/NO. Empty relevance excluded from TP/FP. Unknown precision when no selected known-labelled sources; F1=0 when positives missed. Source recall is not answer completeness. All support-layer results shared between generated systems. Actual answer citations are separate.','answer_citation_syntax':'[cite_N], [view-NNNN], [view-NNNN:span-NNNN] only; bracketed exact known supplied mapping; no implicit source selection or citations inferred from support spans','layers':aggregate_metrics,'invalid_answer_citations':{n:sum(d['metrics'][n+'_answer_citations']['invalid_citation_count'] for d in diagnostics) for n in ['semantic_cfaf','shared_control']},'independent_claim_entailment':None,'binary_mode_accuracy':None,'altered_context_cases':sum(d['context_altered'] for d in diagnostics),'cases':[{'sample_id':d['sample_id'],'status':d['status'],'semantic_valid':d['semantic_valid'],'metrics':d['metrics']} for d in diagnostics]})
 write(ROOT/'mode_comparison.json',{'rows':modes,'distributions':{k:dict(collections.Counter(d[k] for d in modes)) for k in ['T3_gate','T3_generated','control_generated','A0_gate']},'generated_disagreements':sum(d['T3_generated']!=d['control_generated'] for d in modes),'T3_A0_gate_disagreements':sum(d['T3_gate']!=d['A0_gate'] for d in modes),'FULL_CFAF_accuracy':None,'reason':'No original complete-request sufficiency gold. Relevant/answering passage existence is not a defensible binary mapping.'})
 events=rows(ROOT/'api_events.jsonl') if (ROOT/'api_events.jsonl').exists() else [];requests=rows(ROOT/'api_requests.jsonl') if (ROOT/'api_requests.jsonl').exists() else [];bykind={}
 for kind in sorted(set(e['kind'] for e in events)):
  subset=[e for e in events if e['kind']==kind];lat=[e['latency_ms'] for e in subset];bykind[kind]={'attempts':len(subset),'successful':sum(e['status']=='SUCCESS' for e in subset),'input_tokens':sum((e.get('usage') or {}).get('prompt_tokens',0) for e in subset),'output_tokens':sum((e.get('usage') or {}).get('completion_tokens',0) for e in subset),'mean_latency_ms':statistics.mean(lat),'max_latency_ms':max(lat),'errors':sum(e['status']!='SUCCESS' for e in subset),'finish_reasons':dict(collections.Counter(e.get('finish_reason','ERROR') for e in subset))}
 lat=[e['latency_ms'] for e in events];write(ROOT/'api_usage.json',{'attempts':len(requests),'successful_calls':sum(e['status']=='SUCCESS' for e in events),'errors':sum(e['status']!='SUCCESS' for e in events),'unsettled_attempts':len(requests)-len(events),'cap':60,'input_tokens':sum(v['input_tokens'] for v in bykind.values()),'output_tokens':sum(v['output_tokens'] for v in bykind.values()),'mean_latency_ms':statistics.mean(lat) if lat else None,'max_latency_ms':max(lat) if lat else None,'by_kind':bykind,'dollar_cost':None,'pricing_verified':False,'retries':0,'additional_verifiers':0,'embeddings':0,'shared_upstream_counted_once':True})
 print(json.dumps({'modes':read(ROOT/'mode_comparison.json')['distributions'],'calls':len(requests),'grounding':aggregate_metrics},indent=2))
if __name__=='__main__':score()
