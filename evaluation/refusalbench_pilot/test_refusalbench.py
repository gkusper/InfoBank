"""Offline safety and integration tests. Synthetic examples are NOT benchmark results."""
import json
from pathlib import Path
import pytest
from evaluation.refusalbench_pilot.adapter import adapt_runtime, validate_runtime
from evaluation.refusalbench_pilot.run_experiment import AuditedProvider, generate, validate_ten_runtime
from evaluation.refusalbench_pilot.scoring import expected_binary, interpret_output, score_one
from evaluation.wolala2026.adapters import ALL_MODES, adapter_for_mode
from evaluation.wolala2026.labels import StageName
from evaluation.wolala2026.pipeline import assert_pipeline_invariants, run_pipeline
from evaluation.wolala2026.real_api import OpenAIProvider, ProviderCallResult
from evaluation.wolala2026.retrieval import build_retrieval_snapshot

RUNTIME = {'perturbed_query': 'What color is the square?', 'perturbed_context': 'The square is blue.\nKeep this exact context.'}


@pytest.mark.parametrize('field', ['id', 'expected_rag_behavior', 'implementation_reasoning', 'verifier_votes', 'perturbation_class', 'intensity', 'original_query', 'original_context', 'original_answers'])
def test_rejects_extra_benchmark_fields(field):
    with pytest.raises(ValueError):
        validate_runtime({**RUNTIME, field: 'SECRET_SENTINEL'})


def test_no_label_derived_role_or_answer_and_exact_context():
    case = adapt_runtime(RUNTIME, 0)
    assert 'gold_answer' not in case
    assert case['sources'][0]['metadata'] == {}
    assert case['sources'][0]['evidential_role'] == 'UNKNOWN'
    assert case['sources'][0]['content'] == RUNTIME['perturbed_context']
    assert case['case_id'] == 'runtime-00'
    state = run_pipeline(case)
    assert_pipeline_invariants(state)
    assert state.internal_trace['stage_sequence'] == [s.value for s in StageName]
    assert state.mode_decision.mode.value == 'CFAF'
    assert state.mode_decision.reason_code == 'NO_RELEVANT_SOURCE'
    assert not state.response_contract.allowed_claims
    assert state.response_contract.allowed_evidence_views[0]['content'] == RUNTIME['perturbed_context']


@pytest.mark.parametrize('record', [{}, {**RUNTIME, 'perturbed_query': None}, {**RUNTIME, 'perturbed_context': ['text']}])
def test_invalid_runtime(record):
    with pytest.raises(ValueError):
        validate_runtime(record)


def test_exact_case_count_and_index():
    with pytest.raises(ValueError):
        validate_ten_runtime([RUNTIME] * 9)
    with pytest.raises(ValueError):
        adapt_runtime(RUNTIME, 10)


class RecordingProvider:
    provider_name, embedding_model, generator_model, is_mock = 'synthetic-test', 'none', 'synthetic-test', True
    def __init__(self):
        self.requests = []
    def generate_json(self, **kwargs):
        self.requests.append(kwargs)
        return ProviderCallResult(content=json.dumps({'answer': 'Synthetic test abstention.', 'top_level_mode': 'CFAF'}), model='synthetic-test', input_tokens=10, output_tokens=10, latency_ms=1)


def test_existing_adapters_receive_exact_same_context():
    case = adapt_runtime(RUNTIME, 0)
    snapshot = build_retrieval_snapshot(case)
    provider = RecordingProvider()
    for mode in ALL_MODES:
        adapter_for_mode(mode).run(case, snapshot, run_id='TEST-ONLY', repetition=1, provider=provider, max_output_tokens=160)
    for request in provider.requests:
        assert request['max_output_tokens'] == 160
        payload = request['user_payload']
        if 'retrieved_candidates' in payload:
            assert payload['query'] == RUNTIME['perturbed_query']
            assert payload['retrieved_candidates'][0]['permitted_experimental_raw_text'] == RUNTIME['perturbed_context']
        else:
            contract = payload['response_contract_and_permitted_evidence'][0]['response_contract']
            assert contract['allowed_evidence_views'][0]['content'] == RUNTIME['perturbed_context']
            assert contract['allowed_claims'] == []
        text = json.dumps(payload)
        for forbidden in ['original_answers', 'expected_rag_behavior', 'gold_answer', 'RB-NQ_']:
            assert forbidden not in text


