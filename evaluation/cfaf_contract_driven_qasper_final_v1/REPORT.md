# QASPER TEST replacement of Dataset3: final comparative report

The frozen CFAF system C scores **54/80 (67.50%)**, versus **63/80 (78.75%)** for ordinary RAG A and its deterministic guard B, on the preregistered balanced QASPER TEST subset. C minus B is **−11.25 percentage points**, with a paired paper-cluster bootstrap 95% interval of **−21.25 to −1.25 points**. C has eight operational failures, which receive no correctness credit. This is a negative result for the frozen architecture on this selected cohort. It is not an independent factual-answer accuracy estimate.

Only Dataset3 was executed anew. Dataset1 and Dataset2 results are imported byte-for-byte from the frozen previous study. The earlier 160-case study, including GaRAGe, is unchanged and is identified here as **Archived Dataset3-v1 – GaRAGe Grounding Study**. Its grounding percentages are not QASPER results and are not pooled with them.

## Scope and frozen implementation

The isolated local branch is `experiment/cfaf-final-qasper-replacement-v1`, based on `bfd80bbfe2ccbb251da46bdc22b791dad5b9341f` from `experiment/cfaf-contract-driven-v1`. It uses the historical A/B/C algorithms, including the original sparse source assessment, governed projection, requirement/sufficiency analysis, mode selector, realization and operational validation. Public C functions are the same Python function objects as the frozen implementation. All 66 historical frozen source hashes and 72 historical artifact checksums were verified; 78 source files, including the new harness, were frozen before sampling/API execution.

The original QASPER pilot adapter is reused byte-for-byte. The later one-call implementation is not imported or evaluated, and `ComponentBasaedCFAF` is not checked out, used or modified. No new semantic rule, prompt, threshold, span-alias repair, response renderer or output budget was introduced after opening the sample. The inference code and selected sample remain unchanged after results.

A makes one standard selective-RAG generation. B guards that exact A generation deterministically and uses zero additional model calls. C makes the original semantic analysis and response-realization calls, plus a query-only profile when the frozen code requires it. All requests use `gpt-4o-mini`, temperature 0, one repetition; observed deployment is `gpt-4o-mini-2024-07-18`. Frozen limits are 1500 analysis, 512 generation and 500 profile output tokens. There are no retries, embeddings, stronger model, external LLM judge or second semantic verifier.

The prompts, schemas, algorithm and generation budgets match the historical comparison. QASPER's paper representation, paragraph granularity and pilot context allowance differ from historical GaRAGe inputs. This is therefore a revised comparative presentation of preserved development cohorts and a new test cohort, not a perfectly input-controlled rerun or three newly independent cohorts.

## 1. Automatically derived test labels

The official original v0.3 TEST archive has 416 papers and 1451 questions. The preregistered deterministic mapping yields:

| Derived label | Questions |
|---|---:|
| FULL | 854 |
| CFAF | 79 |
| UNKNOWN | 518 |
| Total | 1451 |

FULL requires valid, unanimously answerable original annotations with a usable answer, no explicit Yes/No conflict, and original textual evidence representable for every annotation. Boolean `false` in `yes_no` is a valid No answer. CFAF requires valid, unanimously unanswerable annotations with no simultaneous substantive answer and a complete distributed paper record. Missing/malformed annotations, mixed answerability, conflicting Boolean answers and unsupported source representation are UNKNOWN.

The strict textual eligibility rule excludes an answerable question if any annotation uses FLOAT SELECTED figure/table evidence, has empty evidence, or has evidence not found in the original text/abstract. Captions do not establish availability of image/table contents. A complete distributed JSON record does not guarantee a complete original PDF representation. No model generated these labels or repaired them.

Overlapping exclusion-reason counts are: unavailable nontextual evidence 212; mixed unanswerable flags 164; original text evidence unrepresented 76; contradictory Boolean answers 43; missing original text evidence 30; source-integrity invalid 4. They are not disjoint and must not be summed. The source has 253 questions with nontextual evidence markers across all label categories. One invalid paper record affects four questions.

## 2. Annotation consensus tiers

