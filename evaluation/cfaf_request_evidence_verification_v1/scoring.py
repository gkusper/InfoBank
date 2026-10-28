"""Post-observation scoring, disjoint from runtime and model payload construction."""
import collections,csv,json,re
from .artifacts import *
from evaluation.refusalbench_semantic_dev.scoring import refusal_category
from . import integration as impl

def metric(records,system,gate=False):
 confusion={t:{p:0 for p in ['FULL','CFAF','ERROR']} for t in ['FULL','CFAF']};reason_known=reason_right=generic=0
 for r in records:
  pred=(r['gate_predictions'] if gate else r['predictions']).get(system);confusion[r['expected_mode']][pred if pred in {'FULL','CFAF'} else 'ERROR']+=1
  if not gate and r['expected_mode']=='CFAF':
   reason=r.get('reason_scoring',{}).get(system,{})
   if pred=='CFAF' and reason.get('assessable'):reason_known+=1;reason_right+=reason.get('correct') is True
   if pred=='CFAF' and not reason.get('specific_category'):generic+=1
 n=len(records);nfull=sum(confusion['FULL'].values());ncf=sum(confusion['CFAF'].values());full=confusion['FULL']['FULL']/nfull if nfull else None;cf=confusion['CFAF']['CFAF']/ncf if ncf else None
 pairgroups=collections.defaultdict(list)
 for r in records:
  if r.get('matched_pair'):pairgroups[r['matched_pair']].append(r)
 pairs=[g for g in pairgroups.values() if len(g)==2];contrasting=[g for g in pairs if len({r['expected_mode'] for r in g})==2];p5=[g for g in pairs if all(r['expected_mode']=='CFAF' for r in g)]
 def pair_correct(g):return all((r['gate_predictions'] if gate else r['predictions']).get(system)==r['expected_mode'] for r in g)
 return {'n':n,'accuracy':(confusion['FULL']['FULL']+confusion['CFAF']['CFAF'])/n if n else None,'balanced_accuracy':(full+cf)/2 if full is not None and cf is not None else None,'full_recall':full,'cfaf_recall':cf,'unnecessary_refusal_count':confusion['FULL']['CFAF'],'unnecessary_refusal_rate':confusion['FULL']['CFAF']/nfull if nfull else None,'failure_to_restrict_count':confusion['CFAF']['FULL'],'failure_to_restrict_rate':confusion['CFAF']['FULL']/ncf if ncf else None,'errors':sum(confusion[t]['ERROR'] for t in confusion),'confusion':confusion,'matched_pairs':len(pairs),'correct_matched_pairs':sum(pair_correct(g) for g in pairs),'contrasting_pairs':len(contrasting),'correct_contrasting_pairs':sum(pair_correct(g) for g in contrasting),'p5_nondisclosure_pairs':len(p5),'correct_p5_pairs':sum(pair_correct(g) for g in p5),'structured_reason_assessable':reason_known,'structured_reason_correct':reason_right,'generic_or_uncategorized_refusals':generic,'reason_note':'RB category proxy is lexical; InfoBank class uses original construction labels. Neither proves explanation entailment.'}

def reason_score(gold,response):
 if not response or response.get('top_level_mode')!='CFAF':return {'assessable':False,'specific_category':None,'correct':None}
 if gold['dataset'].startswith('InfoBank'):return {'assessable':True,'specific_category':response.get('public_reason_class'),'correct':response.get('public_reason_class')==gold.get('expected_public_reason_class')}
 text=response.get('answer','');category='REFUSE_FALSE_PREMISE_IN_QUERY' if re.search(r'unsupported premise|premise.{0,35}(?:not established|not supported)',text,re.I) else refusal_category(text)
 return {'assessable':category is not None,'specific_category':category,'correct':category==gold['expected_label'] if category else None}

