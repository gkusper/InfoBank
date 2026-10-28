"""Stage-5b request-relative checks. Determinism validates contracts, not entailment."""
from dataclasses import dataclass,asdict
import hashlib,json,re
from evaluation.refusalbench_span_fix_v1.span_references import build_catalogue,resolve_span
VERSION='recv-1.0'
STATES={'COVERED','PARTIALLY_COVERED','NOT_COVERED','UNKNOWN'}
TYPE_FORMS={'NAMED_IDENTITY':{'NAMED_ENTITY','LIST'},'DATE_TIME':{'DATE_TIME','LIST'},'LOCATION':{'LOCATION','LIST'},'COUNT':{'NUMBER'},'QUANTITY':{'NUMBER'},'DURATION':{'NUMBER','DATE_TIME'},'INSTANCE':{'INSTANCE','LIST'},'BOOLEAN':{'BOOLEAN'},'EXPLANATION':{'EXPLANATION'},'PROCESS':{'EXPLANATION','DESCRIPTION','LIST'},'DESCRIPTION':{'DESCRIPTION','EXPLANATION','DEFINITION','LIST'},'FACT':None,'SELECTION':None,'METADATA':None,'UNRESOLVED':set()}
QUALIFIERS={'first':'FIRST','earliest':'EARLIEST','last':'LAST','latest':'LATEST','only':'ONLY','unique':'UNIQUE'}
@dataclass(frozen=True)
class Requirement:
 requirement_id:str
 request_text:str
 request_type:str
 answer_type:str
 requested_relation:str
 qualifiers:tuple
 cardinality:str
 precision:str
 required:bool=True

def decompose(profile,query):
 """Enrich the existing requirement list, never replace its IDs or infer from access.
 Qualifiers are recognized only in the actual requirement wording. No exact-day
 requirement is invented for an ordinary WHEN question.
 """
 result=[]
 for req in profile['requirements']:
  text=req.get('request_text') or query;words=set(re.findall(r'\b\w+\b',text.casefold()))
  qualifiers=tuple(v for k,v in QUALIFIERS.items() if k in words)
  cardinality='COMPLETE_LIST' if re.search(r'\b(?:list all|all (?:members|names|items|records)|every)\b',text,re.I) else 'SINGLE_OR_UNSPECIFIED'
  kind=req.get('answer_kind','UNRESOLVED');rtype=req.get('request_type','UNRESOLVED')
  if rtype in {'AGGREGATE_COUNT','AGGREGATE_SUM','AGGREGATE_AVERAGE'}:kind={'AGGREGATE_COUNT':'COUNT','AGGREGATE_SUM':'QUANTITY','AGGREGATE_AVERAGE':'QUANTITY'}[rtype]
  precision='EXACT_DAY' if re.search(r'\b(?:exact (?:calendar )?(?:day|date)|day, month and year)\b',text,re.I) else 'RANGE' if re.search(r'\b(?:date range|between which dates)\b',text,re.I) else 'UNSPECIFIED'
  from .source_capability_rules import relation_family
  relation=relation_family(req,query)
  if relation=='UNSPECIFIED':relation='AUTHORSHIP' if re.search(r'\b(?:wrote|author|authored)\b',text,re.I) else 'PUBLICATION' if re.search(r'\b(?:published|publication)\b',text,re.I) else 'QUERY_SPECIFIED_RELATION'
  result.append(Requirement(req['requirement_id'],text,rtype,kind,relation,qualifiers,cardinality,precision))
 return result

def _state(checks,partial):
 vals=list(checks.values())
 if False in vals:return 'PARTIALLY_COVERED' if partial else 'NOT_COVERED'
 if None in vals:return 'UNKNOWN'
 return 'COVERED'