| Tier | FULL | CFAF | Eligible total |
|---|---:|---:|---:|
| M: at least two agreeing annotations | 834 | 76 | 910 |
| S: one valid annotation | 20 | 3 | 23 |

Tier M consensus is about the mapped mode under the fixed rule. It does not establish agreement on every answer detail, independent adjudication or infallible gold. Free-form and extractive answers can differ substantively without an explicit Boolean conflict.

## 3. Feasibility without relaxing eligibility

Yes. Tier M alone offers 357 distinct FULL papers and 59 distinct CFAF papers. Forty per class with global paper disjointness is feasible. No Tier S fallback, eligibility relaxation or sample-size reduction was used.

## 4. Actual selected, exposed and completed sample

All **80 selected cases completed**, with 40 FULL, 40 CFAF, all Tier M and 80 distinct papers. Seed is 20261029. Preregistered paper-first allocation chooses the scarcer class while reserving enough papers for the other class, then chooses one eligible question within each paper. This favors paper diversity and is not uniform sampling over questions. Cases 1–40 are FULL and 41–80 CFAF in the fixed execution order.

All twenty previously exposed validation-pilot paper IDs and twenty question IDs were excluded; selected overlap is zero. All eighty selections are charged as exposed, regardless of later failure. No outputs caused replacement, exclusion, remapping or resampling. The original test source was not used by the earlier validation pilots.

The same authorized question and paper content, in the same order, reach A/B/C. Runtime fields are title, abstract, sections/paragraphs and available textual captions. Original annotations, reference answers, human evidence, derived labels and original benchmark identifiers remain scorer-only. No InfoBank privacy restrictions were invented for public papers.

## 5. Confusion matrices and primary metrics

Rows are derived gold labels; columns are validated non-operational predictions and operational failure. Missing and policy-invalid columns are zero for all systems. An operational fallback remains a failure even if its served mode happens to be CFAF.

| System | Gold | FULL | CFAF | Operational |
|---|---|---:|---:|---:|
| A | FULL (40) | 38 | 2 | 0 |
| A | CFAF (40) | 15 | 25 | 0 |
| B | FULL (40) | 38 | 2 | 0 |
| B | CFAF (40) | 15 | 25 | 0 |
| C | FULL (40) | 32 | 5 | 3 |
| C | CFAF (40) | 13 | 22 | 5 |

| Metric | A | B | C |
|---|---:|---:|---:|
| Correct / planned | 63/80 | 63/80 | 54/80 |
| Accuracy | 78.75% | 78.75% | 67.50% |
| Balanced accuracy | 78.75% | 78.75% | 67.50% |
| FULL precision | 71.70% | 71.70% | 71.11% |
| FULL recall | 95.00% | 95.00% | 80.00% |
| CFAF precision | 92.59% | 92.59% | 81.48% |
| CFAF recall | 62.50% | 62.50% | 55.00% |
| Unnecessary non-operational refusals | 2 | 2 | 5 |
| Non-operational failures to restrict | 15 | 15 | 13 |
| Operational failures | 0 | 0 | 8 |

Precision conditions on valid non-operational predictions; recall and accuracy use all planned class members, so operational failures reduce recall. A/B accuracy intervals are 70.00–87.50%; C's is 57.50–77.50%, using 2000 paper-cluster percentile bootstrap replicates with seed 20261029. All eighty papers are distinct clusters. These conditional sampling intervals do not quantify annotation bias, benchmark familiarity or architecture-general performance.

C serves FULL 45 and CFAF 35 times, but five CFAF fallbacks are operationally invalid. Its served-mode agreement of 59/80 (73.75%) is a diagnostic only and is not the primary score. A/B serve FULL 53 and CFAF 27 times.

## 6. Paired result against equally guarded RAG

C is worse on the prespecified primary metric: −9 correct cases, or −11.25 percentage points, relative to B. Both are correct on 49 cases, C alone on 5, B alone on 14, and neither on 12. The paired bootstrap interval is −21.25 to −1.25 points. A and B are identical on all eighty outputs and correctness outcomes.

