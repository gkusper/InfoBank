"""Requirement-claim-evidence diagnostics; lexical matches never gain authority."""
from dataclasses import dataclass
import hashlib,re,json
from decimal import Decimal,InvalidOperation
from .vendor.relation_anchors import claim_relation_signals
from .metadata_value_typing import bind_metadata,parse_temporal
from evaluation.cfaf_requirement_alignment_v1.requirement_alignment import WORDS

@dataclass(frozen=True)
class StructuredFact:
 source_id:str
 subject_view_ids:tuple[str,...]
 predicate:str
 value:object
 value_type:str
 request_signature:str
 source_sha256:str
 origin:str='AUTHORIZED_INGESTION_SCHEMA'
 operation:str|None=None
 qualifiers:tuple[str,...]=()

def validate_fact(fact,request):
 if not isinstance(fact,StructuredFact) or fact.origin!='AUTHORIZED_INGESTION_SCHEMA':raise ValueError('CLAIM_UNTRUSTED_FACT')
 docs={d['source_id']:d for d in request.documents}
 if fact.request_signature!=request.signature() or fact.source_id not in docs or not set(fact.subject_view_ids)<=set(docs):raise ValueError('CLAIM_UNAUTHORIZED_FACT_BINDING')
 if fact.source_sha256!=hashlib.sha256(docs[fact.source_id]['context'].encode()).hexdigest():raise ValueError('CLAIM_STALE_STRUCTURED_FACT')
 from .metadata_value_typing import typed_value
 if typed_value(fact.value,fact.value_type) is not True:raise ValueError('CLAIM_STRUCTURED_TYPE_INVALID')
 try:record=json.loads(docs[fact.source_id]['context'])
 except (ValueError,TypeError):raise ValueError('CLAIM_STRUCTURED_RECORD_REQUIRED')
 expected={'predicate':fact.predicate,'value':fact.value,'value_type':fact.value_type,'subject_view_ids':list(fact.subject_view_ids)}
 if not isinstance(record,dict) or any(record.get(k)!=v for k,v in expected.items()):raise ValueError('CLAIM_FACT_NOT_BOUND_TO_SOURCE_FIELDS')
 if fact.operation is not None and record.get('operation')!=fact.operation:raise ValueError('CLAIM_OPERATION_NOT_BOUND')
 return True

def predicate(req):
 if req.get('requested_attribute'):return req['requested_attribute']
 q=req['request_text'].casefold()
 if re.search(r'\b(?:play|plays|portray|portrays|role|character)\b',q):return 'actor_role'
 if re.search(r'\b(?:wrote|written|author|authored)\b',q):return 'authored_by'
 if re.search(r'\b(?:published|publication)\b',q):return 'publication_time' if req['answer_type']=='DATE_TIME' else 'publication_attribute'
 if req['answer_type']=='COUNT':
  m=re.search(r'how many\s+([\w-]+)',q);noun=m.group(1) if m else 'items'
  return noun+'_scored' if re.search(r'\bscore|scored\b',q) else noun+'_count'
 return req['relation_or_operation']

def _tokens(text):return set(re.findall(r'[^\W_][\w-]{2,}',str(text).casefold()))-{'the','and','was','were','what','which','who','when','how','many','does','did','for','with','this','that'}
def _normalize_number_words(text):
 def combine(m):return str(WORDS[m.group(1).casefold()]+WORDS[m.group(2).casefold()])
 return re.sub(r'\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)[- ](one|two|three|four|five|six|seven|eight|nine)\b',combine,str(text),flags=re.I)

def _numbers(text):
 text=_normalize_number_words(text)
 text=re.sub(r'(?m)^\s*\d{1,2}[.)]\s+','',str(text));values=set()
 for token in re.findall(r'\b(?:\d+(?:[.,]\d+)?|'+ '|'.join(WORDS)+r')\b',text,re.I):
  value=WORDS.get(token.casefold(),token.replace(',','.'))
  try:values.add(str(Decimal(str(value)).normalize()))
  except InvalidOperation:pass
 return values

