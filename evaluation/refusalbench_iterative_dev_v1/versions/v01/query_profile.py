"""Query-only request/answer typing; access-independent generic factual coverage."""
import re
from evaluation.infobank_semantic_integration_v2.query_profile import profile_query as previous_profile,normalize,target_from_query


def answer_kind(text):
 q=text.strip().casefold()
 rules=[(r'^(?:please\s+)?who\b','NAMED_IDENTITY'),(r'^where\b','LOCATION'),(r'^when\b','DATE_TIME'),(r'^how many\b','COUNT'),(r'^how much\b','QUANTITY'),(r'^how long\b','DURATION'),(r'^which\b','SELECTION'),(r'^what\b','FACT')]
 for pattern,kind in rules:
  if re.search(pattern,q):return kind
 if re.search(r'\b(?:specific |an? )example\b',q):return 'INSTANCE'
 if re.search(r'^(describe|summarize|explain|name|identify)\b',q):return 'DESCRIPTION'
 return 'UNRESOLVED'


def profile_query(query):
 result=previous_profile(query);kind=answer_kind(query);q=query.casefold();types=[r['request_type'] for r in result['requirements']]
 preserve=any(t in {'AGGREGATE_COUNT','AGGREGATE_SUM','AGGREGATE_AVERAGE','AGGREGATE_OTHER','INDIVIDUAL_RECORD','METADATA_LOOKUP','ACTION_LOOKUP'} for t in types)
 # Generic "who received an award" requests a public identity, not necessarily a
 # personal-data record. Explicit individual/record requests retain their scope.
 if types==['INDIVIDUAL_RECORD'] and re.match(r'who\b',q) and not re.search(r'\b(individual|record|ticket|transaction|employee)\b',q):preserve=False
 if types==['DOCUMENT_CONTENT'] and kind!='UNRESOLVED' and not re.search(r'\b(body|contents|full text|document text|memo|report|document|token|code)\b',q):preserve=False
 if types==['METADATA_LOOKUP'] and result['requirements'][0]['metadata_fields']==['author'] and not re.search(r'\b(file|document|memo|report|metadata)\b',q):preserve=False
 if not preserve and kind!='UNRESOLVED':
  parts=re.split(r'\s+(?:and|then)\s+(?=(?:who|what|where|when|which|how)\b)',query,flags=re.I)
  result['requirements']=[{'requirement_id':f'request-{i+1}','request_type':'FACT_LOOKUP','metadata_fields':[],'answer_kind':answer_kind(part),'request_text':part} for i,part in enumerate(parts)]
  result['resolution']='RESOLVED'
 else:
  for req in result['requirements']:
   req['answer_kind']='METADATA' if req['request_type']=='METADATA_LOOKUP' else 'COUNT' if req['request_type']=='AGGREGATE_COUNT' else kind
   req['request_text']=query
 result.update(version='iterative-query-v1',method='query_only_factual_patterns_with_preserved_governance_types',answer_kind=kind)
 return result
