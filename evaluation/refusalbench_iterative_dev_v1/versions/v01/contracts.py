"""Shared public schema with bidirectional mode/status validation; no repair."""
from evaluation.refusalbench_span_fix_v1.contracts import GENERATION_SCHEMA,COMMON_INSTRUCTIONS,validate_response as shape_errors
import json

def validate_response(raw):
 errors=shape_errors(raw)
 if errors:return errors
 d=json.loads(raw)
 if d['top_level_mode']=='FULL' and d['fulfilment_status']!='FULL':errors.append('FULL_REQUIRES_FULL_STATUS')
 if d['top_level_mode']=='CFAF' and d['fulfilment_status']=='FULL':errors.append('CFAF_CANNOT_CLAIM_FULL_STATUS')
 return errors
