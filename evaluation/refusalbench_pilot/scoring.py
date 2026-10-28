"""Post-generation interpretation/scoring. Never imported by generation worker."""
from __future__ import annotations
import json
import re
import statistics
from collections import Counter
from typing import Any


def expected_binary(label: str) -> str:
    if label == 'ANSWER_CORRECTLY':
        return 'FULL'
    if label.startswith('REFUSE_'):
        return 'CFAF'
    raise ValueError(f'Unrecognized benchmark label: {label}')


def interpret_output(raw: str) -> dict[str, Any]:
    """Strict declared-JSON rule for every system; no adapter mode repair.

    A declared mode is a behavior classification, not response correctness.
    Contradictions between prose and mode are reviewed separately. Generic
    EVIDENTIAL does not identify an original refusal category precisely enough.
    """
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError):
        return {'prediction': None, 'answer': None, 'refusal_category': None,
                'interpretation_error': 'INVALID_JSON'}
    if (not isinstance(obj, dict) or not isinstance(obj.get('top_level_mode'), str) or obj.get('top_level_mode') not in {'FULL', 'CFAF'}
            or not isinstance(obj.get('answer'), str) or not obj['answer'].strip()):
        return {'prediction': None, 'answer': obj.get('answer') if isinstance(obj, dict) else None,
                'refusal_category': None, 'interpretation_error': 'INVALID_OUTPUT_SCHEMA'}
    category = None
    if obj['top_level_mode'] == 'CFAF':
        text = obj['answer'].lower()
        patterns = {
            'REFUSE_AMBIGUOUS_QUERY': r'\bambigu(?:ous|ity)\b|\bunderspecified\b|\bmultiple (?:possible )?interpretations\b',
            'REFUSE_CONTRADICTORY_CONTEXT': r'\bcontradict(?:ory|ion|ions)\b|\bconflicting (?:information|statements|claims)\b',
            'REFUSE_INFO_MISSING_IN_CONTEXT': r'\b(?:information|details|answer) (?:is |are )?missing\b|\bcontext (?:does not|doesn.t) (?:contain|provide|include)\b',
            'REFUSE_FALSE_PREMISE_IN_QUERY': r'\bfalse premise\b|\bincorrect (?:premise|assumption)\b',
            'REFUSE_GRANULARITY_MISMATCH': r'\bgranularity mismatch\b|\b(?:too|overly) (?:specific|detailed)\b',
            'REFUSE_NONFACTUAL_QUERY': r'\bnon.?factual\b|\bsubjective (?:question|query|opinion)\b',
        }
        matches = [name for name, pattern in patterns.items() if name.lower() in text or re.search(pattern, text)]
        category = matches[0] if len(matches) == 1 else None
    return {'prediction': obj['top_level_mode'], 'answer': obj['answer'],
            'refusal_category': category, 'interpretation_error': None}


def score_one(case, result, review=None):
    expected = expected_binary(case['expected_rag_behavior'])
    parsed = interpret_output(result.get('raw_model_output', '')) if result['execution_status'] == 'SUCCESS' else {
        'prediction': None, 'answer': None, 'refusal_category': None, 'interpretation_error': None}
    pred, category = parsed['prediction'], parsed['refusal_category']
    measurable = bool(category and expected == 'CFAF' and pred == 'CFAF')
    review = review or {}
    support = review.get('response_supported_by_context')
    return {
        'original_id': case['id'], 'expected_label': case['expected_rag_behavior'],
        'expected_binary': expected, **parsed,
        'classification_correct': pred == expected if pred else None,
        'refusal_reason_measurable': measurable,
        'refusal_reason_correct': category == case['expected_rag_behavior'] if measurable else None,
        'unnecessary_refusal': pred == 'CFAF' and expected == 'FULL' if pred else None,
        'unsupported_full_answer': support is False and pred == 'FULL' if support is not None and pred else None,
        'response_supported_by_context': support, 'response_review': review or None,
    }


