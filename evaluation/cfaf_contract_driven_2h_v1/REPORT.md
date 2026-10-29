# Contract-driven transition and three-dataset bounded study

## Executive summary

**160/160 planned cases completed with paired A/B/C executions**. Dataset1 and Dataset2 are exposed development cohorts. Dataset3 is a newly selected 80-row code-frozen sample, evaluated only for original source-label grounding and technical/response outcomes: it has no native FULL/CFAF gold and no independent claim-adjudication result.

| Dataset | Cohort | Planned | Paired complete | Incomplete |
| --- | --- | --- | --- | --- |
| dataset1 | Original 40 exposed development | 40 | 40 | 0 |
| dataset2 | Fixed40 exposed development fallback; reserved30 untouched | 40 | 40 | 0 |
| dataset3 | Fresh80 code-frozen held-out rows; source grounding only | 80 | 80 | 0 |


The historical `wolala2026` commit **5f377de38312fb39c088551f9c74f8b6d4bd5080** is preserved by annotated local tag **cfaf-wolala2026-freeze-2026-10-29**. The new branch `experiment/cfaf-contract-driven-v1` starts at **69e3e1eaff9143ab350b5366a7e64645ea455d06**, the latest sparse-source experiment. No push, merge, deletion or rewrite occurred. The user performs later publication pushes manually. A local tag is a reproducible reference, not remote branch protection.

A is a standard selective-RAG prompt using the common self-reported mode format. B is deterministic output/policy postprocessing of that **same A generation**, not a new independent model sample. C is the existing sparse-source CFAF semantic-analysis/gate/realization pipeline, with its old unused shared-control generation removed. The four dataclass contracts are boundary scaffolding; no new eight-stage architecture, retriever, NLI model or one-call optimization was evaluated.

Primary non-operational mode agreement on Dataset1: A=80.0%, B=80.0%, C=100.0%. On exposed Dataset2: A=75.0%, B=75.0%, C=72.5%. These are gold **mode** metrics, not generated-answer factual accuracy.

Actual usage: **462 model attempts**, 1,694,395 input tokens and 88,615 output tokens, 0 HTTP/provider errors, zero retries/embeddings/external judges. Model deployment(s) observed: `['gpt-4o-mini-2024-07-18']`. The configured model is only gpt-4o-mini, temperature0, one repetition.

## Cohorts, authorization and preregistration

The exact preregistered rows, seeds, source revisions, hashes and error/statistical plan were frozen before fresh Dataset3 text was materialized. See PREREGISTRATION.md, selection_plan.json, experiment_manifest.json, runtime_manifest.json and the per-dataset selection/exposure manifests. Dataset3 seed20261029 selected 80 without replacement from ordered2366 indices excluding the ten exposed pilot indices; no balancing, gold filtering or resampling. All80 selections were charged before API execution, including any failed/unexecuted case. The cumulative Dataset3 exposure is90; **2276 records remain unused**.

Dataset1 uses all40 already-exposed P1–P5 cases, twenty matched pairs. Legacy filenames say heldout_pilot_v3/HELD3, but the earlier completed full_40 manifest proves these are exposed development data now. They are not the new independently authored40-case holdout. No such independent cohort is established in the attached/current repository inputs, none is invented, and none is opened here.

Dataset2's reservation metadata confirms30 reserved groups have no prior exposure, but its content_policy explicitly forbids reading/displaying/saving/supplying their heldout query/context/answers/reasoning. The current task explicitly instructs respecting such a rule. Therefore the preregistered fallback is40 uniformly sampled already-exposed eligible records, seed20261029, from130 exposed ledger entries sorted by original index. This is **development-only**, not the intended final reserved-group evaluation. The30 reserved and18 other untouched groups remain untouched. The contradiction exclusion and original ANSWER_CORRECTLY -> FULL / eligible REFUSE_* -> CFAF mapping are preserved. No label is changed and original ledgers are not rewritten.

