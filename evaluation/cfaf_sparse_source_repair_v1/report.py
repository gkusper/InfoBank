"""Safe report plus ignored full 19-item case review. Agent judgement is not gold."""
import json,collections,csv,datetime
from .artifacts import *
from .cached import PREVIOUS
from .deadline import elapsed

def table(headers,rs):
 def c(x):return str(x).replace('|','/').replace('\n',' ')
 return '| '+' | '.join(headers)+' |\n| '+' | '.join('---' for h in headers)+' |\n'+'\n'.join('| '+' | '.join(c(x) for x in r)+' |' for r in rs)+'\n'
def pct(v):return 'undefined' if v is None else f'{v*100:.2f}%'
def save(name,txt):(ROOT/name).write_text(txt.strip()+'\n',encoding='utf-8')
REVIEW=[
 {'finding':'New FULL answers remain generic workflow summaries. The original update-scoped request is not fully addressed, and every selected support passage is originally NO for relevance. The statements have nearby textual support, but the scope match is poor.','missing':'Recent-update-specific rollout and commercial-agent context.','unsupported_claims':0,'scope_concern':True,'unnecessary_refusal':False,'flag':'UPDATE_SCOPE_NOT_ESTABLISHED'},
 {'finding':'Both new systems give the same short, source-supported explanation. Four selected sources are originally answering-labelled. The omission of further scientific detail does not itself prove an incomplete answer, but long-form adequacy needs a separate rubric.','missing':'Possible omitted magnetic-field/model-testing detail; essentiality is unadjudicated.','unsupported_claims':0,'scope_concern':None,'unnecessary_refusal':False,'flag':'SUPPORTED_CONCISE_ANSWER_PENDING_COMPLETENESS_REVIEW'},
 {'finding':'Both systems produce a generic benefit list without distinguishing the hosting models or explaining their match to particular organizational needs. Answering-labelled source selection does not establish that this comparative requirement is fulfilled.','missing':'Explicit model-by-model correspondence to organizational requirements.','unsupported_claims':0,'scope_concern':True,'unnecessary_refusal':False,'flag':'COMPARATIVE_MAPPING_MISSING'},
 {'finding':'The short responses describe genuine multi-source reasoning difficulties from the selected evidence. They omit several reference-answer details. No unsupported factual claim was identified in this review; a broader completeness judgement remains independent work.','missing':'More specific retrieval, intermediate-reasoning and performance limitations, if required by a future rubric.','unsupported_claims':0,'scope_concern':None,'unnecessary_refusal':False,'flag':'GROUNDED_SUMMARY_NOT_LONG_FORM_VALIDATION'},
 {'finding':'Primary B withholds FULL because of an unpadded span ID. Both served replies are operational, not successful evidence-insufficiency decisions. The raw control still promotes an accounting rule to a risk-management strategy. Cached A3 and supplemental R1 permit a FULL candidate with the same unsupported strategic relation. Original human grounding deflects; no expected label was used to force this case.','missing':'Evidence connecting the accounting treatment to the requested risk-management approach.','unsupported_claims':0,'raw_control_unsupported_claims':1,'cached_candidate_unsupported_claims':1,'scope_concern':True,'unnecessary_refusal':None,'flag':'TECHNICAL_BLOCK_MASKS_UNSUPPORTED_STRATEGIC_INFERENCE'},
 {'finding':'New T3 and control both assert cultural exchange as part of the diplomatic-tour positioning. The explicit cultural-exchange passage concerns a musician, while the validated selected sources do not establish that relation for the prime minister. This is one flagged unsupported relation in each served FULL response, despite valid references and complete semantic flags.','missing':'Correct subject-to-activity relation; specific diplomatic/economic objectives.','unsupported_claims':1,'raw_control_unsupported_claims':1,'scope_concern':True,'unnecessary_refusal':False,'flag':'UNSUPPORTED_CROSS_SUBJECT_RELATION_IN_SERVED_FULL'},
 {'finding':'The forecast values are found in the selected original answering-labelled evidence and remain described as possible scenarios. Both systems omit source attribution and the condition attached to the high forecast. Neither output is evidence that any forecast was realized.','missing':'Forecast attribution, uncertainty and conditional assumptions.','unsupported_claims':0,'scope_concern':True,'unnecessary_refusal':False,'flag':'FORECAST_CONDITIONS_AND_ATTRIBUTION_MISSING'},
 {'finding':'The new sparse analysis validly reports zero source roles and zero support: all fifteen inventory entries remain NOT_ASSESSED, not irrelevant. It still misses available candidate catalysts and sets an unsupported unresolved-referent property. T3 therefore gives a questionable clarification. The raw control abstains with a missing realization field; the strict validator replaces that invalid response with neutral operational wording.','missing':'Assessment of company-specific developments and correct distinction between an explicit company referent and missing factual support.','unsupported_claims':0,'scope_concern':True,'unnecessary_refusal':True,'flag':'SEMANTIC_MISSED_SUPPORT_WITH_CONTROL_CONTRACT_FAILURE'},
 {'finding':'Both systems provide a concise explanation supported by two answering-labelled passages. Broader scientific detail and independent domain review remain outside this bounded experiment. No unsupported factual assertion was identified in the inspected scope.','missing':'Optional evolution/resummation and physical-mechanism detail pending a completeness rubric.','unsupported_claims':0,'scope_concern':None,'unnecessary_refusal':False,'flag':'SUPPORTED_SCIENTIFIC_SUMMARY_PENDING_INDEPENDENT_REVIEW'},
 {'finding':'The nonexistent span index remains invalid in cached and fresh runs; R1 cannot invent it. Both primary served responses are neutral operational CFAF. The raw control still converts network representation and support for a startup timetable into a rationale for approving the operator. These two relations are not established by the supplied text. This is not credited as a correct semantic refusal.','missing':'Actual approval rationale, rather than appointment description or support for a schedule.','unsupported_claims':0,'raw_control_unsupported_claims':2,'scope_concern':True,'unnecessary_refusal':None,'flag':'INVALID_REFERENCE_AND_UNSUPPORTED_CAUSAL_RAW_CONTROL'}
]