def verify(request,data,semantic_valid=True,semantic_overrides=None):
 """Only validated analyzer properties may attest a relation. Unknown != absence.
 Optional overrides are focused-verifier attestations bound by the caller to the
 exact request/candidate/spans; they never override false mechanical checks.
 """
 docs={d['source_id']:d for d in request.documents};texts={s:d['context'] for s,d in docs.items()};cat=build_catalogue(texts)
 roles={r.get('source_id'):r for r in data.get('source_assessments',[])}
 raw=data.get('requirement_support',[]);supports={r.get('requirement_id'):r for r in raw};overrides=semantic_overrides or {};rows=[]
 requirements=decompose(request.query_profile,request.query)
 duplicates=len(supports)!=len(raw);expected={r.requirement_id for r in requirements};extra=set(supports)-expected
 for req in requirements:
  s=supports.get(req.requirement_id,{});checks={};reasons=[];references=list(s.get('supporting_span_ids',[]));resolved=[]
  def check(key,value,code):
   checks[key]=value
   if value is not True:reasons.append(code)
  check('assessment_valid',bool(semantic_valid),'RECV-INVALID-ASSESSMENT')
  check('requirement_present',bool(s) and not duplicates and not extra,'RECV-REQUIREMENT-MAPPING')
  candidate=data.get('answer_candidate');check('candidate_available',isinstance(candidate,str) and bool(candidate.strip()) and candidate.strip().casefold() not in {'null','none','unknown','n/a'},'RECV-NO-ANSWER')
  valid_refs=bool(references)
  for ref in references:
   try:resolved.append(resolve_span(ref,texts,cat))
   except ValueError:valid_refs=False
  check('references_valid',valid_refs,'RECV-INVALID-OR-MISSING-SPAN')
  check('source_permitted',not any(ref not in cat.spans for ref in references),'RECV-UNAUTHORIZED-SOURCE')
  usable=bool(resolved) and any(roles.get(x['source_id'],{}).get('role')=='PRIMARY' and roles.get(x['source_id'],{}).get('relation_label')=='SUPPORTS' and x['span_id'] in roles.get(x['source_id'],{}).get('grounding_span_ids',[]) for x in resolved)
  check('evidence_role_usable',usable,'RECV-ROLE-NOT-GROUNDED-PRIMARY')
  check('counterevidence_absent',not data.get('contradicting_spans') and data.get('support_status')!='CONFLICTING' and 'conflicting_evidence' not in data.get('uncertainty_causes',[]),'RECV-KNOWN-COUNTEREVIDENCE')
  check('requirement_supported',True if s.get('support_status')=='SUFFICIENT' else None if s.get('support_status') in {None,'UNKNOWN'} else False,'RECV-SUPPORT-'+str(s.get('support_status','UNKNOWN')))
  form=s.get('answer_form');allowed=TYPE_FORMS.get(req.answer_type)
  type_ok=None if not form or form=='UNAVAILABLE' else True if allowed is None else None if form=='OTHER' else form in allowed
  if req.answer_type=='NAMED_IDENTITY' and s.get('identity_identified') is not True:type_ok=False if s.get('identity_identified') is False else None
  check('answer_type_valid',type_ok,'RECV-ANSWER-TYPE')
  check('complete_answer',s.get('complete_answer'),'RECV-INCOMPLETE-REQUIREMENT')
  check('referent_resolved',s.get('referent_resolved'),'RECV-REFERENT-UNRESOLVED')
  relation=s.get('relation_and_qualifiers_supported');check('relation_supported',relation,'RECV-RELATION-UNRESOLVED' if relation is None else 'RECV-RELATION-UNSUPPORTED')
  # The old combined boolean does not separately attest first/only/list scope.
  qstate=None if req.qualifiers and relation is True else relation if req.qualifiers else True
  check('qualifiers_supported',qstate,'RECV-QUALIFIER-SEMANTICS-UNRESOLVED')
  list_state=None if req.cardinality=='COMPLETE_LIST' and s.get('complete_answer') is True else s.get('complete_answer') if req.cardinality=='COMPLETE_LIST' else True
  check('list_exhaustiveness',list_state,'RECV-LIST-EXHAUSTIVENESS-UNRESOLVED')
  metric=data.get('available_granularity','').strip().upper()
  if req.request_type in {'AGGREGATE_SUM','AGGREGATE_AVERAGE'}:
   need=req.request_type.removeprefix('AGGREGATE_');state=(metric==need) if metric in {'COUNT','SUM','AVERAGE'} else None
   check('aggregate_operation_valid',state,'RECV-AGGREGATION-OPERATION')
  if req.precision!='UNSPECIFIED':
   # Only explicit typed precision can attest range/day. Free prose is unknown.
   check('precision_supported',metric==req.precision if metric in {'EXACT_DAY','RANGE','YEAR','DECADE'} else None,'RECV-EXPLICIT-PRECISION-UNRESOLVED')
  check('permitted_scope',all(not (docs[x['source_id']]['view_kind']=='aggregate' and not req.request_type.startswith('AGGREGATE_') or docs[x['source_id']]['view_kind']=='metadata' and req.request_type!='METADATA_LOOKUP') for x in resolved),'RECV-PERMITTED-VIEW-SCOPE')
  inconsistent=(data.get('analysis_refusal_cause') not in {None,'NONE'} and s.get('support_status')=='SUFFICIENT' and s.get('complete_answer') is True) or (data.get('support_status') in {'MISSING','PARTIAL','UNKNOWN'} and s.get('support_status')=='SUFFICIENT')
  check('semantic_fields_consistent',None if inconsistent else True,'RECV-SEMANTIC-FIELDS-INCONSISTENT')
  # Focused semantic assertions resolve only the uncertainty for which supplied.
  override=overrides.get(req.requirement_id)
  if override:
   for key in ['relation_supported','qualifiers_supported','list_exhaustiveness','semantic_fields_consistent']:
    if checks.get(key) is None and key in override:checks[key]=override[key]
   reasons=[code for code in reasons if not (code=='RECV-QUALIFIER-SEMANTICS-UNRESOLVED' and checks['qualifiers_supported'] is True or code=='RECV-LIST-EXHAUSTIVENESS-UNRESOLVED' and checks['list_exhaustiveness'] is True or code=='RECV-RELATION-UNRESOLVED' and checks['relation_supported'] is True or code=='RECV-SEMANTIC-FIELDS-INCONSISTENT' and checks['semantic_fields_consistent'] is True)]
  status=_state(checks,s.get('support_status')=='PARTIAL' or s.get('complete_answer') is False and bool(resolved))
  rows.append({'requirement':asdict(req),'requirement_id':req.requirement_id,'coverage_status':status,**checks,'supporting_spans':references,'reason_codes':reasons,'reason_code':reasons[0] if reasons else None,'semantic_relation_provenance':'focused_model_attestation' if override else 'existing_analyzer_attestation' if relation is not None else 'UNKNOWN','deterministic_entailment_proof':False,'counterevidence_preserved':list(data.get('contradicting_spans',[]))})
 result={'version':VERSION,'request_signature':request.signature(),'assessment_sha256':hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest(),'requirements':rows,'all_essential_covered':bool(rows) and all(r['coverage_status']=='COVERED' for r in rows),'requirements_identified':len(rows)}
 validate(result);return result

def validate(result):
 ids=[r['requirement_id'] for r in result['requirements']]
 if len(ids)!=len(set(ids)):raise ValueError('RECV-DUPLICATE-REQUIREMENTS')
 for r in result['requirements']:
  if r['coverage_status'] not in STATES:raise ValueError('RECV-INVALID-STATE')
  if r['coverage_status']=='COVERED' and (r['reason_codes'] or any(r.get(k) is not True for k in ['assessment_valid','requirement_present','candidate_available','references_valid','source_permitted','evidence_role_usable','counterevidence_absent','requirement_supported','answer_type_valid','complete_answer','referent_resolved','relation_supported','qualifiers_supported','list_exhaustiveness','permitted_scope','semantic_fields_consistent'])):raise ValueError('RECV-INCONSISTENT-COVERED')
 if result['all_essential_covered']!=(bool(ids) and all(r['coverage_status']=='COVERED' for r in result['requirements'])):raise ValueError('RECV-INCONSISTENT-SUMMARY')
 json.dumps(result,allow_nan=False);return True
