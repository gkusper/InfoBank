"""Scoped agent review, separate from gold annotations and human QA."""
from .artifacts import *
REVIEWS=[
 {'topic':'Trusted metadata value typing','live_index':4,'finding':'The existing permitted metadata view supplies file_type and created_at. The corrected representation separates access class METADATA from string versus DATE_TIME value type; both candidate fields match the trusted resolved target. This upgrades provenance of two field relations without changing a mode that was already FULL.','independent':False},
 {'topic':'Catalogue coverage','finding':'Seven live requests resolve from authorized catalogue anchors; none is newly resolved beyond the existing guarded target binding. No RefusalBench cached case has trustworthy application catalogue metadata. NOT_APPLICABLE/UNRESOLVED does not mean the natural-language question has no factual answer.','independent':False},
 {'topic':'Actor/role limitation','live_index':17,'finding':'The passage has the expected lexical role anchors and a supported-looking entity proposal, but also contains another role. New lexical relation/numeric diagnostics do not alert on this label-incompatible FULL. Co-occurrence and an LLM support Boolean are not an independent completeness proof.','independent':False},
 {'topic':'Oregon referent and historical priority','live_indices':[14,23],'finding':'Unresolved temporal candidates or historical first-working qualification produce diagnostics. T3 retains B3/A0 FULL by the declared shadow policy, so these warnings do not constitute prevented false FULL answers.','independent':False},
 {'topic':'Diagnostic specificity','finding':'In the live sample two of three label-incompatible FULL decisions carry some claim uncertainty, while five correct FULL decisions do too. The new lexical relation/number alerts cover none of the three false FULL cases. Treating these warnings as hard refusals would be unjustified.','independent':False},
 {'topic':'Controlled structured claims and aggregation','finding':'Authoritative JSON field binding detects wrong numeric value, subject, actor role and count/average mismatch in synthetic tests. Aggregation uses authorized numeric contributions only. These are secondary controlled results, not an independent benchmark accuracy improvement.','independent':False}
]
if __name__=='__main__':
 for r in REVIEWS:append(ROOT/'qualitative_review.jsonl',r)
