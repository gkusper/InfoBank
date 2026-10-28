"""Query-provenant output obligations, enriching the existing query-profile types."""
import hashlib,re
from evaluation.refusalbench_iterative_dev_v1.versions.v02.query_profile import profile_query as legacy_profile
VERSION='rda-query-1.0'
QUALIFIERS={'first':'FIRST','last':'LAST','earliest':'EARLIEST','latest':'LATEST','only':'ONLY','unique':'UNIQUE','most':'MAXIMUM','fewest':'MINIMUM'}
ATTRIBUTES={'color':'ATTRIBUTE','colour':'ATTRIBUTE','height':'QUANTITY','width':'QUANTITY','age':'QUANTITY','author':'NAMED_IDENTITY','owner':'NAMED_IDENTITY','format':'METADATA','file type':'METADATA','creation date':'DATE_TIME','founding year':'DATE_TIME','year':'DATE_TIME','date':'DATE_TIME'}
BOUNDARY=r'\s+(?:and|then|also)\s+(?=(?:(?:who|what|where|when|which|how many|how much|how long)\b|(?:the |their |its |his |her )?(?:average|mean|sum|total|count|number)\b|(?:give|list|report|identify|name)\b))'

def _trim(query,start,end):
 while start<end and query[start] in ' \t\r\n,;':start+=1
 while end>start and query[end-1] in ' \t\r\n,;':end-=1
 return start,end

def _clauses(query):
 boundaries=[]
 for match in re.finditer(BOUNDARY,query,re.I):boundaries.append((match.start(),match.end()))
 for match in re.finditer(r';\s*(?=\w)',query):boundaries.append((match.start(),match.end()))
 boundaries=sorted(set(boundaries));parts=[];start=0
 for left,right in boundaries:
  if left<start:continue
  a,b=_trim(query,start,left)
  if a<b:parts.append((a,b))
  start=right
 a,b=_trim(query,start,len(query))
 if a<b:parts.append((a,b))
 # Parallel explicit attributes create output obligations, not extra entity questions.
 if len(parts)==1:
  pattern=r'\b('+ '|'.join(sorted((re.escape(k) for k in ATTRIBUTES),key=len,reverse=True))+r')\s+and\s+('+ '|'.join(sorted((re.escape(k) for k in ATTRIBUTES),key=len,reverse=True))+r')\b'
  match=re.search(pattern,query,re.I)
  if match:parts=[match.span(1),match.span(2)]
 return parts or [(0,len(query))]

def _kind(text,legacy):
 q=text.strip().casefold();reqs=legacy.get('requirements',[]);types={r['request_type'] for r in reqs}
 if re.search(r'\b(?:average|mean)\b',q):return 'QUANTITY','AGGREGATE_AVERAGE','AVERAGE'
 if re.search(r'\b(?:sum|total amount)\b',q):return 'QUANTITY','AGGREGATE_SUM','SUM'
 if re.match(r'^(?:(?:report|give) )?(?:the )?(?:count|number)\b',q) or re.match(r'^how many\b',q):return 'COUNT','AGGREGATE_COUNT','COUNT'
 if re.match(r'^list\b',q):return 'DESCRIPTION',next(iter(types)) if len(types)==1 and next(iter(types))!='UNRESOLVED' else 'FACT_LOOKUP','ENUMERATE'
 if re.match(r'^who\b',q):return 'NAMED_IDENTITY','FACT_LOOKUP','IDENTIFY'
 if re.match(r'^where\b',q):return 'LOCATION','FACT_LOOKUP','LOCATE'
 if re.match(r'^when\b',q) or re.search(r'\b(?:what|which) year\b',q):return 'DATE_TIME','FACT_LOOKUP','TIME'
 if re.match(r'^how much\b',q):return 'QUANTITY',next(iter(types)) if len(types)==1 and next(iter(types))!='UNRESOLVED' else 'FACT_LOOKUP','QUANTITY'
 if re.match(r'^how long\b',q):return 'DURATION','FACT_LOOKUP','DURATION'
 if q.rstrip('?') in ATTRIBUTES:
  kind=ATTRIBUTES[q.rstrip('?')];return ('FACT' if kind=='ATTRIBUTE' else kind),'METADATA_LOOKUP' if kind=='METADATA' else 'FACT_LOOKUP','ATTRIBUTE:'+q.rstrip('?')
 if reqs and len(reqs)==1:
  req=reqs[0];return req.get('answer_kind','UNRESOLVED'),req['request_type'],req['request_type']
 return 'UNRESOLVED','UNRESOLVED','UNRESOLVED'

