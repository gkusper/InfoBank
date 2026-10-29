"""Operational and evidence-limit reasons use separate versioned internal states."""
import json
from evaluation.wolala2026.labels import ReasonClass,CFAFRealization
from evaluation.refusalbench_iterative_dev_v1.versions.v02.contracts import validate_response as old_validate
PUBLIC_REASON_VERSION='existing-ReasonClass-v1-strict-validation'
PUBLIC_REASONS={e.value for e in ReasonClass}
REALIZATIONS={e.value for e in CFAFRealization}
OPERATIONAL_PUBLIC='The answer could not be verified reliably for this request.'
OPERATIONAL_CODES={'SEMANTIC_ASSESSMENT_INVALID','SOURCE_ASSESSMENT_CONTRACT_INVALID','INVALID_EVIDENCE_REFERENCE','REFERENCE_RESOLUTION_FAILED','GENERATION_CONTRACT_INVALID'}

def classify(request,assessment,issues=(),audit=None):
 if not request.documents:return {'status':'VALIDATED_RESTRICTED_NO_VIEW','reason':'NO_PERMITTED_EVIDENCE','failure_class':'GOVERNANCE_OR_NO_PUBLIC_VIEW','credited_evidential_CFAF':False}
 audit=audit or getattr(assessment,'sparse_audit',{})
 if assessment is None or not assessment.valid:
  errors=audit.get('errors',getattr(assessment,'validation_errors',[]))
  code='INVALID_EVIDENCE_REFERENCE' if any(any(k in e for k in ['SPAN','REFERENCE','QUOTE','SOURCE_HASH','STALE_SOURCE']) for e in errors) else 'SOURCE_ASSESSMENT_CONTRACT_INVALID' if any(any(k in e for k in ['ROLE','SOURCE_ASSESSMENT','SUPPORT_SOURCE','VIEW_ALIAS']) for e in errors) else 'SEMANTIC_ASSESSMENT_INVALID'
  return {'status':'OPERATIONAL_FAILURE','reason':code,'failure_class':'OPERATIONAL','credited_evidential_CFAF':False,'validation_errors':list(errors)}
 if not issues:return {'status':'VERIFIED_FULFILMENT','reason':'FULFILMENT_ESTABLISHED','failure_class':None,'credited_evidential_CFAF':False}
 code='UNRESOLVED_REFERENT' if 'AMBIGUOUS_REFERENCE' in issues else 'UNSUPPORTED_RELATION' if 'REQUEST_RELATION_UNSUPPORTED' in issues else 'REQUIREMENT_NOT_SUPPORTED' if any('REQUIREMENT_UNSUPPORTED' in v or 'SUPPORT_ROLE' in v for v in issues) else 'INSUFFICIENT_EVIDENCE'
 return {'status':'VALIDATED_CFAF','reason':code,'failure_class':'EVIDENTIAL_OR_REQUEST_RELATIVE','credited_evidential_CFAF':True}

def safe_operational_response():return {'answer':OPERATIONAL_PUBLIC,'top_level_mode':'CFAF','fulfilment_status':'NONE','realization':'ABSTAIN','public_reason_class':'EPISTEMIC','next_step_codes':[]}

def validate_response(raw):
 errors=old_validate(raw)
 if errors:return errors
 d=json.loads(raw);reason=d['public_reason_class'];realization=d['realization']
 if reason is not None and reason not in PUBLIC_REASONS:errors.append('NONCANONICAL_PUBLIC_REASON_CLASS')
 if realization is not None and realization not in REALIZATIONS:errors.append('NONCANONICAL_REALIZATION')
 if d['top_level_mode']=='FULL' and (reason is not None or realization is not None):errors.append('FULL_PUBLIC_REASON_MUST_BE_NULL')
 if d['top_level_mode']=='CFAF' and (reason is None or realization is None):errors.append('CFAF_REASON_AND_REALIZATION_REQUIRED')
 return errors
