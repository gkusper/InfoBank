"""Trusted 5+5 sampler restricted to the already exposed 42 development groups."""
import hashlib,json,os,random,subprocess
from collections import Counter,defaultdict
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[1]
REV='b3684f805563e6ce465e7e9b055b840a48f519c2';SEED=20261028

def dump(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
def jsonl(p,x):p.write_text(''.join(json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(',',':'))+'\n' for v in x),encoding='utf-8',newline='\n')
def main():
 if (HERE/'cases.jsonl').exists():raise RuntimeError('Selection already exists.')
 prev=REPO/'evaluation/refusalbench_semantic_dev'
 old=[json.loads(x) for x in (prev/'development_cases.jsonl').read_text().splitlines()]
 allowed={str(c['source_id']) for c in old};used={c['id'] for c in old}
 held=json.loads((prev/'reserved_holdout_manifest.json').read_text())
 assert len(allowed)==42 and not allowed&set(held['reserved_source_groups'])
 os.environ.setdefault('HF_HOME','C:/Users/EKKE/Documents/Codex/work/rb-hf')
 os.environ.setdefault('HF_DATASETS_CACHE','C:/Users/EKKE/Documents/Codex/work/rb-ds')
 os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING','1')
 from datasets import load_dataset
 ds=load_dataset('aashiqmuhamed/RefusalBench-NQ',split='test',revision=REV)
 metadata=list(ds.select_columns(['source_id','id','expected_rag_behavior']))
 eligible=[i for i,v in enumerate(metadata) if str(v['source_id']) in allowed and v['id'] not in used]
 rng=random.Random(SEED)
 cats=sorted({metadata[i]['expected_rag_behavior'] for i in eligible if metadata[i]['expected_rag_behavior'].startswith('REFUSE_')});rng.shuffle(cats)
 slots=['ANSWER_CORRECTLY']*5+cats[:5];rng.shuffle(slots)
 grouped=defaultdict(list)
 for i in eligible:grouped[metadata[i]['expected_rag_behavior'],str(metadata[i]['source_id'])].append(i)
 candidates={c:sorted({g for label,g in grouped if label==c}) for c in slots}
 for groups in candidates.values():rng.shuffle(groups)
 owners={};assignment={}
 def place(j,seen):
  for g in candidates[slots[j]]:
   if g in seen:continue
   seen.add(g)
   if g not in owners or place(owners[g],seen):owners[g]=j;assignment[j]=g;return True
  return False
 if len(slots)!=10 or not all(place(j,set()) for j in range(10)):raise RuntimeError('New-record, distinct-source design infeasible. No silent relaxation.')
 indices=[rng.choice(grouped[slots[j],assignment[j]]) for j in range(10)];rng.shuffle(indices)
 cases=list(ds.select(indices));runtime=[{k:c[k] for k in ['perturbed_query','perturbed_context']} for c in cases]
 assert len({str(c['source_id']) for c in cases})==10
 jsonl(HERE/'cases.jsonl',cases);jsonl(HERE/'runtime_inputs.jsonl',runtime)
 tracked=subprocess.check_output(['git','ls-files'],cwd=REPO,text=True).splitlines()
 dump(HERE/'protected_files.json',{n:hashlib.sha256((REPO/n).read_bytes()).hexdigest() for n in tracked})
 dump(HERE/'selection_manifest.json',{'dataset_revision':REV,'seed':SEED,'source_group_policy':'Only previous 42 development groups; no reserved or extra untouched group text selected',
  'records':[{'index':j,'dataset_index':i,'id':metadata[i]['id'],'source_id':str(metadata[i]['source_id']),'expected_label':metadata[i]['expected_rag_behavior'],'reused_record':metadata[i]['id'] in used} for j,i in enumerate(indices)],
  'counts':dict(Counter(c['expected_rag_behavior'] for c in cases)),'distinct_groups':10,'reused_records':0,
  'cases_sha256':hashlib.sha256((HERE/'cases.jsonl').read_bytes()).hexdigest(),'runtime_sha256':hashlib.sha256((HERE/'runtime_inputs.jsonl').read_bytes()).hexdigest()})
 print(json.dumps({'selected':10,'new_records':10,'distinct_existing_development_groups':10,'counts':dict(Counter(c['expected_rag_behavior'] for c in cases))}))
if __name__=='__main__':main()
