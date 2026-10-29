"""Reuse exactly 30 already-exposed cases; no downloads, fresh sampling or QASPER."""
from common import *
from component_cfaf.adapters.openai_sdk import PROMPT,STANDARD_PROMPT,strict_schema,OUTPUT_CAP
from component_cfaf.contracts import LLMProposal,StandardAnswer
import argparse,datetime

def prepare():
    ensure();target=ROOT/'results/local/inputs.jsonl';assert not target.exists(),'Never rematerialize exposed sample'
    state=read(STATE);source=Path(state['worktrees'][0]['path']);study=source/'evaluation/cfaf_contract_driven_2h_v1';garage=source/'evaluation/cfaf_dataset3_garage_pilot_v1'
    runtime_manifest=git_json('evaluation/cfaf_contract_driven_2h_v1/runtime_manifest.json');raw_manifest=git_json('evaluation/cfaf_contract_driven_2h_v1/raw_artifact_hashes.json')['files'];sources={}
    for dataset in ['dataset1','dataset2']:
        for suffix in ['runtime.jsonl','gold.jsonl','results_raw.jsonl']:
            p=study/(dataset+'_'+suffix);assert sha(p)==raw_manifest[p.name],p.name;sources[str(p.relative_to(source))]=sha(p)
    manifest1=git_json('evaluation/cfaf_contract_driven_2h_v1/dataset1_selection_manifest.json');manifest2=git_json('evaluation/cfaf_contract_driven_2h_v1/dataset2_selection_manifest.json')
    gf=git_json('evaluation/cfaf_dataset3_garage_pilot_v1/experiment_manifest.json');assert sha(garage/'runtime_inputs.jsonl')==gf['runtime_sha256'];assert sha(garage/'dataset3_selection_manifest.json')==gf['selection_manifest_sha256'];sources['evaluation/cfaf_dataset3_garage_pilot_v1/runtime_inputs.jsonl']=gf['runtime_sha256']
    chosen={'dataset1':[0,1,8,9,16,17,24,25,32,33],'dataset2':list(range(10)),'garage':list(range(10))};selection=[]
    for dataset,indices in chosen.items():
        runtime=rows(study/(dataset+'_runtime.jsonl')) if dataset!='garage' else rows(garage/'runtime_inputs.jsonl')
        gold=rows(study/(dataset+'_gold.jsonl')) if dataset!='garage' else None
        if dataset=='dataset1':assert len(runtime)==40 and [manifest1['case_ids'][i].split('_')[1] for i in indices]==['P1','P1','P2','P2','P3','P3','P4','P4','P5','P5']
        if dataset=='dataset2':assert len(runtime)==40 and manifest2['all_40_previously_exposed'] is True
        if dataset=='garage':assert len(runtime)==10
        for i in indices:
            item=runtime[i];case=item['case'];rid=len(selection)
            # Only original already-authorized application fields reach governance, never scorer labels.
            safe_sources=[]
            for s in case['sources']:
                safe_sources.append({k:s[k] for k in ['source_id','source_type','content','metadata','access_mode','existence_visibility','allowed_metadata_fields','aggregate_view','purpose_compatibility','security_status','title','retrieved','protected_markers'] if k in s})
            append(target,{'index':rid,'dataset':dataset,'source_runtime_index':i,'query':case['query'],'sources':safe_sources,'as_of':(item.get('query_context') or {}).get('question_date')})
            append(ROOT/'results/local/gold.jsonl',{'index':rid,'dataset':dataset,'source_runtime_index':i,'gold':gold[i] if gold else None})
            selection.append({'index':rid,'dataset':dataset,'source_runtime_index':i,'original_manifest_record_sha256':hashlib.sha256(json.dumps(manifest1['case_ids'][i] if dataset=='dataset1' else manifest2['records'][i] if dataset=='dataset2' else git_json('evaluation/cfaf_dataset3_garage_pilot_v1/dataset3_selection_manifest.json')['indices_zero_based'][i],sort_keys=True).encode()).hexdigest()})
    exposure={'protocol':'ComponentCFAF-v1-exposed-development-only','counts':{k:10 for k in chosen},'new_records_opened':0,'selected_charged_before_API':30,'all_previously_exposed':True,'QASPER_read_or_used':False,'reserved_holdout_content_opened':False,'selection_rule':'First completed pair of each InfoBank P1-P5 family; first ten fixed exposed RefusalBench manifest positions; all original ten GaRAGe pilot positions. No random selection or new source records.','records':selection,'source_input_hashes':sources,'source_baseline':state['base']}
    write(ROOT/'results/exposure_manifest.json',exposure)
    own=sorted((ROOT/'src/component_cfaf').rglob('*.py'))+[ROOT/'tools/common.py',ROOT/'tools/prepare.py',ROOT/'tools/live_smoke.py',ROOT/'tools/renderer_ablation.py',ROOT/'pyproject.toml',ROOT/'requirements.lock']
    write(ROOT/'results/freeze.json',{'frozen_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'base_commit':state['base'],'files':{p.relative_to(ROOT).as_posix():sha(p) for p in own},'prompt_sha256':hashlib.sha256(PROMPT.encode()).hexdigest(),'standard_prompt_sha256':hashlib.sha256(STANDARD_PROMPT.encode()).hexdigest(),'schema_sha256':hashlib.sha256(json.dumps(strict_schema(LLMProposal),sort_keys=True).encode()).hexdigest(),'standard_schema_sha256':hashlib.sha256(json.dumps(strict_schema(StandardAnswer),sort_keys=True).encode()).hexdigest(),'model':'gpt-4o-mini','temperature':0,'output_cap_both_systems':OUTPUT_CAP,'attempt_cap':100,'target_max_calls':60,'repetitions':1,'SDK_retries':0,'inputs_sha256':sha(target),'gold_sha256':sha(ROOT/'results/local/gold.jsonl'),'exposure_sha256':sha(ROOT/'results/exposure_manifest.json'),'post_output_tuning_permitted':False})
    print('FROZEN 30 already exposed cases; no QASPER or reserved content; output cap',OUTPUT_CAP)
if __name__=='__main__':prepare()
