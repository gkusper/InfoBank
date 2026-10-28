"""One public response contract for all generated systems in the new pilot."""
from evaluation.wolala2026.semantic_evidence import _schema_errors
import json

COMMON_INSTRUCTIONS='''\nCOMMON PUBLIC RESPONSE CONTRACT: For both FULL and CFAF, answer MUST be a nonempty string containing actual user-visible text. In CFAF, write the abstention explanation in answer; never copy a null semantic answer_candidate into answer. Null means no prepared factual candidate, not no public response. The shared control remains free to choose FULL or CFAF. top_level_mode must be exactly FULL or CFAF; express restrictions using fulfilment_status/realization, not another mode. Return only the six schema fields. Keep explanations concise and next_step_codes empty. Never silently repair an invalid response.'''
GENERATION_SCHEMA={'type':'object','properties':{
 'answer':{'type':'string'},'top_level_mode':{'type':'string','enum':['FULL','CFAF']},
 'fulfilment_status':{'type':'string','enum':['FULL','RESTRICTED','NONE','DEFERRED']},
 'realization':{'type':['string','null']},'public_reason_class':{'type':['string','null']},
 'next_step_codes':{'type':'array','items':{'type':'string'}}},
 'required':['answer','top_level_mode','fulfilment_status','realization','public_reason_class','next_step_codes'],
 'additionalProperties':False}

def validate_response(raw):
 try:data=json.loads(raw)
 except (ValueError,TypeError):return ['INVALID_JSON']
 errors=_schema_errors(data,GENERATION_SCHEMA,'response')
 if not errors and not data['answer'].strip():errors.append('EMPTY_PUBLIC_ANSWER')
 return errors
