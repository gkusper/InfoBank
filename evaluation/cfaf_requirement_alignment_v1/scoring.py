"""Scorer-only paired mode metrics and mechanism diagnostics; never imported by runtime."""
import collections,csv,json,re
from .artifacts import *
from . import integration as impl
from evaluation.cfaf_request_evidence_verification_v1.scoring import metric,reason_score
CONFIGS=['A0','B1','B2','B3']

def change_record(phase,index,config,before,after,truth,v,baseline,extra=None):
 prior=baseline['results']['B1'] if phase=='cached' else baseline['ablations']['B1'];strict=prior.get('strict_recv_reference') or {};strict_issues=strict.get('issues',[])
 mechanisms=[]
 if len(v['requirements_profile']['requirements'])!=len(v['requirements_profile']['legacy_requirements']):mechanisms.append('REQUIREMENT_DECOMPOSITION')
 if any(x.get('candidate_fragments') for x in v['alignment']['requirements']):mechanisms.append('ANSWER_FRAGMENT_ALIGNMENT')
 if not v['hard_failures'] and v['shadow_soft_warnings']:mechanisms.append('HARD_SOFT_CLASSIFICATION')
 return {'phase':phase,'index':index,'configuration':config,'before_A0':before,'after':after,'expected_mode':truth,'cause':v['change_cause'],'mechanisms_present':mechanisms,'strict_B1_issues':strict_issues,'incorrect_full_prevented':before=='FULL' and after=='CFAF' and truth=='CFAF','correct_full_lost':before=='FULL' and after=='CFAF' and truth=='FULL','hard_failures':v['hard_failures'],'soft_warnings':v['shadow_soft_warnings'],'causal_limit':'Decomposition/alignment repair representation. Removing semantic veto authority can independently restore the same mode; no unique decomposition accuracy effect is claimed.',**(extra or {})}

