"""RDA-aware Stage 5: authoritative hard failures, semantic shadow diagnostics."""
from types import SimpleNamespace
from .requirement_decomposition import decompose
from .requirement_alignment import align
from evaluation.refusalbench_iterative_dev_v1.versions.v02 import implementation as base
from evaluation.cfaf_request_evidence_verification_v1.decision import assess as strict_recv
from evaluation.cfaf_request_evidence_verification_v1.source_capability_rules import evaluate_sources
CONFIGURATIONS={'A0','B1','B2','B3'}

def assess(request,assessment,data,configuration='B3',provenance=None,semantic_overrides=None):
 if configuration not in CONFIGURATIONS:raise ValueError('RDA_CONFIGURATION_UNKNOWN')
 if semantic_overrides:raise ValueError('OPTIONAL_VERIFIER_DISABLED')
 legacy=base.support_issues(assessment,data,request) if assessment else ['NO_PERMITTED_EVIDENCE']
 profile=decompose(request.query,request.query_profile);alignment=align(profile,data.get('answer_candidate'),data,request.documents)
 source_request=SimpleNamespace(query=request.query,query_profile=profile,documents=request.documents)
 source_data={**data,'requirement_support':[{'requirement_id':r['requirement_id'],'supporting_span_ids':r['supporting_span_ids']} for r in alignment['requirements']]}
 sources=evaluate_sources(source_request,source_data,provenance);by_source={r['requirement_id']:r for r in sources};docs={d['source_id']:d for d in request.documents};roles={r['source_id']:r for r in data.get('source_assessments',[])};hard=[];soft=[];coverage=[]
 for row in alignment['requirements']:
  rid=row['requirement_id'];req=row['requirement'];h=[];w=[]
  def item(code,detail,basis):return {'requirement_id':rid,'code':code,'detail':detail,'justification':basis}
  def H(code,detail,basis='AUTHORITATIVE_APPLICATION_FACT'):h.append(item(code,detail,basis))
  def W(code,detail,basis='UNRESOLVED_SEMANTIC_INTERPRETATION'):w.append(item(code,detail,basis))
  if not request.documents:H('HARD_NO_AUTHORIZED_VIEW','No permitted evidence view is available; no source-existence statement follows.')
  if assessment is not None and not assessment.valid:H('HARD_ASSESSMENT_CONTRACT_INVALID','The upstream schema/reference/coverage contract was rejected.','DETERMINISTIC_VALIDATION')
  if row['span_errors']:H('HARD_INVALID_SPAN',row['span_errors'],'DETERMINISTIC_REFERENCE_VALIDATION')
  if data.get('answer_candidate') is None:H('HARD_NO_CANDIDATE_OUTPUT','The candidate output is explicitly absent. This does not prove that the requested fact does not exist.','DETERMINISTIC_OUTPUT_STRUCTURE')
  if row['explicit_component_missing']:H('HARD_MISSING_EXPLICIT_COMPONENT','A requirement-keyed structured candidate omits this essential component.','DETERMINISTIC_OUTPUT_STRUCTURE')
  if row['structured_candidate'] and row['candidate_fragment'] and row['type_compatible'] is False:H('HARD_STRUCTURED_VALUE_TYPE','A native typed candidate value has an incompatible application type.','DETERMINISTIC_OUTPUT_STRUCTURE')
  forbidden_views=[]
  for span in row['resolved_supporting_spans']:
   kind=docs[span['source_id']]['view_kind'];rtype=req['request_type']
   if kind=='aggregate' and not rtype.startswith('AGGREGATE_') or kind=='metadata' and rtype!='METADATA_LOOKUP':forbidden_views.append(span['source_id'])
  if forbidden_views:H('HARD_REQUEST_EXCEEDS_VIEW',sorted(set(forbidden_views)))
  available_kinds={d['view_kind'] for d in request.documents}
  if available_kinds and 'content' not in available_kinds and req['request_type'] in {'INDIVIDUAL_RECORD','DOCUMENT_CONTENT','ACTION_LOOKUP'}:H('HARD_NO_PERMITTED_REQUEST_SCOPE','Available limited views cannot authorize the requested individual/body/action detail.')
  source=by_source[rid]
  forbidden=[s['rule_id'] for s in source['sources'] if s['capability_state']=='FORBIDDEN']
  if source['blocked'] and forbidden:H('HARD_TRUSTED_SOURCE_USE_FORBIDDEN',sorted(set(forbidden)))
  if source['blocked'] and not forbidden:W('SOFT_SOURCE_ADDITIONAL_EVIDENCE',source['reason_codes'],'TRUSTED_SOURCE_DEFAULT_CAPABILITY_REQUIRING_SEMANTIC_EVIDENCE')
  props=row['model_semantic_properties']
  if row['semantic_parent_mapping']!='EXACT_TYPED_REQUIREMENT':W('SOFT_COARSE_PARENT_ALIGNMENT','Old assertion does not independently describe each separated requirement.')
  if not row['candidate_fragments'] and data.get('answer_candidate') is not None and not row['structured_candidate']:W('SOFT_FRAGMENT_UNRESOLVED','No reliable fragment was extracted from unstructured prose; this is not proof of omission.')
  if req['answer_type']=='NAMED_IDENTITY' and row['candidate_fragment']:
   import re
   name=row['candidate_fragment']['text'];clauses={c.strip() for e in row['resolved_supporting_spans'] for c in re.split(r'[.;\n!?]',e['quote']) if isinstance(name,str) and re.search(re.escape(name),c,re.I)}
   if len(clauses)>1:W('SOFT_SAME_NAME_MULTIPLE_ROLE_CONTEXTS','The proposed name appears in multiple evidence clauses; requested-role association remains semantic.')
   if isinstance(data.get('answer_candidate'),str) and re.search(r'\band\s+[A-Z]',data['answer_candidate']) and len(row['candidate_fragments'])==1:W('SOFT_POSSIBLE_UNMAPPED_ENTITY','Candidate conjunction may include another entity not supplied by the analyzer.')
  if len(row['candidate_fragments'])>1:W('SOFT_MULTIPLE_CANDIDATE_REFERENTS','Several fragment candidates remain possible.')
  if row['candidate_fragment'] and row['type_compatible'] is None:W('SOFT_ANSWER_TYPE_UNVERIFIED','Token shape does not establish the requested semantic answer type.')
  if row['candidate_fragment'] and row['type_compatible'] is False and not row['structured_candidate']:W('SOFT_INFERRED_TYPE_MISMATCH','An inferred prose type is not an authoritative policy violation.')
  if req['qualifiers']:W('SOFT_QUALIFIER_UNVERIFIED',[q['value'] for q in req['qualifiers']])
  if req['cardinality']=='COMPLETE_LIST':W('SOFT_LIST_EXHAUSTIVENESS','Selected members are not proof of an exhaustive list.')
  for dependency in req['internal_dependencies']:
   if dependency['status']=='UNRESOLVED':W('SOFT_REFERENT_UNRESOLVED',dependency)
  association=row['dependency_association']
  if association['status']!='NOT_APPLICABLE':W('SOFT_'+association['status'],association)
  for field,code in [('complete_answer','SOFT_MODEL_INCOMPLETE'),('referent_resolved','SOFT_MODEL_REFERENT_UNRESOLVED'),('relation_and_qualifiers_supported','SOFT_MODEL_RELATION_UNSUPPORTED')]:
   if props.get(field) is False:W(code,'Existing LLM semantic property is negative.','LLM_SEMANTIC_ASSESSMENT')
   elif field not in props:W('SOFT_SEMANTIC_PROPERTY_UNKNOWN',field)
  usable=any(roles.get(s['source_id'],{}).get('role')=='PRIMARY' and roles.get(s['source_id'],{}).get('relation_label')=='SUPPORTS' for s in row['resolved_supporting_spans'])
  if not usable:W('SOFT_EVIDENCE_ROLE_UNUSABLE','The upstream semantic assessment supplies no PRIMARY/SUPPORTS grounding.','LLM_SEMANTIC_ASSESSMENT')
  support=props.get('support_status')
  status='NOT_COVERED' if h else 'PARTIALLY_COVERED' if support=='PARTIAL' else 'NOT_COVERED' if support=='MISSING' or props.get('complete_answer') is False else 'UNKNOWN' if w or support in {None,'UNKNOWN'} else 'COVERED'
  coverage.append({**row,'coverage_status':status,'hard_failures':h,'soft_warnings':w,'evidence_role_usable':usable,'justification':'DETERMINISTIC_OR_AUTHORITATIVE_VIOLATION' if h else 'LLM_SEMANTIC_ASSESSMENT' if status=='COVERED' else 'UNRESOLVED_OR_LLM_SEMANTIC_ASSESSMENT','deterministic_entailment_proof':False});hard.extend(h);soft.extend(w)
 if configuration=='B1':
  old=strict_recv(request,assessment,data,'B',provenance);issues=old['issues'];strict_diagnostics=old
 elif configuration=='A0':issues=legacy;strict_diagnostics=None
 else:issues=sorted(set(legacy+[f"HARD:{h['requirement_id']}:{h['code']}" for h in hard]));strict_diagnostics=None
 cause='HARD_POLICY_OR_OUTPUT_STRUCTURE' if not legacy and hard and configuration in {'B2','B3'} else 'LEGACY_STRICT_RECV' if configuration=='B1' and not legacy and issues else 'UPSTREAM_OR_EXISTING_POLICY' if legacy else 'UNCHANGED_WITH_SOFT_WARNINGS' if soft else 'UNCHANGED'
 result={'version':'rda-recv-1.0','configuration':configuration,'baseline_issues':legacy,'issues':issues,'validated_request_fulfilment':not issues,'requirements_profile':profile,'alignment':alignment,'coverage':{'requirements':coverage,'all_essential_covered':bool(coverage) and all(r['coverage_status']=='COVERED' for r in coverage)},'source_capabilities':sources,'hard_failures':hard,'soft_warnings':soft if configuration!='B2' else [],'shadow_soft_warnings':soft,'soft_enforced':False,'change_cause':cause,'strict_recv_reference':strict_diagnostics,'independent_sufficiency_still_required':True}
 validate(result);return result

