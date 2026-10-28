"""Trusted sampler: only this process sees labels and source-group metadata.

Reserve holdout groups using metadata before projecting any development text.
No holdout query, context, explanation, or answer is emitted or inspected.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DATASET = 'aashiqmuhamed/RefusalBench-NQ'
REVISION = 'b3684f805563e6ce465e7e9b055b840a48f519c2'
SEED = 20261028
CATEGORIES = [
    'ANSWER_CORRECTLY', 'REFUSE_AMBIGUOUS_QUERY', 'REFUSE_INFO_MISSING_IN_CONTEXT',
    'REFUSE_CONTRADICTORY_CONTEXT', 'REFUSE_FALSE_PREMISE_IN_QUERY',
    'REFUSE_GRANULARITY_MISMATCH', 'REFUSE_NONFACTUAL_QUERY',
]


def canonical(obj):
    return json.dumps(obj,ensure_ascii=True,sort_keys=True,separators=(',',':'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path,obj):
    path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')


def write_jsonl(path,rows):
    path.write_text(''.join(canonical(r)+'\n' for r in rows),encoding='utf-8',newline='\n')


def assign_distinct_groups(metadata, available, rng):
    """Bipartite augmenting-path matching of 42 category slots to unique groups."""
    grouped=defaultdict(list)
    for index,row in enumerate(metadata):
        if row['source_id'] in available:
            grouped[row['expected_rag_behavior'],row['source_id']].append(index)
    slots=[category for category in CATEGORIES for _ in range(6)]
    rng.shuffle(slots)
    eligible={category:sorted({group for (label,group) in grouped if label==category}) for category in CATEGORIES}
    for groups in eligible.values(): rng.shuffle(groups)
    owner={}; assignment={}
    def place(slot,seen):
        for group in eligible[slots[slot]]:
            if group in seen: continue
            seen.add(group)
            if group not in owner or place(owner[group],seen):
                owner[group]=slot; assignment[slot]=group
                return True
        return False
    feasible=all(place(slot,set()) for slot in range(len(slots)))
    if not feasible:
        raise RuntimeError('Exact seven-by-six quotas with 42 distinct groups are infeasible after fixed holdout reservation. No relaxation performed.')
    selected=[rng.choice(sorted(grouped[slots[slot],assignment[slot]])) for slot in range(42)]
    rng.shuffle(selected)
    return selected,{c:len(eligible[c]) for c in CATEGORIES}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=HERE)
    args=parser.parse_args(); out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    if any((out/name).exists() for name in ['development_cases.jsonl','runtime_inputs.jsonl','reserved_holdout_manifest.json']):
        raise RuntimeError('Refusing to overwrite an existing selection/holdout reservation.')
    # The short cache is inside the workspace; avoids Windows long-lock paths.
    workspace=REPO.parents[1]
    cache=workspace.parents[1]/'work'/'rb2-cache' if os.name=='nt' else REPO/'work'/'hf'
    os.environ.setdefault('HF_HOME',str(cache/'hf'))
    os.environ.setdefault('HF_DATASETS_CACHE',str(cache/'ds'))
    os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING','1')
    from datasets import load_dataset
    ds=load_dataset(DATASET,split='test',revision=REVISION)
    # Only group/label/id metadata is used until holdout reservation is saved.
    metadata=list(ds.select_columns(['source_id','expected_rag_behavior','id']))
    old=[json.loads(x) for x in (REPO/'evaluation/refusalbench_pilot/cases.jsonl').read_text().splitlines()]
    excluded={str(c['source_id']) for c in old}
    if len(excluded)!=10: raise RuntimeError('Expected ten distinct source groups in previous pilot.')
    all_groups={str(m['source_id']) for m in metadata}
    for m in metadata: m['source_id']=str(m['source_id'])
    remaining=sorted(all_groups-excluded)
    rng=random.Random(SEED);rng.shuffle(remaining)
    holdout=set(remaining[:30]);available=set(remaining[30:])
    held_indices=[i for i,m in enumerate(metadata) if m['source_id'] in holdout]
    held_metadata=[{'dataset_index':i,**metadata[i]} for i in held_indices]
    write_json(out/'reserved_holdout_manifest.json',{
        'dataset':DATASET,'revision':REVISION,'seed':SEED,
        'reserved_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'reservation_rule':'First 30 groups of sorted eligible groups shuffled with Python random.Random(seed), before selecting development cases.',
        'reserved_source_groups':sorted(holdout),'reserved_group_count':len(holdout),
        'reserved_record_count':len(held_indices),'reserved_dataset_indices':held_indices,
        'metadata_sha256':hashlib.sha256(canonical(held_metadata).encode()).hexdigest(),
        'content_policy':'No heldout query/context/answers/reasoning read, displayed, saved, or supplied to implementation. Metadata-only reservation.',
        'excluded_previous_pilot_source_groups':sorted(excluded),
    })
    selected,eligible=assign_distinct_groups(metadata,available,rng)
    chosen_groups={metadata[i]['source_id'] for i in selected}
    assert len(chosen_groups)==42 and not (chosen_groups&holdout) and not (chosen_groups&excluded)
    counts=Counter(metadata[i]['expected_rag_behavior'] for i in selected)
    assert counts==Counter({c:6 for c in CATEGORIES})
    # Only the 42 selected rows are now materialized as full records.
    cases=list(ds.select(selected))
    runtime=[{k:c[k] for k in ['perturbed_query','perturbed_context']} for c in cases]
    write_jsonl(out/'development_cases.jsonl',cases);write_jsonl(out/'runtime_inputs.jsonl',runtime)
    tracked=subprocess.check_output(['git','ls-files'],cwd=REPO,text=True).splitlines()
    legacy=REPO/'evaluation/refusalbench_pilot'
    preserve=sorted(set(tracked)|{f.relative_to(REPO).as_posix() for f in legacy.iterdir() if f.is_file()})
    write_json(out/'predevelopment_file_hashes.json',{name:sha(REPO/name) for name in preserve if (REPO/name).is_file()})
    write_json(out/'selection_manifest.json',{
        'dataset':DATASET,'revision':REVISION,'seed':SEED,'split':'test','split_records':len(ds),
        'total_source_groups':len(all_groups),'excluded_source_groups':len(excluded),
        'reserved_source_groups':len(holdout),'available_development_groups':len(available),
        'selected_source_groups':42,'selected_records':42,'category_counts':dict(counts),
        'eligible_groups_per_category':eligible,'quotas_feasible_without_relaxation':True,
        'selected_dataset_indices':selected,
        'records':[{'runtime_index':j,'dataset_index':i,**metadata[i]} for j,i in enumerate(selected)],
        'selection_algorithm':'metadata-only fixed holdout reservation, randomized category-slot/source-group augmenting-path matching, then seeded record choice and order shuffle',
        'development_cases_sha256':sha(out/'development_cases.jsonl'),
        'runtime_inputs_sha256':sha(out/'runtime_inputs.jsonl'),
        'previous_pilot_cases_sha256':sha(legacy/'cases.jsonl'),
        'repository_base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
    })
    print(canonical({'quotas_feasible':True,'selected_cases':42,'distinct_source_groups':42,'reserved_groups':30,'reserved_records':len(held_indices),'excluded_previous_groups':10,'category_counts':dict(counts),'runtime_sha256':sha(out/'runtime_inputs.jsonl')}))


if __name__=='__main__':main()
