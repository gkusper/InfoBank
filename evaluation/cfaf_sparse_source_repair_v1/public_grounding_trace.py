"""Separate deterministic provenance sidecar. References do not prove entailment."""
from .source_inventory import build_inventory,validate_inventory,resolve_inventory_span
from .operational_failure_codes import validate_response
import hashlib,json

def build_public_grounding_trace(request,semantic,response,assessment_valid,inventory=None,system='semantic_cfaf'):
 inventory=inventory or build_inventory(request);validate_inventory(inventory,request)
 trace={'version':'public-grounding-trace-1-experimental','citations':[],'unverified_associations':[],'missing_citation_reason':None,'semantic_entailment_proven':False,'system':system}
 if not response or validate_response(json.dumps(response)) or response.get('top_level_mode')!='FULL':trace['missing_citation_reason']='NO_VALID_FULL_RESPONSE';return trace
 if not assessment_valid:trace['missing_citation_reason']='OPERATIONAL_VERIFICATION_FAILURE';return trace
 if response.get('answer')!=semantic.get('answer_candidate'):trace['missing_citation_reason']='CITATION_SUPPORT_UNVERIFIED';return trace
 roles={r['source_id']:r for r in semantic.get('source_assessments',[])};global_support=set(semantic.get('supporting_spans',[]));entries={e.view_id:e for e in inventory.entries}
 for requirement in semantic.get('requirement_support',[]):
  eligible=requirement.get('support_status')=='SUFFICIENT' and all(requirement.get(k) is True for k in ['complete_answer','referent_resolved','relation_and_qualifiers_supported'])
  for reference in requirement.get('supporting_span_ids',[]):
   try:span=resolve_inventory_span(reference,inventory,request)
   except ValueError:continue
   role=roles.get(span['source_id'],{});associated=eligible and reference in global_support and reference in role.get('grounding_span_ids',[]) and role.get('role')=='PRIMARY' and role.get('relation_label')=='SUPPORTS'
   if not associated:continue
   # The explicit analyzer requirement-to-candidate-to-span path is auditable,
   # but is not a per-claim proof or permission to attach it to every sentence.
   trace['unverified_associations'].append({'citation_marker':'[S'+span['source_id'].split('-')[1]+'-'+reference.rsplit('-',1)[1]+']','source_id':span['source_id'],'span_id':reference,'start':span['start'],'end':span['end'],'source_sha256':entries[span['source_id']].source_sha256,'claim_group_id':'answer-candidate','requirement_id':requirement['requirement_id'],'answer_sha256':hashlib.sha256(response['answer'].encode()).hexdigest(),'association_basis':'EXACT_CANDIDATE_COPY_AND_EXPLICIT_REQUIREMENT_GLOBAL_ROLE_REFERENCE_INTERSECTION','reference_valid':True,'claim_group_link_valid':True,'claim_level_entailment':'CITATION_SUPPORT_UNVERIFIED','render_as_verified_claim_citation':False})
 # No unverified candidate group is automatically rendered as a grounded claim.
 trace['missing_citation_reason']='CITATION_SUPPORT_UNVERIFIED' if trace['unverified_associations'] else 'NO_EXPLICIT_VALIDATED_ASSOCIATION'
 return trace
