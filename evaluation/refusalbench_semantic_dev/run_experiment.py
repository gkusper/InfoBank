"""42-case development run: freeze -> generate -> score (separate processes)."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

REPO=Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:sys.path.insert(0,str(REPO))
from evaluation.refusalbench_semantic_dev.api_budget import (BudgetProvider,HARD_CAP,canonical,sha,utc,write_json,read_jsonl,append_jsonl,redact)
from evaluation.refusalbench_semantic_dev.semantic_adapter import runtime_case,validate_runtime
from evaluation.wolala2026.semantic_evidence import (ANALYSIS_PROMPT,REALIZATION_PROMPT,
    SHARED_ASSESSMENT_PROMPT,ASSESSMENT_SCHEMA,ANALYSIS_MAX_TOKENS,analyze_evidence,
    run_semantic_pipeline,unknown_assessment,strict_output)
from evaluation.wolala2026.adapters import (adapter_for_mode,_standard_rag_system_prompt,_prompt_only_system_prompt)
from evaluation.wolala2026.retrieval import build_retrieval_snapshot

HERE=Path(__file__).resolve().parent
SYSTEMS=['standard_rag','prompt_only_control','cfaf_semantic','semantic_prompt_control']


def validate_runtime_file(out):
    data=read_jsonl(out/'runtime_inputs.jsonl')
    if len(data)!=42:raise ValueError('Exactly 42 projected runtime records required.')
    for item in data:validate_runtime(item)
    return data


def source_files():
    selected=list(HERE.glob('*.py'))+list((REPO/'evaluation/wolala2026').glob('*.py'))
    selected+=list((REPO/'evaluation/wolala2026/prompts').glob('*.txt'))
    return sorted(selected)


def freeze(out):
    validate_runtime_file(out)
    if (out/'prerun_protocol.json').exists():raise RuntimeError('Freeze already exists; no overwrite.')
    reports=[]
    comparison=json.loads((out/'regression_comparison.json').read_text())
    if not comparison['no_new_regression_failures']:
        raise RuntimeError('New regression failures relative to pristine base; cannot freeze.')
    for name in ['acceptance_tests.xml','regression_tests.xml']:
        path=out/name
        tree=ET.parse(path).getroot();suites=[tree] if tree.tag=='testsuite' else list(tree)
        if any(int(s.attrib.get('failures',0))+int(s.attrib.get('errors',0)) for s in suites):
            if name!='regression_tests.xml' or comparison['runs']['baseline']['failures']!=comparison['runs']['extended']['failures']:
                raise RuntimeError('Pre-run tests have new failures: '+name)

        reports.append({'file':name,'sha256':sha(path),'tests':sum(int(s.attrib.get('tests',0)) for s in suites)})
    prompt_only=(REPO/'evaluation/wolala2026/prompts/prompt_only_v1.txt').read_text(encoding='utf-8')
    prompts={'semantic_analysis':ANALYSIS_PROMPT,'cfaf_semantic':REALIZATION_PROMPT,
        'semantic_prompt_control':SHARED_ASSESSMENT_PROMPT,'standard_rag':_standard_rag_system_prompt(),
        'prompt_only_control':_prompt_only_system_prompt(prompt_only)}
    write_json(out/'frozen_prompts.json',{'prompts':prompts,'semantic_schema':ASSESSMENT_SCHEMA})
    protocol={
        'frozen_at_utc':utc(),'runtime_inputs_sha256':sha(out/'runtime_inputs.jsonl'),
        'source_sha256':{p.relative_to(REPO).as_posix():sha(p) for p in source_files()},
        'prompt_sha256':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in prompts.items()},
        'frozen_prompts_file_sha256':sha(out/'frozen_prompts.json'),
        'cases':42,'systems':SYSTEMS,'semantic_analysis_shared_per_case':1,
        'planned_semantic_calls':42,'planned_generation_calls':168,'planned_api_attempts':210,
        'hard_api_attempt_cap':HARD_CAP,'model':'gpt-4o-mini','temperature':0,
        'generation_max_output_tokens':160,'semantic_analysis_max_output_tokens':ANALYSIS_MAX_TOKENS,
        'repetitions':1,'max_retries':0,'embedding_calls':0,'additional_validation_api_calls':0,
        'scoring':'strict raw JSON mode; failed analysis/parser/validation is ERROR, never credited as fallback CFAF; all 42 scheduled cases in accuracy denominator',
        'response_support':'benchmark behavior labels are not answer-support gold; exact quote occurrence is mechanical only; unassessed support remains null',
        'tests':reports,
        'original_regression_suite_fully_green':comparison['all_original_regressions_pass'],
        'no_new_regression_failures':comparison['no_new_regression_failures'],
        'preexisting_regression_failures':comparison['runs']['baseline']['failures'],
        'regression_comparison_sha256':sha(out/'regression_comparison.json'),
        'diagnostic_run_caveat':'Strict acceptance condition 5 is unmet if the original suite is not fully green; proceed only as explicitly documented development diagnostics with unchanged baseline failures.',
    }
    assert protocol['planned_api_attempts']<=HARD_CAP
    write_json(out/'prerun_protocol.json',protocol)
    print(canonical({'frozen':True,'planned_api_attempts':210,'cap':HARD_CAP,'tests':reports}))


def check_freeze(out):
    protocol=json.loads((out/'prerun_protocol.json').read_text())
    if sha(out/'runtime_inputs.jsonl')!=protocol['runtime_inputs_sha256']:raise RuntimeError('Runtime projection changed after freeze.')
    for name,digest in protocol['source_sha256'].items():
        if sha(REPO/name)!=digest:raise RuntimeError('Frozen source changed: '+name)
    if sha(out/'frozen_prompts.json')!=protocol['frozen_prompts_file_sha256']:raise RuntimeError('Frozen prompts changed.')
    return protocol


def call_fields(call,event):
    return {'input_tokens':call.input_tokens,'output_tokens':call.output_tokens,
        'generation_api_ms':call.latency_ms,'provider_model':call.model,'provider_response_id':call.response_id,
        'finish_reason':event.get('finish_reason') if event else None}


def base_row(index,mode):
    return {'index':index,'runtime_id':f'runtime-{index:03d}','mode_name':mode,
        'execution_status':'NOT_EXECUTED','raw_model_output':'','public_response':None,
        'selected_mode':None,'actual_generation_attempts':0,'input_tokens':0,'output_tokens':0,
        'validation_errors':[],'real_api':True}


def generate(out):
    runtime=validate_runtime_file(out);protocol=check_freeze(out)
    for name in ['generation_results.jsonl','api_requests.jsonl','api_events.jsonl','semantic_assessments.jsonl','experiment_manifest.json']:
        if (out/name).exists():raise RuntimeError('Refusing to overwrite/resume live artifacts; use a new output directory.')
    provider=BudgetProvider(out) if os.getenv('OPENAI_API_KEY') else None
    blocker=None if provider else 'OPENAI_API_KEY is absent.'
    started=utc();results=[];analyses=[]
    for index,item in enumerate(runtime):
        case=runtime_case(item,index);snapshot=build_retrieval_snapshot(case)
        if provider:provider.index=index
        # Existing baselines see original raw question/context, with no semantic output.
        for mode in SYSTEMS[:2]:
            row=base_row(index,mode);tick=time.perf_counter();before=provider.attempts if provider else 0
            if blocker or provider and provider.blocker:
                row['blocker']=blocker or provider.blocker
            else:
                try:
                    result=adapter_for_mode(mode).run(case,snapshot,run_id='semantic-dev-v1',repetition=1,provider=provider,max_output_tokens=160)
                    row.update({'execution_status':'SUCCESS','raw_model_output':result['raw_model_output'],
                        'public_response':result['public_response'],'retrieval_snapshot_hash':snapshot['snapshot_hash'],
                        'input_tokens':result['input_tokens'],'output_tokens':result['output_tokens'],
                        'provider_response_id':result['provider_response_id'],'provider_model':provider.last_event['model'],
                        'finish_reason':provider.last_event['finish_reason'],'generation_api_ms':provider.last_event['latency_ms']})
                except Exception as exc:row.update({'execution_status':'RUNTIME_ERROR','error':redact(str(exc))})
            row['actual_generation_attempts']=(provider.attempts if provider else 0)-before
            row['end_to_end_ms']=(time.perf_counter()-tick)*1000
            append_jsonl(out/'generation_results.jsonl',row);results.append(row)
        # One shared analysis only; never receives scorer metadata or original ID.
        tick=time.perf_counter();before=provider.attempts if provider else 0
        analysis_call=None;analysis_error=None
        assessment=unknown_assessment(['ANALYSIS_NOT_EXECUTED'])
        if blocker or provider and provider.blocker:
            analysis_error=blocker or provider.blocker
        else:
            try:
                assessment,analysis_call=analyze_evidence(item['perturbed_query'],{'context-1':item['perturbed_context']},provider)
            except Exception as exc:
                analysis_error=redact(str(exc));assessment=unknown_assessment(['ANALYSIS_RUNTIME_ERROR'])
        analysis_ms=(time.perf_counter()-tick)*1000
        analysis_row={'index':index,'runtime_id':case['case_id'],'assessment':assessment.to_dict(),
            'actual_analysis_attempts':(provider.attempts if provider else 0)-before,
            'latency_ms':analysis_ms,'raw_model_output':analysis_call.content if analysis_call else None,
            'input_tokens':analysis_call.input_tokens if analysis_call else 0,'output_tokens':analysis_call.output_tokens if analysis_call else 0,
            'provider_model':analysis_call.model if analysis_call else None,'error':analysis_error,
            'validation_errors':assessment.validation_errors}
        append_jsonl(out/'semantic_assessments.jsonl',analysis_row);analyses.append(analysis_row)
        for mode in SYSTEMS[2:]:
            row=base_row(index,mode);tick=time.perf_counter();before=provider.attempts if provider else 0
            row['semantic_assessment_valid']=assessment.valid;row['shared_semantic_analysis_ms']=analysis_ms
            if blocker or provider and provider.blocker:
                row['blocker']=blocker or provider.blocker
            else:
                try:
                    if mode=='cfaf_semantic':
                        state,realizer=run_semantic_pipeline(case,assessment,provider)
                        row.update(call_fields(realizer.call,provider.last_event))
                        row.update({'raw_model_output':realizer.raw_output,'public_response':state.final_response,
                            'selected_mode':state.mode_decision.mode.value,'selected_reason_code':state.mode_decision.reason_code,
                            'proposed_answer':assessment.data['answer_candidate'],'validation_errors':state.validation.violation_codes,
                            'fallback_used':state.validation.fallback_used,'execution_status':'SUCCESS' if state.validation.status.value=='PASS' else 'VALIDATION_FAILURE'})
                        append_jsonl(out/'pipeline_traces.jsonl',{'index':index,'state':json.loads(state.to_json())})
                    else:
                        call=provider.generate_json(mode_name=mode,system_prompt=SHARED_ASSESSMENT_PROMPT,
                            user_payload={'query':item['perturbed_query'],'documents':[{'source_id':'context-1','context':item['perturbed_context']}],
                                'semantic_assessment':assessment.to_dict()},max_output_tokens=160)
                        parsed,error=strict_output(call.content)
                        row.update(call_fields(call,provider.last_event))
                        row.update({'raw_model_output':call.content,'public_response':parsed['answer'] if parsed else call.content,
                            'execution_status':'SUCCESS' if not error else 'PARSER_FAILURE','validation_errors':[error] if error else []})
                    if not assessment.valid:
                        row['execution_status']='ANALYSIS_FAILURE';row['analysis_errors']=assessment.validation_errors
                except Exception as exc:row.update({'execution_status':'RUNTIME_ERROR','error':redact(str(exc))})
            row['actual_generation_attempts']=(provider.attempts if provider else 0)-before
            row['end_to_end_ms']=(time.perf_counter()-tick)*1000
            row['end_to_end_including_shared_analysis_ms']=row['end_to_end_ms']+analysis_ms
            append_jsonl(out/'generation_results.jsonl',row);results.append(row)
        print(canonical({'completed_cases':index+1,'api_attempts':provider.attempts if provider else 0,
            'semantic_valid':assessment.valid,'statuses':{r['mode_name']:r['execution_status'] for r in results[-4:]}}),flush=True)
    write_json(out/'experiment_manifest.json',{
        'experiment':'refusalbench-semantic-development-v1','started_at_utc':started,'finished_at_utc':utc(),
        'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
        'branch':subprocess.check_output(['git','branch','--show-current'],cwd=REPO,text=True).strip(),
        'python':sys.version,'platform':platform.platform(),'model':'gpt-4o-mini','temperature':0,
        'generation_max_output_tokens':160,'semantic_analysis_max_output_tokens':ANALYSIS_MAX_TOKENS,
        'hard_api_attempt_cap':HARD_CAP,'actual_total_api_attempts':provider.attempts if provider else 0,
        'actual_semantic_analysis_attempts':sum(r['actual_analysis_attempts'] for r in analyses),
        'actual_generation_attempts':sum(r['actual_generation_attempts'] for r in results),
        'retries':0,'embeddings':0,'additional_validation_calls':0,
        'api_key_present':bool(os.getenv('OPENAI_API_KEY')),'api_blocker':blocker or (provider.blocker if provider else None),
        'semantic_valid_cases':sum(r['assessment']['valid'] for r in analyses),
        'execution_status_counts':dict(__import__('collections').Counter(r['execution_status'] for r in results)),
        'dependencies':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},
        'prerun_protocol_sha256':sha(out/'prerun_protocol.json'),'runtime_input_sha256':sha(out/'runtime_inputs.jsonl'),
    })


def score(out):
    # Trusted join after generation: this import never occurs in the worker.
    from evaluation.refusalbench_semantic_dev.scoring import score_rows
    check_freeze(out)
    cases=read_jsonl(out/'development_cases.jsonl');runtime=validate_runtime_file(out)
    manifest=json.loads((out/'selection_manifest.json').read_text())
    holdout=json.loads((out/'reserved_holdout_manifest.json').read_text())
    if sha(out/'development_cases.jsonl')!=manifest['development_cases_sha256'] or sha(out/'runtime_inputs.jsonl')!=manifest['runtime_inputs_sha256']:
        raise RuntimeError('Selected dataset checksums changed.')
    if len(cases)!=42 or len({str(c['source_id']) for c in cases})!=42:raise RuntimeError('Development must contain 42 distinct source groups.')
    groups={str(c['source_id']) for c in cases}
    if groups & (set(holdout['reserved_source_groups'])|set(holdout['excluded_previous_pilot_source_groups'])):
        raise RuntimeError('Source-group overlap with prior pilot or reserved holdout.')
    if any(r!={k:c[k] for k in r} for r,c in zip(runtime,cases)):raise RuntimeError('Runtime projection differs from original selected records.')
    generated=read_jsonl(out/'generation_results.jsonl')
    if len(generated)!=168 or len({(r['index'],r['mode_name']) for r in generated})!=168:raise RuntimeError('Expected exactly 168 scheduled generated-system results.')
    reviews=read_jsonl(out/'independent_response_reviews.jsonl') if (out/'independent_response_reviews.jsonl').exists() else []
    scored,systems=score_rows(cases,generated,reviews)
    (out/'results.jsonl').write_text(''.join(canonical(r)+'\n' for r in scored),encoding='utf-8',newline='\n')
    experiment=json.loads((out/'experiment_manifest.json').read_text())
    analyses=read_jsonl(out/'semantic_assessments.jsonl')
    if (out/'api_events.jsonl').exists():events=read_jsonl(out/'api_events.jsonl')
    else:events=[]
    usage=[e.get('usage') or {} for e in events if e['status']=='SUCCESS']
    original=json.loads((out/'predevelopment_file_hashes.json').read_text())
    modified=[f for f,digest in original.items() if not (REPO/f).exists() or sha(REPO/f)!=digest]
    if modified:raise RuntimeError('Protected pre-development files changed: '+', '.join(modified))
    summary={
        'experiment_type':'development; not independent final validation','cases':42,'distinct_source_groups':42,
        'dataset_revision':manifest['revision'],'seed':manifest['seed'],'expected_category_counts':manifest['category_counts'],
        'systems':systems,'actual_total_api_attempts':experiment['actual_total_api_attempts'],
        'actual_semantic_analysis_attempts':experiment['actual_semantic_analysis_attempts'],
        'actual_generation_attempts':experiment['actual_generation_attempts'],
        'total_api_input_tokens':sum(u.get('prompt_tokens',0) for u in usage),
        'total_api_output_tokens':sum(u.get('completion_tokens',0) for u in usage),
        'semantic_analysis_input_tokens':sum(a['input_tokens'] for a in analyses),
        'semantic_analysis_output_tokens':sum(a['output_tokens'] for a in analyses),
        'semantic_analysis_valid_cases':sum(a['assessment']['valid'] for a in analyses),
        'semantic_analysis_invalid_cases':sum(not a['assessment']['valid'] for a in analyses),
        'protected_predevelopment_files_verified':len(original),'modified_predevelopment_files':modified,
        'reserved_holdout_source_groups':holdout['reserved_group_count'],'reserved_holdout_records':holdout['reserved_record_count'],
        'holdout_text_inspected':False,'inferential_significance_claims':False,
        'support_gold_available':False,'independent_human_response_review_available':False,
        'assessment_prompt_control_incremental_calls':systems['semantic_prompt_control']['generation_api_attempts'],
    }
    write_json(out/'summary.json',summary)
    write_json(out/'confusion_matrices.json',{mode:value['confusion_matrix'] for mode,value in systems.items()})
    print(canonical({'scored_records':len(scored),'system_accuracy':{m:d['accuracy'] for m,d in systems.items()},
        'total_api_attempts':summary['actual_total_api_attempts'],'preserved_files':len(original)}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['freeze','generate','score'])
    parser.add_argument('--output-dir',type=Path,default=HERE)
    args=parser.parse_args();out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    {'freeze':freeze,'generate':generate,'score':score}[args.command](out)


if __name__=='__main__':main()
