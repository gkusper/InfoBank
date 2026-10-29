"""Scorer-only original-gold joins; no model API and no implementation tuning."""
import collections,re,statistics,json
from .artifacts import *
from .adapter import paragraphs
from . import measured_c as impl
from evaluation.cfaf_sparse_source_repair_v1.operational_failure_codes import validate_response
from evaluation.refusalbench_span_fix_v1.span_references import build_catalogue,resolve_span

def normalized(s):return ' '.join(re.sub(r'^FLOAT SELECTED\s*:\s*','',s).split())
def reference(a):
 if a['unanswerable']:return None
 if a['extractive_spans']:return '; '.join(a['extractive_spans'])
 if a['free_form_answer'].strip():return a['free_form_answer']
 return 'Yes' if a['yes_no'] else 'No'

def mode_metrics(records,system):
 c={g:{p:0 for p in ['FULL','CFAF','OPERATIONAL','NOT_EXECUTED']} for g in ['FULL','CFAF']};raw=0
 for r in records:
  s=r['systems'][system];gold=r['gold_mode'];raw+=s['mode']==gold;p='NOT_EXECUTED' if s['status']=='NOT_EXECUTED' else 'OPERATIONAL' if s['operational_failure'] else s['mode'];c[gold][p]+=1
 fulln=sum(c['FULL'].values());cfn=sum(c['CFAF'].values());n=fulln+cfn;correct=c['FULL']['FULL']+c['CFAF']['CFAF'];fr=c['FULL']['FULL']/fulln if fulln else None;cr=c['CFAF']['CFAF']/cfn if cfn else None
 denomf=c['FULL']['FULL']+c['CFAF']['FULL'];denomc=c['FULL']['CFAF']+c['CFAF']['CFAF'];op=sum(c[g]['OPERATIONAL'] for g in c);missing=sum(c[g]['NOT_EXECUTED'] for g in c)
 return {'N_planned':n,'correct_nonoperational':correct,'accuracy':correct/n if n else None,'balanced_accuracy':(fr+cr)/2 if fr is not None and cr is not None else None,'FULL_precision':c['FULL']['FULL']/denomf if denomf else None,'FULL_recall':fr,'CFAF_precision':c['CFAF']['CFAF']/denomc if denomc else None,'CFAF_recall':cr,'unnecessary_refusals':c['FULL']['CFAF'],'failure_to_restrict':c['CFAF']['FULL'],'operational_failures':op,'not_executed':missing,'operational_withholding_on_FULL':c['FULL']['OPERATIONAL'],'confusion_gold_rows_prediction_columns':c,'observed_mode_agreement_including_operational_DO_NOT_USE_AS_ACCURACY':raw/n if n else None,'precision_scope':'Nonoperational predictions only; operational/missing outputs are separate columns and receive zero accuracy/recall credit.','answer_correctness':'Not established by mode agreement'}

def prf(selected,gold):
 tp=len(selected&gold);p=tp/len(selected) if selected else None;r=tp/len(gold) if gold else None
 return {'selected':len(selected),'gold':len(gold),'intersection':tp,'precision':p,'recall':r,'F1':2*tp/(len(selected)+len(gold)) if selected or gold else None}

