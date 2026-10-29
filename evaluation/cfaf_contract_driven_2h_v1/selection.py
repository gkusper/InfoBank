"""Predeclare exact old-cohort rows and new-D3 indices, before opening fresh text."""
import random,collections,datetime
from .artifacts import *
from . import measured_c as impl
D1=REPO/'evaluation/wolala2026/data/heldout_pilot_v3'
D2_LEDGER=REPO/'evaluation/refusalbench_iterative_dev_v1/exposure_ledger.json'
D2_RESERVED=REPO/'evaluation/refusalbench_semantic_dev/reserved_holdout_manifest.json'
D3=REPO/'evaluation/cfaf_dataset3_garage_pilot_v1'
def declare():
 if (ROOT/'selection_plan.json').exists():raise RuntimeError('Selection plan already declared')
 old_indices=read(D3/'dataset3_selection_manifest.json')['indices_zero_based'];eligible=[i for i in range(2366) if i not in old_indices];new_indices=random.Random(20261029).sample(eligible,80)
 ledger=read(D2_LEDGER);reserved=read(D2_RESERVED);assert 'No heldout query/context/answers/reasoning read' in reserved['content_policy'];assert len(set(ledger['reserved_source_groups']))==30;assert not any(e['source_id'] in ledger['reserved_source_groups'] for e in ledger['entries'])
 exposed=sorted([e for e in ledger['entries'] if e['eligible']],key=lambda x:x['dataset_index']);assert len(exposed)==130;chosen=random.Random(20261029).sample(exposed,40)
 d1=rows(D1/'cases.jsonl');assert len(d1)==40;counts=[len(impl.project_case(c).documents) for c in d1]
 plan={'declared_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'seed':20261029,'dataset1':{'cohort':'Original existing 40 development cases, already exposed despite legacy HELD3/heldout filenames','case_ids':[c['case_id'] for c in d1],'pairs':20,'new_independent_holdout_used':False,'permitted_view_counts':counts,'cases_requiring_model_calls':sum(n>0 for n in counts),'source_sha256':sha(D1/'cases.jsonl'),'gold_sha256':sha(D1/'gold.jsonl')},'dataset2':{'cohort':'40 fixed already-exposed eligible cases; development only','planned_reserved_groups':30,'reserved_groups_used':0,'fallback_used':True,'reason':'Existing reserved_holdout_manifest.content_policy explicitly forbids heldout content access; current task instructs obeying that rule.','prohibition':reserved['content_policy'],'ledger_sha256':sha(D2_LEDGER),'reserved_manifest_sha256':sha(D2_RESERVED),'records':[{'dataset_index':e['dataset_index'],'id':e['id'],'source_id':e['source_id'],'record_hash':e['record_hash']} for e in chosen],'unchanged_reserved_groups':ledger['reserved_source_groups'],'unchanged_other_untouched_groups':ledger['untouched_source_groups']},'dataset3':{'cohort':'80 fresh uniformly random records after code freeze; no native mode gold','population':2366,'previously_exposed_indices':old_indices,'eligible_unexposed':len(eligible),'selected_indices_zero_based':new_indices,'algorithm':'random.Random(20261029).sample(ordered indices excluding the ten exposed,80)','source_commit':'2b7264f5d4e066affbe4b67b7d3b9cffeff98ede','source_sha256':'419e3941f6e8eb4082a74ca2140c1f9337f8b467ff76656a6b8b0290ca3f3a72','fresh_text_opened':False},'planned_case_counts':{'dataset1':40,'dataset2':40,'dataset3':80},'expected_model_calls_without_query_fallback':sum(n>0 for n in counts)*3+120+240,'attempt_cap':480,'no_new_DS2_or_DS1_holdout':True}
 write(ROOT/'selection_plan.json',plan);print('PREREGISTERED 40 + 40 development + 80 fresh; expected calls',plan['expected_model_calls_without_query_fallback'])
if __name__=='__main__':declare()
