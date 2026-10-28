"""Trusted post-generation scoring. Never imported by model execution code."""
from __future__ import annotations
from collections import Counter
import json
import re
import statistics
from evaluation.wolala2026.semantic_evidence import strict_output

MODES=['standard_rag','prompt_only_control','cfaf_semantic','semantic_prompt_control']


def expected_binary(label):
    if label=='ANSWER_CORRECTLY':return 'FULL'
    if label.startswith('REFUSE_'):return 'CFAF'
    raise ValueError('Unknown official behavior label.')


def refusal_category(answer):
    text=answer.lower()
    # A false-premise statement inherently mentions contradiction; prefer that specific cause.
    if re.search(r'false premise|incorrect premise|false assumption',text):return 'REFUSE_FALSE_PREMISE_IN_QUERY'
    patterns={
        'REFUSE_AMBIGUOUS_QUERY':r'\bambigu(?:ous|ity)\b|multiple (?:plausible|possible) interpretations|unresolved referen',
        'REFUSE_INFO_MISSING_IN_CONTEXT':r'information is missing|missing (?:information|essential)|insufficient (?:information|evidence)|context (?:does not|doesn.t) (?:provide|contain|include)|no supporting passage',
        'REFUSE_CONTRADICTORY_CONTEXT':r'\bcontradictory\b|\bconflicting\b|incompatible (?:claims|statements|answers)',
        'REFUSE_GRANULARITY_MISMATCH':r'granularity mismatch|requested (?:detail|precision|granularity)|too (?:broad|coarse|specific)',
        'REFUSE_NONFACTUAL_QUERY':r'non.?factual|\bsubjective\b|personal (?:opinion|preference)',
    }
    matches=[code for code,pattern in patterns.items() if code.lower() in text or re.search(pattern,text)]
    return matches[0] if len(matches)==1 else None


def interpretation(row):
    if row.get('is_zero_cost_reference'):return row['reference_prediction'],None,None
    parsed,error=strict_output(row.get('raw_model_output',''))
    observed=parsed['top_level_mode'] if parsed else None
    # A parser, analyzer or validation failure is not credited as a successful refusal.
    prediction=observed if row['execution_status']=='SUCCESS' and not error else None
    return prediction,parsed,error


def metrics(rows):
    n=len(rows);confusion={truth:{pred:0 for pred in ['FULL','CFAF','ERROR']} for truth in ['FULL','CFAF']}
    for r in rows:confusion[r['scoring']['expected_binary']][r['scoring']['prediction'] or 'ERROR']+=1
    recalls={};precisions={}
    for label in ['FULL','CFAF']:
        denom=sum(confusion[label].values());predicted=sum(confusion[t][label] for t in confusion)
        recalls[label]=confusion[label][label]/denom if denom else None
        precisions[label]=confusion[label][label]/predicted if predicted else None
    accuracy=sum(confusion[c][c] for c in confusion)/n if n else None
    category_results={}
    for category in sorted({r['scoring']['expected_label'] for r in rows}):
        group=[r for r in rows if r['scoring']['expected_label']==category]
        category_results[category]={'n':len(group),'correct':sum(r['scoring']['classification_correct'] for r in group),
            'accuracy':sum(r['scoring']['classification_correct'] for r in group)/len(group),
            'predictions':dict(Counter(r['scoring']['prediction'] or 'ERROR' for r in group))}
    reason_predictions=[r for r in rows if r['scoring'].get('refusal_category') and r['scoring']['expected_binary']=='CFAF']
    full=[r for r in rows if r['scoring']['prediction']=='FULL' and not r.get('is_zero_cost_reference')]
    reviewed=[r for r in full if r['scoring'].get('independent_response_review')]
    lat=[r['end_to_end_ms'] for r in rows if r.get('end_to_end_ms') is not None]
    return {
        'n':n,'accuracy':accuracy,'balanced_accuracy':sum(recalls.values())/2 if all(x is not None for x in recalls.values()) else None,
        'full_precision':precisions['FULL'],'full_recall':recalls['FULL'],
        'cfaf_precision':precisions['CFAF'],'cfaf_recall':recalls['CFAF'],'confusion_matrix':confusion,
        'unnecessary_refusal_count':confusion['FULL']['CFAF'],
        'unnecessary_refusal_rate':confusion['FULL']['CFAF']/sum(confusion['FULL'].values()) if sum(confusion['FULL'].values()) else None,
        'failure_to_restrict_count':confusion['CFAF']['FULL'],
        'failure_to_restrict_rate':confusion['CFAF']['FULL']/sum(confusion['CFAF'].values()) if sum(confusion['CFAF'].values()) else None,
        'parser_or_runtime_or_validation_errors':sum(confusion[c]['ERROR'] for c in confusion),
        'execution_status_counts':dict(Counter(r['execution_status'] for r in rows)),
        'per_category':category_results,
        'specific_refusal_reason_predictions':len(reason_predictions),
        'specific_refusal_reason_correct':sum(r['scoring']['refusal_category']==r['scoring']['expected_label'] for r in reason_predictions),
        'specific_refusal_reason_accuracy':sum(r['scoring']['refusal_category']==r['scoring']['expected_label'] for r in reason_predictions)/len(reason_predictions) if reason_predictions else None,
        'generic_abstentions_without_specific_category':sum(r['scoring']['prediction']=='CFAF' and r['scoring'].get('refusal_category') is None for r in rows if not r.get('is_zero_cost_reference')),
        'reason_justification_correctness':'UNMEASURABLE_FROM_BEHAVIOR_LABEL_ALONE',
        'generated_full_responses':len(full),'independently_reviewed_full_responses':len(reviewed),
        'unsupported_full_responses_observed':sum(r['scoring']['independent_response_review'].get('answer_supported') is False for r in reviewed),
        'correctly_grounded_complete_full_responses_observed':sum(r['scoring']['independent_response_review'].get('answer_supported') is True and r['scoring']['independent_response_review'].get('complete_fulfilment') is True for r in reviewed),
        'full_response_support_unmeasurable_or_unreviewed':len(full)-sum(r['scoring']['independent_response_review'].get('answer_supported') is not None for r in reviewed),
        'automatic_exact_extractive_full_answers':sum(r['scoring'].get('exact_answer_substring') is True for r in full),
        'mode_prose_agreement':dict(Counter(str(r['scoring'].get('mode_prose_agreement')) for r in rows if not r.get('is_zero_cost_reference'))),
        'generation_api_attempts':sum(r.get('actual_generation_attempts',0) for r in rows),
        'incremental_generation_input_tokens':sum(r.get('input_tokens',0) for r in rows),
        'incremental_generation_output_tokens':sum(r.get('output_tokens',0) for r in rows),
        'generation_latency_ms':{'n':len(lat),'mean':statistics.mean(lat),'median':statistics.median(lat),'min':min(lat),'max':max(lat)} if lat else None,
    }


