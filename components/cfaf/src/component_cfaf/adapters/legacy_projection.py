"""Authoritative policy projection BEFORE every external model call.

No experimental evidence labels, fixture answers, original IDs or denied-source
existence signals are included in public requests. Raw sources stay local.
"""
from __future__ import annotations
from dataclasses import dataclass,field
import hashlib,json
from typing import Any

ORACLE_KEYS={'gold_answer','runtime_answer','evidential_role','relation','evidence_state',
 'expected_top_level_mode','expected_cfaf_realization','expected_public_reason_class',
 'expected_internal_reason_class','canonical_answer_markers','expected_fulfilment_status',
 'expected_permitted_output','expected_public_response_norm','expected_next_step_codes',
 'family','variant','pair_id','case_id','gold_record_path','protected_markers',
 'protected_markers_used_only_by_validator','forbidden_disclosures','forbidden_disclosures_used_only_by_validator'}
CANONICAL_NO_SUPPORT='The currently usable evidence does not support the requested content.'

def canonical(x):return json.dumps(x,ensure_ascii=True,sort_keys=True,separators=(',',':'))
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()

@dataclass
class PermittedRequest:
 query:str
 documents:list[dict[str,Any]]
 internal_policy:list[dict[str,Any]]=field(default_factory=list)
 blocked_values:list[str]=field(default_factory=list)

 def public(self):return {'query':self.query,'documents':self.documents}
 def signature(self):return digest(self.public())


def project_case(case):
 if not isinstance(case.get('query'),str):raise ValueError('Query text required.')
 documents=[];internal=[];blocked=set()
 for key in ['protected_markers','protected_markers_used_only_by_validator','forbidden_disclosures','forbidden_disclosures_used_only_by_validator']:
  blocked.update(v for v in case.get(key,[]) if isinstance(v,str) and v)
 for source in case.get('sources',[]):
  access=source.get('access_mode','DENY');visibility=source.get('existence_visibility','PUBLIC')
  for value in source.get('protected_markers',[]):
   if value:blocked.add(str(value))
  allowed=(source.get('retrieved',True) and visibility=='PUBLIC' and source.get('purpose_compatibility','compatible')=='compatible' and source.get('security_status','clean')=='clean')
  text=None;kind=None;public_type=None
  if allowed and access=='FULL':
   text=source.get('content','');kind='content';public_type=str(source.get('source_type','Document'))
  elif allowed and access=='AGGREGATE':
   text=source.get('aggregate_view');kind='aggregate';public_type='AuthorizedAggregate'
  elif allowed and access=='METADATA':
   metadata=source.get('metadata') or {}
   fields={key:metadata[key] for key in sorted(set(source.get('allowed_metadata_fields',[]))) if key not in ORACLE_KEYS and key in metadata and (metadata[key] is None or type(metadata[key]) in {str,int,float,bool})}
   text=canonical(fields) if fields else None;kind='metadata';public_type='AuthorizedMetadata'
  if access!='FULL' or not allowed:
   if source.get('content'):blocked.add(source['content'])
  if access=='DENY' or not allowed:
   for key in ['source_id','title']:
    if source.get(key):blocked.add(str(source[key]))
  entry={'original_source_id':source.get('source_id'),'access_mode':access,'existence_visibility':visibility,
   'policy_rule_id':source.get('policy_rule_id'),'purpose_compatibility':source.get('purpose_compatibility','compatible'),
   'included':isinstance(text,str) and bool(text),'projection':kind if isinstance(text,str) and text else None}
  if isinstance(text,str) and text:
   sid=f'view-{len(documents)+1:04d}'
   documents.append({'source_id':sid,'view_kind':kind,'source_type':public_type,'context':text})
   entry['permitted_source_id']=sid
  internal.append(entry)
 request=PermittedRequest(case['query'],documents,internal,sorted(blocked))
 assert_safe_payload(request,request.public())
 return request


def _keys(x):
 if isinstance(x,dict):
  for key,value in x.items():yield key;yield from _keys(value)
 elif isinstance(x,list):
  for value in x:yield from _keys(value)


def assert_safe_payload(request,payload):
 # Same policy-safe documents for analysis and BOTH generators. No hidden counts.
 if payload.get('query')!=request.query or payload.get('documents')!=request.documents:
  raise ValueError('MODEL_PAYLOAD_NOT_BOUND_TO_PERMITTED_REQUEST')
 illegal=set(_keys(payload)) & ORACLE_KEYS
 if illegal:raise ValueError('FORBIDDEN_FIXTURE_FIELDS:'+','.join(sorted(illegal)))
 encoded=canonical(payload)
 for value in request.blocked_values:
  if value and value in encoded or value and value in json.dumps(payload,ensure_ascii=False):
   raise ValueError('PROHIBITED_CONTENT_IN_MODEL_PAYLOAD')
 # Document source IDs are neutral, contiguous after filtering denied sources.
 if [d['source_id'] for d in request.documents]!=[f'view-{i+1:04d}' for i in range(len(request.documents))]:
  raise ValueError('NONNEUTRAL_SOURCE_IDENTIFIER')
 return True