def validate(result):
 import json
 ids=[r['requirement_id'] for r in result['coverage']['requirements']]
 if len(ids)!=len(set(ids)):raise ValueError('RDA_DUPLICATE_COVERAGE')
 if result['configuration'] in {'B2','B3'} and result['validated_request_fulfilment'] and (result['baseline_issues'] or result['hard_failures']):raise ValueError('RDA_PROMOTION_WITH_FAILED_SUFFICIENCY')
 if any(r['coverage_status'] not in {'COVERED','PARTIALLY_COVERED','NOT_COVERED','UNKNOWN'} for r in result['coverage']['requirements']):raise ValueError('RDA_INVALID_COVERAGE_STATE')
 json.dumps(result,allow_nan=False);return True

def reason_details(result,request,data):
 if result['configuration']=='A0':return base.refusal_details(result['baseline_issues'],request,data)
 if result['configuration']=='B1':
  from evaluation.cfaf_request_evidence_verification_v1.decision import reason_details as previous_reason
  return previous_reason(result['strict_recv_reference'],request,data)
 from evaluation.wolala2026.labels import ReasonClass,CFAFRealization
 hard=result['hard_failures'];policy=any(h['code'] in {'HARD_REQUEST_EXCEEDS_VIEW','HARD_NO_PERMITTED_REQUEST_SCOPE','HARD_TRUSTED_SOURCE_USE_FORBIDDEN'} for h in hard)
 if policy:return ReasonClass.GOVERNANCE_PRIVACY,'REQUEST_EXCEEDS_PERMITTED_SCOPE',CFAFRealization.RESTRICT_GRANULARITY,'The permitted evidence view does not authorize every requested component.'
 if result['baseline_issues']:return base.refusal_details(result['baseline_issues'],request,data)
 if hard:return ReasonClass.EVIDENTIAL,hard[0]['code'],CFAFRealization.ABSTAIN,'A required answer component or a valid authorized reference is missing from the proposed output.'
 return ReasonClass.EVIDENTIAL,'NO_BLOCKING_FAILURE',CFAFRealization.ABSTAIN,''
