"""Versioned, claim-relative source capabilities at the trusted ingestion boundary.
No document text is used to establish source provenance or semantic entailment.
"""
from dataclasses import dataclass,asdict
import hashlib,json,re
VERSION='source-capabilities-1.0'
@dataclass(frozen=True)
class Rule:
 rule_id:str
 source_type:str
 relation_family:str
 state:str
 permitted_use:str
 additional_evidence:str
 version:str=VERSION
RULES=[
 Rule('SRC-BROWSER-VISIT','BrowserHistory','PAGE_VISIT','PERMITTED','Recorded page visit',''),
 Rule('SRC-BROWSER-OBLIGATION','BrowserHistory','OBLIGATION','ADDITIONAL_EVIDENCE_REQUIRED','Context about a visit','Evidence establishing the obligation'),
 Rule('SRC-BROWSER-ACTION','BrowserHistory','RECORDED_ACTION','ADDITIONAL_EVIDENCE_REQUIRED','Viewed task description','Recorded acceptance or next action'),
 Rule('SRC-BROWSER-COMPLETION','BrowserHistory','COMPLETION','ADDITIONAL_EVIDENCE_REQUIRED','Context about a visit','Evidence of completion'),
 Rule('SRC-EMAIL-REQUEST','Email','COMMUNICATED_REQUEST','PERMITTED','Communicated request or statement',''),
 Rule('SRC-EMAIL-COMPLETION','Email','COMPLETION','ADDITIONAL_EVIDENCE_REQUIRED','Request or statement','Independent evidence of action completion'),
 Rule('SRC-INVOICE-ISSUE','Invoice','ISSUANCE','PERMITTED','Invoice issuance',''),
 Rule('SRC-INVOICE-AMOUNT','Invoice','AMOUNT','PERMITTED','Stated invoiced amount',''),
 Rule('SRC-INVOICE-PAYMENT','Invoice','PAYMENT','ADDITIONAL_EVIDENCE_REQUIRED','Invoiced amount or issuance','Payment evidence'),
 Rule('SRC-RECEIPT-PAYMENT','PaymentReceipt','PAYMENT','PERMITTED','Documented payment',''),
 Rule('SRC-RECEIPT-CLOSURE','PaymentReceipt','ALL_OBLIGATIONS_CLOSED','ADDITIONAL_EVIDENCE_REQUIRED','A documented payment','Closure of every requested obligation'),
 Rule('SRC-TASK-ACTION','TaskNote','RECORDED_ACTION','PERMITTED','Recorded task or next action',''),
 Rule('SRC-TASK-COMPLETION','TaskNote','COMPLETION','ADDITIONAL_EVIDENCE_REQUIRED','Recorded task','Completion evidence'),
 Rule('SRC-AGGREGATE','AggregateReport','AGGREGATE','PERMITTED','Authorized aggregate value',''),
 Rule('SRC-AGGREGATE-INDIVIDUAL','AggregateReport','INDIVIDUAL','FORBIDDEN','Aggregate only','Authorized individual view'),
 Rule('SRC-METADATA','DocumentMetadata','METADATA','PERMITTED','Whitelisted attributes',''),
 Rule('SRC-METADATA-BODY','DocumentMetadata','DOCUMENT_BODY','FORBIDDEN','Metadata only','Authorized document body'),
]
ALIASES={'browserhistory':'BrowserHistory','browser_history':'BrowserHistory','browser history':'BrowserHistory','email':'Email','e-mail':'Email','invoice':'Invoice','paymentreceipt':'PaymentReceipt','payment receipt':'PaymentReceipt','tasknote':'TaskNote','task note':'TaskNote','aggregatereport':'AggregateReport','documentmetadata':'DocumentMetadata','authorizedaggregate':'AggregateReport','authorizedmetadata':'DocumentMetadata','document':'Document'}
def canonical_type(value):return ALIASES.get(str(value).casefold(),str(value))
def relation_family(requirement,query):
 t=requirement.get('request_type','');q=requirement.get('request_text') or query;q=q.casefold()
 if t.startswith('AGGREGATE_'):return 'AGGREGATE'
 if t=='METADATA_LOOKUP':return 'METADATA'
 if t=='INDIVIDUAL_RECORD':return 'INDIVIDUAL'
 if t=='DOCUMENT_CONTENT':return 'DOCUMENT_BODY'
 if re.search(r'\b(?:all|every)\b.*\b(?:closed|settled|obligations?)\b',q):return 'ALL_OBLIGATIONS_CLOSED'
 if re.search(r'\b(?:complete[ds]?|finished|done|fulfilled)\b',q):return 'COMPLETION'
 if re.search(r'\b(?:paid|payment|settled)\b',q):return 'PAYMENT'
 if re.search(r'\b(?:obligation|contract|obliged|accepted|agreed|must)\b',q):return 'OBLIGATION'
 if re.search(r'\b(?:visited|opened|browsed|page visit)\b',q):return 'PAGE_VISIT'
 if re.search(r'\b(?:requested|communicated|asked|sent)\b',q):return 'COMMUNICATED_REQUEST'
 if re.search(r'\b(?:issued|issuance)\b',q):return 'ISSUANCE'
 if re.search(r'\b(?:amount|price)\b',q):return 'AMOUNT'
 if t=='ACTION_LOOKUP' or re.search(r'\b(?:next action|recorded task)\b',q):return 'RECORDED_ACTION'
 return 'UNSPECIFIED'
