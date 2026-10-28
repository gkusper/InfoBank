"""Authorized catalogue resolution; titles/IDs/counts stay privileged."""
from dataclasses import dataclass,asdict
import hashlib,json,re
from .vendor.query_anchors import deterministic_allowed_keyword_matches
VERSION='trusted-target-1.0'
@dataclass(frozen=True)
class Entry:
 view_id:str
 entity_key:str
 entity_type:str
 aliases:tuple[str,...]
 identifiers:tuple[str,...]=()
 edition:str|None=None
 owned:bool|None=None
 ownership_evidenced:bool=False
 is_previous:bool=False
 origin:str='AUTHORIZED_RETRIEVAL_CATALOGUE'
@dataclass(frozen=True)
class Catalogue:
 entries:tuple[Entry,...]
 request_signature:str
 view_hashes:tuple[tuple[str,str],...]
 catalogue_sha256:str

class Resolution(dict):
 def __init__(self,data,catalogue):super().__init__(data);self.catalogue=catalogue
class LegacyResolution(dict):
 def __init__(self,data,request):super().__init__(data);self.request_signature=request.signature();self.bindings_sha256=_digest(request.view_bindings)

def _digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=True).encode()).hexdigest()
def make_catalogue(request,entries):
 docs={d['source_id']:d for d in request.documents};entries=tuple(entries)
 if any(not isinstance(e,Entry) or e.view_id not in docs for e in entries):raise ValueError('TARGET_UNAUTHORIZED_VIEW')
 if any(e.origin not in {'AUTHORIZED_RETRIEVAL_CATALOGUE','AUTHORIZED_INGESTION_SCHEMA','ORIGINAL_SYNTHETIC_CATALOGUE'} for e in entries):raise ValueError('TARGET_UNTRUSTED_PROVENANCE')
 hashes=tuple(sorted((sid,hashlib.sha256(d['context'].encode()).hexdigest()) for sid,d in docs.items()))
 return Catalogue(entries,request.signature(),hashes,_digest([asdict(e) for e in entries]))

def catalogue_from_request(request,trusted_fixture=False):
 """The flag is a trusted harness/ingestion assertion, never a document field.
 Only included policy views are considered; denied names are never inspected.
 """
 if not trusted_fixture:return make_catalogue(request,[])
 sources={s.get('source_id'):s for s in request._case.get('sources',[])};entries=[]
 for p in request.internal_policy:
  if not p.get('included'):continue
  s=sources[p['original_source_id']];c=s.get('trusted_catalogue') or {};sid=p['permitted_source_id'];aliases=tuple(str(a) for a in (c.get('aliases') or s.get('retrieval_aliases') or [s.get('title','')]) if a)
  entries.append(Entry(sid,str(c.get('entity_id') or p['original_source_id']),str(c.get('entity_type') or 'Document'),aliases,tuple(str(v) for v in c.get('identifiers',[])),str(c['edition']) if c.get('edition') is not None else None,c.get('owned'),bool(c.get('ownership_evidenced',False)),bool(c.get('is_previous',False)),'AUTHORIZED_INGESTION_SCHEMA' if c else 'ORIGINAL_SYNTHETIC_CATALOGUE'))
 return make_catalogue(request,entries)

def _phrase(text,value):return bool(value and re.search(r'(?<!\w)'+re.escape(value)+r'(?!\w)',text,re.I))
def _normal(value):return ' '.join(re.findall(r'[^\W_]+',value.casefold()))
def validate_catalogue(request,catalogue):
 if not isinstance(catalogue,Catalogue) or catalogue.request_signature!=request.signature():raise ValueError('TARGET_STALE_REQUEST')
 fresh=make_catalogue(request,catalogue.entries)
 if fresh!=catalogue:raise ValueError('TARGET_STALE_CATALOGUE_OR_CONTENT')
 return True