def decompose(query,profile=None):
 if not isinstance(query,str) or not query.strip():raise ValueError('RDA_QUERY_REQUIRED')
 profile=legacy_profile(query) if profile is None else profile;requirements=[];prior_identity=[];parts=_clauses(query);attribute_split=len(parts)>1 and all(query[a:b].casefold() in ATTRIBUTES for a,b in parts)
 for index,(start,end) in enumerate(parts):
  text=query[start:end];local=legacy_profile(text);kind,rtype,operation=_kind(text,local)
  # Preserve policy-specific types in each actual clause; a WHO clause itself is
  # not permission to disclose individual records, and an explicit record stays so.
  special=[r for r in local['requirements'] if r['request_type'] in {'INDIVIDUAL_RECORD','METADATA_LOOKUP','DOCUMENT_CONTENT','ACTION_LOOKUP'}]
  if special and not (re.match(r'^who\b',text,re.I) and not re.search(r'\b(?:individual|record|employee|transaction)\b',text,re.I)):
   if len(special)==1:rtype=special[0]['request_type'];kind='METADATA' if rtype=='METADATA_LOOKUP' else kind
  if len(parts)==1 and len(profile.get('requirements',[]))>1:
   # Keep a trace of legacy extra obligations; uncertain mapping is never hidden.
   resolution='PARTIAL'
  else:resolution='RESOLVED' if kind!='UNRESOLVED' else 'UNRESOLVED'
  inferred_qualifiers=[]
  qualifiers=[{'value':v,'query_start':start+m.start(),'query_end':start+m.end(),'explicit':True} for word,v in QUALIFIERS.items() for m in re.finditer(r'\b'+word+r'\b',text,re.I)]
  confirmed=[]
  for qualifier in qualifiers:
   token=query[qualifier['query_start']:qualifier['query_end']]
   preceding=query[max(start,qualifier['query_start']-5):qualifier['query_start']].casefold()
   if token[:1].isupper() and qualifier['query_start']>start or preceding.endswith('not '):
    inferred_qualifiers.append({**qualifier,'explicit':False,'required':False,'resolution_status':'SEMANTIC_SCOPE_UNRESOLVED'})
   else:confirmed.append({**qualifier,'required':True,'resolution_status':'EXPLICIT_WORDING_SCOPE_REQUIRES_SEMANTICS'})
  qualifiers=confirmed
  pronouns=list(re.finditer(r'\b(?:he|him|his|she|her|they|them|their|it|its)\b',text,re.I));dependencies=[];internal=[]
  if pronouns:
   if len(prior_identity)==1:dependencies=[prior_identity[0]];internal.append({'kind':'ANAPHORA','status':'PROPOSED','antecedent_requirement_id':prior_identity[0]})
   else:internal.append({'kind':'ANAPHORA','status':'UNRESOLVED','antecedent_requirement_id':None})
  precision='YEAR' if re.search(r'\b(?:what|which) year\b|\bfounding year\b',text,re.I) else 'DECADE' if re.search(r'\bdecade\b',text,re.I) else 'EXACT_DAY' if re.search(r'\bexact (?:calendar )?(?:date|day)\b',text,re.I) else 'RANGE' if re.search(r'\bdate range\b|\bbetween which dates\b',text,re.I) else 'UNSPECIFIED'
  complete_list=bool(re.search(r'\b(?:list all|all (?:members|names|items|records)|every)\b',text,re.I))
  if attribute_split and {r['request_type'] for r in profile['requirements']}=={'METADATA_LOOKUP'}:rtype='METADATA_LOOKUP'
  rid=f'request-{index+1}';fields=sorted({f for r in local.get('requirements',[]) for f in r.get('metadata_fields',[])})
  if attribute_split and rtype=='METADATA_LOOKUP':
   field_map={'file type':'file_type','format':'file_type','creation date':'created_at','author':'author','owner':'owner'}
   fields=[field_map[text.casefold()]] if text.casefold() in field_map else fields
  if attribute_split:internal.append({'kind':'SHARED_QUERY_SUBJECT','status':'INFERRED_CONTEXT','query_context':query})
  # Legacy-parent IDs record provenance, not a claim that the coarse assertion
  # independently establishes each newly separated child.
  parents=[r['requirement_id'] for r in profile.get('requirements',[]) if len(profile.get('requirements',[]))==1 or (r.get('request_text') or query).casefold() in text.casefold() or text.casefold() in (r.get('request_text') or query).casefold()]
  requirements.append({'requirement_id':rid,'request_type':rtype,'answer_kind':kind,'answer_type':kind,'request_text':text,'query_span':{'start':start,'end':end,'text':text},'relation_or_operation':operation,'metadata_fields':fields,'qualifiers':qualifiers,'inferred_qualifiers':inferred_qualifiers,'depends_on':dependencies,'internal_dependencies':internal,'cardinality':'COMPLETE_LIST' if complete_list else 'SINGLE_OR_UNSPECIFIED','requested_precision':precision,'required':True,'explicit':True,'resolution_status':resolution,'parent_requirement_ids':parents})
  if kind=='NAMED_IDENTITY':prior_identity.append(rid)
 result={**profile,'version':VERSION,'query_sha256':hashlib.sha256(query.encode()).hexdigest(),'original_query':query,'requirements':requirements,'legacy_requirements':profile.get('requirements',[]),'resolution':'RESOLVED' if all(r['resolution_status']=='RESOLVED' for r in requirements) else 'PARTIAL','method':'query-only-output-obligation-decomposition','decomposition_completeness':'NOT_INDEPENDENTLY_ANNOTATED'}
 validate(result);return result

def validate(profile):
 query=profile['original_query'];ids=[r['requirement_id'] for r in profile['requirements']]
 if ids!=[f'request-{i+1}' for i in range(len(ids))]:raise ValueError('RDA_UNSTABLE_IDS')
 if hashlib.sha256(query.encode()).hexdigest()!=profile['query_sha256']:raise ValueError('RDA_QUERY_CHANGED')
 for req in profile['requirements']:
  span=req['query_span']
  if query[span['start']:span['end']]!=span['text'] or req['request_text']!=span['text']:raise ValueError('RDA_INVALID_QUERY_SPAN')
  if any(x not in ids[:ids.index(req['requirement_id'])] for x in req['depends_on']):raise ValueError('RDA_INVALID_DEPENDENCY')
  for qualifier in req['qualifiers']:
   if not qualifier['explicit'] or query[qualifier['query_start']:qualifier['query_end']].casefold() not in QUALIFIERS:raise ValueError('RDA_INVENTED_QUALIFIER')
 return True