def score():
 ensure();selection=read(ROOT/'DATASET3_SELECTION_MANIFEST.json');inputs=rows(ROOT/'local/runtime_inputs.jsonl');golds=rows(ROOT/'local/selected_originals.jsonl');path=ROOT/'local/results_raw.jsonl';observed={r['runtime_index']:r for r in rows(path)} if path.exists() else {};safe=[];evcases=[];packet=[]
 for i,(inp,g,meta) in enumerate(zip(inputs,golds,selection['records'])):
  rr=observed.get(i,{'status':'NOT_EXECUTED','systems':{}});out=rr.get('C_outcome') or {};r={'runtime_index':i,'paper_id':g['paper_id'],'question_id':g['question']['question_id'],'gold_mode':g['derived_gold_mode'],'execution_status':rr['status'],'retrieval_method':inp['retrieval_method'],'systems':{},'case_elapsed_ms':rr.get('elapsed_ms'),'B_postprocess_ms':rr.get('B_postprocess_ms'),'C_verification_outcome':out.get('verification_outcome'),'C_semantic_valid':out.get('semantic_valid'),'query_only_profile_fallback':bool(out.get('query_profile_fallback'))}
  for s in ['A','B','C']:
   entry=rr.get('systems',{}).get(s,{'status':'NOT_EXECUTED','operational_failure':True});response=entry.get('response');errors=validate_response(json.dumps(response));op=entry.get('operational_failure',True) or bool(errors);mode=response.get('top_level_mode') if isinstance(response,dict) else None;status=entry.get('status','NOT_EXECUTED');status='INVALID_OUTPUT_CONTRACT' if errors and status!='NOT_EXECUTED' else status
   r['systems'][s]={'mode':mode,'status':status,'operational_failure':op,'mode_correct':mode==g['derived_gold_mode'] and not op,'output_validation_error_codes':sorted(set(e.split(':')[0] for e in errors)),'answer_characters':len((response or {}).get('answer','')),'public_reason_class':(response or {}).get('public_reason_class')}
  safe.append(r)
  p=g['paper'];public={'question':g['question']['question'],**{k:p[k] for k in ['title','abstract','full_text','figures_and_tables']}};allps=paragraphs(public);keymap=collections.defaultdict(set)
  abstract_start=len('TITLE\n'+public['title']+'\nABSTRACT\n');abstract_unit={'key':'ABSTRACT','kind':'abstract','section':'Abstract','text':public['abstract'],'start':abstract_start,'end':abstract_start+len(public['abstract'])};allps.append(abstract_unit)
  for p in allps:keymap[normalized(p['text'])].add(p['key'])
  evidence_sets=[];goldtexts={};unmapped=[]
  for a in g['question']['answers']:
   gs=set()
   for text in a['answer']['evidence']:
    nt=normalized(text);matches=keymap.get(nt,set());key='E:'+nt
    if matches:gs.update(matches)
    else:gs.add(key);unmapped.append(nt)
    goldtexts[nt]=text
   evidence_sets.append(gs)
  gold=set().union(*evidence_sets) if evidence_sets else set();included={p['key'] for p in inp['paragraph_mapping']}|{'ABSTRACT'};request=impl.project_case(inp['case']);docs={d['source_id']:d['context'] for d in request.documents};cat=build_catalogue(docs);data=out.get('semantic_assessment') or {};refs=data.get('supporting_spans',[]);selected=set();spanerrors=[];selectedrefs=[]
  for ref in refs:
   try:
    span=resolve_span(ref,docs,cat);selectedrefs.append(span)
    for p in inp['paragraph_mapping']+[abstract_unit]:
     if max(span['start'],p['start'])<min(span['end'],p['end']):selected.add(p['key'])
   except (ValueError,TypeError) as e:spanerrors.append(str(e).split(':')[0])
  validselected=selected if out.get('semantic_valid') is True else set();metric=prf(validselected,gold);best=[prf(validselected,gs) for gs in evidence_sets if gs]
  ec={'runtime_index':i,'gold_mode':g['derived_gold_mode'],'retrieval_method':inp['retrieval_method'],'human_evidence_union_count':len(gold),'unmapped_original_evidence_count':len(set(unmapped)),'retrieved_human_evidence_count':len(gold&included),'retrieval_evidence_recall':len(gold&included)/len(gold) if gold else None,'C_assessment_valid':out.get('semantic_valid'),'C_span_reference_errors':spanerrors,'C_validated_paragraph_selection':metric,'C_raw_paragraph_selection':prf(selected,gold),'C_best_annotation_F1':max((x['F1'] for x in best if x['F1'] is not None),default=None),'C_validated_selected_paragraph_keys':sorted(validselected),'C_raw_selected_paragraph_keys':sorted(selected),'A_B_support_selection':'NOT_INSTRUMENTED; common output schema has no passage-reference field','actual_public_verified_citations':{'A':0,'B':0,'C':0},'semantic_entailment':'NOT independently established; overlapping deterministic windows can touch adjacent paragraphs'}
  evcases.append(ec);packet.append({'runtime_index':i,'paper_id':g['paper_id'],'question_id':g['question']['question_id'],'question':g['question']['question'],'title':g['paper']['title'],'gold_mode':g['derived_gold_mode'],'references':[reference(a['answer']) for a in g['question']['answers']],'human_evidence':list(goldtexts.values()),'human_highlighted_evidence':[t for a in g['question']['answers'] for t in a['answer'].get('highlighted_evidence',[])],'responses':{s:rr.get('systems',{}).get(s,{}).get('response') for s in ['A','B','C']},'C_analysis':data,'C_verification':out.get('verification'),'selected_spans':selectedrefs,'evidence_metrics':ec})
 for name,rs in [('RESULTS.jsonl',safe),('local/review_packet.jsonl',packet)]:
  (ROOT/name).write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rs),encoding='utf-8')
 metrics={s:mode_metrics(safe,s) for s in ['A','B','C']};write(ROOT/'MODE_CONFUSION.json',metrics)
 relevant=[r for r in evcases if r['human_evidence_union_count']];macro={k:statistics.mean(r['C_validated_paragraph_selection'][k] for r in relevant if r['C_validated_paragraph_selection'][k] is not None) if any(r['C_validated_paragraph_selection'][k] is not None for r in relevant) else None for k in ['precision','recall','F1']}
 write(ROOT/'EVIDENCE_METRICS.json',{'cases':evcases,'human_evidence_case_count':len(relevant),'C_macro_paragraph_overlap':macro,'retrieval_union_evidence_macro_recall':statistics.mean(r['retrieval_evidence_recall'] for r in relevant) if relevant else None,'not_answer_accuracy':True,'evidence_definition':'Union of original human evidence paragraphs/captions including the supplied abstract as an evidence unit, whitespace normalization and documented FLOAT SELECTED prefix removal; unmatched annotations remain in recall denominator. Supporting catalogue windows select every original paragraph touched. Invalid assessments have zero validated support. A/B passage selection not instrumented.','quality_assessment':'See local qualitative review; non-independent Codex assessment, no second LLM/API judge.'})
 events=rows(ROOT/'local/api_events.jsonl') if (ROOT/'local/api_events.jsonl').exists() else [];requests=rows(ROOT/'local/api_requests.jsonl') if (ROOT/'local/api_requests.jsonl').exists() else [];bykind={}
 for k in sorted(set(e['kind'] for e in events)):
  es=[e for e in events if e['kind']==k];bykind[k]={'attempts':len(es),'successes':sum(e['status']=='SUCCESS' for e in es),'input_tokens':sum((e.get('usage') or {}).get('prompt_tokens',0) for e in es),'output_tokens':sum((e.get('usage') or {}).get('completion_tokens',0) for e in es),'summed_latency_ms':sum(e['latency_ms'] for e in es),'mean_latency_ms':statistics.mean(e['latency_ms'] for e in es)}
 usage={'attempts':len(requests),'attempt_cap':50,'successes':sum(e['status']=='SUCCESS' for e in events),'errors':sum(e['status']!='SUCCESS' for e in events),'unsettled_attempts':len(requests)-len(events),'input_tokens':sum(v['input_tokens'] for v in bykind.values()),'output_tokens':sum(v['output_tokens'] for v in bykind.values()),'by_kind':bykind,'summed_latency_seconds':sum(e['latency_ms'] for e in events)/1000,'mean_latency_ms':statistics.mean(e['latency_ms'] for e in events) if events else None,'max_latency_ms':max((e['latency_ms'] for e in events),default=None),'observed_models':sorted(set(e.get('model','unknown') for e in events)),'finish_reasons':dict(collections.Counter(e.get('finish_reason','ERROR') for e in events)),'B_extra_model_calls':0,'B_summed_postprocess_ms':sum(r.get('B_postprocess_ms',0) or 0 for r in safe),'retries':0,'embeddings':0,'LLM_judges':0,'independent_verification_APIs':0,'last_call_start_epoch':max((r['started_at_epoch'] for r in requests),default=None),'monetary_cost':'Not calculated; tokens and latency recorded without unverified pricing'};write(ROOT/'API_USAGE.json',usage)
 print(json.dumps({'mode_accuracy':{s:v['accuracy'] for s,v in metrics.items()},'attempts':usage['attempts'],'tokens':[usage['input_tokens'],usage['output_tokens']],'evidence_macro':macro},indent=2))
if __name__=='__main__':score()
