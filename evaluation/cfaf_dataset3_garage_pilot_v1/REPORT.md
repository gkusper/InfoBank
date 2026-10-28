# Dataset3: original GaRAGe ten-case CFAF pilot

## A. Executive summary

All **10 selected cases completed** with 30 successful `gpt-4o-mini` calls, zero API errors and zero retries. T3 generated **0 FULL / 10 CFAF**; the shared control generated **9 FULL / 1 CFAF**. A0 gate-only returned 10 CFAF. These counts are observed modes, **not binary accuracy**.

The central result is an integration limitation: eight semantic assessments omitted roles for some supplied passages, one used an invalid span identifier, and only one assessment passed the existing semantic contract. All 30 provider responses ended with `finish_reason=stop`; none was truncated. The existing T3 gate rejected invalid assessments as designed. Its refusal text often hides that structural failure behind a generic evidence-missing reason. The sole valid assessment missed available candidate support and produced an inappropriate clarification candidate.

Dataset1 tests governed InfoBank fulfilment; Dataset2 tests selective refusal; Dataset3 adds source-labelled, multi-passage evidence-grounded answering, temporal metadata and longer reference answers. Original GaRAGe is usable as Dataset3, but this run does **not** establish that T3 successfully answers its questions. No tested source, prompt, original label or selected case was changed after observing outputs. No second pilot was run.

This committed report contains safe summaries. The ignored local companion `local/REPORT_FULL.md` contains the exact ten questions, both public responses, original-answer summaries, span mappings, requirement diagnostics and 17 review items per case. Original full passages, reference answers, raw traces and unredacted gold remain ignored.

## B. Dataset verification