Dataset3 is original AmazonScience GaRAGe, not RefusalBench-GaRAGe: source commit2b7264f5d4e066affbe4b67b7d3b9cffeff98ede, JSONL SHA256419e3941f6e8eb4082a74ca2140c1f9337f8b467ff76656a6b8b0290ca3f3a72, 2366 questions/35,351 passages. Only the80 selected new row objects were parsed for text. Original labels/reference answers stay scorer-only and ignored. No output-dependent code or prompt tuning occurred.

## Shared evidence and measured systems

All systems receive the same authorized source contents/order/provenance, question date and initial deterministic question profile/opaque legitimate view bindings. Sources are projected before any model call; DENY, metadata, aggregate and P5 restrictions apply to A as well as B/C. This is not an unsafe-private-input versus safe-input comparison. No separate synthetic unsafe-disclosure stress condition was run.

A receives no semantic assessment or CFAF response contract and has no application request-relative fulfilment selector. Its FULL/CFAF is the model's self-report under a fixed ordinary evidence-answering prompt and common six-field measurement schema. B reuses the exact A object and applies the existing canonical public contract and output-policy guard with safe operational fallback. B does not run RDA/RECV sufficiency or create a second model answer. In this run every A output passes B's postprocessing unchanged; this shows no activation of the guard, not that guarding is generally ineffective.

C reuses the existing sparse-source inventory, exact references, RDA/RECV, trusted provenance, shadow target/claim diagnostics, original TopLevelModeSelectionStage and eight named stages. Analysis and CFAF realization prompts/schemas are unchanged. A thin version-local adapter removes only the unused fourth-call shared control and its no-view placeholder. C adds semantic analysis and selector/contract realization to the shared evidence; differences from B therefore measure this **whole existing pipeline**, not the selector in isolation. Existing query-only fallbacks are charged and reported, not treated as new judges or free calls. They can change C's derived question interpretation; no source text changes.

The four executable dataclasses in CONTRACTS.md validate request signatures, permitted inventory, decision mode/status and public outputs. They do not constitute a replacement RAG framework. MAKE_OR_REUSE.md provides one reuse decision for each stage, with actual availability/licence/version evidence, cost limits and governance tests. Missing named backend modules and unverified partial-main licences are explicitly identified. No new large dependency was installed; no library replacement or one-call Structured Outputs optimization is credited as measured.

## Mode results and uncertainty

Primary mode accuracy counts only non-operational, policy-valid outputs matching original gold, with **all planned cases in the denominator**. A safe technical CFAF fallback is not a correct evidential refusal even when gold is CFAF. Observed output-mode agreement is separately recorded in comparison_summary.json; it is not the headline metric. Mode matching and marker presence do not establish factual entailment or complete generated answers.

| Dataset | System | Non-op mode accuracy | 95% cluster interval | Balanced | FULL recall | CFAF recall | Operational | FULL | CFAF |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dataset1 | A | 80.0% | [70.0%, 90.0%] | 83.3% | 100.0% | 66.7% | 0 | 24 | 16 |
| dataset1 | B | 80.0% | [70.0%, 90.0%] | 83.3% | 100.0% | 66.7% | 0 | 24 | 16 |
| dataset1 | C | 100.0% | [100.0%, 100.0%] | 100.0% | 100.0% | 100.0% | 0 | 16 | 24 |
| dataset2 | A | 75.0% | [62.8%, 86.5%] | 75.8% | 78.6% | 73.1% | 0 | 18 | 22 |
| dataset2 | B | 75.0% | [62.8%, 86.5%] | 75.8% | 78.6% | 73.1% | 0 | 18 | 22 |
| dataset2 | C | 72.5% | [60.5%, 84.6%] | 69.0% | 57.1% | 80.8% | 0 | 13 | 27 |
| dataset3 | A | N/A | N/A | N/A | N/A | N/A | 0 | 71 | 9 |
| dataset3 | B | N/A | N/A | N/A | N/A | N/A | 0 | 71 | 9 |
| dataset3 | C | N/A | N/A | N/A | N/A | N/A | 9 | 53 | 27 |


N/A on Dataset3 is intentional: original source labels do not independently determine complete request fulfilment. FULL/CFAF distributions there are observed behaviors only.

