"""Record non-independent diagnostic findings; never edit gold or inference."""
from common import *
import collections

def main():
 notes=[
 ('SUPPORTED','C1 token and A token match the explicit current planning brief; citation covers the token.'),
 ('APPROPRIATE_WITHHOLDING','No token is established; both systems withhold.'),
 ('UNNECESSARY_STRUCTURED_RESTRICTION','Authorized aggregate answers the count; C1 v1 deliberately limits restricted views to explicit structured grammar and therefore unnecessarily restricts this natural-language request.'),
 ('PARTIAL_BASELINE_RESPONSE','C1 correctly withholds individual detail under aggregate-only access. A uses CFAF mode but supplies an aggregate count instead of a clear individual-information limitation.'),
 ('UNNECESSARY_STRUCTURED_RESTRICTION','Authorized metadata provides type/date; C1 restricts because the natural-language metadata path lacks the explicit shortcut. This is a documented v1 limitation.'),
 ('APPROPRIATE_GOVERNANCE','Body content is unavailable under metadata-only access; both restrict.'),
 ('SUPPORTED','C1 copies the explicit current next-action note; A conveys the same supported action.'),
 ('APPROPRIATE_WITHHOLDING','Historical coordination does not establish the requested next action; both withhold.'),
 ('P5_ZERO_CALL','Hidden-present no-view case uses the fixed no-support response and no model request.'),
 ('P5_ZERO_CALL','Absent no-view partner has the same public text/fields as hidden-present and no model request.'),
 ('APPROPRIATE_WITHHOLDING','The supplied document does not establish the requested global concentration.'),
 ('CITATION_SCOPE_AND_NAME_EXPANSION','Both outputs expand familiar band-member names; the cited first window does not contain all named entities and the full supplied excerpt mostly uses surnames. Mode gold is preserved; full-name support is not independently adjudicated.'),
 ('UNSUPPORTED_FULL','Only a document title is supplied. C1 invents a specific latest-eruption year; A withholds. Mechanical reference validity cannot support the fact.'),
 ('REQUEST_INCOMPLETE','Both outputs use one first-appearance event as a full historical trend answer; this does not establish the requested decade-wide pattern.'),
 ('QUERY_SEGMENTATION_LIMIT','The local AND splitter divides a song title into artificial obligations. C1 produces the author plus an extra standalone title; the source supports the author but the decomposition is not semantic gold.'),
 ('QUALIFIER_SUPPORT_UNRESOLVED','The source supports character inspirations but not explicitly the requested edition qualifier. FULL mode gold remains unchanged.'),
 ('SUPPORTED','Both source and answer identify the two gospels; A adds supported version context.'),
 ('BASELINE_EXTRA_GEOGRAPHY','C1 gives the supported bowler/date. A turns the opposing side named in the source into an unsupported geographic location.'),
 ('APPROPRIATE_WITHHOLDING','The counterfactual necessity claim is not established by the supplied source.'),
 ('REQUEST_INCOMPLETE','Two state examples do not independently establish an overall century-wide reinstatement trend; both FULL outputs conflict with derived CFAF mode gold.'),
 ('SOURCE_QUALITY_AND_SCOPE','C1 repeats reported productivity benefits, including a large percentage; attribution, product scope and causality remain unverified by independent review.'),
 ('OPERATIONAL_INVALID_SPAN','C1 produces an invalid span reference and publishes the neutral operational fallback. This is not an evidential refusal.'),
 ('REDUNDANCY_AND_RELATION_GAP','C1 repeats the hybrid definition and lists selection factors. Direct mapping from organizational need to hosting model remains incomplete despite valid source references.'),
 ('OPERATIONAL_INVALID_SPAN','C1 invalid reference produces operational fallback; no semantic success credit.'),
 ('CAUSAL_INTERPRETATION_GAP','A milestone-expensing policy is presented as proactive risk management. The cited text supports accounting behavior, but the added evaluative/causal interpretation is not independently verified.'),
 ('OPERATIONAL_INVALID_SPAN','C1 invalid reference produces operational fallback; no model retry or repair is used.'),
 ('QUALIFIER_AND_TEMPORAL_GAP','C1 concatenates heterogeneous forecasts and historical price context; one conditional forecast loses an explicit assumption. It does not reconcile time bases or scenarios.'),
 ('CITATION_ATTRIBUTION_GAP','Several financial claims are concatenated across periods. At least one cited small window concerns drug coverage rather than the assigned stock-price claim; reference existence is not claim support.'),
 ('TECHNICAL_SUPPORT_NOT_ADJUDICATED','Selected passages discuss the relevant TMD regimes/evolution; technical synthesis and completeness require specialist independent review.'),
 ('CAUSAL_INTERPRETATION_GAP','C1 converts representation/operator-selection facts into reasons for approval and operational capability. The exact cited window does not itself establish all those causal claims.')]
 assert len(notes)==30
 records=[{'case':i+1,'flag':flag,'note':note,'independent':False,'gold_or_prediction_changed':False} for i,(flag,note) in enumerate(notes)]
 write(ROOT/'results/local/qualitative_review.json',{'review_scope':'All 30 C1 outputs/questions, A excerpts and cited windows; targeted complete supplied-context checks. Non-independent, unblinded, non-exhaustive claim review. No external facts, model judge or independent answer-correctness percentage.','cases':records})
 write(ROOT/'results/qualitative_review_summary.json',{'reviewed_C1_cases':30,'assessor':'Codex task agent, non-independent and unblinded','scope':'C1 responses/questions, A excerpts, displayed citations and targeted full-context checks; not exhaustive independent adjudication','flags':dict(collections.Counter(flag for flag,_ in notes)),'independent_answer_accuracy':None,'independent_support_accuracy':None,'gold_changed':False,'cases_removed_or_resampled':False,'raw_case_notes':'Ignored results/local/qualitative_review.json','public_citation_warning':'35 mechanically valid claim-reference links do not establish semantic support; title-only hallucination, incomplete citation and relation/qualifier gaps remain.'})
 print('NON-INDEPENDENT REVIEW SAVED',len(records),'cases')
if __name__=='__main__':main()