C-only wins are cases 47, 49, 54, 71 and 76. They illustrate useful restrictions against an unsupported agreement statistic, possible multilingual capability being treated as actual evaluation, a corpus description being treated as publisher identity, multiplying tasks by examples-per-label without label counts, and generalizing the authors' resource choices to all top systems. These examples do not offset the aggregate deficit or establish a broader advantage.

## 7. Incorrect predictions versus annotation support

All observed strict-score errors have Tier M mode support: A/B have 17 each; C has 26, comprising 18 non-operational mode mismatches and 8 operational failures. No Tier S case was selected. Tier S accuracy and error rates are **not estimated**, rather than zero. Stronger annotation consensus makes mode mapping more defensible; it does not prove each apparent semantic error is a hallucination or each reference answer is correct.

## 8. Retrieval evidence loss

The unchanged pilot uses the whole paper when its serialized analysis envelope fits 110000 ASCII bytes; otherwise it performs deterministic, gold-blind SQLite FTS5/BM25 paragraph selection and restores original document order. Actual API envelopes are capped at 120000. These are implementation envelope bounds, not claims about exact tokenizer context capacity.

Seventy-six cases receive full distributed text; four receive retrieved subsets:

| One-based case | Original paragraph/caption units | Included units | Human evidence loss |
|---|---:|---:|---|
| 7 | 57 | 47 | None |
| 19 | 96 | 49 | None |
| 23 | 140 | 38 | 3 of 6 human union items retained |
| 60 | 137 | 60 | Not applicable to CFAF gold |

One of forty FULL cases loses some annotated evidence; **zero FULL cases lose every complete annotation evidence set**. Case 23 still retains at least one entire annotator's evidence set. Macro human-evidence retrieval recall is 98.75% over FULL questions. Human union evidence can contain alternative supporting passages, so losing an annotated union item does not prove indispensable evidence was lost. Conversely, retaining one set does not independently prove the generated answer is complete. Its FULL label is preserved. Its separate C span-reference operational failure is not automatically attributed to retrieval.

## 9. Substantive support, completeness and citations

All eighty cases have an explicitly **non-independent, unblinded Codex-agent review**, comparing questions, A/C outputs, original references and displayed selected source windows, with targeted original-paragraph checks. This is diagnostic review, not an external judge or exhaustive independent claim adjudication. Complete outputs, source evidence, human answers and traces are kept in ignored `local/CASE_REPORT.md` and `local/review_packet.jsonl`. Public `QUALITATIVE_REVIEW.json` retains all eighty paraphrased findings without redistributing full papers or reference answers.

On the forty FULL cases, C's validated internal-window-to-original-paragraph overlap macro precision/recall/F1 is **45.32% / 52.21% / 41.24%**. The scorer maps exact validated span offsets back to original paragraph/caption/abstract units and compares them with original human evidence union. This is a passage-overlap diagnostic, not official QASPER answer F1, semantic entailment, factual correctness or completeness. A/B do not expose selected passage IDs in the shared schema, so their passage precision is uninstrumented and is not assigned zero.

Seventy-seven C semantic assessments have valid references; three do not. Reference existence is weaker than support for a claim: a valid window may contain background, an adjacent result, only part of a needed relation, or the wrong subject. There is no verified public claim-citation renderer; internal IDs are not user-facing verified citations. Five subsequent C realizations fail the generation contract, leaving seventy-two non-operational C outcomes.

Concrete review findings illustrate why mode and content must be separated:

