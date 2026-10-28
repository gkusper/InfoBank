"""Validated Stage-5b component. Existing selector and policy remain authoritative."""
from .request_evidence_coverage import verify
from .source_capability_rules import evaluate_sources
from evaluation.refusalbench_iterative_dev_v1.versions.v02 import implementation as baseline
CONFIGURATIONS={'A0':(False,False),'A1':(True,False),'A2':(False,True),'B':(True,True),'C':(True,True)}
def assess(request,assessment,data,configuration='B',provenance=None,semantic_overrides=None):
 if configuration not in CONFIGURATIONS:raise ValueError('Unknown configuration')
 coverage_on,source_on=CONFIGURATIONS[configuration]
 original=baseline.support_issues(assessment,data,request) if assessment else ['NO_PERMITTED_EVIDENCE']
 from .focused_verification import overrides
 coverage=verify(request,data,assessment.valid if assessment else False,overrides(request,data,semantic_overrides))
 sources=evaluate_sources(request,data,provenance)
 recv=[f"RECV:{r['requirement_id']}:{code}" for r in coverage['requirements'] if r['coverage_status']!='COVERED' for code in r['reason_codes']]
 source=[f"SOURCE:{r['requirement_id']}:{code}" for r in sources if r['blocked'] for code in r['reason_codes']]
 issues=sorted(set(original+(recv if coverage_on else [])+(source if source_on else [])))
 return {'configuration':configuration,'baseline_issues':original,'issues':issues,'coverage':coverage,'source_capabilities':sources,'added_recv_issues':recv if coverage_on else [],'added_source_issues':source if source_on else [],'validated_request_fulfilment':not issues,'change_cause': 'BOTH' if not original and coverage_on and recv and source_on and source else 'RECV' if not original and coverage_on and recv else 'SOURCE_CAPABILITY' if not original and source_on and source else 'UPSTREAM_OR_EXISTING_POLICY' if original else 'UNCHANGED'}

def reason_details(result,request,data):
 if result['baseline_issues']:return baseline.refusal_details(result['baseline_issues'],request,data)
 from evaluation.wolala2026.labels import ReasonClass,CFAFRealization
 issues=result['issues']
 if any(x.startswith('SOURCE:') for x in issues):return ReasonClass.EVIDENTIAL,'SOURCE_CAPABILITY_REQUIRES_ADDITIONAL_EVIDENCE',CFAFRealization.ABSTAIN,'The cited source does not by itself establish the requested relation; additional evidence is required.'
 if any('PERMITTED-VIEW' in x for x in issues):return ReasonClass.GOVERNANCE_PRIVACY,'REQUEST_EXCEEDS_PERMITTED_VIEW',CFAFRealization.RESTRICT_GRANULARITY,'The permitted evidence view does not authorize the requested detail.'
 if any('QUALIFIER' in x or 'LIST-EXHAUSTIVENESS' in x for x in issues):return ReasonClass.EVIDENTIAL,'REQUESTED_COVERAGE_UNRESOLVED',CFAFRealization.ABSTAIN,'The available assessment does not establish complete coverage of the requested qualifier or list.'
 if any('ANSWER-TYPE' in x for x in issues):return ReasonClass.EVIDENTIAL,'ANSWER_TYPE_UNVERIFIED',CFAFRealization.ABSTAIN,'The proposed answer has not been established in the form requested by the question.'
 if any('INCONSISTENT' in x for x in issues):return ReasonClass.EVIDENTIAL,'SEMANTIC_ASSESSMENT_INCONSISTENT',CFAFRealization.ABSTAIN,'The evidence assessment is internally inconsistent about whether the complete request is supported.'
 return ReasonClass.EVIDENTIAL,'REQUEST_COVERAGE_UNRESOLVED',CFAFRealization.ABSTAIN,'The available assessment does not establish complete support for every requested information element.'