| Dataset | Paired contrast | Left-only correct | Right-only correct | Count delta | Fraction delta | 95% group interval |
| --- | --- | --- | --- | --- | --- | --- |
| dataset1 | B_vs_A | 0 | 0 | 0 | 0.0% | [0.0%, 0.0%] |
| dataset1 | C_vs_A | 8 | 0 | 8 | 20.0% | [10.0%, 30.0%] |
| dataset1 | C_vs_B | 8 | 0 | 8 | 20.0% | [10.0%, 30.0%] |
| dataset2 | B_vs_A | 0 | 0 | 0 | 0.0% | [0.0%, 0.0%] |
| dataset2 | C_vs_A | 2 | 3 | -1 | -2.5% | [-13.2%, 7.9%] |
| dataset2 | C_vs_B | 2 | 3 | -1 | -2.5% | [-13.2%, 7.9%] |


dataset1: C has 8 non-operational mode matches that B misses, B has 0 that C misses; net 8/40 (20.0%), cluster interval [10.0%, 30.0%]. dataset2: C has 2 non-operational mode matches that B misses, B has 3 that C misses; net -1/40 (-2.5%), cluster interval [-13.2%, 7.9%].

Intervals use the preregistered seed20261029 and2000 joint cluster-bootstrap replicates: Dataset1 resamples matched pairs; Dataset2 resamples original source groups. B and A share generation, and all systems share cases. Intervals describe these selected dependent cohorts; no population guarantee or statistical-significance claim is made. A degenerate perfect-sample bootstrap interval does not imply population certainty. Exact discordant counts, including failures, are in paired_mode_confusions.json. Any mode advantage over B remains development evidence, not proof of general factual-answer improvement.

Dataset1 matched-pair joint mode accuracy: A=60.0%, B=60.0%, C=100.0%. Exact reason-class, fulfilment-status and gold-marker-presence diagnostics are in comparison_summary.json. They use original annotations and retain failure denominators; they do not certify full natural-language reason/answer correctness. P5 pair-equivalent responses and zero model calls are audited separately; all three share the no-view rule.

## Exact output/reason diagnostics

| D1 system | Mode accuracy | Reason-class agreement | Fulfilment-status agreement | Gold-marker presence (FULL gold) | Policy violations |
| --- | --- | --- | --- | --- | --- |
| A | 80.0% | 60.0% | 60.0% | 50.0% | 0 |
| B | 80.0% | 60.0% | 60.0% | 50.0% | 0 |
| C | 100.0% | 72.5% | 80.0% | 31.2% | 0 |


Thus C's100% development mode result is not100% reason/fulfilment agreement: exact reason-class agreement is72.5% and fulfilment-status agreement80%. These unchanged native labels were not rewritten. Some public-reason differences, especially under P5 indistinguishability, require semantic/privacy interpretation; exact agreement alone is not an adjudicated explanation-quality score.

On Dataset2, C reduces observed false FULL from7 to5 but increases unnecessary non-operational refusals from3 to6. FULL recall falls from78.6% (B) to57.1% (C), while CFAF recall rises from73.1% to80.8%. Balanced accuracy is75.8% for B and69.0% for C. There is no consistent measured superiority across the two development cohorts.

## Operational failure versus evidential refusal

The per-system status and gate outcome distributions are preserved in operational_failures.json and the finer observational categories in operational_failure_breakdown.json. These distinguish HTTP/execution/malformed-output failures, invalid semantic source/reference contracts, generated FULL, and validated request-relative CFAF. In particular, structurally valid source selection and the internal VERIFIED_FULFILMENT label mean the existing gate accepted model properties, not independent entailment verification.

| Dataset | C gate outcomes | C technical error codes | Query-profile fallbacks |
| --- | --- | --- | --- |
| dataset1 | {'VALIDATED_CFAF': 16, 'VALIDATED_RESTRICTED_NO_VIEW': 8, 'VERIFIED_FULFILMENT': 16} | {} | 0 |
| dataset2 | {'VALIDATED_CFAF': 27, 'VERIFIED_FULFILMENT': 13} | {} | 5 |
| dataset3 | {'OPERATIONAL_FAILURE': 9, 'VALIDATED_CFAF': 18, 'VERIFIED_FULFILMENT': 53} | {'SUPPORT_SOURCE_NOT_ASSESSED': 4, 'UNKNOWN_SPAN_ID': 5} | 1 |


