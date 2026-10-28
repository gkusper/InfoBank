"""Separate metadata access, field identity, value type and requested precision."""
import copy,datetime,re,math
from evaluation.cfaf_requirement_alignment_v1.requirement_decomposition import decompose
SCHEMA={'file_type':'STRING','format':'STRING','author':'STRING','owner':'STRING','created_at':'DATE_TIME','modified_at':'DATE_TIME','published_at':'DATE_TIME','creation_date':'DATE_TIME','size_bytes':'COUNT'}
VERSION='trusted-metadata-value-types-1.0'

def decompose_fixed(query,profile=None):
 result=copy.deepcopy(decompose(query,profile));result['value_typing_version']=VERSION
 for req in result['requirements']:
  req['access_class']='METADATA' if req['request_type']=='METADATA_LOOKUP' else 'AGGREGATE' if req['request_type'].startswith('AGGREGATE_') else 'CONTENT_OR_UNRESOLVED'
  fields=req['metadata_fields'];req['requested_attribute']=fields[0] if len(fields)==1 else None
  req['value_type']=SCHEMA.get(fields[0],'UNKNOWN') if req['request_type']=='METADATA_LOOKUP' and len(fields)==1 else req['answer_type']
  if req['request_type']=='METADATA_LOOKUP' and req['value_type']=='DATE_TIME':req['answer_type']=req['answer_kind']='DATE_TIME'
  req['value_type_authority']='APPLICATION_METADATA_SCHEMA' if req['request_type']=='METADATA_LOOKUP' and len(fields)==1 and fields[0] in SCHEMA else 'QUERY_INTERPRETATION'
 return result

def parse_temporal(value):
 if not isinstance(value,str):return None
 try:return datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
 except ValueError:
  try:return datetime.datetime.combine(datetime.date.fromisoformat(value),datetime.time())
  except ValueError:return None

def typed_value(value,value_type):
 if value_type=='DATE_TIME':return parse_temporal(value) is not None
 if value_type=='COUNT':return type(value) is int and value>=0
 if value_type in {'NUMBER','QUANTITY'}:return type(value) in {int,float} and math.isfinite(value)
 if value_type=='STRING':return isinstance(value,str) and bool(value.strip())
 return None

def bind_metadata(requirement,request,target,candidate):
 result={'requirement_id':requirement['requirement_id'],'access_class':requirement['access_class'],'attribute':requirement['requested_attribute'],'value_type':requirement['value_type'],'requested_precision':requirement['requested_precision'],'status':'NOT_APPLICABLE','authority':'UNRESOLVED','source_id':None,'supported_value':None,'candidate_fragment':None}
 if requirement['request_type']!='METADATA_LOOKUP':return result
 from .trusted_target_resolution import validate_target_authority
 validate_target_authority(target,request)
 field=requirement['requested_attribute'];result['status']='UNKNOWN'
 if not field:return result
 if target['state']!='RESOLVED':result['uncertainty']='TARGET_NOT_TRUSTED_RESOLVED';return result
 eligible=[d for d in request.documents if d['source_id'] in target['permitted_view_ids'] and d['view_kind']=='metadata'];values=[]
 import json
 for d in eligible:
  metadata=json.loads(d['context'])
  if field in metadata and metadata[field] is not None:values.append((d['source_id'],metadata[field]))
 if len(values)!=1:result['uncertainty']='MISSING_OR_MULTIPLE_AUTHORIZED_FIELD_VALUES';return result
 sid,value=values[0];result.update(source_id=sid,supported_value=value,authority='TRUSTED_STRUCTURED_SOURCE',type_valid=typed_value(value,requirement['value_type']))
 if result['type_valid'] is not True:result.update(status='INVALID_STRUCTURED_VALUE',uncertainty='METADATA_SCHEMA_VALUE_INVALID');return result
 text=candidate if isinstance(candidate,str) else '';needle=str(value);match=re.search(r'(?<!\w)'+re.escape(needle)+r'(?!\w)',text,re.I)
 if not match and requirement['value_type']=='DATE_TIME' and requirement['requested_precision']=='YEAR':
  needle=str(parse_temporal(value).year);match=re.search(r'\b'+needle+r'\b',text)
 if match:result.update(status='FIELD_VALUE_MATCH',candidate_fragment={'text':text[match.start():match.end()],'start':match.start(),'end':match.end()},relation_status='STRUCTURED_FIELD_OF_RESOLVED_TARGET')
 else:result.update(status='CANDIDATE_FIELD_VALUE_UNRESOLVED',uncertainty='CANDIDATE_DOES_NOT_EXPLICITLY_MATCH_TYPED_FIELD')
 return result
