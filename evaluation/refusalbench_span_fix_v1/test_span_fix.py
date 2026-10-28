"""Synthetic regression tests for shared text contracts and exact span references."""
import copy,json,hashlib
from dataclasses import replace
from pathlib import Path
import pytest
from evaluation.refusalbench_span_fix_v1.span_references import build_catalogue,resolve_span,parse_reference_assessment
from evaluation.refusalbench_span_fix_v1.contracts import validate_response,GENERATION_SCHEMA
from evaluation.refusalbench_span_fix_v1.api_budget import BudgetProvider
from evaluation.refusalbench_semantic_dev.test_semantic import answerable
from evaluation.refusalbench_semantic_dev.semantic_adapter import runtime_case,validate_runtime
from evaluation.wolala2026.semantic_evidence import run_semantic_pipeline
from evaluation.wolala2026.real_api import OpenAIProvider
TEXT='The square is blue.'
def response(mode='FULL',answer='blue'):
 return {'answer':answer,'top_level_mode':mode,'fulfilment_status':'FULL' if mode=='FULL' else 'NONE','realization':None,'public_reason_class':None,'next_step_codes':[]}
def assessment():
 data=answerable();data['supporting_spans']=['context-1:span-0000'];data['contradicting_spans']=[];return data
@pytest.mark.parametrize('value',[None,'','  '])
def test_null_or_empty_cfaf_rejected_without_repair(value):
 raw=json.dumps(response('CFAF',value));assert validate_response(raw);assert json.loads(raw)['answer']==value

def test_nonempty_refusal_and_full_share_schema():
 assert not validate_response(json.dumps(response('CFAF','The evidence does not resolve the reference.')))
 assert not validate_response(json.dumps(response()))
 assert GENERATION_SCHEMA['properties']['answer']['type']=='string'
 assert GENERATION_SCHEMA['properties']['top_level_mode']['enum']==['FULL','CFAF']
@pytest.mark.parametrize('text',['"Quotes" and \'apostrophes\'.','Alpha ... omega.','**who died in 1985**; a comma, not a period.','Árvíztűrő tükörfúrógép — 😀; Ελληνικά.'])
def test_exact_unicode_punctuation_markup(text):
 docs={'doc':text};cat=build_catalogue(docs,window=17,overlap=5);covered=set()
 assert cat==build_catalogue(docs,window=17,overlap=5)
 for sid,span in cat.spans.items():
  assert resolve_span(sid,docs,cat)['quote']==text[span.start_offset:span.end_offset]
  covered.update(range(span.start_offset,span.end_offset))
 assert covered==set(range(len(text)))
@pytest.mark.parametrize('ref',['missing','wrong-source:span-0000','context-1:span-9999',None])
def test_unknown_reference_not_substituted(ref):
 with pytest.raises(ValueError):resolve_span(ref,{'context-1':TEXT},build_catalogue({'context-1':TEXT}))
@pytest.mark.parametrize('start,end',[(-1,5),(0,999),(4,4),(8,3)])
def test_invalid_offsets(start,end):
 docs={'context-1':TEXT};cat=build_catalogue(docs);sid=next(iter(cat.spans));cat.spans[sid]=replace(cat.spans[sid],start_offset=start,end_offset=end)
 with pytest.raises(ValueError,match='OFFSETS'):resolve_span(sid,docs,cat)

def test_wrong_source_changed_content_and_catalogue():
 docs={'context-1':TEXT};cat=build_catalogue(docs);sid=next(iter(cat.spans))
 changed=copy.deepcopy(cat);changed.spans[sid]=replace(changed.spans[sid],source_id='other')
 with pytest.raises(ValueError,match='SOURCE'):resolve_span(sid,docs,changed)
 with pytest.raises(ValueError,match='CHANGED'):resolve_span(sid,{'context-1':TEXT+'!'},cat)
 changed=copy.deepcopy(cat);changed.spans[sid]=replace(changed.spans[sid],end_offset=len(TEXT)-1)
 with pytest.raises(ValueError,match='CATALOGUE'):resolve_span(sid,docs,changed)

def test_multiple_spans_and_repeated_substring_offsets():
 docs={'context-1':'A'*900};cat=build_catalogue(docs,window=20,overlap=0)
 assert resolve_span('context-1:span-0001',docs,cat)['start']==20
 data=assessment();data['supporting_spans']=['context-1:span-0000','context-1:span-0001']
 result,audit=parse_reference_assessment(json.dumps(data),docs,cat)
 assert result.valid and audit['validated_reference_count']==2
 assert result.data['supporting_spans'][1]['start']==20

def test_invalid_model_reference_invalidates_analysis():
 data=assessment();data['supporting_spans']=['invented']
 result,audit=parse_reference_assessment(json.dumps(data),{'context-1':TEXT},build_catalogue({'context-1':TEXT}))
 assert not result.valid and audit['reference_valid'] is False and audit['reference_errors']

def test_identified_counterevidence_preserved_and_blocks_full():
 text='The square is blue. The square is red.';docs={'context-1':text};data=assessment();data['contradicting_spans']=['context-1:span-0000']
 result,audit=parse_reference_assessment(json.dumps(data),docs,build_catalogue(docs))
 assert result.valid and len(result.data['contradicting_spans'])==1
 state,_=run_semantic_pipeline(runtime_case({'perturbed_query':'What color is the square?','perturbed_context':text},0),result)
 assert state.mode_decision.mode.value=='CFAF' and state.mode_decision.reason_code=='INCOMPATIBLE_EVIDENCE'

def test_justified_full_unchanged():
 docs={'context-1':TEXT};result,audit=parse_reference_assessment(json.dumps(assessment()),docs,build_catalogue(docs))
 state,_=run_semantic_pipeline(runtime_case({'perturbed_query':'What color is the square?','perturbed_context':TEXT},0),result)
 assert state.mode_decision.mode.value=='FULL' and state.final_response=='blue'
 assert state.generator_context[0]['query']=='What color is the square?'
 assert audit['resolved_spans'][0]['quote']==TEXT
@pytest.mark.parametrize('field',['expected_rag_behavior','original_answers','perturbation_class','id'])
def test_gold_fields_rejected(field):
 with pytest.raises(ValueError):validate_runtime({'perturbed_query':'q','perturbed_context':'c',field:'secret'})

def test_all_generated_systems_use_common_schema_and_60_cap(tmp_path,monkeypatch):
 monkeypatch.setenv('OPENAI_API_KEY','SYNTHETIC');captured=[]
 def fake(self,path,payload):
  captured.append(payload);return {'choices':[{'message':{'content':json.dumps(response())},'finish_reason':'stop'}]}
 monkeypatch.setattr(OpenAIProvider,'_post_json',fake);provider=BudgetProvider(tmp_path)
 for mode in ['standard_rag','prompt_only_control','cfaf_semantic','semantic_prompt_control']:
  provider.generate_json(mode_name=mode,system_prompt='JSON',user_payload={'query':'q'},max_output_tokens=160)
 assert all(x['response_format']['type']=='json_schema' and x['response_format']['json_schema']['schema']==GENERATION_SCHEMA for x in captured)
 assert all('nonempty string' in x['messages'][0]['content'] for x in captured)
 provider.attempts=60
 with pytest.raises(RuntimeError,match='60'):provider.generate_json(mode_name='standard_rag',system_prompt='JSON',user_payload={},max_output_tokens=160)

def test_previous_frozen_files_unchanged():
 root=Path(__file__).resolve().parents[2];snapshot=json.loads((Path(__file__).parent/'protected_files.json').read_text())
 assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in snapshot.items())
