"""Scorer-only aggregate reporting; raw outputs and gold remain ignored."""
from common import *
import collections,statistics

def score():
    ensure();verify_freeze();inputs=rows(ROOT/'results/local/inputs.jsonl');gold={r['index']:r for r in rows(ROOT/'results/local/gold.jsonl')};data=rows(ROOT/'results/local/live_results.jsonl');byid={r['index']:r for r in data};summary={};packets=[]
    for dataset in ['dataset1','dataset2','garage']:
        selected=[r for r in inputs if r['dataset']==dataset];systems={}
        for system in ['A','B','C1']:
            counts=collections.Counter();confusion=collections.Counter();correct=0;full=0;op=0;viol=0;valid_citations=0;citation_count=0;markers=[]
            for item in selected:
                r=byid.get(item['index'],{});g=gold[item['index']]['gold'];mode_gold=(g.get('expected_top_level_mode',g.get('expected_mode')) if g else None)
                status=(r.get('C1',{}).get('decision',{}).get('execution_status','NOT_EXECUTED') if system=='C1' else r.get(system+'_status','NOT_EXECUTED'))
                answer=r.get('C1',{}).get('response',{}) if system=='C1' else r.get(system) or {};mode=answer.get('mode');text=answer.get('text',answer.get('answer',''))
                blocked=(g or {}).get('forbidden_disclosures',[])+(g or {}).get('protected_markers',[]);policy=any(s and s in text for s in blocked)
                okay=status=='SUCCESS' and not policy;op+=status!='SUCCESS';viol+=policy;counts[mode or 'MISSING']+=1;full+=okay and mode=='FULL';correct+=okay and mode==mode_gold if mode_gold else 0
                if mode_gold:confusion[(mode_gold,mode if okay else 'OPERATIONAL_OR_POLICY')]+=1
                if system=='C1':
                    for citation in answer.get('citations',[]):citation_count+=1;valid_citations+='REFERENCE_VALID' in citation['labels']
                if g and mode_gold=='FULL' and g.get('canonical_answer_markers'):markers.append({'all':all(v.casefold() in text.casefold() for v in g['canonical_answer_markers']),'nonoperational':okay})
            supports={c:sum(v for (g,p),v in confusion.items() if g==c) for c in ['FULL','CFAF']};recalls={c:confusion.get((c,c),0)/supports[c] if supports[c] else None for c in supports}
            systems[system]={'N_planned':len(selected),'mode_accuracy':correct/len(selected) if dataset!='garage' else None,'mode_correct':correct if dataset!='garage' else None,'balanced_accuracy':statistics.mean(recalls.values()) if dataset!='garage' and all(v is not None for v in recalls.values()) else None,'mode_counts':dict(counts),'confusion':{g+'->'+p:v for (g,p),v in confusion.items()},'operational_errors':op,'policy_violations':viol,'nonoperational_FULL_answers':full,'unnecessary_refusals':confusion.get(('FULL','CFAF'),0) if dataset!='garage' else None,'failures_to_restrict':confusion.get(('CFAF','FULL'),0) if dataset!='garage' else None,'mechanically_valid_public_citations':valid_citations if system=='C1' else None,'public_citation_count':citation_count if system=='C1' else None,'independent_answer_accuracy':None,'independent_fulfilment_accuracy':None,'independent_support_accuracy':None,'InfoBank_FULL_marker_diagnostic':{'denominator':len(markers),'all_markers_present':sum(x['all'] and x['nonoperational'] for x in markers)} if markers else None}
        paired=collections.Counter()
        if dataset!='garage':
            for item in selected:
                r=byid[item['index']];g=gold[item['index']]['gold'];expected=g.get('expected_top_level_mode',g.get('expected_mode'));b=r.get('B_status')=='SUCCESS' and r.get('B',{}).get('mode')==expected;c=r.get('C1',{}).get('decision',{}).get('execution_status')=='SUCCESS' and r.get('C1',{}).get('response',{}).get('mode')==expected;paired[('both' if b and c else 'C1_only' if c else 'B_only' if b else 'neither')]+=1
        summary[dataset]={'status':'Previously exposed development only','N':len(selected),'systems':systems,'paired_C1_B':dict(paired),'native_binary_gold':dataset!='garage'}
    for item in inputs:
        r=byid.get(item['index'],{});g=gold[item['index']]['gold'];trace=r.get('C1',{}).get('private_trace',{});views={}
        for e in rows(ROOT/'results/local/api_ledger.jsonl'):
            if e['event']=='ATTEMPT':
                user=json.loads(e['payload']['messages'][1]['content'])
                if user['query']==item['query'] and hashlib.sha256(json.dumps(user['documents'],sort_keys=True).encode()).hexdigest()==r.get('evidence_sha256'):
                    for v in user['documents']:views[v['source_id']]=v
        citations=r.get('C1',{}).get('response',{}).get('citations',[]);windows=[{'claim_id':c['claim_id'],'quote':views[c['source_id']]['text'][c['start']:c['end']]} for c in citations if c['source_id'] in views]
        packets.append({'index':item['index'],'dataset':item['dataset'],'query':item['query'],'gold':g,'A':r.get('A'),'B':r.get('B'),'C1':r.get('C1'),'selected_windows':windows,'authorized_views':list(views.values())})
    (ROOT/'results/local/review_packet.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in packets),encoding='utf-8')
    report=['# Complete local ComponentCFAF pilot record','Raw questions, gold, outputs and private traces: keep out of Git. Review is not independent.']
    for r in packets:report.extend([f"\n## Case {r['index']+1}: {r['dataset']}",'```json\n'+json.dumps(r,ensure_ascii=False,indent=2)+'\n```'])
    (ROOT/'results/local/CASE_REPORT.md').write_text('\n\n'.join(report)+'\n',encoding='utf-8')
    write(ROOT/'results/pilot_summary.json',{'selected':30,'recorded':len(data),'cohorts':summary,'pooled_accuracy':None,'GaRAGe_binary_accuracy':'NOT_MEASURABLE','review_independence':'No independent answer/support/fulfilment adjudication','test_outputs_used_for_tuning':False})
    events=rows(ROOT/'results/local/api_ledger.jsonl');attempts=[e for e in events if e['event']=='ATTEMPT'];results=[e for e in events if e['event']=='RESULT'];usage={}
    for kind in ['A','C1']:
        es=[e for e in results if e['kind']==kind];usage[kind]={'attempts':sum(e['kind']==kind for e in attempts),'input_tokens':sum(e['usage'].get('input_tokens',0) for e in es),'output_tokens':sum(e['usage'].get('output_tokens',0) for e in es),'provider_seconds':sum(e['usage'].get('provider_ms',0) for e in es)/1000,'provider_errors':dict(collections.Counter(e['status'] for e in es if e['status']!='SUCCESS')),'provider_reported_cached_input_tokens':sum((((e.get('response') or {}).get('usage') or {}).get('prompt_tokens_details') or {}).get('cached_tokens',0) or 0 for e in es)}
    totals={'attempts':len(attempts),'input_tokens':sum(e['usage'].get('input_tokens',0) for e in results),'output_tokens':sum(e['usage'].get('output_tokens',0) for e in results),'provider_seconds':sum(e['usage'].get('provider_ms',0) for e in results)/1000}
    local_ms=sum(max(0,r.get('elapsed_ms',0)-r.get('A_usage',{}).get('provider_ms',0)-r.get('C1',{}).get('usage',{}).get('provider_ms',0)) for r in data)
    write(ROOT/'api_usage.json',{'status':'COMPLETED','new_calls_only':True,'by_system':usage,'totals':totals,'B_extra_calls':0,'zero_call_C1_cases':sum(r.get('C1',{}).get('usage',{}).get('attempts')==0 for r in data),'summed_case_seconds':sum(r.get('elapsed_ms',0) for r in data)/1000,'measured_non_transport_case_seconds':local_ms/1000,'application_model_cache_hits':0,'optional_local_model_time_seconds':0,'optional_NLI_cold_warm_memory':'NOT_RUN_OPTIONAL_COMPONENT_NOT_IMPLEMENTED','renderer_ablation_new_calls':0,'SDK_retries':0,'maximum_C1_attempts_per_case':max(r.get('C1',{}).get('usage',{}).get('attempts',0) for r in data),'models_observed':sorted({e['usage'].get('model') for e in results if e['usage'].get('model')}),'elapsed_task_seconds_at_scoring':ensure(),'price_estimate':None})
    print(json.dumps({'cohort_mode_metrics':{d:{s:v['mode_accuracy'] for s,v in x['systems'].items()} for d,x in summary.items()},'ops':{d:{s:v['operational_errors'] for s,v in x['systems'].items()} for d,x in summary.items()},'usage':totals},indent=2))
if __name__=='__main__':score()