def score_rows(cases,generated,reviews=None):
    review_map={(r['index'],r['mode_name']):r for r in (reviews or [])}
    scored=[]
    for row in generated:
        row=dict(row);case=cases[row['index']];expected=expected_binary(case['expected_rag_behavior'])
        pred,parsed,error=interpretation(row)
        category=refusal_category(parsed['answer']) if parsed and parsed['top_level_mode']=='CFAF' else None
        answer=parsed['answer'] if parsed else None
        agreement=None
        if parsed:
            explicit_abstention=bool(re.search(r'\bI (?:cannot|can.t)\b|cannot (?:answer|determine|provide)|not enough (?:information|evidence)|insufficient (?:information|evidence)',answer,re.I))
            if parsed['top_level_mode']=='CFAF':agreement=True if explicit_abstention else None
            else:agreement=not explicit_abstention
        review=review_map.get((row['index'],row['mode_name']))
        if review and review.get('mode_prose_agreement') is not None:agreement=review['mode_prose_agreement']
        row['scoring']={
            'original_id':case['id'],'expected_label':case['expected_rag_behavior'],'expected_binary':expected,
            'prediction':pred,'raw_declared_mode':parsed['top_level_mode'] if parsed else None,
            'classification_correct':pred==expected,'parser_error':error,'refusal_category':category,
            'reason_category_correct':category==case['expected_rag_behavior'] if category and expected=='CFAF' else None,
            'exact_answer_substring':answer.strip() in case['perturbed_context'] if answer and pred=='FULL' else None,
            'mode_prose_agreement':agreement,'independent_response_review':review,
            'support_warning':'Exact-span occurrence and analyzer self-consistency do not prove complete request fulfillment.',
        }
        scored.append(row)
    for mode,prediction in [('always_full','FULL'),('always_cfaf','CFAF')]:
        for index,case in enumerate(cases):
            expected=expected_binary(case['expected_rag_behavior'])
            scored.append({'index':index,'mode_name':mode,'is_zero_cost_reference':True,
                'execution_status':'REFERENCE','reference_prediction':prediction,'raw_model_output':None,
                'scoring':{'original_id':case['id'],'expected_label':case['expected_rag_behavior'],
                    'expected_binary':expected,'prediction':prediction,'classification_correct':prediction==expected}})
    systems={m:metrics([r for r in scored if r['mode_name']==m]) for m in ['always_full','always_cfaf']+MODES}
    return scored,systems