Operational failures use neutral public verification wording and cannot be credited as successful evidential CFAF. P5 retains its unchanged indistinguishable canonical response. Raw versus guarded outputs remain in ignored local logs; safe summaries contain status/code/count information rather than unredacted answers.

## Dataset3 grounding, scope and citations

| D3 layer | N | Relevance P | Relevance R | F1 |
| --- | --- | --- | --- | --- |
| A_actual_citations | 80 | N/A | 0.0% | 0.0% |
| B_actual_citations | 80 | N/A | 0.0% | 0.0% |
| C_actual_citations | 80 | N/A | 0.0% | 0.0% |
| raw_C | 80 | 87.9% | 24.4% | 38.3% |
| validated_C | 80 | 86.8% | 21.2% | 34.1% |
| C valid-assessment subset | 71 | 86.8% | 24.1% | 37.7% |
| C unchanged-context subset | 78 | 86.7% | 21.4% | 34.3% |


Raw C proposals are resolvable model-proposed sources, including invalid assessments. Validated C support requires a valid assessment and explicit usable PRIMARY/SUPPORTS roles with exact authorized references. A/B have no semantic-source-selection stage; only actual citations can establish their measured source selection. Their absent citation precision is undefined, not an inferred empty private retrieval plan. Original YES/NO relevance is not full-answer sufficiency, and answering-labelled sources do not prove multipart completeness. RELATED-INFORMATION, UNKNOWN, OUTDATED and blank labels remain distinct.

Original sampled label counts: `{'correctness': {'': 386, 'ANSWER-THE-QUESTION': 320, 'OUTDATED': 73, 'RELATED-INFORMATION': 312, 'UNKNOWN': 101}, 'relevance': {'NO': 386, 'YES': 806}}`. C has 71/80 structurally valid assessments. There are 2 altered-context cases under the preregistered whole-passage-prefix input policy; all systems receive the same retained views. Their results are separate from the unchanged-context subset. No selected case is replaced. Missing relevant-source recall is not proof that an answer must cite every relevant passage.

| System | Actual public citation sources | Invalid citations | Unverified reference associations | Verified sidecar citations | Citationless FULL |
| --- | --- | --- | --- | --- | --- |
| A | 0 | 0 | 0 | 0 | 71 |
| B | 0 | 0 | 0 | 0 | 71 |
| C | 0 | 0 | 206 | 0 | 53 |


The C trace component retains exact requirement/candidate-to-reference provenance only when mechanically validated; uncertain associations remain CITATION_SUPPORT_UNVERIFIED and are not rendered as verified citations. A reference ID or source hash is not semantic proof. Zero invalid emitted citations is not success if no citations were emitted. Actual citation counts and citationless FULLs are reported rather than manufactured.

No native Dataset3 FULL/CFAF accuracy or human entailment accuracy is calculated. Independent adjudication is PENDING. DATASET3_ADJUDICATION_RUBRIC.md and its blank template are provided; the ignored blinded packet contains authorized context and randomized response aliases, with the system key stored separately. It excludes original human answers/source labels and internal gate diagnostics. Blinding hides system names, not stylistic clues. Any mechanical observations here are not independent answer judgements.

## Case errors and limitations

