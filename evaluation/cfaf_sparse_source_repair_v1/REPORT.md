# Sparse Source Assessment and Operational Failure Repair

## Executive result

The dense source-role requirement was an application/model contract error. The application already owns the complete source inventory; the model's selected evidence roles can be sparse. The new bookkeeping preserves **NOT_ASSESSED**, without inventing relevance, permission, absence or support.

**Phase A, exact cached raw outputs:** structural validity improves from **1/10 to 9/10**, with **zero new model calls**. All eight dense-coverage failures disappear. The original nonexistent span remains invalid. The unchanged substantive gate changes from 0 FULL / 10 CFAF to **8 FULL / 2 CFAF**. This is a decision/candidate replay, not eight newly generated answers and not eight proven correct answers.

**Phase B, one fresh paired development run:** all ten previously exposed records complete; **8/10 assessments are valid**, **7 FULL / 3 CFAF** from the new gate. There are **zero source-role coverage failures**, two reference-verification failures and one structurally valid request-relative CFAF/clarification. The control generates **9 FULL / 1 CFAF** before application validation; served control responses become **7 FULL / 3 CFAF** after two upstream verification failures and one generation-contract failure are safely withheld. Served mode equality does not imply equivalent independent decisions or equal failure reasons.

**Semantic quality did not become independently established.** At least one served T3 FULL has an agent-flagged unsupported subject/relation association. Other FULL answers have scope or conditionality concerns. The two originally deflective examples are restricted in primary B for technical reasons, not demonstrably correct semantic refusal. Cached promotion of one of them exposes the existing risk-strategy inference error.

**Phase C:** a deterministic experimental sidecar records 26 T3 and 19 control mechanically valid, explicit requirement/candidate-group reference associations. All remain `CITATION_SUPPORT_UNVERIFIED`; **zero are rendered as verified public claim citations**. Actual public inline citations remain zero. This is traceability infrastructure, not a citation-quality gain.

The implementation uses only `gpt-4o-mini`: **30 successful API attempts**, **174,531 input tokens**, **6,445 output tokens**, no retries/API errors/embeddings/second verifier. All responses finish normally. Primary source/prompt/schema/runtime hashes were frozen before the live run and remain unchanged.

## Dataset registry, provenance and exposure

Dataset1 remains InfoBank governed fulfilment: original 40 P1–P5 development cases and the planned independent authored corpus. The new independent 40-case holdout remains unopened. Dataset2 remains RefusalBench-NQ, with 1234 eligible, 130 previously exposed, 30 reserved source groups and 18 additional untouched groups. No new Dataset2 records were accessed. Dataset3 remains **original AmazonScience GaRAGe**, not RefusalBench-GaRAGe: 2366 questions, 35,351 passages, ten previously exposed records and **2356 unused records**.

