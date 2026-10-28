"""Trusted annotation-only filtering/sampling; execution never imports this module."""
from __future__ import annotations
import argparse,hashlib,json,random,re,subprocess
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1]
REVISION='b3684f805563e6ce465e7e9b055b840a48f519c2';SEED=20261028
SOURCE=Path('C:/Users/EKKE/Documents/Codex/work/rb-hf/hub/datasets--aashiqmuhamed--RefusalBench-NQ/snapshots')/REVISION/'refusalbench-nq.jsonl'
REFUSALS=['REFUSE_AMBIGUOUS_QUERY','REFUSE_INFO_MISSING_IN_CONTEXT','REFUSE_FALSE_PREMISE_IN_QUERY','REFUSE_GRANULARITY_MISMATCH','REFUSE_NONFACTUAL_QUERY']
QUOTAS={'ANSWER_CORRECTLY':10,**{c:2 for c in REFUSALS}}


def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=True,separators=(',',':'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,obj):Path(path).write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n',encoding='utf-8')
def readl(path):return [json.loads(x) for x in Path(path).read_text(encoding='utf-8').splitlines() if x]
def writel(path,rows):Path(path).write_text(''.join(canonical(x)+'\n' for x in rows),encoding='utf-8')
def filter_a(record):return bool(re.search(r'\bcontradiction\b',record.get('implementation_reasoning') or '',re.I))
def filter_b(record):return record.get('expected_rag_behavior')=='REFUSE_CONTRADICTORY_CONTEXT' or record.get('perturbation_class')=='P-Contradiction'
def eligible(record):return not (filter_a(record) or filter_b(record))


def boundaries():
 previous=[REPO/'evaluation/refusalbench_pilot/cases.jsonl',REPO/'evaluation/refusalbench_semantic_dev/development_cases.jsonl',REPO/'evaluation/refusalbench_span_fix_v1/cases.jsonl']
 # Only manifests/selected old development rows, never reserved passage text.
 seen=[r for path in previous for r in readl(path)]
 allowed={str(r['source_id']) for r in seen};used={r['id'] for r in seen}
 held_path=REPO/'evaluation/refusalbench_semantic_dev/reserved_holdout_manifest.json';held=json.loads(held_path.read_text());reserved=set(held['reserved_source_groups'])
 assert len(allowed)==52 and len(reserved)==30 and not allowed&reserved
 return allowed,used,reserved,{p.relative_to(REPO).as_posix():sha(p) for p in previous+[held_path]}


def metadata_only(path):
 import pyarrow as pa
 import pyarrow.json as paj
 # Explicit schema ignores query/context/answers and verifier fields. Those strings
 # are never materialized as Python objects for reserved or untouched groups.
 schema=pa.schema([(k,pa.string()) for k in ['id','source_id','expected_rag_behavior','implementation_reasoning','perturbation_class']])
 return paj.read_json(path,parse_options=paj.ParseOptions(explicit_schema=schema,unexpected_field_behavior='ignore')).to_pylist()