- Cases 7, 8, 39 and 40 use FULL while omitting requested model variants or concrete categories. For case 40, the source explicitly identifies particular regression models; broad model-family descriptions are incomplete.
- Case 6 confuses an overall corpus size with the rescored subset. Case 22 has a different numerical unit/scope in the human answers versus the model/source discussion; it remains a sensitivity flag.
- In case 24, both outputs infer a No answer from auxiliary supervision despite unanimous original Yes references and wording about absence of manual supervision. C selects CFAF but emits a factual No instead of the contracted limitation. The historical validator accepts this content deviation; it is recorded separately and does not change the frozen metric.
- Case 34 treats perplexity as a used personalization metric despite text rejecting it and adopting cross entropy. In case 37, C transfers a significance value from a perception experiment to the requested language-model result. A valid reference does not resolve this relation mismatch.
- Cases 41 and 43 substitute neighboring procedures or framework descriptions for the exact extraction/tagging information requested. Cases 60 and 62 replace definitions with a described application, giving C false FULL decisions where B restricts correctly.
- Case 55 offers a relative speed/quantity factor instead of the requested absolute count. Case 71 shows why tasks multiplied by examples per label does not yield an instance count without the number of labels.
- Case 63 infers publication language from the subject's nationality; case 73 infers language from familiar benchmark names. Such background familiarity is not explicit document evidence.
- Case 68 shows unsupported acronym expansion in A; C repeats contextual wording without supplying the requested expansion. A/B's better mode score does not imply factually superior answers in every case.
- Generic EPISTEMIC/CLARIFY realization appears in 22 valid C outputs. Several conflate missing evidence with an ambiguous query, although case 69 can plausibly require clarification about units. Correct CFAF mode alone does not establish a correct reason or useful next step.

`LABEL_SENSITIVITY_FLAGS.json` preserves cases 4, 13, 15, 22, 35, 39 and 77 for content/scope adjudication. For example, original references can disagree about metric scope or enumeration, unanimous Boolean references can conflict with a model's interpretation, and a general bias discussion may not satisfy a detailed mechanism question. These flags are not a corrected gold set. No case is deleted or relabelled and no alternate headline accuracy is reported. There is no independently adjudicated substantive-answer accuracy estimate.

## 10. Operational failures

There are **eight C operational failures**, zero A/B failures, zero provider errors and zero missing results. All HTTP calls complete successfully. The frozen system distinguishes transport success from semantic/schema operational validity.

| One-based case | Gold | Failure |
|---|---|---|
| 23 | FULL | Unknown/noncanonical span IDs (`span-003`, `span-004`) |
| 35 | FULL | Required CFAF realization absent/null |
| 36 | FULL | Unknown/noncanonical span IDs (`span-002`, `span-010`) |
| 44 | CFAF | Required CFAF realization absent/null |
| 45 | CFAF | Required CFAF realization absent/null |
| 59 | CFAF | Required CFAF realization absent/null |
| 74 | CFAF | Unknown/noncanonical span IDs (`span-003`, `span-004`, `span-005`) |
| 78 | CFAF | Required CFAF realization absent/null |

The three reference failures use identifiers that fail the original canonical four-digit span reference contract. The five generation errors are `CFAF_REASON_AND_REALIZATION_REQUIRED`. These are preserved as measured, without enabling later repairs, retries or generation changes. Their safe fallbacks are never credited as correct refusals. The case-24 accepted copy-contract deviation described above is an additional qualitative limitation, not a ninth operational error under the frozen validator.

## 11. Calls, tokens, latency and processing

The replacement alone uses **241 successful attempts**, within the 260-attempt hard ceiling: 80 A, 80 C analysis, 80 C realization and one query-only profile. B uses no additional calls. There are no retries or provider failures; every recorded completion finish reason is stop.

| Request kind | Attempts | Input tokens | Output tokens | Summed provider seconds |
|---|---:|---:|---:|---:|
| Standard RAG | 80 | 420121 | 6638 | 176.815 |
| Semantic analysis | 80 | 1425221 | 27996 | 438.311 |
| C realization | 80 | 456471 | 4180 | 170.829 |
| Query profile | 1 | 393 | 59 | 1.356 |
| New QASPER total | 241 | **2302206** | **38873** | **787.311** |

Mean provider latency is 3266.849 ms; maximum is 11723.295 ms. Summed paired-case elapsed time is 829.602 seconds. Total measured non-transport processing is 42.291 seconds: 13.456 outside the provider-call timer plus 28.835 wrapper/preflight overhead. These measures distinguish transport from local serialization/validation work; they do not equal complete task wall time or independent A-versus-C deployment latency. The completion receipt records full task elapsed time against the two-hour bound. All model calls finished well before the 105-minute new-call cutoff. No monetary price estimate is inferred.