def test_thirty_attempt_cap_and_embedding_block(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'SYNTHETIC-TEST-KEY')
    monkeypatch.setattr(OpenAIProvider, '_post_json', lambda *a: {'choices': [{'message': {'content': '{}'}, 'finish_reason': 'stop'}]})
    provider = AuditedProvider(tmp_path)
    for _ in range(30):
        provider._post_json('/chat/completions', {'model': 'synthetic'})
    with pytest.raises(RuntimeError, match='30'):
        provider._post_json('/chat/completions', {})
    with pytest.raises(RuntimeError, match='Only primary'):
        provider._post_json('/embeddings', {})
    assert len((tmp_path / 'api_requests.jsonl').read_text().splitlines()) == 30


def test_overwrite_guard_never_calls_provider(tmp_path):
    (tmp_path / 'runtime_inputs.jsonl').write_text('\n'.join(json.dumps(RUNTIME) for _ in range(10)))
    (tmp_path / 'api_requests.jsonl').write_text('prior run')
    with pytest.raises(RuntimeError, match='overwrite'):
        generate(tmp_path)


@pytest.mark.parametrize('label,result', [('ANSWER_CORRECTLY', 'FULL'), ('REFUSE_AMBIGUOUS_QUERY', 'CFAF'), ('REFUSE_OTHER_UNMODIFIED', 'CFAF')])
def test_original_binary_mapping(label, result):
    assert expected_binary(label) == result


def test_common_interpretation_preserves_mode_and_generic_reason_unknown():
    raw = json.dumps({'answer': 'The currently usable evidence does not support the requested content.', 'top_level_mode': 'CFAF', 'public_reason_class': 'EVIDENTIAL'})
    assert interpret_output(raw)['refusal_category'] is None
    assert interpret_output(json.dumps({'answer': 'The query is ambiguous.', 'top_level_mode': 'CFAF'}))['refusal_category'] == 'REFUSE_AMBIGUOUS_QUERY'
    assert interpret_output(json.dumps({'answer': 'It cannot be 5; it is 4.', 'top_level_mode': 'FULL'}))['prediction'] == 'FULL'


@pytest.mark.parametrize('raw', ['not JSON', '[]', '{"answer":"","top_level_mode":"FULL"}', '{"answer":"x","top_level_mode":"OTHER"}'])
def test_uninterpretable_is_not_correct(raw):
    result = score_one({'id': 'test', 'expected_rag_behavior': 'REFUSE_AMBIGUOUS_QUERY'}, {'execution_status': 'SUCCESS', 'raw_model_output': raw})
    assert result['classification_correct'] is None
    assert result['prediction'] is None


def test_blocked_model_result_is_not_scored_as_a_refusal():
    result = score_one({'id': 'test', 'expected_rag_behavior': 'REFUSE_AMBIGUOUS_QUERY'}, {'execution_status': 'NOT_EXECUTED', 'raw_model_output': ''})
    assert result['classification_correct'] is None
    assert result['refusal_reason_correct'] is None


def test_correct_mode_does_not_imply_response_supported():
    result = score_one({'id': 'test', 'expected_rag_behavior': 'ANSWER_CORRECTLY'}, {'execution_status': 'SUCCESS', 'raw_model_output': '{"answer":"Red","top_level_mode":"FULL"}'}, {'response_supported_by_context': False})
    assert result['classification_correct'] is True
    assert result['unsupported_full_answer'] is True


@pytest.mark.parametrize('text,category', [
    ('The context contains contradictory statements.', 'REFUSE_CONTRADICTORY_CONTEXT'),
    ('The requested information is missing.', 'REFUSE_INFO_MISSING_IN_CONTEXT'),
    ('This query has a false premise.', 'REFUSE_FALSE_PREMISE_IN_QUERY'),
    ('The question has a granularity mismatch.', 'REFUSE_GRANULARITY_MISMATCH'),
    ('This is a subjective question.', 'REFUSE_NONFACTUAL_QUERY'),
])
def test_specific_reason_mapping(text, category):
    assert interpret_output(json.dumps({'answer': text, 'top_level_mode': 'CFAF'}))['refusal_category'] == category


def test_multiple_reason_matches_are_unmeasurable():
    assert interpret_output('{"answer":"The query is ambiguous and has a false premise.","top_level_mode":"CFAF"}')['refusal_category'] is None


def test_non_string_mode_is_uninterpretable():
    assert interpret_output('{"answer":"x","top_level_mode":[]}')['interpretation_error'] == 'INVALID_OUTPUT_SCHEMA'
