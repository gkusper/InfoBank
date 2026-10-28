"""New 5+5 pilot; old studies and mode-selection algorithm remain untouched."""
from __future__ import annotations
import argparse,hashlib,importlib.metadata,json,os,platform,subprocess,sys,time
from pathlib import Path
import xml.etree.ElementTree as ET
REPO=Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:sys.path.insert(0,str(REPO))
from evaluation.refusalbench_span_fix_v1.api_budget import BudgetProvider,HARD_CAP,canonical,sha,utc,write_json,read_jsonl,append_jsonl,redact
from evaluation.refusalbench_span_fix_v1.span_references import analyze_evidence,ANALYSIS_PROMPT,REFERENCE_SCHEMA
from evaluation.refusalbench_span_fix_v1.contracts import COMMON_INSTRUCTIONS,GENERATION_SCHEMA,validate_response
from evaluation.refusalbench_semantic_dev.semantic_adapter import runtime_case,validate_runtime
from evaluation.wolala2026.semantic_evidence import REALIZATION_PROMPT,SHARED_ASSESSMENT_PROMPT,ANALYSIS_MAX_TOKENS,run_semantic_pipeline,unknown_assessment,strict_output
from evaluation.wolala2026.adapters import adapter_for_mode,_standard_rag_system_prompt,_prompt_only_system_prompt
from evaluation.wolala2026.retrieval import build_retrieval_snapshot
HERE=Path(__file__).resolve().parent
SYSTEMS=['standard_rag','prompt_only_control','cfaf_semantic','semantic_prompt_control']

def validate_runtime_file(out):
 data=read_jsonl(out/'runtime_inputs.jsonl')
 if len(data)!=10:raise ValueError('Exactly ten runtime inputs required.')
 for record in data:validate_runtime(record)
 return data

def protected_check(out):
 changed=[name for name,digest in json.loads((out/'protected_files.json').read_text()).items() if sha(REPO/name)!=digest]
 if changed:raise RuntimeError('Prior/frozen file changed: '+str(changed))

def check_freeze(out):
 protocol=json.loads((out/'prerun_protocol.json').read_text())
 if sha(out/'frozen_prompts.json')!=protocol['prompts_sha256']:raise RuntimeError('Frozen prompts changed.')
 if sha(out/'runtime_inputs.jsonl')!=protocol['runtime_inputs_sha256']:raise RuntimeError('Runtime changed after freeze.')
 for name,digest in protocol['source_sha256'].items():
  if sha(REPO/name)!=digest:raise RuntimeError('Frozen source changed: '+name)
 protected_check(out)
 return protocol

