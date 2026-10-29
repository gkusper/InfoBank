"""Existing substantive gate, with sparse-contract and failure classification."""
from evaluation.cfaf_target_claim_alignment_v1.integration_controls import assess as previous_assess,reason_details as previous_reason
from evaluation.wolala2026.labels import ReasonClass,CFAFRealization
from .operational_failure_codes import classify,OPERATIONAL_PUBLIC

def assess(request,assessment,data,configuration='T3',provenance=None,semantic_overrides=None):
 result=previous_assess(request,assessment,data,configuration,provenance,semantic_overrides)
 audit=getattr(assessment,'sparse_audit',{}) if assessment else {};extra=audit.get('substantive_source_issues',[])
 if extra:result['issues']=sorted(set(result['issues']+extra));result['validated_request_fulfilment']=False
 result['verification_outcome']=classify(request,assessment,result['issues'],audit)
 return result

def reason_details(result,request,data):
 outcome=result.get('verification_outcome',{})
 if outcome.get('status')=='OPERATIONAL_FAILURE':return ReasonClass.EPISTEMIC,outcome['reason'],CFAFRealization.ABSTAIN,OPERATIONAL_PUBLIC
 return previous_reason(result,request,data)
