"""Private catalogue resolution and policy-bound, opaque public view bindings."""
from dataclasses import dataclass,field
from evaluation.infobank_semantic_regression_v1.policy_projection import (PermittedRequest,project_case as base_project,assert_safe_payload as base_guard,canonical,digest)
from .query_profile import profile_query,normalize


def policy_snapshot(case):
 # Local only. Includes policy/catalogue changes, excludes semantic fixture labels/answers.
 return digest({'query':case['query'],'sources':[{k:s.get(k) for k in ['source_id','title','retrieval_aliases','retrieved','access_mode','existence_visibility','purpose_compatibility','security_status','allowed_metadata_fields','aggregate_view','content']} | {'metadata':{k:v for k,v in (s.get('metadata') or {}).items() if k in s.get('allowed_metadata_fields',[]) and k!='runtime_answer'}} for s in case.get('sources',[])]})


def resolve_bindings(case,request,profile):
 sources={s.get('source_id'):s for s in case.get('sources',[])}
 permitted={p['permitted_source_id']:sources[p['original_source_id']] for p in request.internal_policy if p.get('included')}
 target=normalize(profile.get('query_target') or '')
 matches=[]
 if target:
  for view,source in permitted.items():
   # Principled interface extension: private search-index names/aliases. A single
   # retrieved item alone never establishes a target binding. Titles stay local.
   aliases=source.get('retrieval_aliases') or [source.get('title','')]
   if any(re.search(r'(?<!\w)'+re.escape(target)+r'(?!\w)',normalize(alias)) for alias in aliases if isinstance(alias,str)):
    matches.append(view)
 status='AMBIGUOUS' if len(matches)>1 else 'UNRESOLVED'
 public=[{'source_id':d['source_id'],'binding_status':'TRUSTED_QUERY_TARGET' if len(matches)==1 and d['source_id']==matches[0] else status} for d in request.documents]
 provenance={'resolver':'authorized-private-catalogue-exact-target-v1','query_sha256':digest(case['query']),'policy_snapshot':policy_snapshot(case),'matched_permitted_view_ids':matches,'catalogue_field_origin':'retrieval_aliases, otherwise internal source title; never case/pair IDs or gold metadata','binding_assertion_requires_unique_authorized_target_match':True}
 return public,provenance

import re
@dataclass
class BoundRequest(PermittedRequest):
 query_profile:dict=field(default_factory=dict)
 view_bindings:list=field(default_factory=list)
 binding_provenance:dict=field(default_factory=dict)
 _case:dict=field(default_factory=dict,repr=False)
 def public(self):return {**super().public(),'query_profile':self.query_profile,'view_bindings':self.view_bindings}


def project_case(case):
 base=base_project(case);profile=profile_query(case['query']);bindings,provenance=resolve_bindings(case,base,profile)
 for source in case.get('sources',[]):
  for key in ['source_id','title']:
   if source.get(key):base.blocked_values.append(str(source[key]))
 request=BoundRequest(base.query,base.documents,base.internal_policy,base.blocked_values,profile,bindings,provenance,case)
 assert_safe_payload(request,request.public())
 return request


def assert_safe_payload(request,payload):
 base_guard(request,payload)
 if request.query_profile!=profile_query(request.query):raise ValueError('UNTRUSTED_QUERY_PROFILE')
 if payload.get('query_profile')!=request.query_profile or payload.get('view_bindings')!=request.view_bindings:raise ValueError('UNTRUSTED_PROFILE_OR_BINDING')
 if request.binding_provenance['policy_snapshot']!=policy_snapshot(request._case):raise ValueError('STALE_POLICY_OR_BINDING')
 fresh=base_project(request._case)
 if fresh.documents!=request.documents:raise ValueError('PERMITTED_VIEW_CHANGED')
 bindings,_=resolve_bindings(request._case,fresh,profile_query(request.query))
 if bindings!=request.view_bindings:raise ValueError('INVALID_BINDING')
 # Private catalogue names and original IDs never become extra model fields.
 return True