Official source: [AmazonScience GaRAGe](https://github.com/amazon-science/GaRAGe), commit `2b7264f5d4e066affbe4b67b7d3b9cffeff98ede`. Download: [immutable JSONL](https://raw.githubusercontent.com/amazon-science/GaRAGe/2b7264f5d4e066affbe4b67b7d3b9cffeff98ede/data/GaRAGe_benchmark.jsonl). Download UTC: 2026-10-28T22:59:48.452762+00:00. File: `GaRAGe_benchmark.jsonl`; **28,426,483 bytes**; SHA-256 **`419e3941f6e8eb4082a74ca2140c1f9337f8b467ff76656a6b8b0290ca3f3a72`**. Parsed 2366 rows, 2366 unique nonmissing IDs, zero duplicates, no dropped records, 35,351 grounding passages. Passage count range 5–15, mean 14.941; 2329 records have 15 passages. All three evidence-annotation lists align with their grounding lists.

The [ACL Findings 2025 publication](https://aclanthology.org/2025.findings-acl.875/) describes the same 2366-question benchmark with over 35K grounding passages. The pinned repository licence is **CC-BY-NC-4.0**; its bytes are hashed in `source_audit.json`. The full original data was downloaded locally and is excluded from Git.

Observed relevance vocabulary: `{'': 4, 'NO': 9393, 'YES': 25954}`. Observed correctness vocabulary: `{'': 9402, 'ANSWER-THE-QUESTION': 11015, 'OUTDATED': 2771, 'RELATED-INFORMATION': 9337, 'UNKNOWN': 2826}`. In particular, **OUTDATED and the empty string are original values**. Neither is collapsed into UNKNOWN. The exact original fields use `question_false_premise`, `question_seeking`, `question_sensitive`, `question_type`, `question_complexity`, `question_category` and `answer_related_info`. The actual grounding is a list of objects with `cite_N`, `age`, `date`, `provider`. All field names, types, label counts and passage-count distribution are in `source_audit.json` and `GARAGE_SOURCE_AUDIT.md`. Free-text comments and tags remain original; they are not invented categorical labels.

## C. Random selection

Population: all ordered 2366 valid JSONL rows. Python: `3.12.14 (main, Aug 25 2026, 14:01:42) [MSC v.1944 64 bit (AMD64)]`. Algorithm: `random.Random(20261028).sample(range(2366), 10)`. Zero-based indices: `[2287, 186, 868, 153, 2044, 2214, 581, 1076, 29, 1881]`. One-based indices: `[2288, 187, 869, 154, 2045, 2215, 582, 1077, 30, 1882]`. The selection was persisted at 2026-10-28T22:59:48.421772+00:00, before any model outputs or qualitative review. No stratification, balancing, resampling, substitutions or sorting by label occurred. Raw-record hashes use exact original line bytes excluding line terminators.

`dataset3_selection_manifest.json`, its metadata supplement and `dataset3_exposure_ledger.json` record the ten IDs and their provenance. Only these ten records were qualitatively inspected. Structural parsing and metadata-only aggregate statistics were performed on the complete file. The other **2356 records were not used for development diagnosis** and should remain reserved. Dataset1 and Dataset2 ledgers are unchanged.

## D. CFAF integration

Baseline HEAD: `394811960ad93059a466417251d17066f51a07f5` on `experiment/cfaf-target-claim-alignment-v1`; this work is on `experiment/cfaf-garage-pilot-v1`. The existing T3 integration, RDA/RECV, target and claim diagnostics, all eight named stages and original `TopLevelModeSelectionStage` remain byte-identical. T3 target/claim additions remain shadow diagnostics; this experiment gives them no new gate authority.

The adapter accepts exactly `question`, `question_date`, `grounding`. It preserves the question verbatim and every original passage body, original citation marker and original date/provider/age metadata. Each passage receives a neutral `view-NNNN` ID and an original-marker mapping. The existing deterministic catalogue supplies 430-character windows with 70-character overlap; exact offsets/hashes validate references. Public source metadata is inserted as a short header, with its length recorded so the unchanged passage body can be independently verified. Original as-of date is sent equally to analysis and both generators; the query-only fallback remains query-only and was not needed.

All supplied passages have task-authorized FULL access. `web` and `ent` remain provider metadata; neither creates a denial, ownership claim, authority claim or trusted InfoBank ingestion provenance. No live grounding retrieval or external case-fact search occurred.

Before execution, the adapter declared an input budget of 60,000 tokens using a conservative serialized ASCII-JSON UTF-8 byte-count bound plus 128. Its gold-blind overflow policy is a maximal whole-passage prefix in original order. Every selected case retained all 15 passages, so no altered-context subgroup was needed. Actual provider input token usage was below every recorded bound.

The existing prompts/schema were unchanged. Both generated systems use the newly authorized 512-token generation ceiling; analysis remains 1500, query profiling 500, temperature 0, repetitions 1. The legacy short-answer instruction and T3 verbatim-candidate copying remain in effect and limit long-form completeness. T3 and control share one semantic assessment per case. Control receives no T3 contract. A0 reuses that assessment for a gate decision and has no redundant generation. There were no embeddings, judges, semantic repair calls or second verifiers.

## E. Overall pilot results

Table 1: exact sample order, original indices and observed modes.

| Order | Row 0/1 | sample_id | Category | Complexity | Passages | T3 | Control | A0 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2287/2288 | 263f7106-41c9-49b1-992e-4c7452aef3a8 | Computers & Electronics | Multi-hop | 15 | CFAF | FULL | CFAF |
| 2 | 186/187 | 90ca5695-a633-40b8-b3dc-56bbbf208245 | Science | Multi-hop | 15 | CFAF | FULL | CFAF |
| 3 | 868/869 | 45caa113-bbd0-4fbf-8526-37c1fcc8bae5 | Internet & Telecom | Comparison | 15 | CFAF | FULL | CFAF |
| 4 | 153/154 | 194cf6ad-e309-4d76-8a70-0f8a972042d2 | Jobs & Education | Set | 15 | CFAF | FULL | CFAF |
| 5 | 2044/2045 | 13c6bf75-a2e0-4943-a586-d3dc5ca1eb20 | Business & Industrial | Comparison | 15 | CFAF | FULL | CFAF |
| 6 | 2214/2215 | 099f1832-11af-4fb4-bb8c-880baee07986 | Law & Government | Post-processing heavy | 15 | CFAF | FULL | CFAF |
| 7 | 581/582 | 49865de4-d298-41f9-a00f-a4c886147680 | Finance, Business & Industrial | Multi-hop | 15 | CFAF | FULL | CFAF |
| 8 | 1076/1077 | 89967e8d-2dd1-4214-a0f7-cf3588558362 | Stock | Simple | 15 | CFAF | CFAF | CFAF |
| 9 | 29/30 | e10bb772-6c4e-426f-a924-3d3ba0b23515 | Science | Post-processing heavy | 15 | CFAF | FULL | CFAF |
| 10 | 1881/1882 | f1456a9c-65d3-46ff-b5b5-c8d4d98bc0ff | Business & Industrial  | Simple w. condition | 15 | CFAF | FULL | CFAF |


Table 2: original annotation counts and the three distinct source-selection notions. ANSWER means the exact original `ANSWER-THE-QUESTION` label; RELATED means `RELATED-INFORMATION`. Public citation counts do not include analyzer support spans.

| Case | YES / NO | ANSWER / RELATED / UNKNOWN / OUTDATED / blank | Global raw sources | PRIMARY SUPPORTS sources | T3 citations | Control citations |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 4 / 11 | 2 / 0 / 0 / 2 / 11 | 3 | 3 | 0 | 0 |
| 2 | 15 / 0 | 4 / 10 / 1 / 0 / 0 | 4 | 4 | 0 | 0 |
| 3 | 15 / 0 | 11 / 4 / 0 / 0 / 0 | 4 | 4 | 0 | 0 |
| 4 | 15 / 0 | 7 / 8 / 0 / 0 / 0 | 4 | 4 | 0 | 0 |
| 5 | 15 / 0 | 0 / 14 / 1 / 0 / 0 | 1 | 1 | 0 | 0 |
| 6 | 11 / 4 | 5 / 6 / 0 / 0 / 4 | 5 | 5 | 0 | 0 |
| 7 | 15 / 0 | 6 / 9 / 0 / 0 / 0 | 3 | 3 | 0 | 0 |
| 8 | 13 / 2 | 6 / 0 / 3 / 4 / 2 | 0 | 0 | 0 | 0 |
| 9 | 15 / 0 | 5 / 6 / 4 / 0 / 0 | 2 | 2 | 0 | 0 |
| 10 | 1 / 14 | 0 / 0 / 1 / 0 / 14 | 1 | 2 | 0 | 0 |


Nine generated mode disagreements occurred between T3 and control; T3 and A0 agreed in all ten gate decisions. Nine of ten semantic assessments were invalid. Eight fail `SOURCE_ROLE_COVERAGE_INVALID`; the last fails `UNKNOWN_SPAN_ID:view-0001:span-0004`. The one valid assessment has no supporting candidate. All generated public response objects passed the existing generator validator. The control in case 8 used the noncanonical public reason string MISSING_EVIDENCE; the permissive string schema accepted it. This does not establish that their content, completeness or reason class is correct.

## F. Detailed case-by-case review

These are **non-independent agent observations**, with all human review fields pending. Safe summaries follow; exact questions, both complete outputs and all 17 requested review items are in the ignored local companion.

### Case 1: `263f7106-41c9-49b1-992e-4c7452aef3a8`

Recent software-assistant rollout and administrative work. Original row 2287 (zero-based), 2288 (one-based); Multi-hop; category `Computers & Electronics`; original as-of date 19 January 2025. All 15 passages retained. T3 CFAF, control FULL, A0 CFAF. Semantic validity: False; validation issues: `['SOURCE_ROLE_COVERAGE_INVALID']`.

The control describes generic automation supported by its selected passages, but all three proposed support sources are labelled NO for original relevance. It does not address the recent-update scope that the original answer emphasizes. T3 refuses because the role list is incomplete, despite other supplied passages addressing that scope.

Raw proposed global source selection P/R/F1: 0.00%/0.00%/0.00%; original correctness distribution {'': 3}. Neither public answer contains a recognized citation. Qualitative flag: `TIME_SCOPE_AND_IRRELEVANT_SUPPORT`; human review pending.

### Case 2: `90ca5695-a633-40b8-b3dc-56bbbf208245`

Space-observatory findings about accretion environments. Original row 186 (zero-based), 187 (one-based); Multi-hop; category `Science`; original as-of date 17 December 2024. All 15 passages retained. T3 CFAF, control FULL, A0 CFAF. Semantic validity: False; validation issues: `['SOURCE_ROLE_COVERAGE_INVALID']`.

The control gives a concise summary supported by four original ANSWER-THE-QUESTION passages. It is shorter than the human answer, which alone does not prove insufficiency. The T3 rejection arises from a four-source role list for fifteen passages. This is a clear candidate for avoidable structural refusal.

Raw proposed global source selection P/R/F1: 100.00%/26.67%/42.11%; original correctness distribution {'ANSWER-THE-QUESTION': 4}. Neither public answer contains a recognized citation. Qualitative flag: `ROLE_COVERAGE_REJECTS_SUPPORTED_CONTENT`; human review pending.

### Case 3: `45caa113-bbd0-4fbf-8526-37c1fcc8bae5`

Hosting choices matched to organizational requirements. Original row 868 (zero-based), 869 (one-based); Comparison; category `Internet & Telecom`; original as-of date 24 December 2024. All 15 passages retained. T3 CFAF, control FULL, A0 CFAF. Semantic validity: False; validation issues: `['SOURCE_ROLE_COVERAGE_INVALID']`.

Four proposed support sources have original ANSWER-THE-QUESTION labels. The control lists relevant factors but does not explain which hosting model addresses which need. Its FULL status is therefore a request-completeness concern despite source-level relevance. T3 again rejects an incomplete role list.

Raw proposed global source selection P/R/F1: 100.00%/26.67%/42.11%; original correctness distribution {'ANSWER-THE-QUESTION': 4}. Neither public answer contains a recognized citation. Qualitative flag: `COMPARISON_WITHOUT_MODEL_MAPPING`; human review pending.

### Case 4: `194cf6ad-e309-4d76-8a70-0f8a972042d2`

Difficulties of reasoning across multiple evidence hops. Original row 153 (zero-based), 154 (one-based); Set; category `Jobs & Education`; original as-of date 17 December 2024. All 15 passages retained. T3 CFAF, control FULL, A0 CFAF. Semantic validity: False; validation issues: `['SOURCE_ROLE_COVERAGE_INVALID']`.

The control accurately summarizes several general difficulties from the selected passages, with a mixture of answering and related-information source labels. It omits several details of the longer reference. T3 refuses because four roles do not cover all fifteen passages. A short answer is not automatically incorrect; completeness needs a separate rubric.

Raw proposed global source selection P/R/F1: 100.00%/26.67%/42.11%; original correctness distribution {'RELATED-INFORMATION': 2, 'ANSWER-THE-QUESTION': 2}. Neither public answer contains a recognized citation. Qualitative flag: `ROLE_COVERAGE_AND_SUMMARY_BREVITY`; human review pending.

### Case 5: `13c6bf75-a2e0-4943-a586-d3dc5ca1eb20`

Contingent-payment accounting versus risk-management strategy. Original row 2044 (zero-based), 2045 (one-based); Comparison; category `Business & Industrial`; original as-of date 16 January 2024. All 15 passages retained. T3 CFAF, control FULL, A0 CFAF. Semantic validity: False; validation issues: `['SOURCE_ROLE_COVERAGE_INVALID']`.

The control turns a documented accounting treatment into a claim about a proactive risk-management approach. The accounting fact is supported, but the causal/strategic characterization does not follow from that passage. T3 abstains, consistent with the original deflective answer, although its immediate veto is structural invalidity rather than a demonstrated semantic diagnosis.

Raw proposed global source selection P/R/F1: 100.00%/6.67%/12.50%; original correctness distribution {'RELATED-INFORMATION': 1}. Neither public answer contains a recognized citation. Qualitative flag: `ACCOUNTING_FACT_PROMOTED_TO_RISK_STRATEGY`; human review pending.

### Case 6: `099f1832-11af-4fb4-bb8c-880baee07986`

A diplomatic tour and international positioning. Original row 2214 (zero-based), 2215 (one-based); Post-processing heavy; category `Law & Government`; original as-of date 19 January 2025. All 15 passages retained. T3 CFAF, control FULL, A0 CFAF. Semantic validity: False; validation issues: `['SOURCE_ROLE_COVERAGE_INVALID']`.

The control captures trade and innovation, but adds cultural exchange. The only explicit cultural-exchange statement in the supplied context concerns a musician's tour, not the prime minister's trip. This is a source/subject alignment risk. T3 rejects five roles for fifteen passages, leaving potentially answerable content unused.

Raw proposed global source selection P/R/F1: 100.00%/45.45%/62.50%; original correctness distribution {'RELATED-INFORMATION': 3, 'ANSWER-THE-QUESTION': 2}. Neither public answer contains a recognized citation. Qualitative flag: `CROSS_SUBJECT_CULTURAL_EXCHANGE`; human review pending.

### Case 7: `49865de4-d298-41f9-a00f-a4c886147680`

Alternative share-price forecasts. Original row 581 (zero-based), 582 (one-based); Multi-hop; category `Finance, Business & Industrial`; original as-of date 19 December 2024. All 15 passages retained. T3 CFAF, control FULL, A0 CFAF. Semantic validity: False; validation issues: `['SOURCE_ROLE_COVERAGE_INVALID']`.

The control preserves forecast language and gives values present in the selected answering passages. It omits attribution and the assumption attached to the high forecast. T3 refuses because three roles do not cover the fifteen supplied passages. The case also illustrates why public benchmark facts must remain anchored to the original as-of date.

Raw proposed global source selection P/R/F1: 100.00%/20.00%/33.33%; original correctness distribution {'ANSWER-THE-QUESTION': 3}. Neither public answer contains a recognized citation. Qualitative flag: `FORECAST_ATTRIBUTION_AND_CONDITIONS`; human review pending.

### Case 8: `89967e8d-2dd1-4214-a0f7-cf3588558362`

Potential stock recovery and company-specific catalysts. Original row 1076 (zero-based), 1077 (one-based); Simple; category `Stock`; original as-of date 26 December 2024. All 15 passages retained. T3 CFAF, control CFAF, A0 CFAF. Semantic validity: True; validation issues: `[]`.

This is the only semantically valid assessment: all fifteen roles are present and references validate. It nevertheless selects no support and states that specific factors are missing. Supplied answering-labelled passages include concrete company developments. T3 asks to clarify the referent even though the company is explicit; the semantic flag confuses missing support with referent ambiguity. Both systems deflect, so their agreement is not evidence of correctness. The control also uses MISSING_EVIDENCE as a public reason class, a noncanonical value accepted by the existing permissive string schema.

Raw proposed global source selection P/R/F1: undefined/0.00%/0.00%; original correctness distribution {}. Neither public answer contains a recognized citation. Qualitative flag: `VALID_SCHEMA_MISSED_CATALYSTS_AND_WRONG_CLARIFY`; human review pending.

### Case 9: `e10bb772-6c4e-426f-a924-3d3ba0b23515`

A transverse-momentum framework in particle calculations. Original row 29 (zero-based), 30 (one-based); Post-processing heavy; category `Science`; original as-of date 17 December 2024. All 15 passages retained. T3 CFAF, control FULL, A0 CFAF. Semantic validity: False; validation issues: `['SOURCE_ROLE_COVERAGE_INVALID']`.

The control's concise explanation is directly supported by two original answering-labelled passages. T3 refuses because the analyzer supplied only two source roles. Some deeper scientific detail is omitted, but that is not itself an unsupported factual claim.

Raw proposed global source selection P/R/F1: 100.00%/13.33%/23.53%; original correctness distribution {'ANSWER-THE-QUESTION': 2}. Neither public answer contains a recognized citation. Qualitative flag: `ROLE_COVERAGE_REJECTS_DOMAIN_ANSWER`; human review pending.

### Case 10: `f1456a9c-65d3-46ff-b5b5-c8d4d98bc0ff`

Grid-operator selection and an inferred approval rationale. Original row 1881 (zero-based), 1882 (one-based); Simple w. condition; category `Business & Industrial `; original as-of date 15 January 2025. All 15 passages retained. T3 CFAF, control FULL, A0 CFAF. Semantic validity: False; validation issues: `['UNKNOWN_SPAN_ID:view-0001:span-0004']`.

The control turns a description of network representation and support for a startup timetable into reasons for approving the operator. These are distinct relations. The analyzer also invents a span identifier beyond the catalogue. A related original NO passage is marked PRIMARY/SUPPORTS. T3 correctly avoids a FULL answer here, but its immediate reason is invalid reference structure, not a validated causal analysis.

Raw proposed global source selection P/R/F1: 100.00%/100.00%/100.00%; original correctness distribution {'UNKNOWN': 1}. Neither public answer contains a recognized citation. Qualitative flag: `CAUSAL_RELATION_AND_INVALID_SPAN`; human review pending.

## G. Evidence-grounding analysis

Table 3: source-level metrics and qualitative limits. The first three layers are **raw analyzer proposals**, including proposals from invalid assessments; they are shared by both systems. They must not be reported as accepted T3 evidence selections. Only one assessment was valid, and it selected no supporting evidence. Metric precision/recall/F1 use the original YES/NO relevance labels; unknown relevance is excluded from TP/FP. A missing selection gives undefined precision, zero recall and zero F1 when relevant sources exist. Recall against every relevant passage is not a demand that an answer cite all passages.

| Layer / system | Precision | Recall | F1 | Invalid public citations | Unsupported FULL | Unnecessary deflection |
| --- | --- | --- | --- | --- | --- | --- |
| analyzer_global_support | 88.89% | 20.17% | 32.88% | not public citations | not measured | not measured |
| analyzer_primary_supports_roles | 85.71% | 20.17% | 32.65% | not public citations | not measured | not measured |
| analyzer_requirement_support | 85.71% | 20.17% | 32.65% | not public citations | not measured | not measured |
| T3 actual public citations | undefined | 0.00% | 0.00% | 0 | 0 observed / 0 FULL; rate undefined | 8 agent-review candidates; no independent label |
| Control actual public citations | undefined | 0.00% | 0.00% | 0 | 3 FULL cases with 4 agent-flagged relation claims | 1 agent-review candidate; no independent label |


Global raw-support micro counts are TP=24, FP=3, FN=95. PRIMARY/SUPPORTS-role and requirement-support proposals give TP=24, FP=4, FN=95. The extra role-layer false positive is an originally irrelevant passage in the final causal question. Invalid-reference diagnostics remain distinct from irrelevant-source selection. The first software-update case uses three originally NO passages for generic workflow benefits; it misses the update-scoped passages. The accounting case has perfect relevance precision for its sole proposed source even though that source is only RELATED-INFORMATION. The final causal case has perfect raw source relevance precision/recall while its sole globally selected source is UNKNOWN. These are direct demonstrations that relevance is not complete-answer sufficiency.

Both public-answer citation layers contain **zero citations**, hence precision is undefined and recall/F1 are 0. Zero invalid inline citations is therefore a vacuous result. Neither system can be said to have selected better public-cited sources; their raw upstream proposals are identical. The unchanged schema has no citation field and the realization prompts do not enforce citation retention. This run is not a reproduction of the paper's RAF or official evaluation pipeline; no such score is claimed.

Qualitative review flags four unsupported relation assertions across three control FULL answers: accounting treatment promoted to risk strategy, a cultural-exchange association transferred across subjects, and two causal/support associations in operator selection. This count is agent judgement, **not** an independent entailment score. The stock-recovery control also makes a disputed absence assertion. T3 generated no FULL answers, so observed unsupported FULL count is 0 over a denominator of 0 and its rate is undefined. Eight T3 refusals are candidates for unnecessary refusal after reviewing supplied evidence/reference summaries; they are not eight independently labelled false refusals.

The failures arise at different layers: available retrieval evidence is often adequate, structural source coverage rejects otherwise promising analyses, one reference is fabricated, shared analysis sometimes misses support or transfers a relation, and public answer generation loses attribution and scope. A valid reference ID only identifies text; it does not prove the claim follows from that text.

## H. FULL/CFAF interpretation

Original `evidence_relevant` supports source-selection scoring. Original `evidence_correct` distinguishes answering, related, unknown, outdated and blank source labels. `evidence_cited` describes the human reference's citations. `answer_validate` refers to the human reference, not generated responses. These labels can support grounding diagnosis and careful qualitative comparison.

They do **not** independently establish complete fulfilment of every part of a broad, comparative, temporal or causal request. No official FULL/CFAF mapping, binary accuracy, false-refusal rate or refusal benchmark score is computed. The two original deflective answers are useful qualitative cases, but were not turned into labels for the other eight. Exact string match was not used as a substitute for grounded-answer review. Use a separate independently adjudicated requirement/completeness rubric before reporting binary accuracy.

## I. Costs and efficiency

Table 4: actual provider usage. Shared upstream analysis is counted once.

| Call kind | Calls | Input tokens | Output tokens | Mean ms | Max ms | API errors |
| --- | --- | --- | --- | --- | --- | --- |
| semantic_analysis | 10 | 95584 | 6160 | 6612.5 | 10431.6 | 0 |
| semantic_cfaf | 10 | 40285 | 511 | 1600.2 | 1909.4 | 0 |
| shared_control | 10 | 40634 | 602 | 2113.1 | 5570.9 | 0 |
| TOTAL | 30 | 176503 | 7273 | 3441.9 | 10431.6 | 0 |


Total **176,503 input tokens + 7,273 output tokens**; 30/60 allowed attempts; 30 successes; zero API errors; zero unsettled attempts; zero retries. All 30 finish reasons are `stop`. No query-profile fallback, embedding, verifier or judge call occurred. No dollar estimate is provided because current pricing was not verified. Differences from prior experiments' call totals are not claimed as algorithmic savings. Per-case end-to-end latency is in the ignored diagnostics and detailed companion.

Task start UTC: `2026-10-28T22:47:23+00:00`. Monotonic and wall-clock anchors are persisted in `task_state.json`; elapsed at report generation: 1300.4 seconds. No deadline was reset. The local completion receipt records final elapsed time and commit.

## J. Limitations and verification

This is a ten-case exposed development pilot with random category/complexity and class imbalance, not an independent final test. Public benchmark familiarity is possible. Source-level annotations do not certify complete answers; provider metadata does not reproduce InfoBank governance; no independent human answer, temporal or entailment audit has been done. Inline citations can be absent or non-entailing, while valid span IDs can still be attached to the wrong claim. All evidence remained available, but schema-contract validity failed in nine cases. The short-answer legacy setup is a poor fit for long reference answers. Agent interpretations and proposed failure counts require independent adjudication.

Adapter preflight: 30 tests passed. Scoring: 6 tests passed. Isolated exact-Git-blob regression: **614 passed, 3 hash-only tests deselected**; those hash tests ran on the original working files and **3 passed**. The adapter 30 are included in 614 and are not an additional unique-test count. Original CFAF suite: **77 passed, 13 subtests passed, one known pre-existing failure** in `test_preheldout_attempt1_plan_artifacts_are_plan_only`, which expects a previously committed authorization metadata file to be absent. It was not changed or hidden. Logs/XML and `regression_audit.json` preserve the result.

Security audit: all **985 pre-existing tracked files** match their starting hashes; frozen runtime/source/selection hashes match; all 150 selected passage bodies match the original text; all 30 serialized API payloads passed gold-field and identifier checks; shared passages, dates and semantic inputs match; model/temperature/limits/cap match. Dataset1/Dataset2 ledgers and original branches remain unchanged. A future defense improvement is to explicitly add `sample_id` to the provider key denylist: this run's exact adapter whitelist excluded it and actual payload scans confirm no leak, but the frozen provider was not patched after results. Human review remains PENDING.

## K. Recommendation

1. **Usable as Dataset3:** yes, for source-grounded answering with original passage-level labels and as-of metadata.
2. **Original labels sufficient for grounding:** sufficient for source-label selection metrics and diagnosis; insufficient alone for claim entailment and full-request completion.
3. **Reliable FULL/CFAF mapping without new judgement:** no. Preserve originals and add a separate independently adjudicated completeness layer when authorized.
4. **Observed T3 modes:** 0 FULL, 10 CFAF. A0 gate is also 0/10.
5. **Control difference:** 9 FULL, 1 CFAF; nine generated disagreements. Structural assessment vetoes dominate T3's refusals.
6. **Better-grounded sources:** neither is better by public citations, which are absent; raw analyzer source proposals are shared. High raw relevance precision is not answer adequacy.
7. **Unsupported T3 FULL:** none observed because there were no FULL outputs; this is no positive evidence of grounded answering ability.
8. **Unnecessary refusal:** eight candidates in agent review; no independent false-refusal count is available. The only structurally valid case also appears to miss candidate support.
9. **Before larger evaluation:** in a separately authorized development task, make all-source role coverage explicit and test it on synthetic multi-source fixtures; prevent invalid span IDs; require retained public citations; distinguish source relevance from answering/temporal/relational support; preserve query-scope coverage and conditional forecasts; correct ambiguity reasoning; design independent completeness/entailment adjudication. Keep the current results frozen. Any rerun of these ten would be exposed development evidence, never a new independent result.
10. **Reserve remaining records:** yes. Keep the other 2356 uninspected for later independently planned sampling/testing. Do not consume them to tune fixes discovered here.