def score():
 cached=rows(ROOT/'cached_ablation_final.jsonl');observations=rows(ROOT/'pilot_observations.jsonl');gold={g['runtime_index']:g for g in rows(ROOT/'pilot_scorer_only.jsonl')};scored=[];changes=[];relative=[];diagnostics=[];states=collections.Counter();warnings=collections.Counter();hard=collections.Counter();mapping=collections.Counter();types=collections.Counter();source_states=collections.Counter();fragments=offsets=0;required=0
 for r in cached:
  for config in ['B1','B2','B3']:
   if r['predictions'][config]!=r['predictions']['A0']:changes.append(change_record('cached',r['index'],config,r['predictions']['A0'],r['predictions'][config],r['expected_mode'],r['results'][config],r,{'origin':r['origin'],'origin_index':r['origin_index']}))
  if r['predictions']['B3']!=r['predictions']['B1']:relative.append({'phase':'cached','index':r['index'],'origin':r['origin'],'origin_index':r['origin_index'],'B1':r['predictions']['B1'],'B3':r['predictions']['B3'],'expected_mode':r['expected_mode'],'restored_correct_full':r['expected_mode']=='FULL' and r['predictions']['B3']=='FULL','reintroduced_incorrect_full':r['expected_mode']=='CFAF' and r['predictions']['B3']=='FULL'})
  diagnostics.append({'phase':'cached','index':r['index'],'origin':r['origin'],'origin_index':r['origin_index'],'result':r['results']['B3']})
 for obs in observations:
  i=obs['runtime_index'];g=gold[i];outcomes=obs.get('outcomes',{});entry={'runtime_index':i,**g,'gate_predictions':dict(obs.get('gate_predictions',{})),'predictions':{},'reason_scoring':{},'validation_errors':{}}
  for config in CONFIGS+['shared_control']:
   o=outcomes.get('A0') if config in {'B2','shared_control'} else outcomes.get(config);system='shared_control' if config=='shared_control' else 'semantic_cfaf';response=(o or {}).get('responses',{}).get(system);errors=impl.validate_response(json.dumps(response)) if response else ['MISSING_RESPONSE'];errors+=list((o or {}).get('system_errors',{}).get(system,[]))
   if (o or {}).get('semantic_valid') is False:errors.append('INVALID_SEMANTIC_ASSESSMENT')
   pred=(obs.get('gate_predictions',{}).get(config) if config=='B2' else response.get('top_level_mode') if response else None) if not errors else None
   entry['predictions'][config]=pred;entry['validation_errors'][config]=errors;entry['reason_scoring'][config]=reason_score(g,response) if config!='B2' else {'assessable':False,'specific_category':None,'correct':None}
  if outcomes.get('A0',{}).get('semantic_valid') is False:entry['raw_gate_predictions']=dict(entry['gate_predictions']);entry['gate_predictions']={c:None for c in entry['gate_predictions']}
  if obs['status']=='SUCCESS':
   for config in ['B1','B2','B3']:
    if obs['gate_predictions'][config]!=obs['gate_predictions']['A0']:changes.append(change_record('live',i,config,obs['gate_predictions']['A0'],obs['gate_predictions'][config],g['expected_mode'],obs['ablations'][config],obs,{'original_id_scorer_only':g['original_id']}))
   if obs['gate_predictions']['B3']!=obs['gate_predictions']['B1']:relative.append({'phase':'live','index':i,'B1':obs['gate_predictions']['B1'],'B3':obs['gate_predictions']['B3'],'expected_mode':g['expected_mode'],'restored_correct_full':g['expected_mode']=='FULL' and obs['gate_predictions']['B3']=='FULL','reintroduced_incorrect_full':g['expected_mode']=='CFAF' and obs['gate_predictions']['B3']=='FULL'})
   diagnostics.append({'phase':'live','index':i,'result':obs['ablations']['B3']})
  scored.append(entry)
 for item in diagnostics:
  phase=item['phase'];v=item['result'];required+=len(v['coverage']['requirements'])
  for row in v['coverage']['requirements']:
   states[(phase,row['coverage_status'])]+=1;mapping[(phase,row['semantic_parent_mapping'])]+=1;types[(phase,str(row['type_compatible']))]+=1
   for fragment in row['candidate_fragments']:fragments+=1;offsets+=fragment.get('start') is not None
   warnings.update((phase,w['code']) for w in row['soft_warnings']);hard.update((phase,h['code']) for h in row['hard_failures'])
  for row in v['source_capabilities']:
   for c in row['sources']:source_states[(phase,c['capability_state'])]+=1
 result={'cached':{'n':len(cached),'systems':{c:metric([{'expected_mode':r['expected_mode'],'predictions':r['predictions']} for r in cached],c) for c in CONFIGS},'api_calls':0},'live':{'n':len(scored),'systems':{c:metric(scored,c) for c in CONFIGS+['shared_control']},'gate_only':{c:metric(scored,c,True) for c in CONFIGS},'by_dataset':{ds:{c:metric([r for r in scored if r['dataset']==ds],c) for c in CONFIGS+['shared_control']} for ds in sorted({r['dataset'] for r in scored})}},'coverage_states':{'|'.join(k):v for k,v in states.items()},'soft_warning_counts':{'|'.join(k):v for k,v in warnings.items()},'hard_violation_counts':{'|'.join(k):v for k,v in hard.items()},'semantic_mapping_counts':{'|'.join(k):v for k,v in mapping.items()},'fragment_type_counts':{'|'.join(k):v for k,v in types.items()},'source_capability_reference_counts':{'|'.join(k):v for k,v in source_states.items()},'alignment_consistency':{'fragments':fragments,'exact_offset_validated_prose_fragments':offsets,'independent_semantic_alignment_gold':False},'identified_requirement_elements':required,'B3_vs_B1_changes':relative,'B3_vs_A0_new_correct_full_losses':sum(c['correct_full_lost'] for c in changes if c['configuration']=='B3'),'B3_vs_A0_new_incorrect_full_preventions':sum(c['incorrect_full_prevented'] for c in changes if c['configuration']=='B3'),'causal_interpretation':'Semantic JSON, candidates and evidence IDs are identical within each paired comparison. Query decomposition, candidate-offset proposals and hard/soft classifications are recomputed. A hard/soft-only counterfactual can recover the same mode without proving decomposition alone caused accuracy changes. Cached/live overlap is not pooled as independent observations.','B4':'NOT_EXECUTED','optional_verifier_calls':0}
 for group in [result['cached']['systems'],result['live']['systems'],*result['live']['by_dataset'].values()]:
  for c,m in group.items():
   if group is result['cached']['systems'] or c=='B2':
    for key in ['structured_reason_assessable','structured_reason_correct','generic_or_uncategorized_refusals']:m[key]=None
    m['reason_note']='Gate-only; no separately generated public explanation.'
 write(ROOT/'ablation_results.json',result);write(ROOT/'pilot_scored_results.json',scored)
 for name,data in [('changed_decisions.jsonl',changes),('requirement_diagnostics.jsonl',diagnostics),('B3_vs_B1_changes.jsonl',relative)]:
  (ROOT/name).write_text('')
  for r in data:append(ROOT/name,r)
 fields=['phase','configuration','n','accuracy','balanced_accuracy','full_recall','cfaf_recall','unnecessary_refusal_count','unnecessary_refusal_rate','failure_to_restrict_count','failure_to_restrict_rate','errors','correct_matched_pairs','matched_pairs']
 with (ROOT/'ablation_summary.csv').open('w',newline='',encoding='utf-8') as f:
  writer=csv.DictWriter(f,fields);writer.writeheader()
  for phase in ['cached','live']:
   for config,m in result[phase]['systems'].items():writer.writerow({'phase':phase,'configuration':config,**{k:m[k] for k in fields if k in m}})
 print(json.dumps({p:{c:{k:m[k] for k in ['accuracy','balanced_accuracy','full_recall','cfaf_recall','errors']} for c,m in result[p]['systems'].items()} for p in ['cached','live']},indent=2));return result
if __name__=='__main__':score()