| Dataset | Sample ID | Execution | Gold mode where available | Observed A/B/C (OP=operational) | C technical error codes |
| --- | --- | --- | --- | --- | --- |
| dataset1 | HELD3_P1_01B | COMPLETED | CFAF | A:FULL / B:FULL / C:CFAF | [] |
| dataset1 | HELD3_P1_02B | COMPLETED | CFAF | A:FULL / B:FULL / C:CFAF | [] |
| dataset1 | HELD3_P1_03B | COMPLETED | CFAF | A:FULL / B:FULL / C:CFAF | [] |
| dataset1 | HELD3_P1_04B | COMPLETED | CFAF | A:FULL / B:FULL / C:CFAF | [] |
| dataset1 | HELD3_P4_01B | COMPLETED | CFAF | A:FULL / B:FULL / C:CFAF | [] |
| dataset1 | HELD3_P4_02B | COMPLETED | CFAF | A:FULL / B:FULL / C:CFAF | [] |
| dataset1 | HELD3_P4_03B | COMPLETED | CFAF | A:FULL / B:FULL / C:CFAF | [] |
| dataset1 | HELD3_P4_04B | COMPLETED | CFAF | A:FULL / B:FULL / C:CFAF | [] |
| dataset2 | RB-NQ_claude_-3655952387338820756_P-FalsePremise_LOW_acb69f06_0635 | COMPLETED | FULL | A:FULL / B:FULL / C:CFAF | [] |
| dataset2 | RB-NQ_gpt_8350528572960416643_P-GranularityMismatch_LOW_cd5fc8b9_3150 | COMPLETED | FULL | A:FULL / B:FULL / C:CFAF | [] |
| dataset2 | RB-NQ_gpt_-6924600758326460563_P-GranularityMismatch_MEDIUM_bfee04e4_2678 | COMPLETED | CFAF | A:FULL / B:FULL / C:FULL | [] |
| dataset2 | RB-NQ_nova_8282063117132135457_P-Ambiguity_MEDIUM_fd923d61_3795 | COMPLETED | CFAF | A:FULL / B:FULL / C:FULL | [] |
| dataset2 | RB-NQ_claude_-918571312056093750_P-GranularityMismatch_LOW_a04d0028_1309 | COMPLETED | FULL | A:CFAF / B:CFAF / C:CFAF | [] |
| dataset2 | RB-NQ_gpt_-5083423407995797659_P-Ambiguity_LOW_17520953_3023 | COMPLETED | FULL | A:FULL / B:FULL / C:CFAF | [] |
| dataset2 | RB-NQ_claude_-4199405438415986663_P-Ambiguity_MEDIUM_8f35a931_1328 | COMPLETED | CFAF | A:FULL / B:FULL / C:FULL | [] |
| dataset2 | RB-NQ_claude_-4481086743458136206_P-Ambiguity_HIGH_67c49d98_0520 | COMPLETED | CFAF | A:FULL / B:FULL / C:CFAF | [] |
| dataset2 | RB-NQ_claude_4433669964771756966_P-FalsePremise_LOW_ac551133_1029 | COMPLETED | FULL | A:CFAF / B:CFAF / C:CFAF | [] |
| dataset2 | RB-NQ_deepseek_6144099837933283715_P-GranularityMismatch_LOW_1b0bebf4_1391 | COMPLETED | FULL | A:CFAF / B:CFAF / C:CFAF | [] |
| dataset2 | RB-NQ_nova_7402184777947527945_P-Ambiguity_HIGH_0bbb96e1_3731 | COMPLETED | CFAF | A:FULL / B:FULL / C:FULL | [] |
| dataset2 | RB-NQ_gpt_-353209775069332597_P-Ambiguity_MEDIUM_05ad5cc9_2997 | COMPLETED | CFAF | A:FULL / B:FULL / C:FULL | [] |
| dataset2 | RB-NQ_nova_-5519267321423308172_P-FalsePremise_HIGH_6ebd546f_4141 | COMPLETED | CFAF | A:FULL / B:FULL / C:CFAF | [] |
| dataset3 | d539166e-95ec-422d-9333-851920988c13 | COMPLETED | No native mode gold | A:FULL / B:FULL / C:CFAF/OP | ['UNKNOWN_SPAN_ID'] |
| dataset3 | c6763443-8f35-47c3-a549-cf767700944d | COMPLETED | No native mode gold | A:FULL / B:FULL / C:CFAF/OP | ['SUPPORT_SOURCE_NOT_ASSESSED'] |
| dataset3 | d9398853-5cef-4532-805d-e20183d1902b | COMPLETED | No native mode gold | A:FULL / B:FULL / C:CFAF/OP | ['SUPPORT_SOURCE_NOT_ASSESSED'] |
| dataset3 | f9920a4b-e5c0-495f-9bde-c996cacb8f6a | COMPLETED | No native mode gold | A:FULL / B:FULL / C:CFAF/OP | ['UNKNOWN_SPAN_ID'] |
| dataset3 | bff37040-d3ce-4bf4-8345-95617ec6a673 | COMPLETED | No native mode gold | A:FULL / B:FULL / C:CFAF/OP | ['UNKNOWN_SPAN_ID'] |
| dataset3 | 33848c9d-0cd4-4047-a186-21e58829ca1a | COMPLETED | No native mode gold | A:FULL / B:FULL / C:CFAF/OP | ['UNKNOWN_SPAN_ID'] |
| dataset3 | 0a775067-fbbb-4b5b-9f0e-f54c9228dfd4 | COMPLETED | No native mode gold | A:FULL / B:FULL / C:CFAF/OP | ['SUPPORT_SOURCE_NOT_ASSESSED'] |
| dataset3 | 82c66762-5121-4d41-8696-b34c8aeddf25 | COMPLETED | No native mode gold | A:FULL / B:FULL / C:CFAF/OP | ['UNKNOWN_SPAN_ID'] |
| dataset3 | 3052360c-571b-4522-85de-a2d1a6c81bcd | COMPLETED | No native mode gold | A:FULL / B:FULL / C:CFAF/OP | ['SUPPORT_SOURCE_NOT_ASSESSED'] |


