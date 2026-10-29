"""Predeclared paper-diverse random test sample; no output-based exclusions."""
import random,collections,hashlib,time
from .artifacts import *
def choose(pool,n,seed=20261029):
 if n==0:return [],True
 rng=random.Random(seed);classes=['FULL','CFAF'];by={m:collections.defaultdict(list) for m in classes}
 for m in classes:
  for r in pool[m]:by[m][r['paper_id']].append(r)
 sets={m:set(by[m]) for m in classes};unique=all(len(sets[m])>=n for m in classes) and len(set.union(*sets.values()))>=2*n;chosen={}
 if unique:
  first,second=sorted(classes,key=lambda m:(len(sets[m]),m));order=sorted(sets[first]);rng.shuffle(order);selected=[]
  for pid in order:
   if len(sets[second]-set(selected)-{pid})>=n:selected.append(pid)
   if len(selected)==n:break
  assert len(selected)==n;rest=sorted(sets[second]-set(selected));rng.shuffle(rest);paperlists={first:selected,second:rest[:n]}
  for m in classes:chosen[m]=[rng.choice(sorted(by[m][pid],key=lambda r:r['question_id'])) for pid in paperlists[m]]
 else:
  for m in classes:chosen[m]=rng.sample(sorted(pool[m],key=lambda r:(r['paper_id'],r['question_id'])),n)
 return [r for m in classes for r in chosen[m]],unique

def select():
 from .runner import verify_frozen
 verify_frozen();ensure();assert not (ROOT/'SAMPLE_MANIFEST.json').exists();state=read(ROOT/'task_state.json');primary=Path(state['primary_repo']);excluded_papers=set();excluded_ids=set();exposure_sources=[]
 for path in ['evaluation/cfaf_qasper_pilot_v1/DATASET3_SELECTION_MANIFEST.json','evaluation/cfaf_qasper_improvement_v2/DATASET3_SELECTION_MANIFEST.json']:
  manifest=read(primary/path);excluded_papers.update(r['paper_id'] for r in manifest['records']);excluded_ids.update(r['question_id'] for r in manifest['records']);exposure_sources.append({'path':path,'sha256':sha(primary/path)})
 metadata=rows(ROOT/'local/eligibility_metadata.jsonl');eligible=[r for r in metadata if r['mode']!='UNKNOWN' and r['paper_id'] not in excluded_papers and r['question_id'] not in excluded_ids];pm={m:[r for r in eligible if r['mode']==m and r['tier']=='M'] for m in ['FULL','CFAF']};primary_M=all(len(pm[m])>=40 and len({r['paper_id'] for r in pm[m]})>=40 for m in pm);pool=pm if primary_M else {m:[r for r in eligible if r['mode']==m] for m in pm};n=min(40,*[len(rs) for rs in pool.values()]);selected,unique=choose(pool,n);papers=read(ROOT/'datasets/qasper-test-v0.3.json');qmap={q['question_id']:(pid,q) for pid,p in papers.items() for q in p['qas']};records=[]
 for i,r in enumerate(selected):
  pid,q=qmap[r['question_id']];paper={k:v for k,v in papers[pid].items() if k!='qas'};h=hashlib.sha256(canonical({'paper_id':pid,'question':q,'paper':paper}).encode()).hexdigest();meta={'runtime_index':i,'paper_id':pid,'question_id':q['question_id'],'split':'test','derived_gold_mode':r['mode'],'annotation_tier':r['tier'],'original_annotation_count':r['annotation_count'],'stable_record_sha256':h};records.append(meta);append(ROOT/'local/selected_originals.jsonl',{'runtime_index':i,'paper_id':pid,'paper':paper,'question':q,'derived_gold_mode':r['mode'],'annotation_tier':r['tier']})
 write(ROOT/'SAMPLE_MANIFEST.json',{'dataset':'Dataset3 – QASPER','source_version':'0.3','source_test_sha256':read(ROOT/'SOURCE_PROVENANCE.json')['test_member']['sha256'],'seed':20261029,'selected_at_epoch':time.time(),'selected_after_code_freeze':True,'code_manifest_sha256':sha(ROOT/'EXPERIMENT_MANIFEST.json'),'primary_pool':'Tier M' if primary_M else 'Tier M + Tier S','class_counts_eligible_pool':{m:len(rs) for m,rs in pool.items()},'excluded_prior_dev_papers':sorted(excluded_papers),'test_questions_excluded_for_prior_dev_overlap':sum(r['paper_id'] in excluded_papers or r['question_id'] in excluded_ids for r in metadata),'N_per_class':n,'N_selected':2*n,'sample_size_reduced':n<40,'globally_distinct_papers_feasible_and_used':unique,'distinct_selected_papers':len({r['paper_id'] for r in records}),'sampling_design':'Preregistered randomized paper-first allocation reserving N other-class papers, then uniform question within paper; question-stratified fallback only if unique allocation infeasible','records':records})
 write(ROOT/'EXPOSURE_LEDGER.json',{'dataset':'Dataset3 – QASPER','split':'test','new_selected_charged':len(records),'selected_ids':[r['question_id'] for r in records],'selected_papers':sorted({r['paper_id'] for r in records}),'prior_dev_manifest_sources':exposure_sources,'prior_dev_question_count':len(excluded_ids),'prior_dev_paper_count':len(excluded_papers),'new_test_question_or_paper_overlap_with_dev':0,'all_selected_exposed_even_if_run_fails':True,'sample_manifest_sha256':sha(ROOT/'SAMPLE_MANIFEST.json'),'other_ledgers_modified':False})
 print('SELECTED',len(records),'cases;',n,'per class; primary',('M' if primary_M else 'M+S'),'; distinct papers',len({r['paper_id'] for r in records}),'; overlap excluded',sum(r['paper_id'] in excluded_papers for r in metadata))
if __name__=='__main__':select()
