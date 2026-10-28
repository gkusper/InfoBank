"""Post-generation paired scoring and diagnostic coverage; no runtime gold access."""
import collections,csv,json
from .artifacts import *
from . import integration as impl
from .prepare import CONFIGS
from evaluation.cfaf_request_evidence_verification_v1.scoring import metric,reason_score

def score():
 cached=rows(ROOT/'cached_ablation_final.jsonl');observations=rows(ROOT/'pilot_observations.jsonl');gold={g['runtime_index']:g for g in rows(ROOT/'pilot_scorer_only.jsonl')};scored=[];changes=[];diagnostics=[]
 for r in cached:
  for config in CONFIGS:
   if r['predictions'][config]!=r['predictions']['B3']:changes.append({'phase':'cached','index':r['index'],'configuration':config,'before_B3':r['predictions']['B3'],'after':r['predictions'][config],'expected_mode':r['expected_mode'],'cause':'EXISTING_A0_VS_B3_DIFFERENCE' if config=='A0' else 'UNEXPECTED_SHADOW_CHANGE'})
  diagnostics.append({'phase':'cached','index':r['index'],'origin':r['origin'],'origin_index':r['origin_index'],'expected_mode':r['expected_mode'],'A0_prediction':r['predictions']['A0'],'target_claim':r['results']['T3']['target_claim'],'claim_only_reference_target':r['results']['T2']['target_claim']['target_used_for_claims'],'baseline_profile':r['results']['B3']['requirements_profile']})
 for r in observations:
  i=r['runtime_index'];g=gold[i];outcomes=r.get('outcomes',{});entry={'runtime_index':i,**g,'gate_predictions':dict(r.get('gate_predictions',{})),'predictions':{},'reason_scoring':{},'validation_errors':{}}
  for config in CONFIGS+['shared_control']:
   gate_only=config in {'B3','T1','T2'};o=outcomes.get('A0') if gate_only or config=='shared_control' else outcomes.get(config);system='shared_control' if config=='shared_control' else 'semantic_cfaf';response=(o or {}).get('responses',{}).get(system);errors=[]
   if (o or {}).get('semantic_valid') is False:errors.append('INVALID_UPSTREAM_SEMANTIC_ASSESSMENT')
   if r['status']!='SUCCESS':errors.append('PIPELINE_EXECUTION_ERROR')
   if not gate_only:
    errors+=impl.validate_response(json.dumps(response)) if response else ['MISSING_RESPONSE'];errors+=list((o or {}).get('system_errors',{}).get(system,[]))
   pred=(r.get('gate_predictions',{}).get(config) if gate_only else response.get('top_level_mode') if response else None) if not errors else None;entry['predictions'][config]=pred;entry['validation_errors'][config]=errors;entry['reason_scoring'][config]=reason_score(g,response) if not gate_only else {'assessable':False,'specific_category':None,'correct':None}
  if outcomes.get('A0',{}).get('semantic_valid') is False:entry['raw_gate_predictions']=dict(entry['gate_predictions']);entry['gate_predictions']={c:None for c in entry['gate_predictions']}
  if r['status']=='SUCCESS':
   for c in CONFIGS:
    if r['gate_predictions'][c]!=r['gate_predictions']['B3']:changes.append({'phase':'live','index':i,'configuration':c,'before_B3':r['gate_predictions']['B3'],'after':r['gate_predictions'][c],'expected_mode':g['expected_mode'],'cause':'EXISTING_A0_VS_B3_DIFFERENCE' if c=='A0' else 'UNEXPECTED_SHADOW_CHANGE'})
   diagnostics.append({'phase':'live','index':i,'expected_mode':g['expected_mode'],'A0_prediction':entry['predictions']['A0'],'target_claim':r['ablations']['T3']['target_claim'],'claim_only_reference_target':r['ablations']['T2']['target_claim']['target_used_for_claims'],'baseline_profile':r['ablations']['B3']['requirements_profile']})
  scored.append(entry)
 stats={}
 for phase in ['cached','live']:
  selected=[d for d in diagnostics if d['phase']==phase];states=collections.Counter();relations=collections.Counter();authorities=collections.Counter();warnings=collections.Counter();type_changes=[];refs=claims_count=metadata_matches=0;target_gain=[];target_loss=[];false_full_total=false_full_warned=false_full_lexical=correct_full_warned=0
  for d in selected:
   tc=d['target_claim'];target=tc['trusted_target'];states[target['state']]+=1
   if target['state']=='RESOLVED' and d['claim_only_reference_target']['state']!='RESOLVED':target_gain.append(d['index'])
   if target['state']!='RESOLVED' and d['claim_only_reference_target']['state']=='RESOLVED':target_loss.append(d['index'])
   before={r['requirement_id']:r for r in d['baseline_profile']['requirements']}
   for req in tc['typed_requirements_profile']['requirements']:
    if req['answer_type']!=before[req['requirement_id']]['answer_type']:type_changes.append({'index':d['index'],'requirement_id':req['requirement_id'],'before':before[req['requirement_id']]['answer_type'],'after':req['answer_type'],'access_class':req['access_class'],'attribute':req['requested_attribute']})
   claims=tc['claim_alignment']['claims'];any_warning=any(c['uncertainties'] for c in claims);lexical=any(c['relation_diagnostics']['missing_relation_anchors'] or c['relation_diagnostics']['unsupported_numeric_tokens'] for c in claims)
   if d['A0_prediction']=='FULL' and d['expected_mode']=='CFAF':false_full_total+=1;false_full_warned+=any_warning;false_full_lexical+=lexical
   if d['A0_prediction']=='FULL' and d['expected_mode']=='FULL':correct_full_warned+=any_warning
   for c in claims:
    claims_count+=1;relations[c['relation_status']]+=1;authorities[c['authority']]+=1;warnings.update(c['uncertainties']);refs+=len(c['supporting_spans']);metadata_matches+=c['metadata_binding']['status']=='FIELD_VALUE_MATCH'
  applicable=sum(v for k,v in states.items() if k!='NOT_APPLICABLE');stats[phase]={'case_count':len(selected),'target_states':dict(states),'resolved_rate_all_cases':states['RESOLVED']/len(selected) if selected else None,'resolved_rate_applicable':states['RESOLVED']/applicable if applicable else None,'ambiguous_rate_applicable':states['AMBIGUOUS']/applicable if applicable else None,'newly_resolved_vs_existing_binding_indices':target_gain,'no_longer_resolved_vs_existing_binding_indices':target_loss,'claim_record_count':claims_count,'all_requirements_have_claim_record':all(len(d['target_claim']['typed_requirements_profile']['requirements'])==len(d['target_claim']['claim_alignment']['claims']) for d in selected),'relation_status_counts':dict(relations),'authority_counts':dict(authorities),'uncertainty_counts':dict(warnings),'scoped_reference_occurrences':refs,'trusted_metadata_candidate_matches':metadata_matches,'type_representation_changes':type_changes,'label_incompatible_FULL_cases':false_full_total,'label_incompatible_FULL_with_any_diagnostic':false_full_warned,'label_incompatible_FULL_with_new_lexical_relation_or_numeric_alert':false_full_lexical,'correct_FULL_with_any_diagnostic':correct_full_warned,'semantic_alignment_correctness':'NOT_INDEPENDENTLY_ANNOTATED; token/reference linkage is not entailment'}
 result={'cached':{'n':len(cached),'systems':{c:metric([{'expected_mode':r['expected_mode'],'predictions':r['predictions']} for r in cached],c) for c in CONFIGS},'model_calls':0},'live':{'n':len(scored),'systems':{c:metric(scored,c) for c in CONFIGS+['shared_control']},'gate_only':{c:metric(scored,c,True) for c in CONFIGS},'by_dataset':{ds:{c:metric([r for r in scored if r['dataset']==ds],c) for c in CONFIGS+['shared_control']} for ds in sorted({r['dataset'] for r in scored})}},'target_claim_metrics':stats,'changed_gate_decisions':len(changes),'correct_FULL_lost_T3_vs_B3':sum(r['predictions'].get('B3')=='FULL' and r['predictions'].get('T3')=='CFAF' and r['expected_mode']=='FULL' for r in scored),'incorrect_FULL_prevented_T3_vs_B3':sum(r['predictions'].get('B3')=='FULL' and r['predictions'].get('T3')=='CFAF' and r['expected_mode']=='CFAF' for r in scored),'T4':'NOT_EXECUTED','causal_interpretation':'T1-T3 are shadow-only. Type correction is separately recorded, does not alter model payloads or gate authority. No accuracy effect is attributed to lexical diagnostics or target binding. Cached/live samples overlap and are not pooled as independent observations.'}
 for group in [result['cached']['systems'],result['live']['systems'],*result['live']['by_dataset'].values()]:
  for c,m in group.items():
   if group is result['cached']['systems'] or c in {'B3','T1','T2'}:
    for key in ['structured_reason_assessable','structured_reason_correct','generic_or_uncategorized_refusals']:m[key]=None
    m['reason_note']='No separate live public response was generated for this gate-only configuration.'
 write(ROOT/'ablation_results.json',result);write(ROOT/'pilot_scored_results.json',scored)
 for name,data in [('changed_decisions.jsonl',changes),('target_claim_diagnostics.jsonl',diagnostics)]:
  (ROOT/name).write_text('',encoding='utf-8')
  for r in data:append(ROOT/name,r)
 fields=['phase','configuration','n','accuracy','balanced_accuracy','full_recall','cfaf_recall','unnecessary_refusal_count','unnecessary_refusal_rate','failure_to_restrict_count','failure_to_restrict_rate','errors','correct_matched_pairs','matched_pairs']
 with (ROOT/'ablation_summary.csv').open('w',newline='',encoding='utf-8') as f:
  writer=csv.DictWriter(f,fields);writer.writeheader()
  for phase in ['cached','live']:
   for c,m in result[phase]['systems'].items():writer.writerow({'phase':phase,'configuration':c,**{k:m[k] for k in fields if k in m}})
 print(json.dumps({p:{c:{k:m[k] for k in ['accuracy','balanced_accuracy','full_recall','cfaf_recall','errors']} for c,m in result[p]['systems'].items()} for p in ['cached','live']},indent=2));return result
if __name__=='__main__':score()