Dataset1/2 have zero new calls. Their retained historical subtotal is 221 calls, 269292 input and 30159 output tokens. The revised presentation totals 462 calls, 2571498 input and 69032 output tokens across separate execution dates. The number 462 happens to equal the old study's call count; it does not mean the original 160 cases were rerun or that GaRAGe usage was included in the new Dataset3 result.

## 12. What the replacement strengthens

It strengthens reproducible binary answerability measurement: original source annotations, fixed mapping, eligibility counts, multi-annotation tiers, exposure accounting, per-case results and paired uncertainty are now auditable. It does **not** strengthen a claim that frozen CFAF outperforms guarded RAG: this selected test cohort shows the opposite on primary mode agreement. It also does not turn historical exposed-development cohorts into independent tests or establish independently verified entailment or answer correctness. Negative findings are retained rather than used to tune the measured system.

## 13. Remaining scientific limits

The labels are derived, fallible annotations. Tier M agreement can conceal shared annotation error or divergent answer detail; Tier S is unevaluated. Strict textual filtering excludes 518 UNKNOWN questions, and balancing changes natural prevalence. Paper-first selection differs from uniform question sampling. The result is conditional on this text-representable, paper-diverse, higher-consensus subset.

Four inputs are retrieved subsets, with human evidence union loss in one FULL case. Even a full distributed record can omit figure/table contents and extraction details. Retrieval evidence retention is not proof of sufficient support for every claim. Public QASPER familiarity of the pretrained model cannot be excluded or measured, despite zero local overlap with the two validation pilots. There is no independent answer-support or label adjudication. The agent review is unblinded and non-independent. C differs from B in additional calls, prompts and fulfilment logic, so this does not isolate the selector's causal contribution. Historical Dataset1/2 remain exposed development and have different source structures/context allowances. None of these uncertainties is absorbed by the bootstrap interval.

## 14. Exact supported manuscript changes

`RESULTS_FOR_PAPER_QASPER.tex` replaces original **CF2AF_v5.9.tex lines 478–609**, ending before Discussion at line 610. It includes revised registry/methods, the unchanged Dataset1/2 results block, measured QASPER results, costs and limitations. The Dataset1/2 subsection is copied verbatim after newline normalization and hashed in `PAPER_SOURCE_AUDIT.json`.

`PAPER_REPLACEMENT_NOTES.md` identifies exact additional updates at abstract line 85, Discussion line 627, efficiency line 645 and conclusion line 655, plus obsolete GaRAGe references and the QASPER bibliography entry. Anchors apply only to the verified source SHA-256 `8f4c1387d41d43e62c3d3e81cd1507036ab4edfd60d19bc563910ed28025dee3`. The replacement supports the observed negative mode comparison, operational errors and costs; it does not support a one-call/component claim, general superiority or independently verified claim entailment.

The fragment successfully compiled inside a standalone desktop LaTeX helper project. `LATEX_COMPILE_AUDIT.json` records validation. The original manuscript, bibliography and PDF are not overwritten; integration belongs to the next manuscript revision.

## Preserved comparative context

| Cohort | Status | N | A accuracy | B accuracy | C accuracy | C−B |
|---|---|---:|---:|---:|---:|---:|
| Dataset1 InfoBank | Imported exposed development | 40 | 80.00% | 80.00% | 100.00% | +20.00 pp |
| Dataset2 RefusalBench-NQ | Imported exposed development fallback | 40 | 75.00% | 75.00% | 72.50% | −2.50 pp |
| Dataset3 QASPER TEST | Newly executed, balanced Tier M subset | 80 | 78.75% | 78.75% | 67.50% | −11.25 pp |

The historical Dataset1 paired interval is +10 to +30 points (matched-pair clusters); Dataset2 is −13.16 to +7.89 points (source-group clusters). These are retained historical statistics, not recomputed QASPER intervals. Dataset1 C reason agreement is 72.5% and fulfilment-status agreement 80%, despite 100% mode accuracy; its mode score is not factual-answer accuracy. Dataset2's protected reserved groups remain unopened by this task. No overall pooled accuracy is presented.

## Verification and reproducibility