def relation_diagnostics(req,candidate,evidence):
 """Adapted from main question_source_support/answer_source_support.
 Uses only scoped authorized spans; no filename, threshold veto or query-number
 exception. Outputs are lexical diagnostics, never a sufficient-support claim.
 """
 question=req['request_text'];text=' '.join(s['quote'] for s in evidence);terms=_tokens(question);qrel=claim_relation_signals(question);arel=claim_relation_signals(str(candidate or ''));srel=claim_relation_signals(text);missing=sorted((set(qrel)|set(arel))-set(srel));unsupported=sorted(_numbers(candidate or '')-_numbers(text));query_only=sorted(set(unsupported)&_numbers(question));warnings=[]
 if missing:warnings.append('LEXICAL_RELATION_ANCHOR_MISSING')
 if unsupported:warnings.append('NUMERIC_TOKEN_NOT_IN_SCOPED_EVIDENCE')
 if req.get('qualifiers'):warnings.append('QUALIFIER_ENTAILMENT_UNRESOLVED')
 if predicate(req)=='actor_role' and not re.search(r'\b(?:play|plays|portray|portrays|role|character)\b',text,re.I):warnings.append('ROLE_RELATION_ANCHOR_MISSING')
 if not evidence:warnings.append('NO_SCOPED_SUPPORTING_SPANS')
 return {'question_relations':qrel,'candidate_relations':arel,'source_relations':srel,'missing_relation_anchors':missing,'unsupported_numeric_tokens':unsupported,'numbers_only_in_question':query_only,'lexical_coverage':len(terms&_tokens(text))/len(terms) if terms else None,'warnings':warnings,'authority':'UNRESOLVED','semantic_entailment_proven':False,'source_functions_adapted':['relevance.claim_relation_signals','evidence_service.question_source_support','evidence_service.answer_source_support']}

def minimal_span_recommendation(req,candidate,spans,counter_refs):
 # Diagnostic only. Retain all counterevidence and never change model retrieval.
 if counter_refs:return {'span_ids':sorted({s['span_id'] for s in spans}|set(counter_refs)),'counter_span_ids':list(counter_refs),'reason':'COUNTEREVIDENCE_PRESERVED_NO_MINIMIZATION','applied_to_model_context':False}
 if len(spans)>12:return {'span_ids':[s['span_id'] for s in spans],'reason':'BOUNDED_SEARCH_FALLBACK','applied_to_model_context':False}
 needed=_tokens(req['request_text'])|_tokens(candidate or '');all_hits=set().union(*(_tokens(s['quote'])&needed for s in spans)) if spans else set();remaining=set(all_hits);selected=[]
 for s in sorted(spans,key=lambda s:(-len(_tokens(s['quote'])&needed),s['span_id'])):
  hits=_tokens(s['quote'])&remaining
  if hits:selected.append(s['span_id']);remaining-=hits
 return {'span_ids':selected,'preserved_lexical_anchors':not remaining,'reason':'GREEDY_ANCHOR_COVERAGE_DIAGNOSTIC','applied_to_model_context':False,'semantic_sufficiency_proven':False}

