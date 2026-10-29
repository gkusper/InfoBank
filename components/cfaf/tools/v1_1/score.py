"""Scorer-only metrics. Benchmark gold, text and full model outputs remain local."""
from common import *
import collections,statistics

def arm(row,name):
 if name!='B':return row.get('systems',{}).get(name,{})
 a=row.get('systems',{}).get('A',{});b=a.get('B',{});return {**b,'usage':{'attempts':0,'input_tokens':0,'output_tokens':0,'provider_ms':0},'system_end_to_end_ms':b.get('postprocess_ms',0),'timing':{},'proposal_bytes':0}
def summary(values):
 return {'N':len(values),'sum':sum(values),'mean':statistics.mean(values) if values else None,'median':statistics.median(values) if values else None,'max':max(values) if values else None}

def score():
 ensure();verify_freeze();inputs=rows(ROOT/'results/local/inputs.jsonl');gold={r['index']:r for r in rows(ROOT/'results/local/gold.jsonl')};raw=rows(OUT/'local/paired_raw.jsonl') if (OUT/'local/paired_raw.jsonl').exists() else [];byid={r['index']:r for r in raw};public=[];private=[];mode={};errors={};latency={};usage={};qualities={}
 for item in inputs:
  row=byid.get(item['index'],{});pub={'index':item['index'],'dataset':item['dataset'],'systems':{}};g=gold[item['index']]['gold'];expected=(g.get('expected_top_level_mode',g.get('expected_mode')) if g else None);scored={}
  for name in ['A','B','C1','C2']:
   data=arm(row,name);response=data.get('response') or {};status=data.get('execution_status','NOT_EXECUTED');text=response.get('text',response.get('answer',''));blocked=(g or {}).get('forbidden_disclosures',[])+(g or {}).get('protected_markers',[]);policy=any(v and v in text for v in blocked);valid=status=='SUCCESS' and not policy;citations=response.get('citations',[]);served=response.get('mode');scored[name]={'mode':served,'status':status,'valid':valid,'policy_violation':policy,'correct':valid and served==expected if expected else None}
   pub['systems'][name]={'mode':served,'execution_status':status,'operational_failure':status!='SUCCESS','policy_violation':policy,'usage':{k:v for k,v in data.get('usage',{}).items() if k in {'attempts','input_tokens','output_tokens','provider_ms','model'}},'system_end_to_end_ms':data.get('system_end_to_end_ms'),'process_wall_ms':data.get('process_wall_ms'),'timing':data.get('timing',{}),'proposal_bytes':data.get('proposal_bytes'),'public_citations':len(citations),'trusted_structured_citations':sum('APPLICATION_STRUCTURED' in c['labels'] for c in citations),'mechanical_validity_not_semantic_proof':True,'context_identity_sha256':data.get('context_identity_sha256')}
  public.append(pub);private.append({'index':item['index'],'dataset':item['dataset'],'gold_mode':expected,'scored':scored,'input':item,'raw':row,'original_gold':g})
 for dataset in ['dataset1','dataset2','garage']:
  chosen=[r for r in private if r['dataset']==dataset];systems={}
  for name in ['A','B','C1','C2']:
   confusion=collections.Counter();served=collections.Counter();op=0;correct=0;policy=0
   for r in chosen:
    a=r['scored'][name];served[a['mode'] or 'MISSING']+=1;op+=a['status']!='SUCCESS';policy+=a['policy_violation'];correct+=bool(a['correct'])
    if r['gold_mode']:confusion[(r['gold_mode'],a['mode'] if a['valid'] else 'OPERATIONAL_OR_POLICY')]+=1
   denominator={c:sum(v for (g,p),v in confusion.items() if g==c) for c in ['FULL','CFAF']};recall={c:confusion.get((c,c),0)/denominator[c] if denominator[c] else None for c in denominator};native=dataset!='garage'
   systems[name]={'N_planned':10,'accuracy':correct/10 if native else None,'correct':correct if native else None,'balanced_accuracy':statistics.mean(recall.values()) if native else None,'FULL_recall':recall['FULL'],'CFAF_recall':recall['CFAF'],'confusion':{g+'->'+p:n for (g,p),n in confusion.items()},'observed_modes':dict(served),'unnecessary_refusal':confusion.get(('FULL','CFAF'),0) if native else None,'failure_to_restrict':confusion.get(('CFAF','FULL'),0) if native else None,'operational_failures':op,'policy_violations':policy}
  paired=collections.Counter()
  if dataset!='garage':
   for r in chosen:
    c1=r['scored']['C1']['correct'];c2=r['scored']['C2']['correct'];paired['both' if c1 and c2 else 'C2_only' if c2 else 'C1_only' if c1 else 'neither']+=1
  mode[dataset]={'systems':systems,'paired_C2_C1_correctness':dict(paired),'native_binary_gold':dataset!='garage'}
 for name in ['A','B','C1','C2']:
  records=[arm(byid.get(i,{}),name) for i in range(30)];ms=[r.get('system_end_to_end_ms',0) for r in records];latency[name]={'selected_case_end_to_end_ms':summary(ms),'process_wall_ms':summary([r['process_wall_ms'] for r in records if r.get('process_wall_ms') is not None]),'provider_ms':summary([r.get('usage',{}).get('provider_ms',0) for r in records if r.get('usage',{}).get('attempts')]),'proposal_bytes':summary([r.get('proposal_bytes',0) for r in records if r.get('usage',{}).get('attempts')]),'gate_ms':summary([r.get('timing',{}).get('gate_ms',0) for r in records]),'render_ms':summary([r.get('timing',{}).get('render_ms',0) for r in records]),'public_validation_ms':summary([r.get('timing',{}).get('public_validation_ms',0) for r in records])};usage[name]={'attempts':sum(r.get('usage',{}).get('attempts',0) for r in records),'input_tokens':sum(r.get('usage',{}).get('input_tokens',0) for r in records),'output_tokens':sum(r.get('usage',{}).get('output_tokens',0) for r in records),'provider_ms':sum(r.get('usage',{}).get('provider_ms',0) for r in records),'zero_call_cases':sum(r.get('usage',{}).get('attempts',0)==0 for r in records),'models':sorted({r.get('usage',{}).get('model') for r in records if r.get('usage',{}).get('model')})}
 for name in ['C1','C2']:
  failure=collections.Counter();role=collections.Counter();refs=0;model_refs=0;app_refs=0;cases=[]
  for i in range(30):
   record=arm(byid.get(i,{}),name);result=record.get('result',{});trace=result.get('private_trace',{});status=record.get('execution_status','NOT_EXECUTED')
   if status!='SUCCESS':failure[trace.get('failure_code',status)]+=1;cases.append({'index':i,'status':status,'failure_code':trace.get('failure_code',status)})
   role.update((trace.get('source_assessment_inventory') or {}).values())
   for c in (record.get('response') or {}).get('citations',[]):refs+=1;model_refs+='MODEL_ATTRIBUTED' in c['labels'];app_refs+='APPLICATION_STRUCTURED' in c['labels']
  errors[name]={'failures':dict(failure),'cases':cases,'public_citations':refs,'model_attributed':model_refs,'application_structured':app_refs,'semantic_support_independently_verified':False,'assessed_role_counts_and_NOT_ASSESSED':dict(role)}
 events=rows(OUT/'local/api_ledger.jsonl') if (OUT/'local/api_ledger.jsonl').exists() else [];attempts=[e for e in events if e['event']=='ATTEMPT'];settled=[e for e in events if e['event']=='RESULT']
 for name in ['A','C1','C2']:
  es=[e for e in settled if e['kind']==name];usage[name]['provider_statuses']=dict(collections.Counter(e['status'] for e in es));usage[name]['cached_input_tokens']=sum((((e.get('response') or {}).get('usage') or {}).get('prompt_tokens_details') or {}).get('cached_tokens',0) or 0 for e in es)
 deltas=[arm(byid[i],'C2').get('system_end_to_end_ms',0)-arm(byid[i],'C1').get('system_end_to_end_ms',0) for i in byid];common=[i for i in byid if all(arm(byid[i],s).get('usage',{}).get('attempts')==1 for s in ['C1','C2'])]
 common_totals={s:{k:sum(arm(byid[i],s).get('usage',{}).get(k,0) for i in common) for k in ['input_tokens','output_tokens','provider_ms']} for s in ['C1','C2']}
 reported_common=[i for i in common if all(arm(byid[i],s).get('usage',{}).get('model') for s in ['C1','C2'])]
 reported_totals={s:{k:sum(arm(byid[i],s).get('usage',{}).get(k,0) for i in reported_common) for k in ['input_tokens','output_tokens','provider_ms']} for s in ['C1','C2']}
 for s in ['A','C1','C2']:
  usage[s]['attempts_without_reported_usage']=sum(arm(byid.get(i,{}),s).get('usage',{}).get('attempts',0)>0 and not arm(byid.get(i,{}),s).get('usage',{}).get('model') for i in range(30))
  usage[s]['token_totals_scope']='Reported successful-response usage only; unavailable failed-request token usage is unknown, not zero.'
 old=rows(ROOT/'results/local/live_results.jsonl');variability={'mode_differences':sum((arm(byid.get(i,{}),'C1').get('response') or {}).get('mode')!=old[i]['C1']['response']['mode'] for i in byid),'comparison':'Historical original C1 modes versus fresh same-config C1; not used as fresh outcomes'}
 (OUT/'paired_results.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in public),encoding='utf-8');(OUT/'local/scored_private.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in private),encoding='utf-8');write(OUT/'mode_confusion.json',{'cohorts':mode,'GaRAGe_accuracy':None,'pooled_accuracy':None,'old_vs_fresh_C1_variability':variability});write(OUT/'reference_error_analysis.json',{'systems':errors,'old_original_span_failure_indices':[21,23,25],'old_failures_fresh_outcomes':{str(i):{s:arm(byid.get(i,{}),s).get('execution_status','NOT_EXECUTED') for s in ['C1','C2']} for i in [21,23,25]},'invalid_accepted_citations':'FINAL_AUDIT_REQUIRED'});write(OUT/'api_usage.json',{'systems':usage,'global_attempts':len(attempts),'settled_attempts':len(settled),'cap':100,'SDK_retries':0,'B_extra_calls':0,'no_NLI_judge_embeddings':True,'all_outputs_fresh':True,'common_generated_cases':len(common),'common_generated_totals':common_totals,'both_reported_common_N':len(reported_common),'both_reported_common_totals':reported_totals,'token_savings_including_zero_routes_percent':100*(1-usage['C2']['output_tokens']/usage['C1']['output_tokens']) if usage['C1']['output_tokens'] else None,'finish_reasons':dict(collections.Counter((e.get('response') or {}).get('choices',[{}])[0].get('finish_reason') for e in settled if e.get('response'))),'complete_selected_cases':len(raw)});write(OUT/'latency_comparison.json',{'systems':latency,'paired_C2_minus_C1_ms':summary(deltas),'common_generated_case_count':len(common),'common_generated_totals':common_totals,'both_reported_common_N':len(reported_common),'both_reported_common_totals':reported_totals,'paired_C2_minus_C1_both_reported_ms':summary([arm(byid[i],'C2')['system_end_to_end_ms']-arm(byid[i],'C1')['system_end_to_end_ms'] for i in reported_common]),'measurement':'SDK provider wrapper includes response parsing; system end-to-end starts before prepare and excludes interpreter/client construction; process wall includes startup. Transparent wrappers measure gate/render/public-validation. All outcomes, including operational failures, are retained.','counterbalanced_C1_C2':True,'single_run_no_significance_claim':True})
 report=['# Complete private v1.1 paired case report','Original inputs/gold, raw outputs and traces remain private. No independent answer-quality adjudication.']
 for r in private:report.extend([f"## Case {r['index']+1}: {r['dataset']}",'```json\n'+json.dumps(r,ensure_ascii=False,indent=2)+'\n```'])
 (OUT/'local/CASE_REPORT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8')
 print(json.dumps({'mode_accuracy':{d:{s:v['accuracy'] for s,v in x['systems'].items()} for d,x in mode.items()},'reference_failures':{s:e['failures'] for s,e in errors.items()},'attempts':len(attempts),'C1_output_tokens':usage['C1']['output_tokens'],'C2_output_tokens':usage['C2']['output_tokens'],'C1_provider_s':usage['C1']['provider_ms']/1000,'C2_provider_s':usage['C2']['provider_ms']/1000},indent=2))
if __name__=='__main__':score()