def freeze(out):
 validate_runtime_file(out);protected_check(out)
 if (out/'prerun_protocol.json').exists():raise RuntimeError('Freeze already exists.')
 regression=ET.parse(out/'regression_test_results.xml').getroot()
 failures=[t.attrib.get('classname','')+'::'+t.attrib.get('name','') for t in regression.iter('testcase') if t.find('failure') is not None or t.find('error') is not None]
 expected=['evaluation.tests.test_wolala_final_experiment_v3.WolalaFinalExperimentV3Tests::test_preheldout_attempt1_plan_artifacts_are_plan_only']
 if failures!=expected:raise RuntimeError('Unexpected original regression failures: '+str(failures))
 tree=ET.parse(out/'test_results.xml').getroot()
 if sum(int(x.attrib.get('tests',0)) for x in tree.iter('testsuite'))<70:raise RuntimeError('Incomplete experimental test suite.')
 if any(int(s.attrib.get('failures',0))+int(s.attrib.get('errors',0)) for s in tree.iter('testsuite')):raise RuntimeError('New experimental tests failed.')
 prompts={'semantic_analysis':ANALYSIS_PROMPT,'cfaf_semantic':REALIZATION_PROMPT+COMMON_INSTRUCTIONS,
 'semantic_prompt_control':SHARED_ASSESSMENT_PROMPT+COMMON_INSTRUCTIONS,'standard_rag':_standard_rag_system_prompt()+COMMON_INSTRUCTIONS,
 'prompt_only_control':_prompt_only_system_prompt((REPO/'evaluation/wolala2026/prompts/prompt_only_v1.txt').read_text())+COMMON_INSTRUCTIONS}
 write_json(out/'frozen_prompts.json',{'prompts':prompts,'reference_analysis_schema':REFERENCE_SCHEMA,'generation_schema':GENERATION_SCHEMA})
 files=list(HERE.glob('*.py'))+list((REPO/'evaluation/wolala2026').glob('*.py'))+list((REPO/'evaluation/refusalbench_semantic_dev').glob('*.py'))
 write_json(out/'prerun_protocol.json',{'frozen_at_utc':utc(),'runtime_inputs_sha256':sha(out/'runtime_inputs.jsonl'),
 'source_sha256':{p.relative_to(REPO).as_posix():sha(p) for p in files},'prompts_sha256':sha(out/'frozen_prompts.json'),
 'cases':10,'positive':5,'negative':5,'model':'gpt-4o-mini','temperature':0,'generation_max_tokens':160,'analysis_max_tokens':1500,
 'planned_attempts':50,'hard_cap':60,'retries':0,'scoring':'Original shared strict interpretation and error-inclusive metrics, no decision repair',
 'test_results_sha256':sha(out/'test_results.xml')})
 print('Frozen 10-case experiment; 50 planned calls, 60 hard cap.')

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
                    result=adapter_for_mode(mode).run(case,snapshot,run_id='span-ref-fix-v1',repetition=1,provider=provider,max_output_tokens=160)
                    row.update({'execution_status':'SUCCESS','raw_model_output':result['raw_model_output'],
                        'public_response':result['public_response'],'retrieval_snapshot_hash':snapshot['snapshot_hash'],
                        'input_tokens':result['input_tokens'],'output_tokens':result['output_tokens'],
                        'provider_response_id':result['provider_response_id'],'provider_model':provider.last_event['model'],
                        'finish_reason':provider.last_event['finish_reason'],'generation_api_ms':provider.last_event['latency_ms']})
                except Exception as exc:row.update({'execution_status':'RUNTIME_ERROR','error':redact(str(exc))})
            row['actual_generation_attempts']=(provider.attempts if provider else 0)-before
            row['end_to_end_ms']=(time.perf_counter()-tick)*1000
            if row['execution_status']=='SUCCESS':
                contract_errors=validate_response(row['raw_model_output'])
                if contract_errors:row['execution_status']='OUTPUT_CONTRACT_FAILURE';row['validation_errors']=contract_errors
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
            'validation_errors':assessment.validation_errors,
            'reference_audit':getattr(analysis_call,'reference_audit',None),
            'span_catalogue':getattr(analysis_call,'span_catalogue',None)}
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
            if row['execution_status']=='SUCCESS':
                contract_errors=validate_response(row['raw_model_output'])
                if contract_errors:row['execution_status']='OUTPUT_CONTRACT_FAILURE';row['validation_errors']=contract_errors
            append_jsonl(out/'generation_results.jsonl',row);results.append(row)
        print(canonical({'completed_cases':index+1,'api_attempts':provider.attempts if provider else 0,
            'semantic_valid':assessment.valid,'statuses':{r['mode_name']:r['execution_status'] for r in results[-4:]}}),flush=True)
    write_json(out/'experiment_manifest.json',{
        'experiment':'refusalbench-span-reference-fix-v1','started_at_utc':started,'finished_at_utc':utc(),
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
 from collections import Counter
 from evaluation.refusalbench_semantic_dev.scoring import score_rows
 check_freeze(out);cases=read_jsonl(out/'cases.jsonl');generated=read_jsonl(out/'generation_results.jsonl')
 selection=json.loads((out/'selection_manifest.json').read_text())
 if len(cases)!=10 or sha(out/'cases.jsonl')!=selection['cases_sha256']:raise RuntimeError('Selection changed.')
 if len(generated)!=40 or len({(r['index'],r['mode_name']) for r in generated})!=40:raise RuntimeError('Expected 40 system outputs.')
 reviews=read_jsonl(out/'response_reviews.jsonl') if (out/'response_reviews.jsonl').exists() else []
 results,systems=score_rows(cases,generated,reviews)
 (out/'results.jsonl').write_text(''.join(canonical(r)+'\n' for r in results),encoding='utf-8',newline='\n')
 analyses=read_jsonl(out/'semantic_assessments.jsonl');events=read_jsonl(out/'api_events.jsonl') if (out/'api_events.jsonl').exists() else []
 span_audit={'cases':[],'requested_references':0,'valid_references':0,'invalid_reference_cases':0}
 for a in analyses:
  ref=a.get('reference_audit') or {};requested=len(ref.get('supporting_references',[]))+len(ref.get('contradicting_references',[]))
  span_audit['requested_references']+=requested;span_audit['valid_references']+=ref.get('validated_reference_count',0)
  span_audit['invalid_reference_cases']+=ref.get('reference_valid') is False
  span_audit['cases'].append({'index':a['index'],'reference_audit':ref})
 span_audit['reference_validity_rate']=span_audit['valid_references']/span_audit['requested_references'] if span_audit['requested_references'] else None
 span_audit['warning']='Reference validity and exact extraction are not semantic entailment or complete request fulfilment.'
 write_json(out/'span_reference_validation.json',span_audit)
 summary={'cases':10,'expected_full':5,'expected_cfaf':5,'systems':systems,
 'actual_api_attempts':len(events),'semantic_calls':sum(e['kind']=='semantic_analysis' for e in events),
 'generation_calls':sum(e['kind']!='semantic_analysis' for e in events),
 'input_tokens':sum((e.get('usage') or {}).get('prompt_tokens',0) for e in events),
 'output_tokens':sum((e.get('usage') or {}).get('completion_tokens',0) for e in events),
 'semantic_valid_cases':sum(a['assessment']['valid'] for a in analyses),
 'null_outputs_by_system':{mode:sum(json.loads(r['raw_model_output']).get('answer') is None for r in generated if r['mode_name']==mode and r['raw_model_output']) for mode in SYSTEMS},
 'output_contract_errors_by_system':{mode:sum(bool(validate_response(r['raw_model_output'])) for r in generated if r['mode_name']==mode and r['raw_model_output']) for mode in SYSTEMS},
 'span_reference_validation':{k:v for k,v in span_audit.items() if k!='cases'},
 'new_records':10,'reused_records':0,'reserved_or_untouched_sources_used':0,
 'scoring':'Frozen, common strict raw JSON interpretation; errors never repaired or credited as CFAF',
 'gold_answer_support_accuracy':None,'independent_human_adjudication_available':False,'inferential_significance':False}
 write_json(out/'summary.json',summary)
 write_json(out/'confusion_matrices.json',{k:v['confusion_matrix'] for k,v in systems.items()})
 print(canonical({'accuracy':{k:v['accuracy'] for k,v in systems.items()},'calls':len(events),'span_valid':span_audit['reference_validity_rate']}))


def main():
 parser=argparse.ArgumentParser();parser.add_argument('command',choices=['freeze','generate','score']);parser.add_argument('--output-dir',type=Path,default=HERE)
 args=parser.parse_args();out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
 {'freeze':freeze,'generate':generate,'score':score}[args.command](out)
if __name__=='__main__':main()