This error list is not a new gold annotation set. The complete original questions, served/raw model responses, request/gate diagnostics and references remain in ignored local files. Source-role/reference validation failures, incorrect mode matches and semantic truth are separate. A/B/C may agree while all miss a requested relation or essential condition. No new parser, NLI model or general LLM judge was introduced to declare such claims correct.

The original 40 synthetic 100% research result and later roughly80–85% mixed development-mode reports belong to different phases. They are not pooled or reinterpreted as final factual-answer correctness. Current D1/D2 observations are also exposed development. Dataset3 is a fresh sample relative to this development history, but a public benchmark may be familiar to the model; it supplies source annotations, not independent contract-specific answerability or entailment gold. A degenerate perfect-sample bootstrap interval does not imply population certainty. Small dependent cohorts, legacy short C candidate limits, as-of metadata, possible partial contexts, operational failures and unadjudicated public citations bound interpretation.

## Cost and reproducibility

| Dataset | Calls | Input tokens | Output tokens | Kinds | Local overhead s | B postprocess ms |
| --- | --- | --- | --- | --- | --- | --- |
| dataset1 | 96 | 112672 | 12811 | {'semantic_analysis': 32, 'semantic_cfaf': 32, 'standard_rag': 32} | 0.822 | 30.973 |
| dataset2 | 125 | 156620 | 17348 | {'query_profile': 5, 'semantic_analysis': 40, 'semantic_cfaf': 40, 'standard_rag': 40} | 0.872 | 29.985 |
| dataset3 | 241 | 1425103 | 58456 | {'query_profile': 1, 'semantic_analysis': 80, 'semantic_cfaf': 80, 'standard_rag': 80} | 36.946 | 599.868 |


Total model attempts 462/480; input tokens 1,694,395, output tokens 88,615; successes 462, API errors 0, unsettled attempts 0. Mean HTTP/provider latency 2694.8 ms, maximum 16914.6 ms, summed HTTP/provider time 1245.012 seconds. B adds zero model calls; its measured postprocessing time is separate. Query-only fallback is included in C costs. No retries, embeddings or external judges; no monetary estimate without verified pricing.

Shared A/B output is charged once. Local overhead in the table is measured outside the provider wrapper; latency_analysis.json also separates end-to-end case wall time from inner HTTP timing so durable accounting/serialization overhead is visible. No production CPU/memory throughput or unexecuted one-call savings is claimed.

