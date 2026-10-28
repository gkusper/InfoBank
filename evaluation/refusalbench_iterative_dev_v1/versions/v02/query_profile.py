"""Query-only request/answer typing; access-independent generic factual coverage."""
import re
from evaluation.infobank_semantic_integration_v2.query_profile import profile_query as previous_profile,normalize,target_from_query


def answer_kind(text):
 q=text.strip().casefold()
 if re.search(r'\b(?:specific|concrete|an?)\s+example\b',q):return 'INSTANCE'
 q=re.sub(r'^(?:please\s+)?(?:can|could|would) you (?:tell|show) me\s+','',q)
 rules=[(r'^who\b','NAMED_IDENTITY'),(r'^where\b','LOCATION'),(r'^when\b','DATE_TIME'),(r'^how many\b','COUNT'),(r'^how much\b','QUANTITY'),(r'^how long\b','DURATION'),(r'^which\b','SELECTION'),(r'^what\b','FACT'),(r'^why\b','EXPLANATION'),(r'^how\b','PROCESS'),(r'^(is|are|was|were|does|do|did|has|have|can|could|would|will)\b','BOOLEAN')]
 for pattern,kind in rules:
  if re.search(pattern,q):return kind
 # Fronted user context/edition/date does not erase the actual question type.
 m=re.search(r'(?:^|,\s*)(who|where|when|what|which|why|how)\b',q)
 if m:return answer_kind(q[m.start(1):])
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
 result.update(version='iterative-query-v2',method='query_only_factual_patterns_with_preserved_governance_types',answer_kind=kind)
 return result

# Strict query-only fallback: no context, answer text, source ID or mode field.
import dataclasses,hashlib,json
from evaluation.wolala2026.semantic_evidence import _schema_errors
PROFILE_SCHEMA={'type':'object','properties':{
 'resolution':{'type':'string','enum':['RESOLVED','UNRESOLVED']},
 'query_target':{'type':['string','null']},
 'requirements':{'type':'array','items':{'type':'object','properties':{
  'requirement_id':{'type':'string'},'request_type':{'type':'string','enum':['FACT_LOOKUP','AGGREGATE_COUNT','AGGREGATE_SUM','AGGREGATE_AVERAGE','AGGREGATE_OTHER','INDIVIDUAL_RECORD','METADATA_LOOKUP','DOCUMENT_CONTENT','ACTION_LOOKUP','UNRESOLVED']},
  'metadata_fields':{'type':'array','items':{'type':'string'}},
  'answer_kind':{'type':'string','enum':['NAMED_IDENTITY','LOCATION','DATE_TIME','FACT','SELECTION','COUNT','QUANTITY','DURATION','INSTANCE','DESCRIPTION','EXPLANATION','PROCESS','BOOLEAN','METADATA','UNRESOLVED']},
  'request_text':{'type':'string'}},'required':['requirement_id','request_type','metadata_fields','answer_kind','request_text'],'additionalProperties':False}}},
 'required':['resolution','query_target','requirements'],'additionalProperties':False}
PROFILE_PROMPT="""Interpret only the user's query, without any retrieved context. Return typed request requirements, not a decision whether to answer or refuse. Never propose an answer or infer permissions. Ordinary telegraphic factual queries can be resolved to an answer type when their intent is clear. WHO/person-name fragments request identity; a generic person question does not automatically request an individual data record. Preserve metadata, aggregate, action and explicit individual-record intents. Retain multiple essential requirements. If the requested information/referent cannot be specified from the question, keep UNRESOLVED. Use sequential requirement IDs request-1, request-2. Copy request_text exactly from the query or one contiguous query span; never add an answer. query_target must be null or a copied query substring. No FULL/CFAF fields."""
@dataclasses.dataclass(frozen=True)
class ProfileAssessment:
 query_sha256:str
 raw:str

def parse_profile(query,raw):
 try:data=json.loads(raw)
 except (ValueError,TypeError):raise ValueError('QUERY_PROFILE_INVALID_JSON')
 errors=_schema_errors(data,PROFILE_SCHEMA)
 if errors:raise ValueError('QUERY_PROFILE_SCHEMA_INVALID:'+','.join(errors))
 if not data['requirements'] or [r['requirement_id'] for r in data['requirements']]!=[f'request-{i+1}' for i in range(len(data['requirements']))]:raise ValueError('QUERY_PROFILE_REQUIREMENT_IDS_INVALID')
 if any(not req['request_text'] or req['request_text'].casefold() not in query.casefold() for req in data['requirements']):raise ValueError('QUERY_PROFILE_INVENTED_REQUEST_TEXT')
 if data['query_target'] is not None and data['query_target'].casefold() not in query.casefold():raise ValueError('QUERY_PROFILE_INVENTED_TARGET')
 if data['resolution']=='RESOLVED' and any(r['request_type']=='UNRESOLVED' or r['answer_kind']=='UNRESOLVED' for r in data['requirements']):raise ValueError('QUERY_PROFILE_INCONSISTENT_RESOLUTION')
 return ProfileAssessment(hashlib.sha256(query.encode()).hexdigest(),raw)

def profile_from_assessment(query,assessment):
 if assessment.query_sha256!=hashlib.sha256(query.encode()).hexdigest():raise ValueError('QUERY_PROFILE_WRONG_QUERY')
 validated=parse_profile(query,assessment.raw);data=json.loads(validated.raw)
 data.update(version='iterative-query-v2-query-only-fallback',method='validated_query_only_llm_fallback',answer_kind=data['requirements'][0]['answer_kind'])
 return data
