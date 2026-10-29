# QASPER random ten-question CFAF pilot

Report prepared: 2026-10-29T11:00:03.133965+00:00. Exploratory development experiment; one frozen execution, ten distinct papers. Registry: **Dataset3-QASPER-v2-candidate**.

**Result:** Standard RAG A and Guarded RAG B agree with original mapped modes on 8/10 (80%); CFAF C on 7/10 (70%). Balanced accuracy is the same because the pilot deliberately contains five FULL and five CFAF questions. All ten paired cases completed, with 30 successful gpt-4o-mini calls and zero recorded operational failures. C does not outperform A/B in this sample. Mode agreement is not complete-answer correctness.

**Dataset decision:** QASPER supplies a clearer original human answerability field, reference answers and evidence than GaRAGe for this particular research question. Keep it as the preferred provisional candidate for binary Dataset3 development, but **do not declare a final replacement yet**. Two of the five selected original-unanswerable questions appear directly answerable from the supplied paper, and one FULL question has conflicting substantive reference answers. Those are non-independent review findings requiring independent adjudication, not corrected gold. Preserve GaRAGe Dataset3-v1 as a historically reproducible, complementary grounding/temporal benchmark. No further run is performed or authorized by this report.

## Source, registry and split

Actual download: [original QASPER v0.3 train/dev archive](https://qasper-dataset.s3.us-west-2.amazonaws.com/qasper-train-dev-v0.3.tgz); 10,835,856 bytes; SHA-256 `a28fdf966db827bcee3d873107d6b6669864fb7ca8fbf73a192f5e39191bdb5a`. Extracted dev JSON SHA-256 `2ae7ee62a65b1c4225791c70de80c2aad4e8998cf1fd4f09a53103db4f21af93`. Official [Hugging Face source revision](https://huggingface.co/datasets/allenai/qasper/tree/fdc9d8214fbab5dd782958601db4d678e6934a54) is `fdc9d8214fbab5dd782958601db4d678e6934a54`; its inspected loader declares 0.3.0 and the same archive URL. The default loader was not executed because it also downloads test. The train member was not extracted or parsed; no test archive or test record was used.

The pinned dataset card identifies CC BY 4.0. Attribution: Dasigi, Lo, Beltagy, Cohan, Smith and Gardner (2021), [A Dataset of Information-Seeking Questions and Answers Anchored in Research Papers](https://aclanthology.org/2021.naacl-main.365/). The paper reports 5049 questions/1585 papers overall; the actual dev file used here has 1005 questions/281 papers/1764 answer annotations. [QASPER_SOURCE_AUDIT.md](QASPER_SOURCE_AUDIT.md) records actual nested schema and all downloaded-file checksums. Full originals, gold and raw traces remain ignored under datasets/ and local/.

Dataset1 remains InfoBank and Dataset2 remains RefusalBench-NQ. Neither is modified. All earlier GaRAGe experiments retain their Dataset3-v1 names and contents; their cumulative exposed set remains 90 from the previous study. No GaRAGe records are newly run or relabelled here.

## Original annotation mapping and random selection

Original unanswerable flags alone determine the initial binary mapping, with usable original answers required for FULL. Every annotation must be valid. Unanimous true gives CFAF; unanimous false plus one usable answer representation per annotation gives FULL; conflict, missing or ambiguous representations give UNKNOWN. Boolean yes_no=false is a usable No answer; null means that answer type is absent. Original annotations and derived labels are stored separately. See [QASPER_LABEL_MAPPING.md](QASPER_LABEL_MAPPING.md).

| Dev question class | Count |
|---|---:|
| FULL | 870 |
| CFAF | 60 |
| UNKNOWN | 75 |
| Total | 1005 |

All 75 UNKNOWN questions have conflicting answerability annotations. No invalid or ambiguous answer representation was encountered. The yes/no field has 1556 null, 105 true and 103 false annotations. Binary consensus does not imply that different human reference answers agree on their substantive content (case 5). Four of the five selected CFAF questions have one annotation; case 7 has two. Single-annotation consensus provides no inter-annotator reliability evidence.

Seed 20261029; Python Random.sample without replacement, FULL pool first and CFAF pool second, each canonically sorted by paper ID and question ID. Five from each class. The first independent draw already yielded ten distinct papers; no rejection, replacement or hand selection occurred. The manifest was saved before the first API attempt and hashes original question-plus-paper records. The schema-audit first-record answer exposure is disclosed in the exposure ledger; it did not alter the draw. Label auditing covered the complete dev pool; remaining questions are not claimed to be label-unseen holdout data.

This balanced 5/5 pilot does not represent the natural 870/60 eligible-class distribution. UNKNOWN cases were excluded before sampling, not discarded based on predictions. [DATASET3_SELECTION_MANIFEST.json](DATASET3_SELECTION_MANIFEST.json) and [DATASET3_EXPOSURE_LEDGER.json](DATASET3_EXPOSURE_LEDGER.json) give the ten original question IDs, paper IDs, counts and hashes.

## Frozen systems and common evidence

Starting branch experiment/cfaf-contract-driven-v1 at bfd80bbfe2ccbb251da46bdc22b791dad5b9341f; new local branch experiment/cfaf-qasper-pilot-v1. All 1163 previously tracked working files are byte-identical. C is a byte-identical copy of the existing measured_c.py. Its prompts, schemas, RDA/RECV checks, sparse source assessment, source inventory, original top-level selector, controlled realization and eight named stages are unchanged. No experimental reference-alias ablation is enabled.

A uses the established ordinary selective-RAG prompt with a six-field self-reported mode. B applies the existing deterministic output/policy validator to the same exact A generation: zero extra calls, and no CFAF sufficiency gate. C makes semantic-analysis and realization calls using the existing sparse-source pipeline. Optional query-only profile fallback was allowed but used zero times. All supplied public paper content has FULL access; no governance restriction was invented.

Each question receives its original paper title, abstract, full-text sections/paragraphs and textual figure/table captions, represented as one neutral paper source with deterministic span windows. Images and equation bodies absent from the original textual extraction are not reconstructed. The runtime whitelist excludes annotations, human answers/evidence, worker/annotation IDs, original paper/question IDs and expected modes. Gold evidence enters only the scorer.

Nine papers fit whole. For case 2, SQLite FTS5/BM25 over question terms chooses whole paragraphs/captions, then restores original order. Title and abstract are always supplied. All systems receive identical projected document arrays and ordering, verified in every actual outgoing request. The old 60000 serialized-byte bound was predeclared as 110000 for retrieval materialization and 120000 for the actual full API envelope; this accommodates research papers while conservatively bounding input tokens. Analysis stays 1500 output tokens, generation 512, profile 500. No token limit, prompt or implementation was changed after outputs.

| Case | Paper | Included / available paragraphs and captions | Context |
|---|---|---:|---|
| 1 | 1909.00512 | 49 / 49 | WHOLE_PAPER |
| 2 | 1907.01468 | 42 / 73 | SQLITE_FTS5_BM25 |
| 3 | 1803.05223 | 66 / 66 | WHOLE_PAPER |
| 4 | 1910.12574 | 30 / 30 | WHOLE_PAPER |
| 5 | 1811.08603 | 70 / 70 | WHOLE_PAPER |
| 6 | 1903.11283 | 86 / 86 | WHOLE_PAPER |
| 7 | 1804.00720 | 29 / 29 | WHOLE_PAPER |
| 8 | 1707.06806 | 33 / 33 | WHOLE_PAPER |
| 9 | 1910.06592 | 33 / 33 | WHOLE_PAPER |
| 10 | 1910.03634 | 23 / 23 | WHOLE_PAPER |

Case 2 retains one of its two original human evidence paragraphs. This is a retrieval/pipeline limitation; its gold remains FULL. The retained context also contains relevant interdisciplinary motivation, so missing one annotated passage does not independently prove all complete answers impossible. [RUNTIME_INPUTS.jsonl](RUNTIME_INPUTS.jsonl) contains public integrity metadata; exact full inputs are in ignored local/runtime_inputs.jsonl.

## Ten individual predictions

| Case | Original paper ID | Original question ID | Gold | A | B | C |
|---|---|---|---|---|---|---|
| 1 | 1909.00512 | 891c2001d6baaaf0da4e65b647402acac621a7d2 | FULL | FULL | FULL | FULL |
| 2 | 1907.01468 | b970f48d30775d3468952795bc72976baab3438e | FULL | FULL | FULL | CFAF |
| 3 | 1803.05223 | 2eb9280d72cde9de3aabbed993009a98a5fe0990 | FULL | FULL | FULL | FULL |
| 4 | 1910.12574 | c81f215d457bdb913a5bade2b4283f19c4ee826c | FULL | FULL | FULL | FULL |
| 5 | 1811.08603 | b8d0e4e0e820753ffc107c1847fe1dfd48883989 | FULL | FULL | FULL | FULL |
| 6 | 1903.11283 | a66a275a817f980c36e0b67d2e00bd823f63abf8 | CFAF | FULL | FULL | FULL |
| 7 | 1804.00720 | 63c3550c6fb42f41a0c93133e9fca12ac00df9b3 | CFAF | CFAF | CFAF | CFAF |
| 8 | 1707.06806 | 252a645af9876241fb166e5822992ce17fec6eb6 | CFAF | CFAF | CFAF | CFAF |
| 9 | 1910.06592 | 8e12b5c459fa963b3e549deadb864c244879fe82 | CFAF | CFAF | CFAF | CFAF |
| 10 | 1910.03634 | 63b92dcc701ec77fdb3355ede5d37d2fbf057bcc | CFAF | FULL | FULL | FULL |

Exact questions and case findings follow; full A/B/C responses, human references, human evidence, selected span quotes and requirement diagnostics are in ignored **local/CASE_REPORT.md**. [QUALITATIVE_ASSESSMENT.json](QUALITATIVE_ASSESSMENT.json) gives the review rationale and flags. All qualitative assessment is **Codex-produced, non-independent and not blinded**. No second model/judge or independent verification API was called.

## Classification metrics

Operational and unexecuted outputs have their own confusion columns and receive zero accuracy/recall credit. Precision is over nonoperational mode predictions; all ten remain in accuracy/recall denominators. No operational fallback is credited as a correct evidential CFAF. There are no operational or missing outputs in this run.

| System | Accuracy | Balanced | FULL P | FULL R | CFAF P | CFAF R | Unnecessary refusal | Nominal failure to restrict | Operational |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 80.00% | 80.00% | 71.43% | 100.00% | 100.00% | 60.00% | 0 | 2 | 0 |
| B | 80.00% | 80.00% | 71.43% | 100.00% | 100.00% | 60.00% | 0 | 2 | 0 |
| C | 70.00% | 70.00% | 66.67% | 80.00% | 75.00% | 60.00% | 1 | 2 | 0 |

### System A: gold rows, predicted columns

| Gold | FULL | CFAF | OPERATIONAL | NOT EXECUTED |
|---|---:|---:|---:|---:|
| FULL | 5 | 0 | 0 | 0 |
| CFAF | 2 | 3 | 0 | 0 |

### System B: gold rows, predicted columns

| Gold | FULL | CFAF | OPERATIONAL | NOT EXECUTED |
|---|---:|---:|---:|---:|
| FULL | 5 | 0 | 0 | 0 |
| CFAF | 2 | 3 | 0 | 0 |

### System C: gold rows, predicted columns

| Gold | FULL | CFAF | OPERATIONAL | NOT EXECUTED |
|---|---:|---:|---:|---:|
| FULL | 4 | 1 | 0 | 0 |
| CFAF | 2 | 3 | 0 | 0 |

A/B and C differ only on case 2: A/B are nominally correct FULL and C is nominally incorrect CFAF. All three are nominally wrong on original CFAF cases 6 and 10. Those two outputs have explicit document support on this qualitative review; “failure to restrict” is the required original-label confusion count, not a finding that these answers are hallucinations. No adjusted-gold or corrected-accuracy result is calculated. The ten cases do not establish statistical superiority or population accuracy.

## Evidence support and answer quality

All ten C assessments passed the existing structural/reference checks: zero unknown span IDs, zero missing-assessment support errors, zero source-role coverage failures. The gate reports six VERIFIED_FULFILMENT and four VALIDATED_CFAF decisions. These names express validation under existing model-supplied semantic properties; they are not independent truth judgments.

Scorer-only evidence diagnostics map original human evidence to paragraph/caption units, plus the supplied abstract; remove only the documented FLOAT SELECTED prefix and normalize whitespace. A referenced 430-character catalogue window selects every evidence unit it touches. Original unmapped evidence would remain in the recall denominator; there are none in these ten. Invalid assessments would contribute no validated support. Union evidence from different humans may be alternative sufficient evidence, so low union recall need not mean an incomplete answer.

| Case | Human evidence union | Retrieved | C selected units | C matches | C P | C R | C F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2 | 2 | 1 | 1 | 100.00% | 50.00% | 66.67% |
| 2 | 2 | 1 | 1 | 0 | 0.00% | 0.00% | 0.00% |
| 3 | 1 | 1 | 3 | 1 | 33.33% | 100.00% | 50.00% |
| 4 | 1 | 1 | 1 | 1 | 100.00% | 100.00% | 100.00% |
| 5 | 2 | 2 | 3 | 1 | 33.33% | 50.00% | 40.00% |
| 6 | 0 | 0 | 3 | 0 | 0.00% | N/A | 0.00% |
| 7 | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| 8 | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| 9 | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| 10 | 0 | 0 | 2 | 0 | 0.00% | N/A | 0.00% |

Across the five cases with original human evidence, C macro passage-overlap precision/recall/F1 is 53.33% / 60.00% / 51.33%. Retrieval macro evidence recall is 90.00%. These are diagnostic overlap metrics, not official QASPER answer/evidence scores, entailment accuracy or complete-answer accuracy. Empty selection against nonempty gold has F1 zero; both-empty evidence F1 is undefined. The scorer was corrected to include abstract support and this empty-set convention; no inference source, output, selection or label was changed.

A/B do not expose passage-selection IDs under the common six-field output schema. Their selection precision/recall is **not instrumented**, rather than assigned an artificial zero or inferred from C. All systems have zero verified public citations; C internal span identifiers are not rendered citations and do not establish per-claim entailment. Source relevance, exact reference validity, support for a relation and complete request fulfilment remain different questions.

### Per-case question and qualitative findings

#### Case 1: 1909.00512

Question: How do they calculate a static embedding for each word?

All three systems answer the static-embedding method consistently with the paper and both references. C is concise and identifies the first principal component in a given layer.

A/B: Document-supported and addresses the question. The additional explanation about contexts is consistent with the described construction.

C: Document-supported and substantively adequate on this review. Its selected window includes the explicit method statement.

Reference comparison: One human uses the table caption and another uses the method paragraph. Selecting one valid alternative yields 50% union recall and 100% best-annotation F1; union recall is not answer completeness.

Unsupported-claim review: None identified in the reviewed answer claims; this is not an independent error-rate estimate.

#### Case 2: 1907.01468

Question: What kind of issues (that are not on the forefront of computational text analysis) do they tackle?

A/B give a supported but broad list of conceptual challenges; C rejects its own generic background candidate for missing requested relation, then fails to realize the contracted refusal text.

A/B: The conceptual-validity and meaning/interpretation claims are directly supported by provided P0002. Compared with the human reference, the answer does not cover the full research-question and cross-disciplinary scope; FULL mode agreement does not establish complete answer quality.

C: Nonoperational CFAF is a nominal unnecessary refusal against original FULL gold. The analysis selected an abstract-level restatement instead of the available research-question details. The sent contract required an evidence-relation limitation, but the final answer instead repeats the background candidate. The existing validator accepted this six-field CFAF object and did not enforce CFAF reason-text copying.

Reference comparison: Only one of two human evidence paragraphs was retrieved (P0006); the interdisciplinary example paragraph was omitted. Related interdisciplinary motivation is still present in P0005. This is a retrieval limitation, not proof that the retained context was entirely unanswerable; gold stays FULL.

Unsupported-claim review: No new external entity/date/causal claim identified in A/B; primary concerns are scope coverage and C's unflagged realization-copy deviation.

#### Case 3: 1803.05223

Question: what is the size of their dataset?

A/B provide the exact final question total. C gives supported approximate text/question counts, with less precision than the human reference.

A/B: The final total and the commonsense subset/count/percentage are present in the data-statistics paragraph and are supported.

C: Approximately 2100 texts and 14000 questions is stated in the introduction. It addresses dataset size, although the more precise final 13939-question total was available. This is reduced precision, not an invented number or automatic semantic failure.

Reference comparison: Human reference gives the exact final question count. Do not reject the C answer solely for different wording or numerically consistent rounding. Independent adequacy remains pending.

Unsupported-claim review: No unsupported numerical or causal claim identified; exact-versus-approximate precision is the material issue.

#### Case 4: 1910.12574

Question: Which publicly available datasets are used?

All systems identify the two main dataset families named by the references.

A/B: Waseem/Hovy and Davidson are correctly identified. The added tweet counts and annotation categories are in the paper, but the answer omits the 6900-tweet extension merged into the Waseem family; its extra description should not be mistaken for the exact final merged dataset composition.

C: Concise identification of the two main datasets is supported and adequate for the main question. Hovy/Hovey spelling variation is not treated as a semantic mismatch.

Reference comparison: Both reference variants name the same two main dataset families. This is a semantic match, without exact-string scoring.

Unsupported-claim review: No unsupported main dataset identity found. A/B's extra collection-size description loses a merging detail.

#### Case 5: 1811.08603

Question: Do they only use adjacent entity mentions or use more than that in some cases (next to adjacent)?

Binary FULL gold is valid under the requested mapping, but the two usable human answers disagree about the substantive adjacent-mention interpretation. Neither generated answer resolves the window/propagation distinction well.

A/B: The statement that the paper does not explicitly say it only uses adjacent mentions conflicts with P0054, which does say so. The paper separately defines a window over neighboring mentions, configures the neighbor window to six, and discusses chain-like propagation; a careful answer must distinguish local neighborhoods from indirect document-level influence.

C: Adjacent and neighboring are treated as though they were different evidence scopes, without stating the configured window or indirect propagation. The response is too vague to resolve the actual contrast. One selected window is generic efficiency text, demonstrating that paragraph overlap alone is weak support evidence.

Reference comparison: One reference says only adjacent; the other says more than adjacent. Both annotations mark answerable, so the specified initial mapping remains FULL. This is answer-content disagreement hidden by binary answerability consensus, and must not be relabelled UNKNOWN post hoc.

Unsupported-claim review: A/B contains a contradicted absence assertion; C's adjacent-versus-neighbor contrast is not clearly substantiated. No new external entity/date is introduced.

#### Case 6: 1903.11283

Question: How do they measure style transfer success?

All systems are nominal failures to restrict against original CFAF gold, but the supplied paper directly explains human style-transfer evaluation and RMSE. This is a potential annotation/document discrepancy.

A/B: Evaluation criteria correspond to P0051, while style-direction scores and RMSE are explicitly explained in P0056-P0057. The answer is document-supported and appears to address the question.

C: The concise human-evaluation/RMSE answer is directly supported by its selected windows. It is a plausible substantive answer despite disagreement with the original unanswerable annotation.

Reference comparison: The single original annotation is unanswerable and supplies no reference/evidence. Preserve that gold; this non-independent review flags a discrepancy rather than producing a corrected label or adjusted accuracy.

Unsupported-claim review: No unsupported external entity/date or causal claim identified. The disagreement concerns original label validity, not a demonstrated hallucination.

#### Case 7: 1804.00720

Question: Is it possible to convert a cloze-style questions to a naturally-looking questions?

All systems return CFAF, agreeing with original unanswerable gold. C gives a misleading referent-ambiguity reason instead of the evidence limitation.

A/B: Appropriate evidence-based abstention: the paper's cloze construction and downstream fine-tuning do not establish a procedure for conversion into natural questions.

C: The analysis itself reports MISSING_EVIDENCE but also marks referent_resolved false, causing the existing gate to request referent clarification. Missing information is being conflated with ambiguous reference. This is not a technical fallback.

Reference comparison: Both original annotations are unanswerable. Mode agrees, but original gold has no reason-class label; the reason criticism is non-independent qualitative review.

Unsupported-claim review: C asserts query ambiguity without a demonstrated competing referent. No external factual answer is supplied.

#### Case 8: 1707.06806

Question: What is the average length of the title text?

All systems return CFAF for the unreported average title length. C again asks for referent clarification.

A/B: Evidence-based refusal is appropriate: the paper describes variable-length headlines and dataset construction but does not report the requested average.

C: Mode is consistent with gold, but the requested statistic and target are understandable. The missing average does not establish ambiguous reference. The original pipeline's response is valid structurally and weak semantically.

Reference comparison: Single unanswerable annotation, no reference answer/evidence. No label correction made.

Unsupported-claim review: The unsupported element is the ambiguity explanation; no average or date is invented.

#### Case 9: 1910.06592

Question: How many layers does their model have?

All systems return CFAF for the unspecified total model-layer count. Their refusal rationales still contain quality limitations.

A/B: Withholding an exact layer count is appropriate. However, saying the paper gives no architecture detail beyond LSTM is too broad: P0006/P0015 explicitly describe attention and softmax components. Those components alone do not establish the requested total layer count.

C: The missing count is converted into a generic ambiguity request, despite the analysis recognizing missing evidence. This is a reason-quality defect, not an operational error.

Reference comparison: Single unanswerable annotation, no reference answer/evidence. Caption-only input does not supply the image's full architecture details; no layer count is inferred from it.

Unsupported-claim review: A/B's blanket absence-of-architecture assertion is contradicted by provided text; C's ambiguity assertion lacks competing referents. No layer count is invented.

#### Case 10: 1910.03634

Question: What applicability of their approach is demonstrated by the authors?

All systems are nominal failures to restrict against CFAF gold, although the abstract explicitly describes the demonstrated painting-to-prose application. This is another potential annotation/document discrepancy.

A/B: The demonstration of generating Shakespearean prose from paintings is explicitly stated in the abstract and illustrated/evaluated in the results. The additional creativity description aligns with the paper's aim/results, rather than introducing an outside application.

C: Its concise application statement is directly supported by the selected abstract window. It appears to answer the question, despite the original unanswerable label.

Reference comparison: Single original unanswerable annotation with no evidence. Gold stays CFAF. No corrected accuracy or alternate-label score is calculated.

Unsupported-claim review: No unsupported application identity or causal/date assertion identified in the reviewed output. Original label versus paper text is the material uncertainty.

### Cross-case interpretation

The original answerability labels permit transparent binary scoring without inferring FULL from merely relevant passages. However, mode consensus is weaker than complete answer correctness. Case 2 has incomplete reference-scope coverage despite A/B FULL, case 3 has supported approximate rather than exact counts, case 4 adds a dataset-merging nuance, and case 5 contains conflicting substantive human references plus weak generated adjacency reasoning. Exact string equality is not used to reject paraphrases or rounding.

Cases 6 and 10 are potential gold/document discrepancies: the supplied text directly describes the requested evaluation method and demonstrated application, respectively. Both original CFAF labels remain unchanged. This pilot therefore cannot establish that the model errors reflect inappropriate answering rather than annotation error. Cases 7–9 have correct C CFAF modes but generic ambiguity explanations even though the analysis identifies missing evidence. Missing facts are being conflated with unresolved referents. Case 9 also shows that an evidence-based refusal can overstate what architecture information is absent.

There is one additional C realization defect in case 2: the final CFAF answer restates background instead of copying the contract’s evidence-relation limitation. The existing validator accepts that structurally valid object; it is reported as an unflagged copy/meaning deviation, not retroactively converted into an operational fallback. No fix or rerun follows these observations. Independent answer-adequacy and claim-support scores remain pending.

## Operational failures, calls and latency

Recorded operational failures: A 0, B 0, C 0. Schema, source-reference and policy failures: zero. Incomplete paired cases: zero. No request was retried, replaced or dropped. Every response finished with stop; no output was truncated. The one realization-copy defect above is a substantive contract-enforcement limitation missed by the frozen validator.

Requested model: gpt-4o-mini; observed deployment: gpt-4o-mini-2024-07-18; temperature 0; repetitions 1. Actual attempts: 30/50, all successful. Input tokens 329,344; output tokens 4,596. Summed provider latency 90.145 seconds; mean 3004.8 ms; max 5834.2 ms. Summed measured paired-case time is 92.875 seconds; this is distinct from the complete task duration. B adds 27.440 ms deterministic postprocessing and zero model calls.

| Call type | Calls | Input tokens | Output tokens | Mean latency ms |
|---|---:|---:|---:|---:|
| semantic_analysis | 10 | 204672 | 3184 | 4651.9 |
| semantic_cfaf | 10 | 64435 | 518 | 1857.0 |
| standard_rag | 10 | 60237 | 894 | 2505.7 |

No profile fallback, embeddings, second LLM judge or independent verifier was used. No monetary estimate is supplied from unverified pricing. [API_USAGE.json](API_USAGE.json) contains aggregate usage and [API_CALLS.jsonl](API_CALLS.jsonl) records every attempt’s usage, latency, input bound and payload hash. Unredacted payloads/responses remain private.

## Regression and security

31 focused tests passed before execution, including annotation mapping, Boolean No handling, no-gold input whitelist, deterministic retrieval, unchanged pipeline and operational-scoring safeguards. The final advanced suite passed 718 tests (including 27 new adapter checks), with three historical hash checks deselected there and passed separately against the original working bytes. Six scorer checks passed after scoring corrections; four overlap the earlier focused tests. Do not sum overlapping suite counts.

The original suite has 77 passing tests and 13 passing subtests, with one known pre-existing failure: test_preheldout_attempt1_plan_artifacts_are_plan_only expects a previously committed HELDOUT_RUN_AUTHORIZATION.json to be absent. The same failure existed at the starting point; the file is preserved. Tests ran without the API key in a disposable exact-Git-blob checkout, with archived clocks rebased only in that test process. A temporary-directory setup failure on a repeat check was resolved by explicitly placing pytest temporary files in the workspace; the final suite passed.

Security audit checks all 30 actual outgoing payloads for forbidden annotation fields, exact common document arrays/order, A isolation from C’s assessment/contract, model settings, attempt/time limits and request hashes. All 1163 prior files and all 76 frozen source hashes pass. Dataset1, Dataset2 and GaRAGe ledgers are unchanged. Original full papers, annotations and raw traces are ignored. Finalization additionally verifies the staged file inventory, no API credential bytes, no whole original paper paragraphs or long reference answers in public artifacts, index/worktree byte equality and checksum coverage. [SECURITY_AUDIT.json](SECURITY_AUDIT.json) and [REGRESSION_AUDIT.json](REGRESSION_AUDIT.json) record the checks.

## Comparison with archived GaRAGe

The original GaRAGe ten-case pilot used fifteen supplied passages per case and an older dense-source contract: only one assessment was valid and T3 produced 0 FULL/10 CFAF. The later sparse-source development rerun on the same ten had 8/10 valid assessments and served C 7 FULL/3 CFAF, with two operational reference failures. The latest contract-driven study added 80 fresh GaRAGe questions, bringing historical exposure to 90. None of these results is overwritten.

Those GaRAGe runs do not have native complete-request FULL/CFAF gold. Their source relevance/correctness labels, temporal metadata and long-form answers serve a different purpose. QASPER offers explicit human unanswerable annotations and human answer/evidence references, enabling the mapped binary confusion matrices in this report. Conversely, QASPER scientific-paper extraction may omit image contents, uses a rare natural unanswerable class, and can contain substantive reference disagreement or apparent unanswerable annotation errors.

The older GaRAGe pilot also used a control sharing semantic analysis, unlike this study’s Standard A and deterministic B. Pipeline versions, sample selection, context allowance and source granularity differ. Therefore the operational validity/mode counts are diagnostic context, not a controlled cross-dataset performance gain. No GaRAGe and QASPER mode or grounding metrics are pooled.

## Recommendation and limits

QASPER is a better **candidate instrument** for document-relative answerability because original human labels make the binary mapping explicit and human evidence/reference answers support separate grounding and quality analysis. This ten-case result does not validate a clean replacement dataset, prove CFAF improves refusal decisions, or establish factual-answer accuracy. The frozen C loses one nominal mode decision versus A/B, and reveals refusal-reason and realization limitations. Two apparent label/document conflicts and one substantive reference disagreement make independent review essential before final promotion.

Retain the provisional name Dataset3-QASPER-v2-candidate and preserve archived GaRAGe Dataset3-v1. Prefer QASPER for planning a future independently reviewed, preregistered binary-answerability study, while retaining GaRAGe for complementary multi-source/temporal grounding. A larger run, label adjudication protocol or pipeline improvement requires a separate authorization; none is executed here. No selected output or gold label is changed and no ten-case optimization is performed.

## Artifacts and local publication

Required public artifacts: REPORT.md, QASPER_SOURCE_AUDIT.md, QASPER_LABEL_MAPPING.md, DATASET3_SELECTION_MANIFEST.json, DATASET3_EXPOSURE_LEDGER.json, EXPERIMENT_MANIFEST.json, RUNTIME_INPUTS.jsonl (integrity metadata), RESULTS.jsonl (derived predictions), MODE_CONFUSION.json, EVIDENCE_METRICS.json, API_USAGE.json, REGRESSION_AUDIT.json, SECURITY_AUDIT.json and checksums.sha256. Additional files include source/tests, per-call usage and qualitative summaries. Exact original full inputs, annotations and traces are under ignored datasets/ and local/; **local/CASE_REPORT.md** is the complete detailed companion.

The entire task uses the conservative 10:37 UTC start, hard stop 11:37, and last-new-call deadline 11:27. Selection and code freeze precede the first API call; all calls completed before the last-new-call deadline. A final local completion receipt outside the repository records commit, elapsed time and clean worktree verification. No merge or push is performed.

Manual publication command, only when the user chooses to publish:

```powershell
git -C "C:\Users\EKKE\Documents\Codex\2026-10-28\files-pasted-by-the-user-codex\outputs\InfoBank" push -u origin experiment/cfaf-qasper-pilot-v1
```
