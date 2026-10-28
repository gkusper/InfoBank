"""Offline budget, sampling, metrics and failure-credit tests."""
import json
import random
import pytest
from evaluation.refusalbench_semantic_dev.api_budget import BudgetProvider
from evaluation.refusalbench_semantic_dev.sample_development_cases import assign_distinct_groups,CATEGORIES,SEED
from evaluation.refusalbench_semantic_dev.scoring import score_rows,interpretation
from evaluation.wolala2026.real_api import OpenAIProvider


def test_hard_225_durable_cap_and_no_embeddings(tmp_path,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','SYNTHETIC-TEST-KEY')
    monkeypatch.setattr(OpenAIProvider,'_post_json',lambda *a:{'choices':[{'message':{'content':'{}'},'finish_reason':'stop'}]})
    provider=BudgetProvider(tmp_path);provider.kind='standard_rag'
    payload={'model':'gpt-4o-mini','temperature':0,'max_tokens':160}
    for i in range(225):provider._post_json('/chat/completions',dict(payload))
    with pytest.raises(RuntimeError,match='225'):provider._post_json('/chat/completions',dict(payload))
    resumed=BudgetProvider(tmp_path);resumed.kind='standard_rag'
    with pytest.raises(RuntimeError,match='225'):resumed._post_json('/chat/completions',dict(payload))
    with pytest.raises(RuntimeError,match='embeddings'):resumed._post_json('/embeddings',{})
    assert len((tmp_path/'api_requests.jsonl').read_text().splitlines())==225


def test_sampler_synthetic_distinct_group_quotas_and_reproducibility():
    metadata=[{'source_id':f'source-{i:02d}','expected_rag_behavior':label,'id':f'row-{i}'} for i,label in enumerate(c for c in CATEGORIES for _ in range(6))]
    available={m['source_id'] for m in metadata}
    first,_=assign_distinct_groups(metadata,available,random.Random(SEED))
    second,_=assign_distinct_groups(metadata,available,random.Random(SEED))
    assert first==second and len(set(first))==42
    assert len({metadata[i]['source_id'] for i in first})==42


def test_infeasible_quotas_never_silently_relaxed():
    with pytest.raises(RuntimeError,match='infeasible'):
        assign_distinct_groups([{'source_id':'one','expected_rag_behavior':'ANSWER_CORRECTLY','id':'synthetic'}],{'one'},random.Random(SEED))


def test_zero_cost_reference_metrics_for_six_answerable_and_36_refusal_cases():
    cases=[{'id':f'synthetic-{i}','expected_rag_behavior':label,'perturbed_context':'context'} for i,label in enumerate(c for c in CATEGORIES for _ in range(6))]
    rows,systems=score_rows(cases,[])
    assert len(rows)==84
    assert systems['always_full']['accuracy']==6/42
    assert systems['always_cfaf']['accuracy']==36/42
    assert systems['always_full']['balanced_accuracy']==0.5
    assert systems['always_cfaf']['balanced_accuracy']==0.5
    assert systems['always_full']['failure_to_restrict_rate']==1
    assert systems['always_cfaf']['unnecessary_refusal_rate']==1


@pytest.mark.parametrize('status',['ANALYSIS_FAILURE','VALIDATION_FAILURE','PARSER_FAILURE','RUNTIME_ERROR','NOT_EXECUTED'])
def test_failure_fallback_cannot_receive_primary_refusal_credit(status):
    row={'execution_status':status,'raw_model_output':'{"answer":"I cannot answer.","top_level_mode":"CFAF"}'}
    prediction,parsed,error=interpretation(row)
    assert prediction is None
    assert parsed['top_level_mode']=='CFAF'


def test_full_orchestration_uses_one_analysis_per_synthetic_case_and_four_generations(tmp_path,monkeypatch):
    from evaluation.refusalbench_semantic_dev.run_experiment import generate
    from evaluation.refusalbench_semantic_dev.api_budget import sha
    from evaluation.refusalbench_semantic_dev.test_semantic import answerable
    monkeypatch.setenv('OPENAI_API_KEY','SYNTHETIC-TEST-KEY')
    def fake_http(self,path,payload):
        user=json.loads(payload['messages'][1]['content'])
        if payload['response_format']['type']=='json_schema':content=json.dumps(answerable())
        else:content=json.dumps({'answer':'blue','top_level_mode':'FULL','fulfilment_status':'FULL','realization':None,'public_reason_class':None,'next_step_codes':[]})
        return {'model':'synthetic-test','id':'synthetic-test-response','choices':[{'message':{'content':content},'finish_reason':'stop'}],'usage':{'prompt_tokens':2,'completion_tokens':2}}
    monkeypatch.setattr(OpenAIProvider,'_post_json',fake_http)
    runtime={'perturbed_query':'What color is the square?','perturbed_context':'The square is blue.'}
    (tmp_path/'runtime_inputs.jsonl').write_text(''.join(json.dumps(runtime)+'\n' for _ in range(42)))
    (tmp_path/'frozen_prompts.json').write_text('{}')
    (tmp_path/'prerun_protocol.json').write_text(json.dumps({'runtime_inputs_sha256':sha(tmp_path/'runtime_inputs.jsonl'),
        'source_sha256':{},'frozen_prompts_file_sha256':sha(tmp_path/'frozen_prompts.json')}))
    generate(tmp_path)
    manifest=json.loads((tmp_path/'experiment_manifest.json').read_text())
    assert manifest['actual_total_api_attempts']==210
    assert manifest['actual_semantic_analysis_attempts']==42
    assert manifest['actual_generation_attempts']==168
    assert manifest['execution_status_counts']=={'SUCCESS':168}
    assert len((tmp_path/'semantic_assessments.jsonl').read_text().splitlines())==42
    assert len((tmp_path/'pipeline_traces.jsonl').read_text().splitlines())==42