- Twenty-two new focused protocol tests passed. The advanced compatibility run passed 713 tests; three historical working-byte hash checks passed separately. Four scoring tests passed.
- The original suite retains one known pre-existing failure, `test_preheldout_attempt1_plan_artifacts_are_plan_only`, because a previously committed `HELDOUT_RUN_AUTHORIZATION.json` contradicts its plan-only assertion. It is disclosed, not hidden or repaired in historical code. The other original tests passed. XML/log artifacts and `REGRESSION_AUDIT.json` retain exact counts and diagnostics.
- Git checkout CRLF conversion was restored to the already-frozen historical working bytes in 89 files, after verifying content equivalence under newline normalization. This is not an algorithm edit; old tracked Git content remains unchanged. The exact Git-blob scratch checkout used by regressions is separate from the actual frozen-byte checks.
- Security audit verifies all 241 actual request payloads: source/question equality across A/B/C, no gold/reference/benchmark-ID fields, unchanged prompts/schemas/limits, zero B calls and zero new Dataset1/2 calls. The 1163 historical files in this worktree, 1261 tracked files in the primary worktree, primary HEAD and all prior refs are protected. The current manuscript source hash remains unchanged.
- Complete test papers, human answers, detailed evidence and raw requests/results are ignored under `datasets/` and `local/`. Public artifacts contain manifests, hashes, modes, aggregate metrics and paraphrased review. Final scoped privacy scanning and staging checks are recorded in `SECURITY_AUDIT.json` and `COMPLETION_AUDIT.json`. `checksums.sha256` covers the committed public delivery.

The reproducible order is source audit/mapping rules → historical verification/import → code and preregistration freeze → deterministic sample/runtime materialization → bounded execution → fixed scoring → non-independent review → manuscript fragment → scoped checksums/local commit. Execution is complete: **do not rerun the sample or API runner as a verification step**. Read the saved per-case and request metadata instead. The ignored source can be reacquired from the pinned URL and verified by its recorded SHA without opening another split.

The local commit identifier, actual task wall time and clean-worktree result are in the adjacent output completion receipt. No remote push or merge is performed.

## Source and artifact map

- [Detailed source audit](QASPER_TEST_SOURCE_AUDIT.md), [fixed gold mapping](QASPER_GOLD_MAPPING.md), [preregistration](PREREGISTRATION.md), sample and exposure manifests.
- `QASPER_MODE_RESULTS.jsonl`: eighty per-case mode/validity/evidence records; `QASPER_CONFUSION_MATRICES.json`, `PAIRED_COMPARISON.json`, `ANNOTATION_TIER_ANALYSIS.json`: exact unrounded metrics.
- `EVIDENCE_RETRIEVAL_AUDIT.json`, `OPERATIONAL_FAILURES.json`, `API_USAGE.json`, `API_CALLS.jsonl`: separate evidence, operations and resources.
- `QUALITATIVE_REVIEW.json`, `LABEL_SENSITIVITY_FLAGS.json`: non-independent findings; ignored `local/CASE_REPORT.md`: complete case-level responses, source excerpts, human references and diagnostic traces.
- [Revised three-dataset summary](REVISED_THREE_DATASET_SUMMARY.md), [LaTeX replacement](RESULTS_FOR_PAPER_QASPER.tex), [precise integration notes](PAPER_REPLACEMENT_NOTES.md).

Official source: [original QASPER TEST v0.3 archive](https://qasper-dataset.s3.us-west-2.amazonaws.com/qasper-test-and-evaluator-v0.3.tgz), SHA-256 `72a52a41193e2838b8074f80ac074b94f956b84886c36a61c58a7df4171bdd72`. Test JSON SHA-256 is `6e29ad410e6e39aa1936017fb965b30a20eb2e7751997f55b97c9d281aa884e5`. The [pinned official dataset loader](https://huggingface.co/datasets/allenai/qasper/tree/fdc9d8214fbab5dd782958601db4d678e6934a54) was read for provenance, not executed to fetch other splits. The exact verified revision is recorded in `SOURCE_PROVENANCE.json` (use that manifest if a display link is unavailable). QASPER is described by [Dasigi et al., NAACL 2021](https://aclanthology.org/2021.naacl-main.365/); the pinned dataset card identifies CC BY 4.0.