def build():
 s=read(ROOT/'evaluation_summary.json');cached=read(ROOT/'cached_ablation_results.json');alias=read(ROOT/'reference_alias_ablation.json');usage=read(ROOT/'api_usage.json');sec=read(ROOT/'security_audit.json');reg=read(ROOT/'regression_audit.json');selection=read(ROOT/'selection_manifest.json');metrics=rows(ROOT/'case_metrics.jsonl');details=rows(ROOT/'local/per_case_diagnostics.jsonl');runtime=rows(ROOT/'runtime_inputs.jsonl');live=rows(ROOT/'live_paired_results.jsonl');oldreview=read(PREVIOUS/'local/agent_review.json')['cases'];gold=rows(PREVIOUS/'gold_annotations.jsonl');rawcached=rows(ROOT/'cached_ablation_raw.jsonl');cited=rows(ROOT/'citation_diagnostics.jsonl')
 write(ROOT/'qualitative_review_summary.json',{'type':'Non-independent agent post-run review, not original gold or independent human labels','served_T3_FULL_with_flagged_unsupported_relations':1,'flagged_served_T3_relation_claims':1,'served_control_FULL_with_flagged_unsupported_relations':1,'raw_control_FULL_cases_with_flagged_unsupported_relations':3,'raw_control_flagged_relation_claims':4,'cached_promoted_deflective_example_flagged':1,'primary_T3_questionable_clarifications':1,'official_accuracy':None,'human_review':'PENDING','cases':[{'sample_id':r['sample_id'],**review} for r,review in zip(metrics,REVIEW)]})
 safe_cases=[];full_cases=[]
 for i,(r,private,review,prior,inp,run,g,crow) in enumerate(zip(metrics,details,REVIEW,oldreview,runtime,live,gold,cached['cases'])):
  out=run['outcome'];a3=crow['variants']['A3'];trace=cited[i]['systems'];role_audit=out['reference_audit'];reported=out['semantic_assessment'].get('source_assessments',[]);raw_refs=out['semantic_assessment'].get('supporting_spans',[]);accepted_sources=r['validated_support_metric']['selected_markers'];unassessed=[x['source_id'] for x in role_audit.get('inventory_states',[]) if x['assessment_state']=='NOT_ASSESSED'];selected_answering=r['validated_support_metric']['correctness_distribution'].get('ANSWER-THE-QUESTION',0)
  safe_response='Concise factual answer; full exact text is in local/REPORT_FULL.md.' if r['new_gate']=='FULL' else 'Neutral operational verification failure.' if r['operational_outcome']['status']=='OPERATIONAL_FAILURE' else 'Clarification request; semantic reason is disputed in review.'
  head=f"### Case {i+1}: `{r['sample_id']}`\n\nAttributed summary of the original GaRAGe question: **{prior['topic']}**."
  item1=f"1. **Original ID / row:** `{r['sample_id']}`; original zero-based row {selection['records'][i]['index_zero_based']}."
  item2=f"2. **Question summary:** {prior['topic']} (original AmazonScience GaRAGe, pinned source commit)."
  item3=f"3. **Original labels:** relevance {r['gold_relevance_distribution']}; correctness {r['gold_correctness_distribution']}. Original strings are preserved, including blank and OUTDATED."
  common=[item1,item2,item3,f"4. **Old strict validation:** {r['old_strict_valid']}. Original mode {r['old_mode']}. The original pilot files are unchanged.",f"5. **New sparse validation:** live {r['new_semantic_valid']}; cached original-raw A3 {a3['semantic_valid']}; live errors `{r['validation_errors']}`.",f"6. **Inventory / roles:** all 15 authorized passages retained; {r['assessed_count']} explicit source roles; {r['not_assessed_count']} NOT_ASSESSED. Complete application inventory hash `{r['source_inventory_sha256']}`.",f"7. **Selected support:** raw span IDs `{raw_refs}`; validated original source markers `{accepted_sources}`. Validation is reference/role/scope validation, not an entailment proof.",f"8. **Unassessed inventory entries:** `{unassessed}`. These entries create no support, no irrelevance inference and no new permission.",f"9. **Old prediction:** strict original pilot {r['old_mode']}; strict validator on the same freshly generated analysis {r['strict_original_gate_same_fresh']}.",f"10. **New prediction:** primary gate {r['new_gate']}; original A0 substantive gate after sparse validation {r['original_A0_gate_on_sparse']}; cached A3 {r['cached_new_mode']}.",f"11. **Shared control:** raw generated {r['systems']['shared_control']['raw_generated_mode']}; served {r['systems']['shared_control']['served_mode']}; response status `{r['systems']['shared_control']['post_generation_status']}`.",f"12. **Public response:** {safe_response}",f"13. **Failure semantics:** `{r['operational_outcome']}`. Immediate internal reason `{r['internal_reason_code']}`. Model-output post-validation status is audited separately from the T3 gate.",f"14. **Original answering-labelled sources selected:** {selected_answering}; full selected-source correctness distribution {r['validated_support_metric']['correctness_distribution']}. An answering-labelled source is not a complete-answer label.",f"15. **Citations:** actual inline/rendered citations T3={r['systems']['semantic_cfaf']['inline_citation_count']+r['systems']['semantic_cfaf']['rendered_sidecar_citations']}, control={r['systems']['shared_control']['inline_citation_count']+r['systems']['shared_control']['rendered_sidecar_citations']}; invalid inline {r['systems']['semantic_cfaf']['invalid_inline_citations']} / {r['systems']['shared_control']['invalid_inline_citations']}. Valid unverified claim-group reference associations T3={r['systems']['semantic_cfaf']['mechanically_valid_unverified_associations']}, control={r['systems']['shared_control']['mechanically_valid_unverified_associations']}. These are not rendered as verified citations.",f"16. **Missing requirements / limitations:** {review['missing']} Gate issues `{r['missing_or_unfulfilled_requirements']}`.",f"17. **Non-independent qualitative grounding assessment:** {review['finding']}",f"18. **Actual cost:** {r['api_calls']} calls, {r['input_tokens']} input tokens, {r['output_tokens']} output tokens; case wall {r['case_latency_ms']:.1f} ms; local/deterministic overhead {r['deterministic_and_local_overhead_ms']:.1f} ms.",f"19. **Uncertainty:** independent human completeness, causal/subject alignment, temporal scope and claim entailment remain PENDING. Agent flag `{review['flag']}`. This exposed development example cannot become an untouched test case again."]
  safe_cases.append(head+'\n\n'+'\n\n'.join(common))
  detailed=common.copy();detailed[1]=f"2. **Exact original question:** {private['question']}";detailed[11]="12. **Complete served public responses:**\n\n```json\n"+json.dumps(private['responses'],ensure_ascii=False,indent=2)+"\n```\n\nRaw generated responses before safe operational fallback:\n\n```json\n"+json.dumps(private['raw_responses'],ensure_ascii=False,indent=2)+"\n```";detailed.append('Original human-answer summary (not a generated-answer label): '+prior['reference_summary']);detailed.append('Fresh per-requirement model assertions:\n\n```json\n'+json.dumps(private['requirements'],ensure_ascii=False,indent=2)+'\n```');detailed.append('Phase C deterministic sidecar:\n\n```json\n'+json.dumps(trace,ensure_ascii=False,indent=2)+'\n```');full_cases.append(head+'\n\n'+'\n\n'.join(detailed))
 tableA=table(['Configuration','Valid','Invalid','FULL','CFAF','Operational failures','Validated CFAF','NOT_ASSESSED','Repairs'],[[k,v['valid'],v['invalid'],v['modes'].get('FULL',0),v['modes'].get('CFAF',0),v['operational_failures'],v['validated_CFAF'],v['not_assessed_sources'],v['repaired_references']] for k,v in cached['summary'].items()])
 tableB=table(['Case / sample_id','Old valid','Cached A3 valid/mode','Fresh valid','Roles / 15','NOT_ASSESSED','New gate','Control raw / served','Gate outcome'],[[f"{i+1} / {r['sample_id']}",r['old_strict_valid'],f"{cached['cases'][i]['variants']['A3']['semantic_valid']} / {r['cached_new_mode']}",r['new_semantic_valid'],r['assessed_count'],r['not_assessed_count'],r['new_gate'],f"{r['systems']['shared_control']['raw_generated_mode']} / {r['systems']['shared_control']['served_mode']}",r['operational_outcome']['status']] for i,r in enumerate(metrics)])
 tableCosts=table(['Kind','Calls','Input tokens','Output tokens','Mean ms','Max ms','API errors'],[[k,v['attempts'],v['input_tokens'],v['output_tokens'],f"{v['mean_latency_ms']:.1f}",f"{v['max_latency_ms']:.1f}",v['errors']] for k,v in usage['by_kind'].items()])
 tableGround=table(['Layer','Cases','Precision','Recall','F1'],[[name,v['case_count'],pct(v['micro_precision']),pct(v['micro_recall']),pct(v['micro_f1'])] for name,v in [('Resolvable raw analyzer proposals',s['raw_proposal_grounding']),('Validated support, all selected cases',s['validated_support_grounding']),('Validated support, valid assessments only',s['validated_support_grounding_on_valid_assessments_only']),('T3 actual public citations',s['public_citations']['semantic_cfaf']['metric']),('Control actual public citations',s['public_citations']['shared_control']['metric'])]])
 body=f'''# Sparse Source Assessment and Operational Failure Repair

## Executive result

The dense source-role requirement was an application/model contract error. The application already owns the complete source inventory; the model's selected evidence roles can be sparse. The new bookkeeping preserves **NOT_ASSESSED**, without inventing relevance, permission, absence or support.

**Phase A, exact cached raw outputs:** structural validity improves from **1/10 to 9/10**, with **zero new model calls**. All eight dense-coverage failures disappear. The original nonexistent span remains invalid. The unchanged substantive gate changes from 0 FULL / 10 CFAF to **8 FULL / 2 CFAF**. This is a decision/candidate replay, not eight newly generated answers and not eight proven correct answers.

**Phase B, one fresh paired development run:** all ten previously exposed records complete; **8/10 assessments are valid**, **7 FULL / 3 CFAF** from the new gate. There are **zero source-role coverage failures**, two reference-verification failures and one structurally valid request-relative CFAF/clarification. The control generates **9 FULL / 1 CFAF** before application validation; served control responses become **7 FULL / 3 CFAF** after two upstream verification failures and one generation-contract failure are safely withheld. Served mode equality does not imply equivalent independent decisions or equal failure reasons.

**Semantic quality did not become independently established.** At least one served T3 FULL has an agent-flagged unsupported subject/relation association. Other FULL answers have scope or conditionality concerns. The two originally deflective examples are restricted in primary B for technical reasons, not demonstrably correct semantic refusal. Cached promotion of one of them exposes the existing risk-strategy inference error.

**Phase C:** a deterministic experimental sidecar records 26 T3 and 19 control mechanically valid, explicit requirement/candidate-group reference associations. All remain `CITATION_SUPPORT_UNVERIFIED`; **zero are rendered as verified public claim citations**. Actual public inline citations remain zero. This is traceability infrastructure, not a citation-quality gain.

The implementation uses only `gpt-4o-mini`: **30 successful API attempts**, **{usage['input_tokens']:,} input tokens**, **{usage['output_tokens']:,} output tokens**, no retries/API errors/embeddings/second verifier. All responses finish normally. Primary source/prompt/schema/runtime hashes were frozen before the live run and remain unchanged.

## Dataset registry, provenance and exposure

Dataset1 remains InfoBank governed fulfilment: original 40 P1–P5 development cases and the planned independent authored corpus. The new independent 40-case holdout remains unopened. Dataset2 remains RefusalBench-NQ, with 1234 eligible, 130 previously exposed, 30 reserved source groups and 18 additional untouched groups. No new Dataset2 records were accessed. Dataset3 remains **original AmazonScience GaRAGe**, not RefusalBench-GaRAGe: 2366 questions, 35,351 passages, ten previously exposed records and **2356 unused records**.

Pinned Dataset3 source commit: `2b7264f5d4e066affbe4b67b7d3b9cffeff98ede`; SHA-256 `419e3941f6e8eb4082a74ca2140c1f9337f8b467ff76656a6b8b0290ca3f3a72`. The [original repository](https://github.com/amazon-science/GaRAGe/tree/2b7264f5d4e066affbe4b67b7d3b9cffeff98ede) and prior source audit establish provenance. This task did not reopen the complete dataset or download additional records. It reused only the original ten runtime rows, prior raw responses and scorer-only annotations, in their original selection order. No exposure ledger was modified and no new record was sampled.

Starting HEAD: `{read(ROOT/'task_state.json')['baseline_commit']}` on `experiment/cfaf-garage-pilot-v1`. New branch: `experiment/cfaf-sparse-source-repair-v1`. All **1029 earlier tracked files** are byte-identical. Historical branches, prior raw events, prior reports and original annotations remain unchanged. No push or merge occurred.

## Contract and architecture

`source_inventory.py` builds the complete inventory from the authorized request before the semantic model call: neutral view ID, access mode/view kind, original marker in a private mapping, source date when supplied, source/view SHA-256, span IDs, exact offsets and hashes, request-projection signature and a stable inventory hash. Every selected case retains all fifteen passages in their original order and exact body bytes. Inventory construction and validation invoke the existing policy-bound request guard; omitted roles cannot authorize a source. DENY sources are absent, metadata/aggregate restrictions remain in force, and trusted target provenance is unchanged.

`sparse_source_assessment.py` accepts dense and sparse outputs, detects duplicate/conflicting roles, checks every declared view and every span/source association, validates selected support roles and preserves requirement coverage. Unreported inventory entries have only `assessment_state=NOT_ASSESSED`, with no invented evidential role in that bookkeeping. Model data remains sparse and unchanged except an explicitly logged exact field/reference representation normalization. The legacy candidate data structure can retain its UNKNOWN enum default for an unlabeled candidate; the inventory audit still distinguishes NOT_ASSESSED and it never supplies evidence.

Every supporting source must be explicitly assessed. A missing assessment on a selected support source is a contract failure; a source explicitly labelled CONTEXTUAL does not establish sufficiency. Source existence, access and hashes are application facts. Existing model-semantic support, relation, completeness, confidence, referent and granularity properties still feed the original RDA/RECV conditions. Valid syntax is not a new entailment oracle.

The original eight named stages and `TopLevelModeSelectionStage` are unchanged. New modules wrap normalization/validation and failure reporting inside a version-local copy of the previous integration. Old substantive target/claim mechanisms remain shadow diagnostics; they gain no new authority. No semantic claim is silently rewritten.

## Phase A — cached causal comparison

All comparisons below use the **exact same old raw semantic response bytes**, original queries and permitted documents. A0 here means original dense validation with the old T3 substantive gate; it is distinct from the older framework's separately named A0 gate configuration.

{tableA}

A1 removes only the false requirement to enumerate every inventory source. A2 adds exact deterministic reference normalization. A3 changes operational reason/status presentation; it does not change A2 validity or gate decisions. All eight promoted old outputs pass the existing support, explicit PRIMARY/SUPPORTS role, permission, per-requirement completeness/relation/referent and RDA hard-failure conditions as expressed in those old analyses. Their semantic assertions remain fallible. No gold label contributes to any of these decisions.

Final frozen sources reproduce the saved cached decisions and validation errors. The original unknown reference has no supplied exact quotation, offsets or equivalent valid catalogue representation; it remains `UNKNOWN_SPAN_ID:view-0001:span-0004`. No nearest window is selected. There are no actual repairs in A1–A3 on the old ten outputs.

Cached modes change for cases 1–7 and 9. This includes a deflective original reference whose model candidate incorrectly treats accounting recognition as a risk strategy. Structural acceptance exposes that old semantic defect; it does not resolve it.

## Phase B — fresh paired development regression

Controlled tests and cached comparison completed before any live API request. The model-visible analysis prompt, generation prompts, schemas, original question, date context, passage bodies, ordering and settings match the previous pilot. All **ten analysis request payloads match the prior pilot exactly**. Application inventory/private diagnostics are not sent to either generator. T3 alone receives its ordinary response contract; the control receives no gate decision or private inventory. Both share the same newly produced semantic data and authorized passages.

Settings: `gpt-4o-mini`, temperature 0, repetitions 1, analysis maximum 1500 tokens, generation maximum 512 for both systems, unchanged query-only fallback settings (no fallback call needed). The 75-attempt cap includes failed attempts/retries; only 30 were used. No stronger model, embedding or general second-pass verifier. Old frozen model outputs are the baseline; they were not regenerated.

{tableB}

Primary B has 7 gate changes versus the old pilot and 3 unchanged modes. Running the old strict validator on the **same fresh analyses** still produces 10 CFAF decisions; seven are changed by sparse normalization. T3 and the old framework's A0 substantive gate agree after the new parsing. The exact cached comparison supports a contract-level causal conclusion; old-versus-fresh output differences are not attributable solely to the contract, even at temperature zero.

There are 40 explicitly reported role assessments and **110 NOT_ASSESSED** entries across 150 authorized sources. These omissions are neither missing passages nor newly inferred irrelevant sources. The valid-but-incomplete semantic case now reports no source roles at all and remains a semantic-diagnosis problem, separate from the eliminated coverage error.

## Operational versus evidential semantics

The gate records 7 `VERIFIED_FULFILMENT`, 2 `OPERATIONAL_FAILURE`, and 1 `VALIDATED_CFAF` outcome. **VERIFIED_FULFILMENT is the existing gate's conditional acceptance of model evidence properties, not independent factual or entailment verification.** The one validated CFAF is a clarification candidate whose semantic adequacy is disputed.

Invalid semantic contracts/references never authorize FULL. Internal codes distinguish operational contract/reference causes from `INSUFFICIENT_EVIDENCE`, `REQUIREMENT_NOT_SUPPORTED`, `UNRESOLVED_REFERENT` and `UNSUPPORTED_RELATION`. Structural failure is never treated as established absence of information or credited as successful evidential CFAF.

Operational public text is neutral: **The answer could not be verified reliably for this request.** It contains no view identifier, source count, exception, access-control state or hidden-source existence claim. P5 uses the unchanged canonical indistinguishable no-view response and makes zero model calls. Raw model responses remain local; safe replacement is explicit and logged, not a silent claim repair.

The existing ReasonClass vocabulary is versioned and strictly validated after generation; no new public category was introduced. The old control's `MISSING_EVIDENCE` string is rejected by the new validator. In fresh case 8 the control instead uses canonical EVIDENTIAL but a null realization, failing `CFAF_REASON_AND_REALIZATION_REQUIRED`; it is served as operational CFAF. Thus control has **three operational response fallbacks**, while T3 has two upstream operational failures. Identical served mode totals conceal this distinction. The unchanged model-visible permissive string schema is retained for the primary comparison; a future enum-schema change requires a separate configuration.
'''
 body+=f'''
## Supplemental R1 — exact numeric reference alias investigation

After primary B was frozen and completed, a separate deterministic zero-call ablation investigated the fresh unpadded reference `view-0011:span-1`. R1 canonicalizes the decimal index to `view-0011:span-0001` **only if that exact span already exists for the same authorized source**. Five synthetic tests cover positive equivalence, nonexistent source/index, no nearest-ID repair and preserved negative completeness. Each occurrence logs original/normalized value, method and inventory hash.

R1 repairs three occurrences in one fresh assessment and gives **9/10 valid, 8 FULL / 2 CFAF** on those frozen fresh analyses. It does not repair nonexistent `span-0004`. R1 changes no primary source file, raw response, served output or main B metric. It is a separately labelled experimental reference-format component, not a second live run. No new generated response exists for its promoted decision.

The newly enabled R1 FULL candidate still makes the unsupported risk-management inference. Removing a technical failure cannot be credited as correcting semantic answerability.

## Phase C — public grounding trace

After A and B completed, `public_grounding_trace.py` produced a deterministic sidecar with no model calls or prompt/schema changes. A reference is associated only through a valid FULL response, exact candidate-copy match, explicit requirement support, an intersection of global/requirement/role span references, usable PRIMARY/SUPPORTS role, valid authorized span, stable neutral marker, offsets and source hash. References are revalidated against the request projection. Sources are not automatically attached to every factual sentence.

There are **26 mechanically valid T3 candidate-group associations and 19 control associations**, with requirement IDs, answer hashes and source/span hashes. T3's greater count reflects exact-candidate-copy eligibility; control paraphrases in two cases have no fabricated equivalence mapping. It is not evidence that T3 is more factual.

The model contract does not provide independently validated per-claim entailment. Every association remains **CITATION_SUPPORT_UNVERIFIED**, with rendering disabled. Thus **actual public citations = 0**, **verified claim-linked citations = 0**, and each system has **7 citationless served FULL answers**. Zero invalid rendered citations is vacuous. This mechanism is experimental provenance infrastructure; a controlled claim/citation realization design remains unfinished and must not be conflated with sparse-role improvement.

## Evidence-grounding metrics

Original GaRAGe labels are scorer-only. Relevant is not sufficient; an answering-labelled source is not complete multipart support; RELATED-INFORMATION, UNKNOWN, OUTDATED and blank remain distinct. No label was changed. The first layer below contains resolvable raw proposals, including invalid analyses. The second rejects all support from an invalid assessment. The conditional third layer removes operational-assessment failures from the denominator.

{tableGround}

All-case validated support counts are TP=21, FP=3, FN=98. The eight-valid-assessment denominator is reported separately. Relevance precision does not measure semantic correctness: the update-scoped first case selects three originally NO passages describing generic benefits. In the accounting case, R1 selects relevant related-only material yet still makes an unsupported strategic inference. Actual citation precision is undefined because no public citations were produced; positive-source recall/F1 are zero. Answers are not required to cite every relevant passage, and low source recall is not itself an incomplete-answer proof.

At least one served T3 FULL and the corresponding control FULL contain an agent-flagged unsupported subject/relation association. Cases 1 and 3 have request-scope concerns; forecast conditions are omitted in case 7. The raw control has four flagged relation claims across three FULL outputs, two of which are withheld by the operational boundary. These are **non-independent agent judgements**, not official entailment or binary accuracy scores. Exact reference-answer matching is not used as the quality criterion.

## Detailed review of all ten exposed cases

The public review uses attributed question summaries. Exact original questions, complete served/raw responses, original-answer summaries, per-requirement assertions and sidecars are in ignored **local/REPORT_FULL.md**. All 19 requested items are covered for each case. Original passages and gold remain local and ignored.

{{CASE_REVIEWS}}

## Costs, tests and security

{tableCosts}

Totals: **30 attempts / 30 successes / 0 API errors / 0 retries**; {usage['input_tokens']:,} input + {usage['output_tokens']:,} output tokens; mean provider latency {usage['mean_latency_ms']:.1f} ms, maximum {usage['max_latency_ms']:.1f} ms. All 30 finish reasons are stop; no truncation. Cached A, R1 and C use zero calls. Local/deterministic overhead totals **{usage['case_local_and_deterministic_overhead_ms']/1000:.3f} seconds**, estimated as case wall time minus provider latency, including guards, inventories, parsing and counterfactual comparisons rather than pure CPU time. Cached A elapsed {cached['elapsed_seconds']:.3f} seconds.

The original pilot used 30 calls, with 176,503 input and 7,273 output tokens. Fresh output sizes differ despite identical analysis requests. Lower new totals are not claimed as an algorithmic token reduction: validation is deterministic and the model prompt/schema did not change. No dollar estimate is provided because pricing was not verified.

Final primary synthetic tests: **57 passed**. Final isolated compatibility suite: **677 passed, 3 hash-only tests deselected**; those three ran against unchanged original working files and **3 passed**. The 57 are included in 677, not extra unique tests. Supplemental R1: **5 passed**. Original CFAF suite: **77 passed, 13 subtests passed, one known pre-existing failure**, `test_preheldout_attempt1_plan_artifacts_are_plan_only`, because a previously committed authorization metadata file exists. It was preserved. The final compatibility retest follows the last primary source changes; archived timer rebasing occurred only in a disposable test process with API credentials removed.

All **1029 pre-existing tracked files**, prior raw event hash, original selection/runtime bytes, and frozen primary files match. All thirty serialized payloads passed forbidden-gold, explicit `sample_id`, selected/private-ID and authorization checks. Ten analysis payloads match prior payloads exactly. Both generators receive identical passages, date and fresh semantic data; neither receives the private inventory. Body hashes and span mappings validate. P5, DENY exclusion, metadata/aggregate scope, native provenance and original selector/stage tests pass. No reserved/new record was used. No unauthorized public citation is rendered.

Task start UTC `{read(ROOT/'task_state.json')['start_utc']}` (Budapest 08:06:18, 29 October 2026); persistent wall/monotonic anchors and 45/50/55/60-minute cutoffs are in task_state.json. Elapsed at report generation: {elapsed():.1f} seconds. No clock/call ledger reset. A completion receipt records final commit and elapsed time.

## Answers to the sixteen research questions

1. **Why eight old failures?** The validator demanded a role for every passage although the application already knew the full inventory; the model reported only selected sources.
2. **How does sparse avoid them?** Complete inventory and explicit model assessments are separate. Omitted entries are NOT_ASSESSED and add no support or authority.
3. **How many old assessments become valid?** Eight newly valid: 1/10 becomes 9/10 with zero calls on identical raw outputs.
4. **Invalid reference case?** Nonexistent span remains invalid in A/B/R1. The new numeric-format alias is resolved only in separately labelled R1; no nearest span is chosen.
5. **Which obtain FULL?** Cached decisions: cases 1–7 and 9. Fresh primary generated T3 FULL: cases 1–4, 6, 7 and 9. R1 adds only a decision/candidate in case 5, with no new generation.
6. **Actually grounded?** Several concise summaries have direct support; one served FULL has an unsupported relation and others have scope/condition gaps. No independent full-answer judgement exists.
7. **Originally deflective cases restricted?** Yes in primary B, because reference verification failed. Neither is credited as a correct semantic refusal. Cached/R1 promotion of the accounting example exposes an unsupported candidate.
8. **Technical failures described correctly?** Handled contract/reference/generation failures have distinct operational status, neutral wording, no evidential-CFAF credit and no served FULL. P5 is unchanged.
9. **New unsupported FULL?** One served T3 FULL relation is flagged in agent review, with other scope concerns. This is not an independently adjudicated false-answer rate.
10. **Governance/security regression?** None in controlled/historical suites; earlier files are unchanged. The known unrelated historical failure remains.
11. **Actual public citations?** None; no positive citation-quality claim.
12. **Claim-linked and verifiable?** Candidate-group/requirement reference paths are mechanically verifiable; individual claim entailment is not. Associations remain unverified and are not rendered as verified citations.
13. **Cost?** 30 calls, {usage['input_tokens']:,}/{usage['output_tokens']:,} input/output tokens, {usage['case_local_and_deterministic_overhead_ms']/1000:.3f} seconds local overhead; zero cached/R1/C calls.
14. **Ready for default?** Application inventory, sparse bookkeeping, duplicate/unknown-reference checks, existing authorization checks and explicit operational/public-vocabulary validation are suitable mechanical building blocks. This is not approval of the whole pipeline as a factually reliable default answerer.
15. **Experimental?** R1 aliases have deterministic tests but no live run; public claim citation realization and semantic entailment/coverage remain experimental. Gate promotions require development review.
16. **Before larger Dataset3?** Add independently adjudicated request-completeness/claim-entailment criteria; prevent subject/causal inference errors; handle temporal/conditional scope; reduce format errors in a separate schema/prompt configuration; build robust per-claim citation mapping. Freeze these ten exposed outputs. Reserve the other **2356 records** for a separately planned independent test.

Structural validity, semantic quality, mode changes, citations and operational reporting are separate outcomes. This experiment demonstrates contract repair and clearer failure reporting; it does not establish independent semantic accuracy or a completed public-grounding solution.
'''
 save('REPORT.md',body.replace('{CASE_REVIEWS}','\n\n'.join(safe_cases)))
 save('local/REPORT_FULL.md',body.replace('{CASE_REVIEWS}','\n\n'.join(full_cases)))
 save('README.md','''# Sparse-source repair research version

REPORT.md is the safe committed report. local/REPORT_FULL.md contains exact original ten questions, complete raw/served responses and 19-item reviews; it is ignored. No original dataset, unredacted gold or raw trace is committed.

Core modules: source_inventory.py (application inventory), sparse_source_assessment.py (dense/sparse contract), reference_validation.py (exact reference checks), operational_failure_codes.py (internal states and strict existing public vocabulary), gate_controls.py/integration.py (existing substantive gate with new boundary), public_grounding_trace.py (experimental; no verified citations rendered).

Phase A: cached.py replays only the original ten exposed raw analyses. Phase B: runner.py freezes and runs one shared-analysis paired regression. Phase C: runner.py citations computes sidecars only after B completes. reference_alias_ablation.py is a separately labelled post-B numeric-format diagnostic, not frozen primary runtime.

The ten records remain exposed development data; the other 2356 were not opened. Dataset1's independent holdout and new Dataset2 records remain untouched. Earlier files/branches are preserved; no push/merge.

Offline synthetic checks from the repository:

```powershell
python -m pytest evaluation/cfaf_sparse_source_repair_v1/test_sparse.py evaluation/cfaf_sparse_source_repair_v1/test_reference_alias.py -q
```

Primary manifest excludes post-run scorer/report/audit files. R1 has separate tests and artifact hashes. Do not rerun cached/live preparation in this completed directory: results are immutable, commands refuse duplicate execution and persistent deadlines must not reset. A future run needs a fresh research directory/clock/budget and remains exposed development if it uses these ten records.

Artifacts: cached_ablation_results.json and cached_final_source_verification.json (zero-call comparison); case_metrics.jsonl / evaluation_summary.json / mode_transition_matrix.csv (safe live summaries); source_coverage_diagnostics.jsonl / reason_audit.jsonl / citation_diagnostics.jsonl; reference_alias_ablation.json (R1); api_usage.json; security_audit.json / regression_audit.json; CHANGED_FILES.txt / checksums.sha256.

Ignored: runtime_inputs.jsonl, live_paired_results.jsonl, api_requests.jsonl, api_events.jsonl, *_raw.jsonl and local/. Original scorer-only annotations stay in the previous ignored gold file. Do not force-add them. Exact questions, original answers and full passages remain ignored.
''')
 save('SPARSE_SOURCE_CONTRACT_SPEC.md','''# Sparse Source Assessment Contract v1

Complete source inventory is an application fact, constructed from the policy-authorized request before the model call. It records neutral view ID, access/view kind, source hash, exact span IDs/offsets/hashes, source date, private original marker mapping, request signature and stable inventory hash. Private mappings must refer only to authorized views and be unambiguous. Revalidation reconstructs inventory from the bound request; stale content/policy/hash fails.

Model source_assessments can be dense, sparse or empty. Explicit roles need known views, unique/conflict-free declarations and valid same-source grounding references. Omission creates NOT_ASSESSED bookkeeping, without inventing role, relevance, permission, absence or support. The legacy pipeline enum may retain UNKNOWN for an unlabeled candidate; assessed coverage comes from the explicit audit, not that enum default.

Every selected global/requirement support source needs an explicit assessment. Missing selected-source assessment fails the contract; CONTEXTUAL/non-SUPPORTS roles cannot establish sufficiency. Requirement IDs remain covered and completeness/relation/referent/granularity/confidence/premise conditions remain in the substantive gate. DENY, metadata, aggregate and trusted-target controls are preserved. Original selector/eight stages are unchanged.

Original prompts/schemas remain identical. Optional view_id spelling can be normalized exactly to source_id with a logged representation change; conflicting spellings fail. Normalization does not fill in model claims or relabel sources. Model data stays unchanged except logged exact representation normalization.

Reference v1 accepts existing catalogue IDs, unique exact whole-catalogue-span quotations, exact catalogue offsets, or verified original-marker/equivalent-span mapping. Partial-quote-to-larger-window guessing, absent/nonunique text, stale hashes, arbitrary/nearest spans and gold/LLM repairs are rejected. Overlapping duplicate quotations are ambiguous. The original nonexistent span remains invalid.

R1 is a separate post-B ablation: decimal index padding is canonicalized only if that exact source/span ID exists. It changes representation, not source choice, offsets or claims. Every repair logs original/normalized value/method. Primary frozen outputs are not rewritten.
''')
 save('OPERATIONAL_FAILURE_SEMANTICS.md','''# Failure semantics v1

Internal states distinguish VERIFIED_FULFILMENT, VALIDATED_CFAF, OPERATIONAL_FAILURE and VALIDATED_RESTRICTED_NO_VIEW. VERIFIED_FULFILMENT means the existing gate accepted supplied model properties; it does not certify independent factual entailment.

Operational codes include SEMANTIC_ASSESSMENT_INVALID, SOURCE_ASSESSMENT_CONTRACT_INVALID, INVALID_EVIDENCE_REFERENCE, REFERENCE_RESOLUTION_FAILED and GENERATION_CONTRACT_INVALID. Evidence/request-limit codes include INSUFFICIENT_EVIDENCE, REQUIREMENT_NOT_SUPPORTED, UNRESOLVED_REFERENT and UNSUPPORTED_RELATION. Invalid contracts/references do not establish information absence.

Operational failures cannot serve FULL or be credited as successful evidential CFAF. Public fallback uses the existing six-field schema: CFAF, NONE, ABSTAIN, EPISTEMIC, empty next steps and neutral text: The answer could not be verified reliably for this request. Raw generation stays local with explicit fallback status; no silent repair is claimed.

P5/no-view retains the canonical public response and zero calls. Hidden/absent source worlds yield identical public traces. No operational wording reveals source IDs/counts, hidden existence, exceptions or policy state.

Public reason vocabulary is the existing ReasonClass enum, version existing-ReasonClass-v1-strict-validation. No new public category. Unknown reasons/realizations, nonnull FULL reasons and missing CFAF reason/realization are rejected. Primary model-visible prompts/schema stay unchanged; strict checks occur after generation. Control chooses its raw mode independently, then the same publication boundary withholds invalid/operational output. Raw and served modes must be reported separately.

Gate and per-generator status differ: valid T3 evidential/clarification can coexist with invalid control generation. Such control fallback is operational and cannot be credited as semantic refusal. Top-level CFAF alone cannot support an accuracy claim.
''')
 save('PUBLIC_GROUNDING_TRACE_SPEC.md','''# Public grounding trace v1 — experimental

Phase C runs deterministically after cached/live comparisons. No new prompt/schema or model API. Primary runtime sidecars record NOT_EXECUTED_PRIMARY_COMPARISON.

Eligibility requires contract-valid FULL, valid semantic assessment, exact response/candidate match, explicit sufficient/complete/referent/relation requirement properties, matching global/requirement/role span references and explicit PRIMARY/SUPPORTS roles. References are checked against the authorized request, offsets and source hash. Stable neutral marker and answer hash identify the candidate-group association.

This establishes reference validity and traceable assertion provenance, not independent claim entailment. It does not attach all PRIMARY sources to all sentences. A control paraphrase is not silently equated to the candidate. Unsupported claims with valid references remain possible and are tested.

The sidecar separates citations, eligible for verified rendering, from unverified_associations. Candidate-group associations get CITATION_SUPPORT_UNVERIFIED and render_as_verified_claim_citation=false. No independent per-claim mapping proves entailment in this version, so citations stays empty. Coverage is zero; missing citations/citationless FULL remain explicit. Zero invalid emitted citations is not success.

Actual run: 26 T3 and 19 control mechanically valid unverified associations, zero verified claim citations and zero actual inline/rendered citations. Different counts reflect exact-copy eligibility, not factuality. This component remains experimental until separately tested claim mapping/realization exists.
''')
 save('DATASET_REGISTRY.md','''# Permanent dataset registry

| Dataset | Scientific role | Exposure restriction |
| --- | --- | --- |
| Dataset1 — InfoBank | Governed fulfilment, P1–P5 permission/evidence/metadata/aggregate handling; original 40 development cases and planned independent corpus | New independent 40-case holdout unopened; no new independent authored case used. |
| Dataset2 — RefusalBench-NQ | Selective refusal/answerability; 1234 eligible, 130 exposed, 30 reserved groups, 18 additional untouched groups | No new records/groups or exposure-ledger changes. |
| Dataset3 — original AmazonScience GaRAGe | Evidence-grounded answering; 2366 questions / 35,351 passages | Exactly ten already-exposed IDs reused in original order; 2356 unused. No new sampling or full-dataset reopening. |

Dataset3 is not RefusalBench-GaRAGe. Repeating these ten is exposed development, not independent testing. The three annotation concepts are not interchangeable binary gold.
''')
 with (ROOT/'HUMAN_REVIEW_TEMPLATE.csv').open('w',newline='',encoding='utf-8') as f:
  fields=['sample_id','reviewer','reviewed_utc','essential_requirements','complete_answer_possible','T3_claim_support','control_claim_support','scope_and_conditions','refusal_appropriate','citation_entailment','notes','status'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for r in metrics:w.writerow({'sample_id':r['sample_id'],'status':'PENDING'})
 print('Reports saved: public', (ROOT/'REPORT.md').stat().st_size,'bytes; detailed local',(ROOT/'local/REPORT_FULL.md').stat().st_size,'bytes')
if __name__=='__main__':build()