def resolve(request,catalogue):
 validate_catalogue(request,catalogue);q=request.query;entries=catalogue.entries;query_target=request.query_profile.get('query_target');pronoun=bool(re.search(r'\b(?:it|its|this|that|previous|earlier)\b',q,re.I));candidates={};method='NO_AUTHORIZED_ANCHOR';matched=[]
 identifiers=[v for e in entries for v in e.identifiers if _phrase(q,v)]
 if identifiers:
  selected=[e for e in entries if set(e.identifiers)&set(identifiers)];method='EXPLICIT_AUTHORIZED_IDENTIFIER';matched=identifiers
 else:
  aliases=[a for e in entries for a in e.aliases];anchors=deterministic_allowed_keyword_matches(q,aliases,limit=max(1,len(aliases)));contiguous=[a for a in anchors if _phrase(_normal(q),_normal(a))]
  if contiguous:selected=[e for e in entries if any(a in contiguous for a in e.aliases)];method='DECLARED_AUTHORIZED_ALIAS';matched=contiguous
  elif query_target and len(re.findall(r'\w+',query_target))>=2:
   selected=[e for e in entries if any(_phrase(_normal(a),_normal(query_target)) for a in e.aliases)];method='AUTHORIZED_QUERY_TARGET_ANCHOR';matched=[query_target] if selected else []
  else:selected=[]
  if not selected and re.search(r'\b(?:my|owned)\b',q,re.I):
   selected=[e for e in entries if e.owned is True and e.ownership_evidenced and _phrase(q,e.entity_type)];method='EXPLICIT_OWNED_TYPE_WITH_TRUSTED_OWNERSHIP';matched=sorted({e.entity_type for e in selected})
 for e in selected:candidates.setdefault(e.entity_key,[]).append(e)
 # Resolve editions only from declared version/previous relations, never retrieval order.
 if re.search(r'\b(?:previous|earlier) (?:version|edition)\b',q,re.I):
  previous=[e for e in selected if e.is_previous]
  if previous:candidates={k:[e for e in v if e.is_previous] for k,v in candidates.items() if any(e.is_previous for e in v)};method+=':TRUSTED_PREVIOUS_VERSION'
  elif selected:method+=':PREVIOUS_VERSION_UNRESOLVED';candidates={}
 else:
  edition=re.search(r'\b(?:edition|version)\s+([\w.-]+)',q,re.I)
  if edition:
   candidates={k:[e for e in v if e.edition and e.edition.casefold()==edition.group(1).rstrip('.,;:?!').casefold()] for k,v in candidates.items() if any(e.edition and e.edition.casefold()==edition.group(1).rstrip('.,;:?!').casefold() for e in v)};method+=':EXPLICIT_EDITION'
 count=len(candidates)
 if count==1:
  key=next(iter(candidates));matched_entries=candidates[key]
  edition_scoped='EDITION' in method or 'VERSION' in method
  selected_views=sorted({e.view_id for e in matched_entries}) if edition_scoped else sorted({e.view_id for e in entries if e.entity_key==key})
  state='RESOLVED';target='resolved-target-0001';target_type=matched_entries[0].entity_type
 elif count>1:state='AMBIGUOUS';target=None;target_type=None;selected_views=[]
 else:state='UNRESOLVED' if query_target or pronoun or identifiers or re.search(r'\b(?:document|file|object|my|edition|version)\b',q,re.I) else 'NOT_APPLICABLE';target=None;target_type=None;selected_views=[]
 result={'version':VERSION,'query_target':query_target,'target_id':target,'target_type':target_type,'state':state,'resolution_method':method,'permitted_view_ids':selected_views,'authoritative_anchor':matched,'authority':'TRUSTED_STRUCTURED_SOURCE' if state=='RESOLVED' else 'UNRESOLVED','candidate_count_privileged':count,'catalogue_entry_count_privileged':len(entries),'request_signature':request.signature(),'catalogue_sha256':catalogue.catalogue_sha256,'relation_entailment_proven':False}
 return Resolution(result,catalogue)

def validate_resolution(result,request,catalogue):
 validate_catalogue(request,catalogue)
 if result!=resolve(request,catalogue):raise ValueError('TARGET_BINDING_TAMPERED_OR_STALE')
 return True

def public_summary(result):
 # Deliberately contains no target text, identifier, titles, view list or counts.
 return {'resolution_state':result['state'],'binding_available':result['state']=='RESOLVED','relation_entailment_proven':False}


def legacy_resolution(request):
 from evaluation.refusalbench_iterative_dev_v1.versions.v02.metadata_binding import assert_safe_payload
 assert_safe_payload(request,request.public())
 views=[b['source_id'] for b in request.view_bindings if b['binding_status']=='TRUSTED_QUERY_TARGET']
 data={'state':'RESOLVED' if views else 'UNRESOLVED' if request.query_profile.get('query_target') else 'NOT_APPLICABLE','target_id':'legacy-target-0001' if views else None,'target_type':'Document' if views else None,'permitted_view_ids':views,'authority':'TRUSTED_STRUCTURED_SOURCE' if views else 'UNRESOLVED','resolution_method':'EXISTING_PRIVATE_METADATA_BINDING','candidate_count_privileged':len(views),'relation_entailment_proven':False}
 return LegacyResolution(data,request)

def validate_target_authority(target,request):
 if target['state']!='RESOLVED':return True
 if isinstance(target,Resolution):return validate_resolution(target,request,target.catalogue)
 if isinstance(target,LegacyResolution):
  fresh=legacy_resolution(request)
  if target!=fresh or target.request_signature!=request.signature() or target.bindings_sha256!=_digest(request.view_bindings):raise ValueError('TARGET_STALE_LEGACY_BINDING')
  return True
 raise ValueError('TARGET_NATIVE_AUTHORITY_REQUIRED')