def select_indices(metadata,allowed,used,seed=SEED):
 pool=[i for i,m in enumerate(metadata) if eligible(m) and str(m['source_id']) in allowed and m['id'] not in used]
 rng=random.Random(seed);slots=[label for label,n in QUOTAS.items() for _ in range(n)];rng.shuffle(slots)
 grouped=defaultdict(list)
 for i in pool:grouped[metadata[i]['expected_rag_behavior'],str(metadata[i]['source_id'])].append(i)
 candidates={label:sorted({g for c,g in grouped if c==label}) for label in QUOTAS}
 for values in candidates.values():rng.shuffle(values)
 owners={};assignment={}
 def place(slot,visited):
  for group in candidates[slots[slot]]:
   if group in visited:continue
   visited.add(group)
   if group not in owners or place(owners[group],visited):owners[group]=slot;assignment[slot]=group;return True
  return False
 if not all(place(j,set()) for j in range(len(slots))):raise RuntimeError('Exact new-record 20-distinct-development-source quota infeasible. No boundary relaxation.')
 indices=[rng.choice(sorted(grouped[slots[j],assignment[j]])) for j in range(len(slots))];rng.shuffle(indices)
 assert len(indices)==20 and len({metadata[i]['source_id'] for i in indices})==20
 return indices,pool


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,default=SOURCE);args=parser.parse_args();path=args.source
 if any((ROOT/name).exists() for name in ['selected_cases.jsonl','runtime_inputs.jsonl','filtered_selection_manifest.json']):raise RuntimeError('Refusing to overwrite frozen selection.')
 original_sha=sha(path);metadata=metadata_only(path);assert len(metadata)==1600
 allowed,used,reserved,prior_hashes=boundaries();indices,pool=select_indices(metadata,allowed,used)
 aset={i for i,m in enumerate(metadata) if filter_a(m)};bset={i for i,m in enumerate(metadata) if filter_b(m)};retained=[i for i,m in enumerate(metadata) if eligible(m)];allgroups={str(m['source_id']) for m in metadata};remaining=[metadata[i] for i in retained]
 related={word:{'records':sum(bool(re.search(r'\b'+word+r'\b',m.get('implementation_reasoning') or '',re.I)) for m in metadata),'occurrences':sum(len(re.findall(r'\b'+word+r'\b',m.get('implementation_reasoning') or '',re.I)) for m in metadata),'eligible_records':sum(bool(re.search(r'\b'+word+r'\b',metadata[i].get('implementation_reasoning') or '',re.I)) for i in retained)} for word in ['contradictory','contradictions','conflict']}
 report={'dataset':'aashiqmuhamed/RefusalBench-NQ','revision':REVISION,'split':'test','original_records':len(metadata),'original_file':str(path),'original_file_sha256':original_sha,'filter_A_exact_rule':r'(?i)\bcontradiction\b in implementation_reasoning','filter_A_excluded':len(aset),'filter_B_exact_rule':'expected_rag_behavior == REFUSE_CONTRADICTORY_CONTEXT OR perturbation_class == P-Contradiction','filter_B_excluded':len(bset),'A_B_overlap':len(aset&bset),'A_only':len(aset-bset),'B_only':len(bset-aset),'total_excluded_union':len(aset|bset),'eligible_records':len(retained),'eligible_FULL':sum(m['expected_rag_behavior']=='ANSWER_CORRECTLY' for m in remaining),'eligible_CFAF':sum(m['expected_rag_behavior'].startswith('REFUSE_') for m in remaining),'eligible_counts_by_original_behavior':dict(Counter(m['expected_rag_behavior'] for m in remaining)),'source_groups_before':len(allgroups),'source_groups_after':len({m['source_id'] for m in remaining}),'related_word_audit_only':related,'already_exposed_development_groups':len(allowed),'reserved_holdout_groups':len(reserved),'additional_untouched_groups':len(allgroups-allowed-reserved),'eligible_unused_development_records':len(pool),'eligible_unused_development_counts':dict(Counter(metadata[i]['expected_rag_behavior'] for i in pool)),'prior_executed_record_ids':len(used),'filtering_scope':'Global annotation-only preparation. No reserved/untouched query/context/answer text materialized, emitted or executed.'}
 selected_metadata=[{'runtime_index':j,'dataset_index':i,'id':metadata[i]['id'],'source_id':str(metadata[i]['source_id']),'expected_rag_behavior':metadata[i]['expected_rag_behavior'],'new_record':metadata[i]['id'] not in used} for j,i in enumerate(indices)]
 manifest={'dataset_revision':REVISION,'seed':SEED,'source_file_sha256':original_sha,'selected_records':selected_metadata,'target_quotas':QUOTAS,'distinct_source_groups':20,'reused_records':0,'reserved_source_intersection':[],'untouched_source_intersection':[],'group_uniqueness_relaxed':False,'selection_algorithm':'Seeded category-slot/source-group bipartite augmenting-path matching; seeded within-group new-record choice and final shuffle. No passage text or model performance used.','allowed_development_source_groups':sorted(allowed),'prior_manifest_checksums':prior_hashes,'eligible_indices_global':retained}
 # Freeze ID selection BEFORE decoding selected passage text.
 dump(ROOT/'filtering_report.json',report);dump(ROOT/'filtered_selection_manifest.json',manifest)
 wanted=set(indices);selected={}
 with path.open('rb') as handle:
  for i,line in enumerate(handle):
   if i in wanted:selected[i]=json.loads(line)
 cases=[selected[i] for i in indices];runtime=[{k:c[k] for k in ['perturbed_query','perturbed_context']} for c in cases]
 assert all(eligible(c) and str(c['source_id']) in allowed and str(c['source_id']) not in reserved and c['id'] not in used for c in cases)
 assert Counter(c['expected_rag_behavior'] for c in cases)==Counter(QUOTAS)
 writel(ROOT/'selected_cases.jsonl',cases);writel(ROOT/'runtime_inputs.jsonl',runtime)
 dump(ROOT/'runtime_authorization.json',{'runtime_sha256':sha(ROOT/'runtime_inputs.jsonl'),'row_count':20,'rows':[{'runtime_index':j,'input_sha256':hashlib.sha256(canonical(row).encode()).hexdigest()} for j,row in enumerate(runtime)],'selection_approved':True,'purpose':'No original IDs, labels or reserved metadata are exposed to execution.'})
 manifest.update(selected_cases_sha256=sha(ROOT/'selected_cases.jsonl'),runtime_sha256=sha(ROOT/'runtime_inputs.jsonl'));dump(ROOT/'filtered_selection_manifest.json',manifest)
 tracked=subprocess.check_output(['git','ls-files'],cwd=REPO,text=True).splitlines();dump(ROOT/'protected_files.json',{n:sha(REPO/n) for n in tracked})
 assert sha(path)==original_sha
 print(json.dumps({k:report[k] for k in ['original_records','filter_A_excluded','filter_B_excluded','A_B_overlap','total_excluded_union','eligible_records','eligible_FULL','eligible_CFAF','source_groups_before','source_groups_after','eligible_unused_development_records']}));print('Selection frozen: 20 distinct already exposed development groups; all 20 record IDs new; 10 FULL + 10 CFAF.')
if __name__=='__main__':main()
