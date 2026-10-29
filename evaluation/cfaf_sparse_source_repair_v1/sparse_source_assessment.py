"""Sparse bookkeeping does not invent evidential roles or semantic claims."""
import copy,json
from evaluation.cfaf_target_claim_alignment_v1 import integration as baseline
from evaluation.wolala2026.semantic_evidence import _schema_errors,unknown_assessment
from evaluation.refusalbench_span_fix_v1.span_references import REFERENCE_SCHEMA,parse_reference_assessment,build_catalogue
from .source_inventory import build_inventory,validate_inventory
from .reference_validation import normalize_reference

def parse_sparse(raw,request,inventory=None,allow_repair=True):
 inventory=inventory or build_inventory(request);validate_inventory(inventory,request)
 audit={'version':'sparse-source-contract-1','valid':False,'errors':[],'repairs':[],'inventory_sha256':inventory.inventory_sha256,'request_signature':inventory.request_signature,'inventory_states':[],'substantive_source_issues':[],'raw_model_changed':False}
 try:rawdata=json.loads(raw)
 except (ValueError,TypeError):return unknown_assessment(['INVALID_JSON'],'gpt-4o-mini'),{},dict(audit,errors=['INVALID_JSON'])
 data=copy.deepcopy(rawdata)
 if isinstance(data,dict) and isinstance(data.get('source_assessments'),list):
  for role in data['source_assessments']:
   if isinstance(role,dict) and 'view_id' in role:
    if 'source_id' in role and role['source_id']!=role['view_id']:audit['errors'].append('CONFLICTING_VIEW_ALIAS')
    else:
     role['source_id']=role.pop('view_id');audit['repairs'].append({'method':'FIELD_ALIAS_VIEW_ID_TO_SOURCE_ID'})
 # Normalize only exact alternative representations. Invalid references stay invalid.
 if isinstance(data,dict):
  containers=[(data,k) for k in ['supporting_spans','contradicting_spans']]
  containers += [(r,'grounding_span_ids') for r in data.get('source_assessments',[]) if isinstance(r,dict)] if isinstance(data.get('source_assessments'),list) else []
  containers += [(r,'supporting_span_ids') for r in data.get('requirement_support',[]) if isinstance(r,dict)] if isinstance(data.get('requirement_support'),list) else []
  for obj,key in containers:
   if not isinstance(obj.get(key),list):continue
   for i,reference in enumerate(obj[key]):
    try:
     normalized,repair,span=normalize_reference(reference,inventory,request,allow_repair)
     if repair:obj[key][i]=normalized;audit['repairs'].append({**repair,'field':key,'index':i})
    except ValueError as exc:audit['errors'].append(str(exc))
 schema_errors=_schema_errors(data,baseline.ANALYSIS_SCHEMA);audit['errors'].extend(schema_errors)
 if schema_errors:return unknown_assessment(sorted(set(audit['errors'])),'gpt-4o-mini'),data,audit
 docs={d['source_id']:d['context'] for d in request.documents};cat=build_catalogue(docs);roles={}
 for role in data['source_assessments']:
  sid=role['source_id']
  if sid not in docs:audit['errors'].append('ROLE_UNKNOWN_SOURCE:'+sid)
  if sid in roles:audit['errors'].append('DUPLICATE_SOURCE_ASSESSMENT:'+sid if roles[sid]==role else 'CONFLICTING_SOURCE_ASSESSMENT:'+sid)
  roles[sid]=role
  for reference in role['grounding_span_ids']:
   try:
    normalized,repair,span=normalize_reference(reference,inventory,request,False)
    if span['source_id']!=sid:audit['errors'].append('ROLE_REFERENCE_SOURCE_MISMATCH')
   except ValueError as exc:audit['errors'].append(str(exc))
 expected=[r['requirement_id'] for r in request.query_profile['requirements']]
 if sorted(r['requirement_id'] for r in data['requirement_support'])!=sorted(expected):audit['errors'].append('REQUIREMENT_COVERAGE_INVALID')
 support=list(data['supporting_spans'])+[s for r in data['requirement_support'] for s in r['supporting_span_ids']]
 for ref in support:
  try:
   normalized,repair,span=normalize_reference(ref,inventory,request,False);role=roles.get(span['source_id'])
   if role is None:audit['errors'].append('SUPPORT_SOURCE_NOT_ASSESSED:'+span['source_id'])
   elif role['role']!='PRIMARY' or role['relation_label']!='SUPPORTS':audit['substantive_source_issues'].append('SUPPORT_ROLE_UNUSABLE:'+span['source_id'])
  except ValueError as exc:audit['errors'].append(str(exc))
 for entry in inventory.entries:audit['inventory_states'].append({'source_id':entry.view_id,'assessment_state':'ASSESSED' if entry.view_id in roles else 'NOT_ASSESSED'})
 base={k:v for k,v in data.items() if k in REFERENCE_SCHEMA['properties']};assessment,reference_audit=parse_reference_assessment(json.dumps(base),docs,cat,'gpt-4o-mini')
 audit['reference_audit']=reference_audit;audit['errors']=sorted(set(audit['errors']+reference_audit.get('errors',[])));audit['substantive_source_issues']=sorted(set(audit['substantive_source_issues']));audit['not_assessed_count']=sum(e['assessment_state']=='NOT_ASSESSED' for e in audit['inventory_states']);audit['reported_source_count']=len(roles);audit['source_count']=len(inventory.entries);audit['raw_model_changed']=data!=rawdata
 if audit['errors']:assessment=unknown_assessment(audit['errors'],'gpt-4o-mini')
 audit['valid']=assessment.valid
 # Attach private trusted audit to the native object; it is never put in model data.
 assessment.sparse_audit=audit
 return assessment,data,audit