def summarize(cases, rows):
    systems = {}
    for mode in ('standard_rag', 'prompt_only_control', 'cfaf_pipeline'):
        results = [r for r in rows if r['mode_name'] == mode]
        usable = [r for r in results if r['scoring']['prediction'] is not None]
        correct = sum(r['scoring']['classification_correct'] is True for r in usable)
        specific = [r for r in results if r['scoring']['refusal_reason_measurable']]
        supported = [r for r in results if r['scoring']['response_supported_by_context'] is not None]
        full_reviewed = [r for r in supported if r['scoring']['prediction'] == 'FULL']
        expected_full = [r for r in usable if r['scoring']['expected_binary'] == 'FULL']
        expected_refusals = sum(r['scoring']['expected_binary'] == 'CFAF' for r in results)
        reason_correct = sum(r['scoring']['refusal_reason_correct'] is True for r in specific)
        latencies = [r['end_to_end_ms'] for r in results if r['execution_status'] == 'SUCCESS']
        tokens_known = [r for r in results if r.get('actual_api_usage') is not None]
        systems[mode] = {
            'scheduled_cases': len(cases),
            'attempted_cases': sum(r['execution_status'] != 'NOT_EXECUTED' for r in results),
            'successful_cases': sum(r['execution_status'] == 'SUCCESS' for r in results),
            'runtime_errors': sum(r['execution_status'] == 'ERROR' for r in results),
            'not_executed': sum(r['execution_status'] == 'NOT_EXECUTED' for r in results),
            'interpretable_cases': len(usable), 'correct_binary_classifications': correct,
            'binary_accuracy': correct / len(usable) if usable else None,
            'binary_accuracy_denominator': len(usable),
            'success_and_correct_fraction_of_scheduled': correct / len(cases) if cases else None,
            'output_interpretation_errors': sum(bool(r['scoring']['interpretation_error']) for r in results),
            'predicted_modes': dict(Counter(r['scoring']['prediction'] or 'UNAVAILABLE' for r in results)),
            'errors_by_expected_category': dict(Counter(r['scoring']['expected_label'] for r in usable if not r['scoring']['classification_correct'])),
            'confusion_matrix': dict(Counter(r['scoring']['expected_binary'] + '->' + r['scoring']['prediction'] for r in usable)),
            'specific_refusal_reason_predictions': len(specific), 'specific_refusal_reason_correct': reason_correct,
            'specific_refusal_reason_accuracy': reason_correct / len(specific) if specific else None,
            'expected_refusal_cases': expected_refusals,
            'correct_specific_reason_coverage_of_expected_refusals': reason_correct / expected_refusals if expected_refusals else None,
            'unnecessary_refusals': sum(r['scoring']['unnecessary_refusal'] is True for r in usable),
            'unnecessary_refusal_opportunities': len(expected_full),
            'unnecessary_refusal_rate': sum(r['scoring']['unnecessary_refusal'] is True for r in expected_full) / len(expected_full) if expected_full else None,
            'context_support_reviewed': len(supported),
            'context_support_counts': dict(Counter(str(r['scoring']['response_supported_by_context']) for r in supported)),
            'unsupported_full_answers': sum(r['scoring']['unsupported_full_answer'] is True for r in full_reviewed),
            'reviewed_full_answers': len(full_reviewed),
            'full_answer_review_coverage': len(full_reviewed) / sum(r['scoring']['prediction'] == 'FULL' for r in usable) if any(r['scoring']['prediction'] == 'FULL' for r in usable) else None,
            'actual_generation_api_attempts': sum(r['actual_api_attempts'] for r in results),
            'actual_embedding_api_calls': 0, 'actual_classifier_api_calls': 0, 'retries': 0,
            'input_tokens': sum(r['actual_api_usage']['input_tokens'] for r in tokens_known),
            'output_tokens': sum(r['actual_api_usage']['output_tokens'] for r in tokens_known),
            'token_usage_known_cases': len(tokens_known),
            'latency_ms': {'n': len(latencies), 'mean': statistics.mean(latencies), 'median': statistics.median(latencies), 'min': min(latencies), 'max': max(latencies)} if latencies else None,
        }
    return {'cases_selected': len(cases), 'indices': list(range(10)),
            'expected_label_distribution': dict(Counter(c['expected_rag_behavior'] for c in cases)),
            'systems': systems,
            'unique_cases_with_any_successful_real_execution': len({r['index'] for r in rows if r['execution_status'] == 'SUCCESS'}),
            'actual_generation_api_attempts': sum(r['actual_api_attempts'] for r in rows),
            'statistical_inference_performed': False, 'interpretation_procedure': 'strict-declared-json-v1',
            'validity_limit': 'Conservative UNKNOWN-role integration pilot; not an independent semantic CFAF benchmark validation.'}
