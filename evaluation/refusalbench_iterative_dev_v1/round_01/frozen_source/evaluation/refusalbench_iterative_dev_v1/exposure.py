"""Metadata-only exposure reconstruction and bounded, seeded new-round sampling."""
import collections,hashlib,json,random,subprocess
from pathlib import Path
from evaluation.refusalbench_noncontradiction_v1.prepare_dataset import metadata_only,eligible,SOURCE,REVISION,QUOTAS,SEED,select_indices
from evaluation.refusalbench_span_fix_v1.api_budget import write_json,read_jsonl
from .deadline import ensure,snapshot
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def stable(value):return hashlib.sha256(str(value).encode()).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(',',':'))
def writel(path,rows):Path(path).write_text(''.join(canonical(r)+'\n' for r in rows),encoding='utf-8')
def atomic_ledger(ledger):
 path=ROOT/'exposure_ledger.json';tmp=path.with_suffix('.tmp');write_json(tmp,ledger);tmp.replace(path)

def original_id_strings(value):
 if isinstance(value,str) and value.startswith('RB-NQ_'):yield value
 elif isinstance(value,list):
  for v in value:yield from original_id_strings(v)
 elif isinstance(value,dict):
  for v in value.values():yield from original_id_strings(v)

def initialize():
 ensure('exposure reconstruction',60)
 if (ROOT/'exposure_ledger.json').exists():raise RuntimeError('Exposure ledger already exists; never reset it.')
 metadata=metadata_only(SOURCE);assert len(metadata)==1600
 previous_report=json.loads((REPO/'evaluation/refusalbench_noncontradiction_v1/filtering_report.json').read_text());assert sha(SOURCE)==previous_report['original_file_sha256']
 eligible_indices=[i for i,m in enumerate(metadata) if eligible(m)];assert len(eligible_indices)==1234
 held=json.loads((REPO/'evaluation/refusalbench_semantic_dev/reserved_holdout_manifest.json').read_text());reserved=set(held['reserved_source_groups'])
 previous_paths=['evaluation/refusalbench_pilot/cases.jsonl','evaluation/refusalbench_semantic_dev/development_cases.jsonl','evaluation/refusalbench_span_fix_v1/cases.jsonl','evaluation/refusalbench_noncontradiction_v1/selected_cases.jsonl']
 allowed=set();known=collections.defaultdict(set)
 for name in previous_paths:
  for row in read_jsonl(REPO/name):known[row['id']].add(name);allowed.add(str(row['source_id']))
 # Inspect all available local branch manifests (not reserved record texts).
 branches=subprocess.check_output(['git','for-each-ref','--format=%(refname:short)','refs/heads'],cwd=REPO,text=True).splitlines();audit=[]
 for branch in branches:
  files=subprocess.check_output(['git','ls-tree','-r','--name-only',branch,'--','evaluation'],cwd=REPO,text=True).splitlines()
  names=[n for n in files if '/refusalbench_' in n and n.endswith('.json') and any(token in Path(n).name for token in ['selection_manifest','dataset_provenance','experiment_manifest','generation_manifest','prerun_protocol']) and 'reserved' not in n]
  for name in names:
   data=json.loads(subprocess.check_output(['git','show',branch+':'+name],cwd=REPO));ids=set(original_id_strings(data));audit.append({'branch':branch,'manifest':name,'record_ids_found':len(ids)})
   for rid in ids:known[rid].add(branch+':'+name)
 byid={m['id']:(i,m) for i,m in enumerate(metadata)}
 missing=set(known)-set(byid)
 if missing:raise RuntimeError('Cannot reconstruct prior exposure: unknown IDs '+repr(sorted(missing)))
 assert len(allowed)==52 and len(reserved)==30 and not allowed&reserved
 allgroups={str(m['source_id']) for m in metadata};untouched=allgroups-allowed-reserved;assert len(untouched)==18
 entries=[]
 for rid,origins in sorted(known.items()):
  i,m=byid[rid]
  if str(m['source_id']) not in allowed:raise RuntimeError('Prior exposure outside authorized development groups; new sampling stopped.')
  entries.append({'id':rid,'record_hash':stable(rid),'dataset_index':i,'source_id':str(m['source_id']),'source_group_hash':stable(m['source_id']),'eligible':eligible(m),'first_exposure':'prior_experiment','origins':sorted(origins)})
 exposed_eligible=sum(e['eligible'] for e in entries)
 ledger={'dataset_revision':REVISION,'official_source_sha256':sha(SOURCE),'original_records':1600,'eligible_records':len(eligible_indices),'maximum_exposed_eligible_records':len(eligible_indices)//2,'prior_unique_exposed_records_all_categories':len(entries),'prior_exposed_unique_eligible_records':exposed_eligible,'newly_exposed_unique_eligible_records':0,'cumulative_exposed_eligible_records':exposed_eligible,'remaining_unseen_eligible_records':len(eligible_indices)-exposed_eligible,'allowed_development_source_groups':sorted(allowed),'reserved_source_groups':sorted(reserved),'untouched_source_groups':sorted(untouched),'reconstruction_status':'RECONCILED_ALL_AVAILABLE_BRANCH_MANIFESTS_AND_SELECTED_CASE_ARTIFACTS','manifest_inventory':audit,'record_exposure_definition':'Conservative: every earlier selected record counts, including failed/unexecuted selections; new IDs are charged before text materialization. Metadata-only filtering does not expose text.','entries':entries,'rounds':[],'last_updated':snapshot()}
 assert exposed_eligible<=ledger['maximum_exposed_eligible_records'];atomic_ledger(ledger)
 write_json(ROOT/'filtering_report.json',{**previous_report,'verified_eligible_count':len(eligible_indices),'prior_unique_exposed_all':len(entries),'prior_unique_exposed_eligible':exposed_eligible,'exposure_ceiling':ledger['maximum_exposed_eligible_records'],'metadata_only':True})
 print(json.dumps({k:ledger[k] for k in ['eligible_records','maximum_exposed_eligible_records','prior_unique_exposed_records_all_categories','prior_exposed_unique_eligible_records','remaining_unseen_eligible_records']}))
 return ledger


def sample(round_number,source_version):
 ensure('new round sampling',120)
 ledger=json.loads((ROOT/'exposure_ledger.json').read_text());metadata=metadata_only(SOURCE);assert sha(SOURCE)==ledger['official_source_sha256']
 out=ROOT/f'round_{round_number:02d}'
 if out.exists():raise RuntimeError('Round already exists.')
 used={e['id'] for e in ledger['entries']};allowed=set(ledger['allowed_development_source_groups']);seed=SEED+round_number-1
 indices,_=select_indices(metadata,allowed,used,seed)
 rows=[metadata[i] for i in indices];assert len({r['id'] for r in rows})==20
 if ledger['cumulative_exposed_eligible_records']+20>ledger['maximum_exposed_eligible_records']:raise RuntimeError('50% cumulative exposure ceiling blocks new materialization.')
 if any(not eligible(r) or str(r['source_id']) not in allowed for r in rows):raise RuntimeError('Invalid sampling boundary.')
 out.mkdir();write_json(out/'source_version.json',source_version)
 selected=[{'runtime_index':j,'dataset_index':i,'original_id':r['id'],'record_hash':stable(r['id']),'source_id':str(r['source_id']),'source_group_hash':stable(r['source_id']),'expected_behavior':r['expected_rag_behavior'],'round':round_number,'seed':seed} for j,(i,r) in enumerate(zip(indices,rows))]
 write_json(out/'selection_manifest.json',{'round':round_number,'seed':seed,'selection_frozen_at':snapshot(),'records':selected,'quota':QUOTAS,'source_groups':20,'new_record_ids':20,'source_version_sha256':sha(out/'source_version.json'),'selection_rule':'New IDs, exact 10/10 and 2/category quotas, seeded group matching, no performance-based choice.'})
 # Persistent exposure commit occurs BEFORE selected raw texts are decoded or saved.
 for i,m in zip(indices,rows):ledger['entries'].append({'id':m['id'],'record_hash':stable(m['id']),'dataset_index':i,'source_id':str(m['source_id']),'source_group_hash':stable(m['source_id']),'eligible':True,'first_exposure':f'round_{round_number:02d}','origins':[f'round_{round_number:02d}/selection_manifest.json']})
 ledger['newly_exposed_unique_eligible_records']+=20;ledger['cumulative_exposed_eligible_records']+=20;ledger['remaining_unseen_eligible_records']-=20;ledger['rounds'].append({'round':round_number,'seed':seed,'new_records':20,'selection_manifest_sha256':sha(out/'selection_manifest.json'),'charged_before_text_materialization':True});ledger['last_updated']=snapshot();atomic_ledger(ledger)
 wanted=set(indices);raw={}
 with SOURCE.open('rb') as handle:
  for i,line in enumerate(handle):
   if i in wanted:raw[i]=json.loads(line)
 cases=[raw[i] for i in indices];runtime=[{k:c[k] for k in ['perturbed_query','perturbed_context']} for c in cases]
 writel(out/'selected_cases.jsonl',cases);writel(out/'runtime_inputs.jsonl',runtime)
 write_json(out/'runtime_authorization.json',{'row_count':20,'selection_approved':True,'runtime_sha256':sha(out/'runtime_inputs.jsonl'),'rows':[{'runtime_index':i,'input_sha256':stable(canonical(r))} for i,r in enumerate(runtime)]})
 print(json.dumps({'round':round_number,'seed':seed,'selected':20,'cumulative_eligible_exposure':ledger['cumulative_exposed_eligible_records'],'ceiling':ledger['maximum_exposed_eligible_records']}))
 return out

if __name__=='__main__':initialize()