def align_claims(profile,alignment,data,request,target,structured_facts=()):
 from .trusted_target_resolution import validate_target_authority
 validate_target_authority(target,request)
 for fact in structured_facts:validate_fact(fact,request)
 claims=[]
 roles={r['source_id']:r for r in data.get('source_assessments',[])};documents={d['source_id']:d for d in request.documents}
 for row in alignment['requirements']:
  req=row['requirement'];value=(row['candidate_fragment'] or {}).get('text')
  if value is not None and req['answer_type']=='COUNT':
   fragment=row['candidate_fragment'];candidate=data.get('answer_candidate') or '';start=fragment.get('start')
   if isinstance(start,int):
    prefix=candidate[:start];m=re.search(r'\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)-$',prefix,re.I)
    if m:value=m.group(0)+str(value)
   normalized=_normalize_number_words(value);normalized=str(WORDS.get(normalized.casefold(),normalized))
   if re.fullmatch(r'\d+',normalized):value=int(normalized)
  pred=predicate(req);spans=row['resolved_supporting_spans'];scoped=[s for s in spans if target['state']!='RESOLVED' or s['source_id'] in target['permitted_view_ids']];warnings=[]
  if target['state']=='RESOLVED' and len(scoped)!=len(spans):warnings.append('SUPPORT_OUTSIDE_RESOLVED_TARGET')
  meta=bind_metadata(req,request,target,data.get('answer_candidate'));authority='LLM_SEMANTIC_ASSESSMENT' if row['model_semantic_properties'].get('relation_and_qualifiers_supported') is True else 'UNRESOLVED';status='SUPPORTED_BY_ASSESSMENT' if authority=='LLM_SEMANTIC_ASSESSMENT' else 'UNRESOLVED'
  lexical=relation_diagnostics(req,value or data.get('answer_candidate') or '',scoped);warnings.extend(lexical['warnings'])
  if value is None:warnings.append('CANDIDATE_FRAGMENT_UNRESOLVED')
  if req['depends_on']:warnings.append('SUBJECT_VALUE_ASSOCIATION_REQUIRES_SEMANTICS')
  scope_compatible=all(not (documents[e['source_id']]['view_kind']=='aggregate' and not req['request_type'].startswith('AGGREGATE_') or documents[e['source_id']]['view_kind']=='metadata' and req['request_type']!='METADATA_LOOKUP') for e in scoped)
  role_usable=any(roles.get(e['source_id'],{}).get('role')=='PRIMARY' and roles.get(e['source_id'],{}).get('relation_label')=='SUPPORTS' for e in scoped)
  if not scope_compatible:warnings.append('REQUEST_EXCEEDS_PERMITTED_VIEW_SCOPE')
  trusted_value=None
  if meta['status']=='FIELD_VALUE_MATCH':value=meta['candidate_fragment']['text'];trusted_value=meta['supported_value'];authority='TRUSTED_STRUCTURED_SOURCE';status='STRUCTURED_FIELD_MATCH'
  elif meta['status'] not in {'NOT_APPLICABLE'}:warnings.append(meta.get('uncertainty',meta['status']))
  facts=[f for f in structured_facts if f.predicate==pred and f.source_id in {s['source_id'] for s in scoped}]
  if facts:
   f=facts[0];trusted_value=f.value;authority='TRUSTED_STRUCTURED_SOURCE'
   if target['state']!='RESOLVED':status='UNRESOLVED_TARGET_ASSOCIATION';authority='UNRESOLVED';warnings.append('TARGET_NOT_TRUSTED_RESOLVED')
   elif not set(f.subject_view_ids)&set(target['permitted_view_ids']):status='STRUCTURED_TARGET_MISMATCH';warnings.append('WRONG_STRUCTURED_TARGET')
   elif value is None:status='UNRESOLVED_CANDIDATE_ALIGNMENT';authority='UNRESOLVED';warnings.append('CANDIDATE_FRAGMENT_UNRESOLVED')
   elif f.operation and req['relation_or_operation'] in {'COUNT','SUM','AVERAGE'} and f.operation!=req['relation_or_operation']:status='STRUCTURED_OPERATION_MISMATCH';warnings.append('COUNT_SUM_AVERAGE_MISMATCH')
   else:
    def equal(a,b):
     if f.value_type in {'COUNT','QUANTITY','NUMBER'}:
      av=WORDS.get(str(a).casefold(),a)
      try:return Decimal(str(av))==Decimal(str(b))
      except (InvalidOperation,ValueError):return False
     return str(a).casefold()==str(b).casefold()
    status='STRUCTURED_VALUE_MATCH' if equal(value,f.value) else 'STRUCTURED_VALUE_MISMATCH'
    if status.endswith('MISMATCH'):warnings.append('CANDIDATE_DIFFERS_FROM_TRUSTED_FIELD')
  claims.append({'requirement_id':req['requirement_id'],'subject_target_id':target['target_id'] if target['state']=='RESOLVED' else None,'target_state':target['state'],'proposed_subject_dependency':req['depends_on'],'predicate':pred,'predicate_query_span':req['query_span'],'candidate_value':value,'value_type':req.get('value_type',req['answer_type']),'value_authority':'TRUSTED_STRUCTURED_SOURCE' if authority=='TRUSTED_STRUCTURED_SOURCE' else 'DETERMINISTIC_TYPED_EXTRACTION' if row['candidate_fragment'] else 'UNRESOLVED','qualifiers':req['qualifiers'],'temporal_scope':req['requested_precision'],'supporting_spans':[s['span_id'] for s in scoped],'original_supporting_spans':row['supporting_span_ids'],'authority':authority,'relation_status':status,'evidence_scope_compatible':scope_compatible,'upstream_evidence_role_usable':role_usable,'trusted_supported_value':trusted_value,'metadata_binding':meta,'relation_diagnostics':lexical,'uncertainties':sorted(set(warnings)),'minimal_evidence_recommendation':minimal_span_recommendation(req,value,scoped,data.get('contradicting_spans',[])),'general_entailment_proof':False})
 return {'version':'claim-evidence-1.0','claims':claims,'no_evidence_removed_from_model':True,'lexical_checks_are_shadow_only':True}