Pinned Dataset3 source commit: `2b7264f5d4e066affbe4b67b7d3b9cffeff98ede`; SHA-256 `419e3941f6e8eb4082a74ca2140c1f9337f8b467ff76656a6b8b0290ca3f3a72`. The [original repository](https://github.com/amazon-science/GaRAGe/tree/2b7264f5d4e066affbe4b67b7d3b9cffeff98ede) and prior source audit establish provenance. This task did not reopen the complete dataset or download additional records. It reused only the original ten runtime rows, prior raw responses and scorer-only annotations, in their original selection order. No exposure ledger was modified and no new record was sampled.

Starting HEAD: `a931772ba0587d6a6fcb77f04a03bf1957aac5ac` on `experiment/cfaf-garage-pilot-v1`. New branch: `experiment/cfaf-sparse-source-repair-v1`. All **1029 earlier tracked files** are byte-identical. Historical branches, prior raw events, prior reports and original annotations remain unchanged. No push or merge occurred.

## Contract and architecture

`source_inventory.py` builds the complete inventory from the authorized request before the semantic model call: neutral view ID, access mode/view kind, original marker in a private mapping, source date when supplied, source/view SHA-256, span IDs, exact offsets and hashes, request-projection signature and a stable inventory hash. Every selected case retains all fifteen passages in their original order and exact body bytes. Inventory construction and validation invoke the existing policy-bound request guard; omitted roles cannot authorize a source. DENY sources are absent, metadata/aggregate restrictions remain in force, and trusted target provenance is unchanged.

`sparse_source_assessment.py` accepts dense and sparse outputs, detects duplicate/conflicting roles, checks every declared view and every span/source association, validates selected support roles and preserves requirement coverage. Unreported inventory entries have only `assessment_state=NOT_ASSESSED`, with no invented evidential role in that bookkeeping. Model data remains sparse and unchanged except an explicitly logged exact field/reference representation normalization. The legacy candidate data structure can retain its UNKNOWN enum default for an unlabeled candidate; the inventory audit still distinguishes NOT_ASSESSED and it never supplies evidence.

Every supporting source must be explicitly assessed. A missing assessment on a selected support source is a contract failure; a source explicitly labelled CONTEXTUAL does not establish sufficiency. Source existence, access and hashes are application facts. Existing model-semantic support, relation, completeness, confidence, referent and granularity properties still feed the original RDA/RECV conditions. Valid syntax is not a new entailment oracle.

The original eight named stages and `TopLevelModeSelectionStage` are unchanged. New modules wrap normalization/validation and failure reporting inside a version-local copy of the previous integration. Old substantive target/claim mechanisms remain shadow diagnostics; they gain no new authority. No semantic claim is silently rewritten.

## Phase A — cached causal comparison

All comparisons below use the **exact same old raw semantic response bytes**, original queries and permitted documents. A0 here means original dense validation with the old T3 substantive gate; it is distinct from the older framework's separately named A0 gate configuration.

| Configuration | Valid | Invalid | FULL | CFAF | Operational failures | Validated CFAF | NOT_ASSESSED | Repairs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A0 | 1 | 9 | 0 | 10 | 9 | 1 | 94 | 0 |
| A1 | 9 | 1 | 8 | 2 | 1 | 1 | 94 | 0 |
| A2 | 9 | 1 | 8 | 2 | 1 | 1 | 94 | 0 |
| A3 | 9 | 1 | 8 | 2 | 1 | 1 | 94 | 0 |


A1 removes only the false requirement to enumerate every inventory source. A2 adds exact deterministic reference normalization. A3 changes operational reason/status presentation; it does not change A2 validity or gate decisions. All eight promoted old outputs pass the existing support, explicit PRIMARY/SUPPORTS role, permission, per-requirement completeness/relation/referent and RDA hard-failure conditions as expressed in those old analyses. Their semantic assertions remain fallible. No gold label contributes to any of these decisions.

Final frozen sources reproduce the saved cached decisions and validation errors. The original unknown reference has no supplied exact quotation, offsets or equivalent valid catalogue representation; it remains `UNKNOWN_SPAN_ID:view-0001:span-0004`. No nearest window is selected. There are no actual repairs in A1–A3 on the old ten outputs.

Cached modes change for cases 1–7 and 9. This includes a deflective original reference whose model candidate incorrectly treats accounting recognition as a risk strategy. Structural acceptance exposes that old semantic defect; it does not resolve it.

## Phase B — fresh paired development regression

Controlled tests and cached comparison completed before any live API request. The model-visible analysis prompt, generation prompts, schemas, original question, date context, passage bodies, ordering and settings match the previous pilot. All **ten analysis request payloads match the prior pilot exactly**. Application inventory/private diagnostics are not sent to either generator. T3 alone receives its ordinary response contract; the control receives no gate decision or private inventory. Both share the same newly produced semantic data and authorized passages.

Settings: `gpt-4o-mini`, temperature 0, repetitions 1, analysis maximum 1500 tokens, generation maximum 512 for both systems, unchanged query-only fallback settings (no fallback call needed). The 75-attempt cap includes failed attempts/retries; only 30 were used. No stronger model, embedding or general second-pass verifier. Old frozen model outputs are the baseline; they were not regenerated.

| Case / sample_id | Old valid | Cached A3 valid/mode | Fresh valid | Roles / 15 | NOT_ASSESSED | New gate | Control raw / served | Gate outcome |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 / 263f7106-41c9-49b1-992e-4c7452aef3a8 | False | True / FULL | True | 3 | 12 | FULL | FULL / FULL | VERIFIED_FULFILMENT |
| 2 / 90ca5695-a633-40b8-b3dc-56bbbf208245 | False | True / FULL | True | 4 | 11 | FULL | FULL / FULL | VERIFIED_FULFILMENT |
| 3 / 45caa113-bbd0-4fbf-8526-37c1fcc8bae5 | False | True / FULL | True | 4 | 11 | FULL | FULL / FULL | VERIFIED_FULFILMENT |
| 4 / 194cf6ad-e309-4d76-8a70-0f8a972042d2 | False | True / FULL | True | 4 | 11 | FULL | FULL / FULL | VERIFIED_FULFILMENT |
| 5 / 13c6bf75-a2e0-4943-a586-d3dc5ca1eb20 | False | True / FULL | False | 1 | 14 | CFAF | FULL / CFAF | OPERATIONAL_FAILURE |
| 6 / 099f1832-11af-4fb4-bb8c-880baee07986 | False | True / FULL | True | 4 | 11 | FULL | FULL / FULL | VERIFIED_FULFILMENT |
| 7 / 49865de4-d298-41f9-a00f-a4c886147680 | False | True / FULL | True | 3 | 12 | FULL | FULL / FULL | VERIFIED_FULFILMENT |
| 8 / 89967e8d-2dd1-4214-a0f7-cf3588558362 | True | True / CFAF | True | 0 | 15 | CFAF | CFAF / CFAF | VALIDATED_CFAF |
| 9 / e10bb772-6c4e-426f-a924-3d3ba0b23515 | False | True / FULL | True | 2 | 13 | FULL | FULL / FULL | VERIFIED_FULFILMENT |
| 10 / f1456a9c-65d3-46ff-b5b5-c8d4d98bc0ff | False | False / CFAF | False | 15 | 0 | CFAF | FULL / CFAF | OPERATIONAL_FAILURE |


Primary B has 7 gate changes versus the old pilot and 3 unchanged modes. Running the old strict validator on the **same fresh analyses** still produces 10 CFAF decisions; seven are changed by sparse normalization. T3 and the old framework's A0 substantive gate agree after the new parsing. The exact cached comparison supports a contract-level causal conclusion; old-versus-fresh output differences are not attributable solely to the contract, even at temperature zero.

There are 40 explicitly reported role assessments and **110 NOT_ASSESSED** entries across 150 authorized sources. These omissions are neither missing passages nor newly inferred irrelevant sources. The valid-but-incomplete semantic case now reports no source roles at all and remains a semantic-diagnosis problem, separate from the eliminated coverage error.

## Operational versus evidential semantics

The gate records 7 `VERIFIED_FULFILMENT`, 2 `OPERATIONAL_FAILURE`, and 1 `VALIDATED_CFAF` outcome. **VERIFIED_FULFILMENT is the existing gate's conditional acceptance of model evidence properties, not independent factual or entailment verification.** The one validated CFAF is a clarification candidate whose semantic adequacy is disputed.

Invalid semantic contracts/references never authorize FULL. Internal codes distinguish operational contract/reference causes from `INSUFFICIENT_EVIDENCE`, `REQUIREMENT_NOT_SUPPORTED`, `UNRESOLVED_REFERENT` and `UNSUPPORTED_RELATION`. Structural failure is never treated as established absence of information or credited as successful evidential CFAF.

Operational public text is neutral: **The answer could not be verified reliably for this request.** It contains no view identifier, source count, exception, access-control state or hidden-source existence claim. P5 uses the unchanged canonical indistinguishable no-view response and makes zero model calls. Raw model responses remain local; safe replacement is explicit and logged, not a silent claim repair.

The existing ReasonClass vocabulary is versioned and strictly validated after generation; no new public category was introduced. The old control's `MISSING_EVIDENCE` string is rejected by the new validator. In fresh case 8 the control instead uses canonical EVIDENTIAL but a null realization, failing `CFAF_REASON_AND_REALIZATION_REQUIRED`; it is served as operational CFAF. Thus control has **three operational response fallbacks**, while T3 has two upstream operational failures. Identical served mode totals conceal this distinction. The unchanged model-visible permissive string schema is retained for the primary comparison; a future enum-schema change requires a separate configuration.

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

| Layer | Cases | Precision | Recall | F1 |
| --- | --- | --- | --- | --- |
| Resolvable raw analyzer proposals | 10 | 88.00% | 18.49% | 30.56% |
| Validated support, all selected cases | 10 | 87.50% | 17.65% | 29.37% |
| Validated support, valid assessments only | 8 | 87.50% | 20.39% | 33.07% |
| T3 actual public citations | 10 | undefined | 0.00% | 0.00% |
| Control actual public citations | 10 | undefined | 0.00% | 0.00% |


All-case validated support counts are TP=21, FP=3, FN=98. The eight-valid-assessment denominator is reported separately. Relevance precision does not measure semantic correctness: the update-scoped first case selects three originally NO passages describing generic benefits. In the accounting case, R1 selects relevant related-only material yet still makes an unsupported strategic inference. Actual citation precision is undefined because no public citations were produced; positive-source recall/F1 are zero. Answers are not required to cite every relevant passage, and low source recall is not itself an incomplete-answer proof.

At least one served T3 FULL and the corresponding control FULL contain an agent-flagged unsupported subject/relation association. Cases 1 and 3 have request-scope concerns; forecast conditions are omitted in case 7. The raw control has four flagged relation claims across three FULL outputs, two of which are withheld by the operational boundary. These are **non-independent agent judgements**, not official entailment or binary accuracy scores. Exact reference-answer matching is not used as the quality criterion.

## Detailed review of all ten exposed cases

The public review uses attributed question summaries. Exact original questions, complete served/raw responses, original-answer summaries, per-requirement assertions and sidecars are in ignored **local/REPORT_FULL.md**. All 19 requested items are covered for each case. Original passages and gold remain local and ignored.

### Case 1: `263f7106-41c9-49b1-992e-4c7452aef3a8`

Attributed summary of the original GaRAGe question: **Recent software-assistant rollout and administrative work**.

1. **Original ID / row:** `263f7106-41c9-49b1-992e-4c7452aef3a8`; original zero-based row 2287.

2. **Question summary:** Recent software-assistant rollout and administrative work (original AmazonScience GaRAGe, pinned source commit).

3. **Original labels:** relevance {'NO': 11, 'YES': 4}; correctness {'': 11, 'ANSWER-THE-QUESTION': 2, 'OUTDATED': 2}. Original strings are preserved, including blank and OUTDATED.

4. **Old strict validation:** False. Original mode CFAF. The original pilot files are unchanged.

5. **New sparse validation:** live True; cached original-raw A3 True; live errors `[]`.

6. **Inventory / roles:** all 15 authorized passages retained; 3 explicit source roles; 12 NOT_ASSESSED. Complete application inventory hash `8ff3e534713c12d5245851b945ff846d70f238b1ec65d611c178c5e68a01e4d6`.

7. **Selected support:** raw span IDs `['view-0002:span-0001', 'view-0008:span-0001', 'view-0015:span-0001']`; validated original source markers `['cite_2', 'cite_8', 'cite_15']`. Validation is reference/role/scope validation, not an entailment proof.

8. **Unassessed inventory entries:** `['view-0001', 'view-0003', 'view-0004', 'view-0005', 'view-0006', 'view-0007', 'view-0009', 'view-0010', 'view-0011', 'view-0012', 'view-0013', 'view-0014']`. These entries create no support, no irrelevance inference and no new permission.

9. **Old prediction:** strict original pilot CFAF; strict validator on the same freshly generated analysis CFAF.

10. **New prediction:** primary gate FULL; original A0 substantive gate after sparse validation FULL; cached A3 FULL.

11. **Shared control:** raw generated FULL; served FULL; response status `{'errors': [], 'raw_declared_mode': 'FULL', 'safe_fallback_applied': False, 'status': 'GENERATED_VALID_CONTRACT'}`.

12. **Public response:** Concise factual answer; full exact text is in local/REPORT_FULL.md.

13. **Failure semantics:** `{'credited_evidential_CFAF': False, 'failure_class': None, 'reason': 'FULFILMENT_ESTABLISHED', 'status': 'VERIFIED_FULFILMENT'}`. Immediate internal reason `None`. Model-output post-validation status is audited separately from the T3 gate.

14. **Original answering-labelled sources selected:** 0; full selected-source correctness distribution {'': 3}. An answering-labelled source is not a complete-answer label.

15. **Citations:** actual inline/rendered citations T3=0, control=0; invalid inline [] / []. Valid unverified claim-group reference associations T3=3, control=0. These are not rendered as verified citations.

16. **Missing requirements / limitations:** Recent-update-specific rollout and commercial-agent context. Gate issues `[]`.

17. **Non-independent qualitative grounding assessment:** New FULL answers remain generic workflow summaries. The original update-scoped request is not fully addressed, and every selected support passage is originally NO for relevance. The statements have nearby textual support, but the scope match is poor.

18. **Actual cost:** 3 calls, 15247 input tokens, 586 output tokens; case wall 11184.4 ms; local/deterministic overhead 813.1 ms.

19. **Uncertainty:** independent human completeness, causal/subject alignment, temporal scope and claim entailment remain PENDING. Agent flag `UPDATE_SCOPE_NOT_ESTABLISHED`. This exposed development example cannot become an untouched test case again.

### Case 2: `90ca5695-a633-40b8-b3dc-56bbbf208245`

Attributed summary of the original GaRAGe question: **Space-observatory findings about accretion environments**.

1. **Original ID / row:** `90ca5695-a633-40b8-b3dc-56bbbf208245`; original zero-based row 186.

2. **Question summary:** Space-observatory findings about accretion environments (original AmazonScience GaRAGe, pinned source commit).

3. **Original labels:** relevance {'YES': 15}; correctness {'ANSWER-THE-QUESTION': 4, 'RELATED-INFORMATION': 10, 'UNKNOWN': 1}. Original strings are preserved, including blank and OUTDATED.

4. **Old strict validation:** False. Original mode CFAF. The original pilot files are unchanged.

5. **New sparse validation:** live True; cached original-raw A3 True; live errors `[]`.

6. **Inventory / roles:** all 15 authorized passages retained; 4 explicit source roles; 11 NOT_ASSESSED. Complete application inventory hash `ce956baef7093d558e83e643ae26d81d83eaa487d72481e618a6e5e8cb59eca7`.

7. **Selected support:** raw span IDs `['view-0001:span-0000', 'view-0003:span-0001', 'view-0004:span-0000', 'view-0012:span-0001']`; validated original source markers `['cite_1', 'cite_3', 'cite_4', 'cite_12']`. Validation is reference/role/scope validation, not an entailment proof.

8. **Unassessed inventory entries:** `['view-0002', 'view-0005', 'view-0006', 'view-0007', 'view-0008', 'view-0009', 'view-0010', 'view-0011', 'view-0013', 'view-0014', 'view-0015']`. These entries create no support, no irrelevance inference and no new permission.

9. **Old prediction:** strict original pilot CFAF; strict validator on the same freshly generated analysis CFAF.

10. **New prediction:** primary gate FULL; original A0 substantive gate after sparse validation FULL; cached A3 FULL.

11. **Shared control:** raw generated FULL; served FULL; response status `{'errors': [], 'raw_declared_mode': 'FULL', 'safe_fallback_applied': False, 'status': 'GENERATED_VALID_CONTRACT'}`.

12. **Public response:** Concise factual answer; full exact text is in local/REPORT_FULL.md.

13. **Failure semantics:** `{'credited_evidential_CFAF': False, 'failure_class': None, 'reason': 'FULFILMENT_ESTABLISHED', 'status': 'VERIFIED_FULFILMENT'}`. Immediate internal reason `None`. Model-output post-validation status is audited separately from the T3 gate.

14. **Original answering-labelled sources selected:** 4; full selected-source correctness distribution {'ANSWER-THE-QUESTION': 4}. An answering-labelled source is not a complete-answer label.

15. **Citations:** actual inline/rendered citations T3=0, control=0; invalid inline [] / []. Valid unverified claim-group reference associations T3=4, control=4. These are not rendered as verified citations.

16. **Missing requirements / limitations:** Possible omitted magnetic-field/model-testing detail; essentiality is unadjudicated. Gate issues `[]`.

17. **Non-independent qualitative grounding assessment:** Both new systems give the same short, source-supported explanation. Four selected sources are originally answering-labelled. The omission of further scientific detail does not itself prove an incomplete answer, but long-form adequacy needs a separate rubric.

18. **Actual cost:** 3 calls, 17956 input tokens, 686 output tokens; case wall 9567.3 ms; local/deterministic overhead 904.7 ms.

19. **Uncertainty:** independent human completeness, causal/subject alignment, temporal scope and claim entailment remain PENDING. Agent flag `SUPPORTED_CONCISE_ANSWER_PENDING_COMPLETENESS_REVIEW`. This exposed development example cannot become an untouched test case again.

### Case 3: `45caa113-bbd0-4fbf-8526-37c1fcc8bae5`

Attributed summary of the original GaRAGe question: **Hosting choices matched to organizational requirements**.

1. **Original ID / row:** `45caa113-bbd0-4fbf-8526-37c1fcc8bae5`; original zero-based row 868.

2. **Question summary:** Hosting choices matched to organizational requirements (original AmazonScience GaRAGe, pinned source commit).

3. **Original labels:** relevance {'YES': 15}; correctness {'ANSWER-THE-QUESTION': 11, 'RELATED-INFORMATION': 4}. Original strings are preserved, including blank and OUTDATED.

4. **Old strict validation:** False. Original mode CFAF. The original pilot files are unchanged.

5. **New sparse validation:** live True; cached original-raw A3 True; live errors `[]`.

6. **Inventory / roles:** all 15 authorized passages retained; 4 explicit source roles; 11 NOT_ASSESSED. Complete application inventory hash `0f9377dfaab1bfa139e47f013d365d8b2aac7c86a6be2826516a8640a426a107`.

7. **Selected support:** raw span IDs `['view-0009:span-0000', 'view-0009:span-0001', 'view-0010:span-0000', 'view-0010:span-0001', 'view-0011:span-0000', 'view-0012:span-0000']`; validated original source markers `['cite_9', 'cite_10', 'cite_11', 'cite_12']`. Validation is reference/role/scope validation, not an entailment proof.

8. **Unassessed inventory entries:** `['view-0001', 'view-0002', 'view-0003', 'view-0004', 'view-0005', 'view-0006', 'view-0007', 'view-0008', 'view-0013', 'view-0014', 'view-0015']`. These entries create no support, no irrelevance inference and no new permission.

9. **Old prediction:** strict original pilot CFAF; strict validator on the same freshly generated analysis CFAF.

10. **New prediction:** primary gate FULL; original A0 substantive gate after sparse validation FULL; cached A3 FULL.

11. **Shared control:** raw generated FULL; served FULL; response status `{'errors': [], 'raw_declared_mode': 'FULL', 'safe_fallback_applied': False, 'status': 'GENERATED_VALID_CONTRACT'}`.

12. **Public response:** Concise factual answer; full exact text is in local/REPORT_FULL.md.

13. **Failure semantics:** `{'credited_evidential_CFAF': False, 'failure_class': None, 'reason': 'FULFILMENT_ESTABLISHED', 'status': 'VERIFIED_FULFILMENT'}`. Immediate internal reason `None`. Model-output post-validation status is audited separately from the T3 gate.

14. **Original answering-labelled sources selected:** 4; full selected-source correctness distribution {'ANSWER-THE-QUESTION': 4}. An answering-labelled source is not a complete-answer label.

15. **Citations:** actual inline/rendered citations T3=0, control=0; invalid inline [] / []. Valid unverified claim-group reference associations T3=6, control=6. These are not rendered as verified citations.

16. **Missing requirements / limitations:** Explicit model-by-model correspondence to organizational requirements. Gate issues `[]`.

17. **Non-independent qualitative grounding assessment:** Both systems produce a generic benefit list without distinguishing the hosting models or explaining their match to particular organizational needs. Answering-labelled source selection does not establish that this comparative requirement is fulfilled.

18. **Actual cost:** 3 calls, 17793 input tokens, 728 output tokens; case wall 9846.8 ms; local/deterministic overhead 1251.9 ms.

19. **Uncertainty:** independent human completeness, causal/subject alignment, temporal scope and claim entailment remain PENDING. Agent flag `COMPARATIVE_MAPPING_MISSING`. This exposed development example cannot become an untouched test case again.

### Case 4: `194cf6ad-e309-4d76-8a70-0f8a972042d2`

Attributed summary of the original GaRAGe question: **Difficulties of reasoning across multiple evidence hops**.

1. **Original ID / row:** `194cf6ad-e309-4d76-8a70-0f8a972042d2`; original zero-based row 153.

2. **Question summary:** Difficulties of reasoning across multiple evidence hops (original AmazonScience GaRAGe, pinned source commit).

3. **Original labels:** relevance {'YES': 15}; correctness {'ANSWER-THE-QUESTION': 7, 'RELATED-INFORMATION': 8}. Original strings are preserved, including blank and OUTDATED.

4. **Old strict validation:** False. Original mode CFAF. The original pilot files are unchanged.

5. **New sparse validation:** live True; cached original-raw A3 True; live errors `[]`.

6. **Inventory / roles:** all 15 authorized passages retained; 4 explicit source roles; 11 NOT_ASSESSED. Complete application inventory hash `189d8d8d380586013d7e2e4f6e6cfe977a01fdf2ac7cceb34300787acf6d0dd0`.

7. **Selected support:** raw span IDs `['view-0001:span-0001', 'view-0003:span-0001', 'view-0012:span-0001', 'view-0015:span-0001']`; validated original source markers `['cite_1', 'cite_3', 'cite_12', 'cite_15']`. Validation is reference/role/scope validation, not an entailment proof.

8. **Unassessed inventory entries:** `['view-0002', 'view-0004', 'view-0005', 'view-0006', 'view-0007', 'view-0008', 'view-0009', 'view-0010', 'view-0011', 'view-0013', 'view-0014']`. These entries create no support, no irrelevance inference and no new permission.

9. **Old prediction:** strict original pilot CFAF; strict validator on the same freshly generated analysis CFAF.

10. **New prediction:** primary gate FULL; original A0 substantive gate after sparse validation FULL; cached A3 FULL.

11. **Shared control:** raw generated FULL; served FULL; response status `{'errors': [], 'raw_declared_mode': 'FULL', 'safe_fallback_applied': False, 'status': 'GENERATED_VALID_CONTRACT'}`.

12. **Public response:** Concise factual answer; full exact text is in local/REPORT_FULL.md.

13. **Failure semantics:** `{'credited_evidential_CFAF': False, 'failure_class': None, 'reason': 'FULFILMENT_ESTABLISHED', 'status': 'VERIFIED_FULFILMENT'}`. Immediate internal reason `None`. Model-output post-validation status is audited separately from the T3 gate.

14. **Original answering-labelled sources selected:** 2; full selected-source correctness distribution {'RELATED-INFORMATION': 2, 'ANSWER-THE-QUESTION': 2}. An answering-labelled source is not a complete-answer label.

15. **Citations:** actual inline/rendered citations T3=0, control=0; invalid inline [] / []. Valid unverified claim-group reference associations T3=4, control=0. These are not rendered as verified citations.

16. **Missing requirements / limitations:** More specific retrieval, intermediate-reasoning and performance limitations, if required by a future rubric. Gate issues `[]`.

17. **Non-independent qualitative grounding assessment:** The short responses describe genuine multi-source reasoning difficulties from the selected evidence. They omit several reference-answer details. No unsupported factual claim was identified in this review; a broader completeness judgement remains independent work.

18. **Actual cost:** 3 calls, 16026 input tokens, 623 output tokens; case wall 8199.0 ms; local/deterministic overhead 953.2 ms.

19. **Uncertainty:** independent human completeness, causal/subject alignment, temporal scope and claim entailment remain PENDING. Agent flag `GROUNDED_SUMMARY_NOT_LONG_FORM_VALIDATION`. This exposed development example cannot become an untouched test case again.

### Case 5: `13c6bf75-a2e0-4943-a586-d3dc5ca1eb20`

Attributed summary of the original GaRAGe question: **Contingent-payment accounting versus risk-management strategy**.

1. **Original ID / row:** `13c6bf75-a2e0-4943-a586-d3dc5ca1eb20`; original zero-based row 2044.

2. **Question summary:** Contingent-payment accounting versus risk-management strategy (original AmazonScience GaRAGe, pinned source commit).

3. **Original labels:** relevance {'YES': 15}; correctness {'RELATED-INFORMATION': 14, 'UNKNOWN': 1}. Original strings are preserved, including blank and OUTDATED.

4. **Old strict validation:** False. Original mode CFAF. The original pilot files are unchanged.

5. **New sparse validation:** live False; cached original-raw A3 True; live errors `['UNKNOWN_SPAN_ID:view-0011:span-1']`.

6. **Inventory / roles:** all 15 authorized passages retained; 1 explicit source roles; 14 NOT_ASSESSED. Complete application inventory hash `919f1b8250d2b551c7cb66935f57516ed0054252160181369bdb74ba43b7cb28`.

7. **Selected support:** raw span IDs `['view-0011:span-1']`; validated original source markers `[]`. Validation is reference/role/scope validation, not an entailment proof.

8. **Unassessed inventory entries:** `['view-0001', 'view-0002', 'view-0003', 'view-0004', 'view-0005', 'view-0006', 'view-0007', 'view-0008', 'view-0009', 'view-0010', 'view-0012', 'view-0013', 'view-0014', 'view-0015']`. These entries create no support, no irrelevance inference and no new permission.

9. **Old prediction:** strict original pilot CFAF; strict validator on the same freshly generated analysis CFAF.

10. **New prediction:** primary gate CFAF; original A0 substantive gate after sparse validation CFAF; cached A3 FULL.

11. **Shared control:** raw generated FULL; served CFAF; response status `{'credited_evidential_CFAF': False, 'errors': [], 'raw_declared_mode': 'FULL', 'reason': 'INVALID_EVIDENCE_REFERENCE', 'safe_fallback_applied': True, 'status': 'OPERATIONAL_FAILURE'}`.

12. **Public response:** Neutral operational verification failure.

13. **Failure semantics:** `{'credited_evidential_CFAF': False, 'failure_class': 'OPERATIONAL', 'reason': 'INVALID_EVIDENCE_REFERENCE', 'status': 'OPERATIONAL_FAILURE', 'validation_errors': ['UNKNOWN_SPAN_ID:view-0011:span-1']}`. Immediate internal reason `INVALID_EVIDENCE_REFERENCE`. Model-output post-validation status is audited separately from the T3 gate.

14. **Original answering-labelled sources selected:** 0; full selected-source correctness distribution {}. An answering-labelled source is not a complete-answer label.

15. **Citations:** actual inline/rendered citations T3=0, control=0; invalid inline [] / []. Valid unverified claim-group reference associations T3=0, control=0. These are not rendered as verified citations.

16. **Missing requirements / limitations:** Evidence connecting the accounting treatment to the requested risk-management approach. Gate issues `['HARD:request-1:HARD_ASSESSMENT_CONTRACT_INVALID', 'HARD:request-1:HARD_INVALID_SPAN', 'SEMANTIC_ASSESSMENT_INVALID']`.

17. **Non-independent qualitative grounding assessment:** Primary B withholds FULL because of an unpadded span ID. Both served replies are operational, not successful evidence-insufficiency decisions. The raw control still promotes an accounting rule to a risk-management strategy. Cached A3 and supplemental R1 permit a FULL candidate with the same unsupported strategic relation. Original human grounding deflects; no expected label was used to force this case.

18. **Actual cost:** 3 calls, 20065 input tokens, 434 output tokens; case wall 6766.1 ms; local/deterministic overhead 383.6 ms.

19. **Uncertainty:** independent human completeness, causal/subject alignment, temporal scope and claim entailment remain PENDING. Agent flag `TECHNICAL_BLOCK_MASKS_UNSUPPORTED_STRATEGIC_INFERENCE`. This exposed development example cannot become an untouched test case again.

### Case 6: `099f1832-11af-4fb4-bb8c-880baee07986`

Attributed summary of the original GaRAGe question: **A diplomatic tour and international positioning**.

1. **Original ID / row:** `099f1832-11af-4fb4-bb8c-880baee07986`; original zero-based row 2214.

2. **Question summary:** A diplomatic tour and international positioning (original AmazonScience GaRAGe, pinned source commit).

3. **Original labels:** relevance {'NO': 4, 'YES': 11}; correctness {'': 4, 'RELATED-INFORMATION': 6, 'ANSWER-THE-QUESTION': 5}. Original strings are preserved, including blank and OUTDATED.

4. **Old strict validation:** False. Original mode CFAF. The original pilot files are unchanged.

5. **New sparse validation:** live True; cached original-raw A3 True; live errors `[]`.

6. **Inventory / roles:** all 15 authorized passages retained; 4 explicit source roles; 11 NOT_ASSESSED. Complete application inventory hash `d014663264cc4898e219e7d900f1a380acd5eefb3ad26e04fc0f7468563fc9a8`.

7. **Selected support:** raw span IDs `['view-0002:span-0000', 'view-0003:span-0000', 'view-0005:span-0000', 'view-0014:span-0000']`; validated original source markers `['cite_2', 'cite_3', 'cite_5', 'cite_14']`. Validation is reference/role/scope validation, not an entailment proof.

8. **Unassessed inventory entries:** `['view-0001', 'view-0004', 'view-0006', 'view-0007', 'view-0008', 'view-0009', 'view-0010', 'view-0011', 'view-0012', 'view-0013', 'view-0015']`. These entries create no support, no irrelevance inference and no new permission.

9. **Old prediction:** strict original pilot CFAF; strict validator on the same freshly generated analysis CFAF.

10. **New prediction:** primary gate FULL; original A0 substantive gate after sparse validation FULL; cached A3 FULL.

11. **Shared control:** raw generated FULL; served FULL; response status `{'errors': [], 'raw_declared_mode': 'FULL', 'safe_fallback_applied': False, 'status': 'GENERATED_VALID_CONTRACT'}`.

12. **Public response:** Concise factual answer; full exact text is in local/REPORT_FULL.md.

13. **Failure semantics:** `{'credited_evidential_CFAF': False, 'failure_class': None, 'reason': 'FULFILMENT_ESTABLISHED', 'status': 'VERIFIED_FULFILMENT'}`. Immediate internal reason `None`. Model-output post-validation status is audited separately from the T3 gate.

14. **Original answering-labelled sources selected:** 2; full selected-source correctness distribution {'RELATED-INFORMATION': 2, 'ANSWER-THE-QUESTION': 2}. An answering-labelled source is not a complete-answer label.

15. **Citations:** actual inline/rendered citations T3=0, control=0; invalid inline [] / []. Valid unverified claim-group reference associations T3=4, control=4. These are not rendered as verified citations.

16. **Missing requirements / limitations:** Correct subject-to-activity relation; specific diplomatic/economic objectives. Gate issues `[]`.

17. **Non-independent qualitative grounding assessment:** New T3 and control both assert cultural exchange as part of the diplomatic-tour positioning. The explicit cultural-exchange passage concerns a musician, while the validated selected sources do not establish that relation for the prime minister. This is one flagged unsupported relation in each served FULL response, despite valid references and complete semantic flags.

18. **Actual cost:** 3 calls, 15909 input tokens, 707 output tokens; case wall 10372.8 ms; local/deterministic overhead 911.6 ms.

19. **Uncertainty:** independent human completeness, causal/subject alignment, temporal scope and claim entailment remain PENDING. Agent flag `UNSUPPORTED_CROSS_SUBJECT_RELATION_IN_SERVED_FULL`. This exposed development example cannot become an untouched test case again.

### Case 7: `49865de4-d298-41f9-a00f-a4c886147680`

Attributed summary of the original GaRAGe question: **Alternative share-price forecasts**.

1. **Original ID / row:** `49865de4-d298-41f9-a00f-a4c886147680`; original zero-based row 581.

2. **Question summary:** Alternative share-price forecasts (original AmazonScience GaRAGe, pinned source commit).

3. **Original labels:** relevance {'YES': 15}; correctness {'ANSWER-THE-QUESTION': 6, 'RELATED-INFORMATION': 9}. Original strings are preserved, including blank and OUTDATED.

4. **Old strict validation:** False. Original mode CFAF. The original pilot files are unchanged.

5. **New sparse validation:** live True; cached original-raw A3 True; live errors `[]`.

6. **Inventory / roles:** all 15 authorized passages retained; 3 explicit source roles; 12 NOT_ASSESSED. Complete application inventory hash `51dd5e0e87e2ec2b9c724807a204e100648f28ea2620ae318d0b31bd267580e9`.

7. **Selected support:** raw span IDs `['view-0003:span-0000', 'view-0004:span-0000', 'view-0005:span-0000']`; validated original source markers `['cite_3', 'cite_4', 'cite_5']`. Validation is reference/role/scope validation, not an entailment proof.

8. **Unassessed inventory entries:** `['view-0001', 'view-0002', 'view-0006', 'view-0007', 'view-0008', 'view-0009', 'view-0010', 'view-0011', 'view-0012', 'view-0013', 'view-0014', 'view-0015']`. These entries create no support, no irrelevance inference and no new permission.

9. **Old prediction:** strict original pilot CFAF; strict validator on the same freshly generated analysis CFAF.

10. **New prediction:** primary gate FULL; original A0 substantive gate after sparse validation FULL; cached A3 FULL.

11. **Shared control:** raw generated FULL; served FULL; response status `{'errors': [], 'raw_declared_mode': 'FULL', 'safe_fallback_applied': False, 'status': 'GENERATED_VALID_CONTRACT'}`.

12. **Public response:** Concise factual answer; full exact text is in local/REPORT_FULL.md.

13. **Failure semantics:** `{'credited_evidential_CFAF': False, 'failure_class': None, 'reason': 'FULFILMENT_ESTABLISHED', 'status': 'VERIFIED_FULFILMENT'}`. Immediate internal reason `None`. Model-output post-validation status is audited separately from the T3 gate.

14. **Original answering-labelled sources selected:** 3; full selected-source correctness distribution {'ANSWER-THE-QUESTION': 3}. An answering-labelled source is not a complete-answer label.

15. **Citations:** actual inline/rendered citations T3=0, control=0; invalid inline [] / []. Valid unverified claim-group reference associations T3=3, control=3. These are not rendered as verified citations.

16. **Missing requirements / limitations:** Forecast attribution, uncertainty and conditional assumptions. Gate issues `[]`.

17. **Non-independent qualitative grounding assessment:** The forecast values are found in the selected original answering-labelled evidence and remain described as possible scenarios. Both systems omit source attribution and the condition attached to the high forecast. Neither output is evidence that any forecast was realized.

18. **Actual cost:** 3 calls, 15506 input tokens, 658 output tokens; case wall 11952.3 ms; local/deterministic overhead 682.9 ms.

19. **Uncertainty:** independent human completeness, causal/subject alignment, temporal scope and claim entailment remain PENDING. Agent flag `FORECAST_CONDITIONS_AND_ATTRIBUTION_MISSING`. This exposed development example cannot become an untouched test case again.

### Case 8: `89967e8d-2dd1-4214-a0f7-cf3588558362`

Attributed summary of the original GaRAGe question: **Potential stock recovery and company-specific catalysts**.

1. **Original ID / row:** `89967e8d-2dd1-4214-a0f7-cf3588558362`; original zero-based row 1076.

2. **Question summary:** Potential stock recovery and company-specific catalysts (original AmazonScience GaRAGe, pinned source commit).

3. **Original labels:** relevance {'YES': 13, 'NO': 2}; correctness {'UNKNOWN': 3, '': 2, 'OUTDATED': 4, 'ANSWER-THE-QUESTION': 6}. Original strings are preserved, including blank and OUTDATED.

4. **Old strict validation:** True. Original mode CFAF. The original pilot files are unchanged.

5. **New sparse validation:** live True; cached original-raw A3 True; live errors `[]`.

6. **Inventory / roles:** all 15 authorized passages retained; 0 explicit source roles; 15 NOT_ASSESSED. Complete application inventory hash `941771308a821841de92afd54dcbc8fde57c9b2353aa31adaa37f5a8115ec1a8`.

7. **Selected support:** raw span IDs `[]`; validated original source markers `[]`. Validation is reference/role/scope validation, not an entailment proof.

8. **Unassessed inventory entries:** `['view-0001', 'view-0002', 'view-0003', 'view-0004', 'view-0005', 'view-0006', 'view-0007', 'view-0008', 'view-0009', 'view-0010', 'view-0011', 'view-0012', 'view-0013', 'view-0014', 'view-0015']`. These entries create no support, no irrelevance inference and no new permission.

9. **Old prediction:** strict original pilot CFAF; strict validator on the same freshly generated analysis CFAF.

10. **New prediction:** primary gate CFAF; original A0 substantive gate after sparse validation CFAF; cached A3 CFAF.

11. **Shared control:** raw generated CFAF; served CFAF; response status `{'credited_evidential_CFAF': False, 'errors': ['CFAF_REASON_AND_REALIZATION_REQUIRED'], 'raw_declared_mode': 'CFAF', 'reason': 'GENERATION_CONTRACT_INVALID', 'safe_fallback_applied': True, 'status': 'OPERATIONAL_FAILURE'}`.

12. **Public response:** Clarification request; semantic reason is disputed in review.

13. **Failure semantics:** `{'credited_evidential_CFAF': True, 'failure_class': 'EVIDENTIAL_OR_REQUEST_RELATIVE', 'reason': 'UNRESOLVED_REFERENT', 'status': 'VALIDATED_CFAF'}`. Immediate internal reason `AMBIGUOUS_REQUEST`. Model-output post-validation status is audited separately from the T3 gate.

14. **Original answering-labelled sources selected:** 0; full selected-source correctness distribution {}. An answering-labelled source is not a complete-answer label.

15. **Citations:** actual inline/rendered citations T3=0, control=0; invalid inline [] / []. Valid unverified claim-group reference associations T3=0, control=0. These are not rendered as verified citations.

16. **Missing requirements / limitations:** Assessment of company-specific developments and correct distinction between an explicit company referent and missing factual support. Gate issues `['AMBIGUOUS_REFERENCE', 'ESSENTIAL_INFORMATION_MISSING', 'GRANULARITY_NOT_SUPPORTED', 'HARD:request-1:HARD_NO_CANDIDATE_OUTPUT', 'NO_GROUNDED_ANSWER_CANDIDATE', 'NO_VERIFIED_SUPPORT_SPANS', 'REQUEST_INCOMPLETE', 'REQUEST_RELATION_UNSUPPORTED', 'REQUIREMENT_UNSUPPORTED:FACT_LOOKUP']`.

17. **Non-independent qualitative grounding assessment:** The new sparse analysis validly reports zero source roles and zero support: all fifteen inventory entries remain NOT_ASSESSED, not irrelevant. It still misses available candidate catalysts and sets an unsupported unresolved-referent property. T3 therefore gives a questionable clarification. The raw control abstains with a missing realization field; the strict validator replaces that invalid response with neutral operational wording.

18. **Actual cost:** 3 calls, 14741 input tokens, 343 output tokens; case wall 7872.7 ms; local/deterministic overhead 129.5 ms.

19. **Uncertainty:** independent human completeness, causal/subject alignment, temporal scope and claim entailment remain PENDING. Agent flag `SEMANTIC_MISSED_SUPPORT_WITH_CONTROL_CONTRACT_FAILURE`. This exposed development example cannot become an untouched test case again.

### Case 9: `e10bb772-6c4e-426f-a924-3d3ba0b23515`

Attributed summary of the original GaRAGe question: **A transverse-momentum framework in particle calculations**.

1. **Original ID / row:** `e10bb772-6c4e-426f-a924-3d3ba0b23515`; original zero-based row 29.

2. **Question summary:** A transverse-momentum framework in particle calculations (original AmazonScience GaRAGe, pinned source commit).

3. **Original labels:** relevance {'YES': 15}; correctness {'ANSWER-THE-QUESTION': 5, 'UNKNOWN': 4, 'RELATED-INFORMATION': 6}. Original strings are preserved, including blank and OUTDATED.

4. **Old strict validation:** False. Original mode CFAF. The original pilot files are unchanged.

5. **New sparse validation:** live True; cached original-raw A3 True; live errors `[]`.

6. **Inventory / roles:** all 15 authorized passages retained; 2 explicit source roles; 13 NOT_ASSESSED. Complete application inventory hash `b29bfdc7c79d997c16feee621cdf7d4cc85f6b3138ed8bb9dfcf353485d68a1b`.

7. **Selected support:** raw span IDs `['view-0001:span-0001', 'view-0006:span-0001']`; validated original source markers `['cite_1', 'cite_6']`. Validation is reference/role/scope validation, not an entailment proof.

8. **Unassessed inventory entries:** `['view-0002', 'view-0003', 'view-0004', 'view-0005', 'view-0007', 'view-0008', 'view-0009', 'view-0010', 'view-0011', 'view-0012', 'view-0013', 'view-0014', 'view-0015']`. These entries create no support, no irrelevance inference and no new permission.

9. **Old prediction:** strict original pilot CFAF; strict validator on the same freshly generated analysis CFAF.

10. **New prediction:** primary gate FULL; original A0 substantive gate after sparse validation FULL; cached A3 FULL.

11. **Shared control:** raw generated FULL; served FULL; response status `{'errors': [], 'raw_declared_mode': 'FULL', 'safe_fallback_applied': False, 'status': 'GENERATED_VALID_CONTRACT'}`.

12. **Public response:** Concise factual answer; full exact text is in local/REPORT_FULL.md.

13. **Failure semantics:** `{'credited_evidential_CFAF': False, 'failure_class': None, 'reason': 'FULFILMENT_ESTABLISHED', 'status': 'VERIFIED_FULFILMENT'}`. Immediate internal reason `None`. Model-output post-validation status is audited separately from the T3 gate.

14. **Original answering-labelled sources selected:** 2; full selected-source correctness distribution {'ANSWER-THE-QUESTION': 2}. An answering-labelled source is not a complete-answer label.

15. **Citations:** actual inline/rendered citations T3=0, control=0; invalid inline [] / []. Valid unverified claim-group reference associations T3=2, control=2. These are not rendered as verified citations.

16. **Missing requirements / limitations:** Optional evolution/resummation and physical-mechanism detail pending a completeness rubric. Gate issues `[]`.

17. **Non-independent qualitative grounding assessment:** Both systems provide a concise explanation supported by two answering-labelled passages. Broader scientific detail and independent domain review remain outside this bounded experiment. No unsupported factual assertion was identified in the inspected scope.

18. **Actual cost:** 3 calls, 20356 input tokens, 569 output tokens; case wall 7922.4 ms; local/deterministic overhead 498.7 ms.

19. **Uncertainty:** independent human completeness, causal/subject alignment, temporal scope and claim entailment remain PENDING. Agent flag `SUPPORTED_SCIENTIFIC_SUMMARY_PENDING_INDEPENDENT_REVIEW`. This exposed development example cannot become an untouched test case again.

### Case 10: `f1456a9c-65d3-46ff-b5b5-c8d4d98bc0ff`

Attributed summary of the original GaRAGe question: **Grid-operator selection and an inferred approval rationale**.

1. **Original ID / row:** `f1456a9c-65d3-46ff-b5b5-c8d4d98bc0ff`; original zero-based row 1881.

2. **Question summary:** Grid-operator selection and an inferred approval rationale (original AmazonScience GaRAGe, pinned source commit).

3. **Original labels:** relevance {'YES': 1, 'NO': 14}; correctness {'UNKNOWN': 1, '': 14}. Original strings are preserved, including blank and OUTDATED.

4. **Old strict validation:** False. Original mode CFAF. The original pilot files are unchanged.

5. **New sparse validation:** live False; cached original-raw A3 False; live errors `['UNKNOWN_SPAN_ID:view-0001:span-0004']`.

6. **Inventory / roles:** all 15 authorized passages retained; 15 explicit source roles; 0 NOT_ASSESSED. Complete application inventory hash `04ae69f1b9b4e0608318965bf719753c6724e7955f188cb439adda9ca42135c9`.

7. **Selected support:** raw span IDs `['view-0001:span-0001', 'view-0001:span-0004']`; validated original source markers `[]`. Validation is reference/role/scope validation, not an entailment proof.

8. **Unassessed inventory entries:** `[]`. These entries create no support, no irrelevance inference and no new permission.

9. **Old prediction:** strict original pilot CFAF; strict validator on the same freshly generated analysis CFAF.

10. **New prediction:** primary gate CFAF; original A0 substantive gate after sparse validation CFAF; cached A3 CFAF.

11. **Shared control:** raw generated FULL; served CFAF; response status `{'credited_evidential_CFAF': False, 'errors': [], 'raw_declared_mode': 'FULL', 'reason': 'INVALID_EVIDENCE_REFERENCE', 'safe_fallback_applied': True, 'status': 'OPERATIONAL_FAILURE'}`.

12. **Public response:** Neutral operational verification failure.

13. **Failure semantics:** `{'credited_evidential_CFAF': False, 'failure_class': 'OPERATIONAL', 'reason': 'INVALID_EVIDENCE_REFERENCE', 'status': 'OPERATIONAL_FAILURE', 'validation_errors': ['UNKNOWN_SPAN_ID:view-0001:span-0004']}`. Immediate internal reason `INVALID_EVIDENCE_REFERENCE`. Model-output post-validation status is audited separately from the T3 gate.

14. **Original answering-labelled sources selected:** 0; full selected-source correctness distribution {}. An answering-labelled source is not a complete-answer label.

15. **Citations:** actual inline/rendered citations T3=0, control=0; invalid inline [] / []. Valid unverified claim-group reference associations T3=0, control=0. These are not rendered as verified citations.

16. **Missing requirements / limitations:** Actual approval rationale, rather than appointment description or support for a schedule. Gate issues `['HARD:request-1:HARD_ASSESSMENT_CONTRACT_INVALID', 'HARD:request-1:HARD_INVALID_SPAN', 'SEMANTIC_ASSESSMENT_INVALID']`.

17. **Non-independent qualitative grounding assessment:** The nonexistent span index remains invalid in cached and fresh runs; R1 cannot invent it. Both primary served responses are neutral operational CFAF. The raw control still converts network representation and support for a startup timetable into a rationale for approving the operator. These two relations are not established by the supplied text. This is not credited as a correct semantic refusal.

18. **Actual cost:** 3 calls, 20932 input tokens, 1111 output tokens; case wall 12919.7 ms; local/deterministic overhead 794.8 ms.

19. **Uncertainty:** independent human completeness, causal/subject alignment, temporal scope and claim entailment remain PENDING. Agent flag `INVALID_REFERENCE_AND_UNSUPPORTED_CAUSAL_RAW_CONTROL`. This exposed development example cannot become an untouched test case again.

## Costs, tests and security

| Kind | Calls | Input tokens | Output tokens | Mean ms | Max ms | API errors |
| --- | --- | --- | --- | --- | --- | --- |
| semantic_analysis | 10 | 95584 | 5299 | 5758.9 | 9211.1 | 0 |
| semantic_cfaf | 10 | 39309 | 552 | 1451.1 | 1966.3 | 0 |
| shared_control | 10 | 39638 | 594 | 1631.6 | 2706.3 | 0 |


Totals: **30 attempts / 30 successes / 0 API errors / 0 retries**; 174,531 input + 6,445 output tokens; mean provider latency 2947.2 ms, maximum 9211.1 ms. All 30 finish reasons are stop; no truncation. Cached A, R1 and C use zero calls. Local/deterministic overhead totals **7.324 seconds**, estimated as case wall time minus provider latency, including guards, inventories, parsing and counterfactual comparisons rather than pure CPU time. Cached A elapsed 8.113 seconds.

The original pilot used 30 calls, with 176,503 input and 7,273 output tokens. Fresh output sizes differ despite identical analysis requests. Lower new totals are not claimed as an algorithmic token reduction: validation is deterministic and the model prompt/schema did not change. No dollar estimate is provided because pricing was not verified.

Final primary synthetic tests: **57 passed**. Final isolated compatibility suite: **677 passed, 3 hash-only tests deselected**; those three ran against unchanged original working files and **3 passed**. The 57 are included in 677, not extra unique tests. Supplemental R1: **5 passed**. Original CFAF suite: **77 passed, 13 subtests passed, one known pre-existing failure**, `test_preheldout_attempt1_plan_artifacts_are_plan_only`, because a previously committed authorization metadata file exists. It was preserved. The final compatibility retest follows the last primary source changes; archived timer rebasing occurred only in a disposable test process with API credentials removed.

All **1029 pre-existing tracked files**, prior raw event hash, original selection/runtime bytes, and frozen primary files match. All thirty serialized payloads passed forbidden-gold, explicit `sample_id`, selected/private-ID and authorization checks. Ten analysis payloads match prior payloads exactly. Both generators receive identical passages, date and fresh semantic data; neither receives the private inventory. Body hashes and span mappings validate. P5, DENY exclusion, metadata/aggregate scope, native provenance and original selector/stage tests pass. No reserved/new record was used. No unauthorized public citation is rendered.

Task start UTC `2026-10-29T06:06:18+00:00` (Budapest 08:06:18, 29 October 2026); persistent wall/monotonic anchors and 45/50/55/60-minute cutoffs are in task_state.json. Elapsed at report generation: 1185.6 seconds. No clock/call ledger reset. A completion receipt records final commit and elapsed time.

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
13. **Cost?** 30 calls, 174,531/6,445 input/output tokens, 7.324 seconds local overhead; zero cached/R1/C calls.
14. **Ready for default?** Application inventory, sparse bookkeeping, duplicate/unknown-reference checks, existing authorization checks and explicit operational/public-vocabulary validation are suitable mechanical building blocks. This is not approval of the whole pipeline as a factually reliable default answerer.
15. **Experimental?** R1 aliases have deterministic tests but no live run; public claim citation realization and semantic entailment/coverage remain experimental. Gate promotions require development review.
16. **Before larger Dataset3?** Add independently adjudicated request-completeness/claim-entailment criteria; prevent subject/causal inference errors; handle temporal/conditional scope; reduce format errors in a separate schema/prompt configuration; build robust per-claim citation mapping. Freeze these ten exposed outputs. Reserve the other **2356 records** for a separately planned independent test.

Structural validity, semantic quality, mode changes, citations and operational reporting are separate outcomes. This experiment demonstrates contract repair and clearer failure reporting; it does not establish independent semantic accuracy or a completed public-grounding solution.