@dataclass(frozen=True)
class Provenance:
 source_id:str
 source_type:str
 content_sha256:str
 origin:str
 trusted:bool

def trusted_provenance(request,allowed_origin=False):
 """Called by trusted application ingestion, never with a model-supplied type.
 Fixture origin is an explicit harness assertion, not a production connector claim.
 Restricted-view types follow authoritative policy projection regardless of origin.
 """
 result={}
 for d in request.documents:
  projected=d['view_kind'] in {'aggregate','metadata'}
  result[d['source_id']]=Provenance(d['source_id'],canonical_type(d['source_type']),hashlib.sha256(d['context'].encode()).hexdigest(),'policy_projection' if projected else 'original_synthetic_ingestion_fixture' if allowed_origin else 'unattested_public_passage',projected or allowed_origin)
 return result

def capability(document,relation,provenance=None,registry=None):
 registry=RULES if registry is None else registry
 trusted=isinstance(provenance,Provenance) and provenance.trusted and provenance.source_id==document['source_id'] and provenance.content_sha256==hashlib.sha256(document['context'].encode()).hexdigest() and canonical_type(provenance.source_type)==canonical_type(document['source_type'])
 # Policy views are authoritative, independent of claimed content provenance.
 typ='AggregateReport' if document['view_kind']=='aggregate' else 'DocumentMetadata' if document['view_kind']=='metadata' else canonical_type(provenance.source_type) if trusted else None
 rules=[r for r in registry if r.source_type==typ and r.relation_family==relation]
 rule=rules[0] if rules else None
 return {'source_id':document['source_id'],'relation_family':relation,'source_type':typ,'provenance_trusted':trusted or document['view_kind']!='content','capability_state':rule.state if rule else 'UNKNOWN','rule_id':rule.rule_id if rule else 'SRC-NO-APPLICABLE-TRUSTED-RULE','rule_version':VERSION,'semantic_sufficiency_proven':False,'requires_additional_evidence':rule.additional_evidence if rule else 'Claim-relative semantic assessment remains necessary'}

def evaluate_sources(request,data,provenance=None):
 """An unknown capability alone does not invalidate otherwise usable evidence."""
 provenance=provenance or {};docs={d['source_id']:d for d in request.documents};roles={r['source_id']:r for r in data.get('source_assessments',[])}
 from evaluation.refusalbench_span_fix_v1.span_references import build_catalogue
 cat=build_catalogue({s:d['context'] for s,d in docs.items()});results=[]
 supports={r['requirement_id']:r for r in data.get('requirement_support',[])}
 for req in request.query_profile['requirements']:
  support=supports.get(req['requirement_id'],{});family=relation_family(req,request.query);caps=[]
  for ref in support.get('supporting_span_ids',[]):
   if ref not in cat.spans:continue
   sid=cat.spans[ref].source_id;c=capability(docs[sid],family,provenance.get(sid));role=roles.get(sid,{})
   c['span_id']=ref;c['upstream_role']=role.get('role','UNKNOWN');c['effective_role']='CONTEXTUAL' if c['capability_state'] in {'FORBIDDEN','ADDITIONAL_EVIDENCE_REQUIRED'} else c['upstream_role'];caps.append(c)
  usable=[c for c in caps if c['effective_role']=='PRIMARY' and roles.get(c['source_id'],{}).get('relation_label')=='SUPPORTS']
  constrained=[c for c in caps if c['capability_state'] in {'FORBIDDEN','ADDITIONAL_EVIDENCE_REQUIRED'}]
  blocked=bool(constrained) and not usable
  results.append({'requirement_id':req['requirement_id'],'relation_family':family,'sources':caps,'blocked':blocked,'reason_codes':sorted({c['rule_id'] for c in constrained}) if blocked else [],'unknown_capability_count':sum(c['capability_state']=='UNKNOWN' for c in caps)})
 return results