def score():
 cached=rows(ROOT/'cached_ablation_final.jsonl');gold={g['runtime_index']:g for g in rows(ROOT/'pilot_scorer_only.jsonl')};live=[];changes=[];diagnostics=[];rules=collections.Counter();states=collections.Counter();source_states=collections.Counter();causes=collections.Counter()
 for r in cached:
  for config in ['A1','A2','B']:
   if r['predictions'][config]!=r['predictions']['A0']:
    v=r['results'][config];changes.append({'phase':'cached','index':r['index'],'origin':r['origin'],'origin_index':r['origin_index'],'configuration':config,'before':r['predictions']['A0'],'after':r['predictions'][config],'expected_mode':r['expected_mode'],'cause':v['change_cause'],'incorrect_full_prevented':r['expected_mode']=='CFAF','correct_full_lost':r['expected_mode']=='FULL','unsatisfied_requirements':[x for x in v['coverage']['requirements'] if x['coverage_status']!='COVERED'],'source_rules':[x for x in v['source_capabilities'] if x['blocked']]})
  v=r['results']['B'];diagnostics.append({'phase':'cached','index':r['index'],'origin':r['origin'],'origin_index':r['origin_index'],'coverage':v['coverage'],'source_capabilities':v['source_capabilities']})
 optional={r['runtime_index']:r for r in rows(ROOT/'optional_observations.jsonl')} if (ROOT/'optional_observations.jsonl').exists() else {}
 for r in rows(ROOT/'pilot_observations.jsonl'):
  i=r['runtime_index'];g=gold[i];outcomes=r.get('outcomes',{});entry={'runtime_index':i,**g,'gate_predictions':r.get('gate_predictions',{}),'predictions':{},'reason_scoring':{},'validation_errors':{}}
  for config in ['A0','A1','A2','B','shared_control']+(['C'] if optional else []):
   o=outcomes.get('A0') if config in {'A0','A1','A2','shared_control'} else outcomes.get('B') if config=='B' else optional.get(i,{}).get('outcome')
   system='shared_control' if config=='shared_control' else 'semantic_cfaf';response=(o or {}).get('responses',{}).get(system);errors=[]
   if response:errors=impl.validate_response(json.dumps(response))+list(o.get('system_errors',{}).get(system,[]))
   else:errors=['MISSING_RESPONSE']
   if (o or {}).get('semantic_valid') is False:errors.append('INVALID_SEMANTIC_ASSESSMENT')
   if config=='C' and optional.get(i,{}).get('status')=='ERROR':errors.append('FOCUSED_EXECUTION_ERROR')
   pred=(r.get('gate_predictions',{}).get(config) if config in {'A1','A2'} else response.get('top_level_mode') if response else None) if not errors else None
   entry['predictions'][config]=pred;entry['validation_errors'][config]=errors;entry['reason_scoring'][config]=reason_score(g,response) if config not in {'A1','A2'} else {'assessable':False,'specific_category':None,'correct':None}
  if optional:
   entry['gate_predictions']['C']=(optional.get(i,{}).get('outcome') or {}).get('selected_mode')
  if outcomes.get('A0',{}).get('semantic_valid') is False:
   entry['raw_gate_predictions']=dict(entry['gate_predictions']);entry['gate_predictions']={c:None for c in entry['gate_predictions']}
  for config in ['A1','A2','B']:
   if r.get('gate_predictions',{}).get(config)!=r.get('gate_predictions',{}).get('A0'):
    v=r['ablations'][config];changes.append({'phase':'live','index':i,'original_id_scorer_only':g['original_id'],'configuration':config,'before':r['gate_predictions']['A0'],'after':r['gate_predictions'][config],'expected_mode':g['expected_mode'],'cause':v['change_cause'],'incorrect_full_prevented':g['expected_mode']=='CFAF','correct_full_lost':g['expected_mode']=='FULL','unsatisfied_requirements':[x for x in v['coverage']['requirements'] if x['coverage_status']!='COVERED'],'source_rules':[x for x in v['source_capabilities'] if x['blocked']]})
  if r['status']=='SUCCESS':
   v=r['ablations']['B'];diagnostics.append({'phase':'live','index':i,'coverage':v['coverage'],'source_capabilities':v['source_capabilities']})
  live.append(entry)
 for d in diagnostics:
  for r in d['coverage']['requirements']:states[(d['phase'],r['coverage_status'])]+=1;rules.update((d['phase'],x) for x in r['reason_codes'])
  for r in d['source_capabilities']:
   for c in r['sources']:source_states[(d['phase'],c['capability_state'])]+=1
 for ch in changes:causes[(ch['phase'],ch['configuration'],ch['cause'])]+=1
 summary={'cached':{'case_count':len(cached),'systems':{c:metric([{'expected_mode':r['expected_mode'],'predictions':r['predictions']} for r in cached],c) for c in ['A0','A1','A2','B']},'zero_model_calls':True},'live':{'case_count':len(live),'systems':{c:metric(live,c) for c in ['A0','A1','A2','B','shared_control']+(['C'] if optional else [])},'gate_only':{c:metric(live,c,True) for c in ['A0','A1','A2','B']+(['C'] if optional else [])},'by_dataset':{ds:{c:metric([r for r in live if r['dataset']==ds],c) for c in ['A0','A1','A2','B','shared_control']+(['C'] if optional else [])} for ds in sorted({r['dataset'] for r in live})}},'coverage_counts':{'|'.join(k):v for k,v in states.items()},'rule_failure_counts':{'|'.join(k):v for k,v in rules.items()},'source_capability_reference_counts':{'|'.join(k):v for k,v in source_states.items()},'changed_decision_causes':{'|'.join(k):v for k,v in causes.items()},'interpretation':'Two separate development analyses; overlapping cases are never pooled as independent observations. A1/A2 have gate metrics only; live public generations are A0/B/control and conditionally C.'}
 for group in [summary['cached']['systems'],summary['live']['systems'],*summary['live']['by_dataset'].values()]:
  for config,m in group.items():
   if group is summary['cached']['systems'] or config in {'A1','A2'}:
    for key in ['structured_reason_assessable','structured_reason_correct','generic_or_uncategorized_refusals']:m[key]=None
    m['reason_note']='Not measured in this gate-only ablation; no new public response was generated.'
 write(ROOT/'ablation_results.json',summary);write(ROOT/'pilot_scored_results.json',live)
 for filename,data in [('changed_decisions.jsonl',changes),('coverage_diagnostics.jsonl',diagnostics)]:
  path=ROOT/filename;path.write_text('',encoding='utf-8')
  for r in data:append(path,r)
 fields=['phase','configuration','n','accuracy','balanced_accuracy','full_recall','cfaf_recall','unnecessary_refusal_count','unnecessary_refusal_rate','failure_to_restrict_count','failure_to_restrict_rate','errors','correct_matched_pairs','matched_pairs']
 with (ROOT/'ablation_summary.csv').open('w',newline='',encoding='utf-8') as f:
  writer=csv.DictWriter(f,fields);writer.writeheader()
  for phase in ['cached','live']:
   for config,m in summary[phase]['systems'].items():writer.writerow({'phase':phase,'configuration':config,**{k:m[k] for k in fields if k in m}})
 print(json.dumps({phase:{c:{k:m[k] for k in ['accuracy','full_recall','cfaf_recall','errors']} for c,m in summary[phase]['systems'].items()} for phase in ['cached','live']},indent=2));return summary
if __name__=='__main__':score()