All 1090 earlier tracked files and prior branches/annotations are preserved. The frozen source hashes, preregistration, selected runtime/gold hashes, API payload audits, source hashes and exact exposure ledgers support reproduction. New raw text/gold/traces are ignored and are not added to public Git. The final commit receipt and checksums cover safe artifacts. Final compatibility tests: 691 passed, with 3 historical hash-only tests deselected and separately passing on the original working files. The new 9 synthetic checks are included in 691, not extra unique tests. The original suite has 77 passed plus 13 passing subtests and one known pre-existing failure, test_preheldout_attempt1_plan_artifacts_are_plan_only, caused by the previously committed authorization metadata file. It is preserved; no failure is hidden by changing old sources.

Study start UTC 2026-10-29T07:55:48+00:00; current elapsed at report generation 3328.8 seconds. Persistent monotonic and wall clocks enforce120 minutes total, no new requests after105. No timer reset or promised later run. The completion receipt records final elapsed time and commit.

## Twelve required conclusions

1. Frozen historical commit: 5f377de38312fb39c088551f9c74f8b6d4bd5080, annotated local tag cfaf-wolala2026-freeze-2026-10-29; exact tree/tag hashes are in WOLALA2026_FREEZE.md.
2. New branch: experiment/cfaf-contract-driven-v1, starting at sparse-source commit 69e3e1eaff9143ab350b5366a7e64645ea455d06.
3. Each of eight stage reuse choices and the retained CFAF contract is listed in MAKE_OR_REUSE.md; the original selector/stages are retained.
4. The compact four-contract skeleton ran as boundary validation scaffolding. The measured empirical pipeline is existing sparse CFAF, not a new framework or validated library replacement. One-call optimization is future-only.
5. Planned/completed/incomplete: dataset1: 40/40/0, dataset2: 40/40/0, dataset3: 80/80/0. Reserved Dataset2 final groups were not consumed; the authorized development fallback was preregistered.
6. Fully paired mode outcomes, discordant counts and grouped intervals are separate by dataset above; Dataset3 has no binary accuracy. No significance claim.
7. Benefit over guarded B: dataset1: C has 8 non-operational mode matches that B misses, B has 0 that C misses; net 8/40 (20.0%), cluster interval [10.0%, 30.0%]. dataset2: C has 2 non-operational mode matches that B misses, B has 3 that C misses; net -1/40 (-2.5%), cluster interval [-13.2%, 7.9%]. This concerns exposed-cohort mode agreement under the whole C pipeline, not independent factual superiority or an isolated selector effect.
8. Operational fallback credit is excluded from the primary mode numerator. Status counts and observed-mode agreement show any apparent agreement caused by technical withholding separately.
9. Dataset3 labels support source-level relevance/correctness-category/citation diagnostics. Complete fulfilment, per-claim entailment and refusal appropriateness await independent adjudication.
10. Actual usage: 462 attempts, 1,694,395/88,615 input/output tokens; exact elapsed/cost splits are in the usage/timeline artifacts and final receipt. No invented dollar cost.
11. Evidence-ready manuscript material: observed development-mode comparisons with cluster intervals, fresh 80 source-label/technical metrics, exposure/provenance and limitations. Independent final Dataset2, factual-answer accuracy and new-architecture/one-call gains are not evidence-ready.
12. Best next action: use the already-existing response contract for deterministic rendering in a separately named one-call-C ablation, retaining the same semantic analysis and selector. Measure calls/latency and equivalence on fixed evidence, with an independent fulfilment/claim rubric. This is a future design, not a measured saving. Avoid increasing bespoke semantic code; do not tune on the just-exposed80 or consume the remaining 2276 casually.

## Manual publication commands

No push was executed. From the repository, the user may run:

```powershell
git push origin refs/tags/cfaf-wolala2026-freeze-2026-10-29
git push -u origin experiment/cfaf-contract-driven-v1
```

Configure remote branch/tag protection separately as described in WOLALA2026_FREEZE.md; this study does not assert protection is active.

## Manuscript source verification

RESULTS_FOR_PAPER.tex successfully compiled with the built-in LaTeX compiler in an article wrapper. No original CF2AF_v5.8 manuscript was overwritten. Paper integration notes distinguish observed results from future one-call design.
