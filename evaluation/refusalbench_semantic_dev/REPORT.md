# CFAF Semantic Evidence Adapter: 42-case development experiment

**Readiness recommendation: not ready for a frozen 300-case independent evaluation.** The implementation now prepares evidence assessments and answer candidates from runtime text, can produce genuine FULL answers, passes the actual question into final generation, and preserves the existing CFAF mode-selection principle. Its live semantic and integration failures remain substantial.

All 42 cases were run across four generated systems: **210 real API attempts, comprising 42 shared semantic analyses and 168 generations**, with no retries or embeddings. All calls succeeded at the provider/transport level. The frozen, error-inclusive results are **CFAF 28/42 (66.7% accuracy; 45.8% balanced accuracy)** versus **Always CFAF 36/42 (85.7%; 50.0%)**. Both existing baselines scored 6/42. The optional shared-assessment control scored 1/42 because most abstentions had null answer text. These are diagnostic development results, with no independent-validation or significance claim.

## A. Implementation changes

### Files and architecture

Only new files are added. All **405 pre-development files**—381 original tracked files and 24 prior-pilot deliverables—match their preserved byte hashes. Original CFAF code, frozen D1–D8 datasets, publication results and earlier outputs are unchanged.

- `evaluation/wolala2026/semantic_evidence.py`: reusable analysis, span verification, semantic stages and eight-stage orchestration. Public entry points accept query text and neutral source-ID/context mappings; no benchmark answers or metadata are accepted.
- `semantic_adapter.py`: strict two-field benchmark projection and neutral runtime IDs.
- `sample_development_cases.py`: trusted, source-group-aware sampler and holdout reservation.
- `run_experiment.py`, `api_budget.py`, `scoring.py`: separate freeze/execution/scoring processes, durable attempt cap, exact API logging and common interpretation/metrics.
- `test_semantic.py`, `test_experiment.py`, `verify_regressions.py`: synthetic acceptance, leakage, budgets, sampling, output consistency and isolated baseline/extension regression comparison.

The existing pipeline, adapters, labels, runner and provider were inspected, alongside backend `controlled_failure.py` and `relevance.py`. Their internal fixture/gold-answer behavior is retained for backward compatibility. The new entry point reuses the original retrieval and permission stages, existing claim/contract/state types, actual `TopLevelModeSelectionStage`, and trace/invariant functions. It does not route external cases through gold-answer realization or replace the architecture with a direct mode-choice prompt.

The analyzer produces requested information, entities, relations, interpretations, query/premise/support status, requested/available detail, confidence, uncertainty causes, candidate answer and supporting/counterevidence spans. **Its schema has no FULL/CFAF or benchmark refusal-code field.** Code checks request-relative fulfilment separately. The original selector remains unchanged: FULL iff permitted, sufficient evidence can completely fulfil all required request content; CFAF otherwise.

```mermaid
flowchart LR
 A[Query and original context] --> B[One semantic analysis]
 B --> C[Query profiling]
 A --> D[Provided-context retrieval]
 C --> D --> E[Access and safety]
 E --> F[Semantic evidence labels]
 B --> F
 F --> G[Request-relative sufficiency]
 G --> H[Existing FULL/CFAF selector]
 H --> I[Contract and realization]
 I --> J[Validation and trace]
 A --> K[Shared-assessment prompt control]
 B --> K
```

The minimal extensions are a validated `SemanticAssessment`, explicit uncertainty/premise/support properties, and generic reason codes such as `AMBIGUOUS_REFERENCE`, `INCOMPATIBLE_EVIDENCE`, `PREMISE_REFUTED` and `GRANULARITY_NOT_SUPPORTED`. No original enum/type is changed. Official `REFUSE_*` labels occur only in trusted sampling/scoring. The separate entry point preserves the frozen fixture pipeline.

PRIMARY requires verified support spans, a specified/sufficiently supported request, adequate detail, established premises, no detected conflict, an answer candidate, and confidence at least 0.70. Retrieval alone never establishes PRIMARY. Permission is distinct from semantic role. CURRENT is the existing default, not an independently validated recency judgement.

Every quote must occur literally in the named runtime document; local code records exact offsets. Invalid schema/source/quote or an unquoted counterevidence claim invalidates analysis. No normalization, ellipsis repair, case folding or markup stripping is performed.

### Genuine FULL realization and validation

The final generator receives the actual question, selected contract, runtime-derived candidate and only verified permitted spans. It copies the candidate for FULL and the cause-specific public explanation for CFAF. Proposed answer, selected mode, raw generation, final response and validation remain separate. No `gold_answer`, `original_answers` or annotation-derived `runtime_answer` is supplied. Output mismatch would be an explicit failure, never a successful fallback refusal.

All 42 CFAF realizations match their contracts. This proves presentation/contract consistency, **not entailment or complete fulfilment**: copying an incomplete candidate preserves the semantic error. Filtering can hide counterevidence the analyzer missed; case 28 illustrates this. No extra model validator is used.

### Tests and acceptance

**43 new deterministic tests pass**, including the seven synthetic uncertainty/support situations, malformed/UNKNOWN analyses, forbidden fields, quote/counterspan verification, FULL generation without a gold answer, response consistency, source-group matching, the persistent 225-attempt cap and synthetic 42-case/210-call orchestration. Synthetic assessments/provider responses are test fixtures, not benchmark results. They establish representation/gate capability, not live analyzer quality.

The historical suite has **77 passed test functions, 13 passed subtests and one identical failure** on pristine base and extension using exact Git blob bytes in isolated copies. The failing old plan-only test expects `preheldout_v3_attempt1/HELDOUT_RUN_AUTHORIZATION.json` to be absent, although that file is committed at the verified base. No frozen artifact is removed to make it pass. Windows checkout line-ending checksum artifacts were isolated by using exact blob bytes. There are no new historical-regression failures, but strict acceptance condition 5 (all historical tests green) is **not fully satisfied**. The pre-run protocol records this exception; the experiment is diagnostic development work, not acceptance certification.

## B. Dataset and reproducibility

| Item | Recorded value |
|---|---|
| Original base | `wolala2026`, `5f377de38312fb39c088551f9c74f8b6d4bd5080` |
| Branch | `experiment/refusalbench-semantic-dev-v1` |
| Implementation snapshot | `ce0e67d942f37027cc52d722efcdb2d885602e12`; exact source hashes also frozen |
| Official dataset | [RefusalBench-NQ](https://huggingface.co/datasets/aashiqmuhamed/RefusalBench-NQ) |
| Revision | `b3684f805563e6ce465e7e9b055b840a48f519c2` |
| Seed | `20261028` |
| Grouping | Original NQ `source_id`, not perturbation ID |
| Prior exclusion | All perturbations of the ten previous-pilot source questions |
| Reserved holdout | 30 untouched groups, 455 records; metadata-only reservation before semantic development |
| Development | Six records per seven original categories; **42 distinct source groups**, no relaxation |
| Other untouched groups | 18 after prior/development/reserved group accounting |
| Selected-record SHA-256 | `089841a661942d793286a7209d02b44ac6a9175931322ac8b1967ceb52940a5c` |
| Runtime projection SHA-256 | `5d9af084b296685290f36ab5eb73c1b7b0b6a99abf4a34d31402cb33c4299f48` |
| Python / platform | 3.12.14 (main, Aug 25 2026, 14:01:42) [MSC v.1944 64 bit (AMD64)]; Windows-11-10.0.26300-SP0 |
| Dependencies | datasets 5.1.0; huggingface_hub 2.3.0; pyarrow 26.0.0; pytest 9.2.0; full lockfile/manifest supplied |
| Requested / actual model | `gpt-4o-mini` / `gpt-4o-mini-2024-07-18` on all calls |
| Settings | Temperature 0, one repetition, 160 generation output tokens; 1,500 analysis output tokens |
| UTC run | 2026-10-28T13:26:21.658444+00:00 to 2026-10-28T13:33:39.306742+00:00; 437.648 seconds |
| Europe/Budapest | 2026-10-28 14:26:21 CET to 14:33:39 CET |
| API use | 210 attempts, cap 225; 42 analysis + 168 generation; 0 retries/embeddings/additional judges |
| Execution blocker | None; all provider responses finish with `stop`, no truncation |

The trusted sampler uses metadata to exclude prior groups, sorts/shuffles eligible groups with `random.Random(20261028)`, and first reserves 30. A seeded augmenting-path matching assigns 42 category slots to distinct available groups, followed by seeded within-group record selection and final order shuffle. All seven quotas are feasible. Original annotations are unchanged. JSONL uses sorted keys, ASCII escapes, UTF-8 and LF. Original IDs and dataset indices are in `selection_manifest.json` and `CASE_RESULTS.md`.

The official split is loaded by trusted preparation, but reserved query/context/answer/explanation text is not inspected by the report author, exported as heldout cases, or passed to implementation/models. Reservation and overlap checks use metadata only.

### Leakage separation and freeze

Preparation, model execution and scoring run in separate processes. The worker reads only the 42-row two-field runtime file; it does not read original cases/selection/holdout metadata or import the scorer. IDs are neutral. No expected behavior, original answers/query/context, perturbation metadata, verifier votes, implementation explanations or original record IDs enter an evaluated component.

All systems begin with identical original perturbed questions and contexts. The analyzer receives the complete context; CFAF final realization uses verified permitted spans and the original question. This is an application data-flow boundary, not OS filesystem isolation. Payloads are preserved without authentication headers; no API key is printed, saved or committed.

Source hashes, prompts, analysis schema, projection, settings, scoring and test caveat are frozen before the first call. No frozen source/prompt changes during or after execution. The implementation commit was created during execution after a missing local Git identity error; its bytes match the pre-call freeze. The connected GitHub account supplies commit identity without changing global Git configuration. The final artifact commit is returned with delivery; no push or merge occurs.

| Prompt component | SHA-256 |
|---|---|
| `cfaf_semantic` | `de77f0ca703c1aac0fe1388be69fd43d2daf8f4f826179511195af3ac0a60316` |
| `prompt_only_control` | `ec0c586b26b3aa28a76474af5f0fd6c9bf9fc91073916c769aad4d16c762d852` |
| `semantic_analysis` | `d4f792dca32e6d9def87d01b89f12f58cdc079c88c026f882d2529efb8bf130d` |
| `semantic_prompt_control` | `d7e7e57ec3f9abef0c35896b69e524c2df2eb4ef31b68ec399adb84d46f2615b` |
| `standard_rag` | `2b9870b0c8541f4e2ac6f235d59681df3848016745e13efcfbac38f3ca740e8a` |

### Common interpretation

Raw JSON must have a nonempty string `answer` and explicit FULL/CFAF mode for every generated system. Other modes, null/invalid output, failed analysis or validation yield ERROR. No adapter repair/fallback earns credit. All 42 scheduled cases remain in accuracy/recall denominators; confusion matrices include ERROR. Original `ANSWER_CORRECTLY` maps to FULL and every original `REFUSE_*` to CFAF. This operationalization is not proof that every individual refusal is semantically necessary.

One frozen lexical procedure recognizes specific refusal categories. Category wording alone does not establish a justified reason. Factual support, complete request fulfilment, prose/mode agreement and label accuracy stay separate. Unperturbed original answers are never used as perturbed-answer keys.

## C. Semantic adapter evaluation

**Correct support and FULL realization: case 9.** The context names Jimmy Matthews and hat-tricks in both innings on 28 May 1912. The analyzer prepares that runtime-derived candidate and exact support, the original gate selects FULL, and the generator copies the grounded answer. It matches the positive behavior label. The freshness of the added latest-statistics qualifier is not independently established; that caveat remains in the review.

**Correct missing-evidence diagnosis: case 2.** A Lord's Prayer title contains no location evidence. CFAF refuses; both baselines add Bible verses absent from runtime text. **Cases 13 and 15** correctly identify the subjective beauty judgement and popularity counterfactual as nonfactual.

**No successful live structured ambiguity or contradiction diagnosis exists to show.** The analyzer emits zero AMBIGUOUS query states, zero CONFLICTING support states and zero REFUTED premise states. Counts are 33 SPECIFIED, 4 NONFACTUAL, 5 invalid/UNKNOWN; support is 30 MISSING, 7 SUFFICIENT, 5 UNKNOWN. Synthetic tests distinguish these causes, but supplied test assessments cannot substitute for live inference.

In case 7 the rationale mentions conflicting information while structured support remains MISSING. This is not credited as contradiction detection. Six false-premise records receive coarse refusal, but none is identified as a refuted premise. Confidence 0.95–1.0 accompanies some erroneous FULL decisions and is not calibrated evidence of reliability.

**Failed/uncertain examples:** case 5 treats “[an event]” and “[a deity]” placeholders as a sufficient identity answer; case 11 selects one of two series/roles; case 28 selects Will Friedle despite Ben Savage in an incompatible casting statement; case 32 resolves an ambiguous pronoun to Nicholas; case 40 demands unspecified further detail despite explicit Melbourne/Canberra content.

Exact-quote errors occur in cases 12 (invented ellipsis), 23 (added opening quote), 30 (changed capitalization), 36 (period replacing continuing comma/clause), and 39 (removed literal emphasis markup). No repair is applied. Case 30's raw candidate also ignores six-versus-sixty titles: quote rejection is mechanical, not successful semantic contradiction detection.

## D. Results

### Primary outcomes, all scheduled cases

| System | N | Accuracy | Balanced accuracy | FULL recall | CFAF recall |
|---|---:|---:|---:|---:|---:|
| Always FULL | 42 | 14.3% | 50.0% | 100.0% | 0.0% |
| Always CFAF | 42 | 85.7% | 50.0% | 0.0% | 100.0% |
| Standard RAG | 42 | 14.3% | 50.0% | 100.0% | 0.0% |
| Prompt-only | 42 | 14.3% | 50.0% | 100.0% | 0.0% |
| CFAF + Semantic Adapter | 42 | 66.7% | 45.8% | 16.7% | 75.0% |
| Shared-assessment prompt control | 42 | 2.4% | 8.3% | 16.7% | 0.0% |

The seven categories are balanced; binary prevalence is six FULL and 36 CFAF. Both constant references have 50% balanced accuracy. Semantic CFAF does not beat Always CFAF and has lower balanced accuracy than either constant. No significance tests, confidence intervals or publication-level inference are calculated.

| System | FULL precision | CFAF precision | Unnecessary refusal | Failure to restrict | ERROR |
|---|---:|---:|---:|---:|---:|
| Always FULL | 14.3% | N/A | 0/6 (0.0%) | 36/36 (100.0%) | 0 |
| Always CFAF | N/A | 85.7% | 6/6 (100.0%) | 0/36 (0.0%) | 0 |
| Standard RAG | 14.6% | N/A | 0/6 (0.0%) | 35/36 (97.2%) | 1 |
| Prompt-only | 17.6% | N/A | 0/6 (0.0%) | 28/36 (77.8%) | 8 |
| CFAF + Semantic Adapter | 14.3% | 90.0% | 3/6 (50.0%) | 6/36 (16.7%) | 5 |
| Shared-assessment prompt control | 14.3% | N/A | 0/6 (0.0%) | 6/36 (16.7%) | 35 |

Precision uses valid predicted classes; recall/rates retain gold-class cases that produce errors. CFAF gold-FULL outcomes are 1 FULL, 3 CFAF, 2 ERROR; gold-CFAF outcomes are 27 CFAF, 6 FULL, 3 ERROR. A low failure-to-restrict rate alongside many ERROR outcomes is not successful restriction. Full matrices are in `confusion_matrices.json`.

### Per-category binary correctness

| Original expected category | N | Standard | Prompt-only | Semantic CFAF | Shared prompt |
|---|---:|---:|---:|---:|---:|
| `ANSWER_CORRECTLY` | 6 | 6/6 | 6/6 | 1/6 | 1/6 |
| `REFUSE_AMBIGUOUS_QUERY` | 6 | 0/6 | 0/6 | 3/6 | 0/6 |
| `REFUSE_CONTRADICTORY_CONTEXT` | 6 | 0/6 | 0/6 | 1/6 | 0/6 |
| `REFUSE_FALSE_PREMISE_IN_QUERY` | 6 | 0/6 | 0/6 | 6/6 | 0/6 |
| `REFUSE_GRANULARITY_MISMATCH` | 6 | 0/6 | 0/6 | 6/6 | 0/6 |
| `REFUSE_INFO_MISSING_IN_CONTEXT` | 6 | 0/6 | 0/6 | 5/6 | 0/6 |
| `REFUSE_NONFACTUAL_QUERY` | 6 | 0/6 | 0/6 | 6/6 | 0/6 |

Six-for-six coarse refusal in false-premise, granularity and nonfactual categories does not demonstrate correct cause recognition. Much of it is the general missing-information diagnosis.

### Secondary outcomes

CFAF has 26 sufficiently specific category predictions on expected-refusal records, with **7/26 (26.9%)** matching the original category. Correct reason coverage is **7/36 (19.4%)** of expected refusals: five missing-information and two nonfactual matches. There is no correct original ambiguity, contradiction, false-premise or granularity diagnosis. One valid refusal cannot map to a unique category because its missing-information template and conflicting-information rationale disagree. Five invalid-analysis safety messages are errors, not successful generic refusals. No other generated system produces a valid specific refusal-category prediction under the common interpreter.

Behavior labels are not a complete perturbed-answer gold standard: **gold-backed answer-support accuracy and independent human-adjudicated correctness are unmeasurable**. All 168 outputs were reviewed separately by the report-authoring assistant against runtime context. These reviews are unblinded, see expected labels after generation, are not independent human annotations, and incur no API calls. The JSON field `independent_response_review` means a separate contextual assessment, not blinded human adjudication. Uncertain or non-answer support stays null.

| System | Valid declared FULL | Material assertions unsupported (author review) | No factual support judgement | Grounded and complete FULL observed |
|---|---:|---:|---:|---:|
| Standard RAG | 41 | 19 | 5 | 4 |
| Prompt-only | 34 | 14 | 6 | 4 |
| CFAF + Semantic Adapter | 7 | 2 | 0 | 1 |
| Shared-assessment prompt control | 7 | 2 | 0 | 1 |

These are descriptive author annotations, not independent answer-accuracy estimates. Some declared FULL outputs are non-answers or supported background. For CFAF's seven FULL responses, five contain literally supported material and two have unsupported/conflicting attribution; only case 9 is credited as clearly grounded complete core fulfilment. Cases 20 and 35 retain uncertainty about contradiction scope and are not relabelled.

Prose/mode review gives Standard 34 agreements, 7 disagreements, 1 unmeasurable; prompt-only 26 agreements, 8 disagreements, 8 invalid modes; CFAF 42 agreements including five disclosed analysis-failure messages; shared control 7 agreements and 35 null-answer outputs. Agreement is presentation consistency, not a correct semantic decision.

### Costs and runtime

| Component | Calls | Input tokens | Output tokens | Mean incremental latency (ms) |
|---|---:|---:|---:|---:|
| Shared semantic analysis | 42 | 32,307 | 6,968 | 2611.0 |
| Standard RAG generation | 42 | 14,859 | 3,193 | 1857.2 |
| Prompt-only generation | 42 | 17,631 | 3,117 | 1830.7 |
| CFAF + Semantic Adapter generation | 42 | 12,594 | 3,469 | 2227.2 |
| Shared-assessment prompt control generation | 42 | 21,359 | 3,187 | 1877.1 |

Total actual usage is **98,750 input + 19,934 output = 118,684 tokens**. CFAF including analysis uses 44,901 input and 10,437 output tokens, with mean end-to-end latency **4838.2 ms**. The optional control costs 42 additional generations (21,359 input, 3,187 output); analysis is shared and never double-billed in totals. Including shared analysis its mean latency would be 4488.1 ms. Single-repetition timing differences are descriptive, not a reliable performance ranking.

All 210 provider calls succeed and finish naturally. Strict interpretation yields **49 error-scored generated-system outcomes**: Standard 1, prompt-only 8, CFAF 5, shared control 35. Analysis/parser failures overlap in the shared control and must not be double-counted. No CFAF output-contract mismatch occurs. The invalid modes are Standard `NONE` once and prompt-only `RESTRICTED` eight times. The shared control returns null answers on 35 refusals. These are neither repaired nor attributed to truncation.

## E. Error analysis

`error_analysis.jsonl` explains **all 127 incorrect generated-system outcomes**, with record ID, original label, raw/primary prediction, status, selected mode, root-cause family and case reasoning. `CASE_RESULTS.md` gives all 42 original IDs/questions, system predictions and full case notes. Raw/public responses remain in `results.jsonl`; original contexts remain in `development_cases.jsonl`.

### CFAF's 14 primary errors

| Index | Expected | Outcome | Main explanation |
|---|---|---|---|
| 4 | `ANSWER_CORRECTLY` | CFAF | Benchmark ambiguity / request-relative sufficiency disagreement |
| 5 | `REFUSE_INFO_MISSING_IN_CONTEXT` | FULL | Semantic sufficiency error: placeholders mistaken for a complete answer |
| 11 | `REFUSE_AMBIGUOUS_QUERY` | FULL | Semantic misunderstanding: unresolved series reference |
| 12 | `REFUSE_AMBIGUOUS_QUERY` | ERROR | Evidence quotation validation failure; underlying semantic diagnosis not credited |
| 20 | `REFUSE_CONTRADICTORY_CONTEXT` | FULL | Benchmark ambiguity: contradiction scope versus actor identity |
| 23 | `ANSWER_CORRECTLY` | ERROR | Evidence quotation validation failure; underlying semantic diagnosis not credited |
| 28 | `REFUSE_CONTRADICTORY_CONTEXT` | FULL | Evidence labelling error: incompatible casting evidence promoted to PRIMARY |
| 30 | `REFUSE_CONTRADICTORY_CONTEXT` | ERROR | Evidence quotation validation failure; underlying semantic diagnosis not credited |
| 32 | `REFUSE_AMBIGUOUS_QUERY` | FULL | Semantic misunderstanding / unsupported pronoun resolution |
| 34 | `ANSWER_CORRECTLY` | CFAF | Benchmark ambiguity / request-relative sufficiency disagreement |
| 35 | `REFUSE_CONTRADICTORY_CONTEXT` | FULL | Benchmark ambiguity: mistaken counter-account may be a defeated claim |
| 36 | `ANSWER_CORRECTLY` | ERROR | Evidence quotation validation failure; underlying semantic diagnosis not credited |
| 39 | `REFUSE_CONTRADICTORY_CONTEXT` | ERROR | Evidence quotation validation failure; underlying semantic diagnosis not credited |
| 40 | `ANSWER_CORRECTLY` | CFAF | Semantic sufficiency error: unnecessary demand for further detail |

There are zero observed violations of the deterministic mode-selection rule: selected modes always follow the request-fulfilment flag. Failures enter through semantic understanding, evidence role/sufficiency assignment and quote validation. This does not vindicate the whole system; the architecture depends on those assessments.

### Baselines, control and response realization

The baselines often supply familiar external facts despite title-only evidence: Bible verses, Jefferson, Korean dates and Ruapehu's eruption year. They select actors/roles from conflicting or ambiguous passages. Some correctly state that no answer is supported but still declare FULL, so their low classification score does not mean all prose is factually wrong. Prompt-only RESTRICTED outputs fail the same frozen binary enum check.

The shared control's null answers are schema failures. All finish with `stop` and short output usage. Unlike the CFAF contract, its prompt does not enforce a nonempty explanation field strongly enough; the synthetic full-orchestration test used answerable copies and did not reveal this abstention behavior. This is a control-design flaw. Accepting/filling null after seeing results would change the frozen scoring rule and is not done.

Final CFAF generation copies the selected answer/explanation without added claims, so its principal FULL errors are proposed-answer/sufficiency errors rather than new final-generator hallucination. Case 5's placeholder response and case 11's first-series choice demonstrate why a supported sentence does not imply complete fulfilment. Cases 28/32 show missed conflict and unsupported reference resolution. Cases 23/36 show mechanically rejected otherwise plausible core answers. Each remains separately recorded.

### Benchmark ambiguities, with original labels retained

Case 4's positive label asks since 2010 but supplies a 1951 record. Case 34's positive label asks for a unique centre state from a list of seven states in a central zone. Refusals are defensible from runtime text even though scored wrong. Case 20's inconsistency concerns character chronology while the asked actor identity is explicit. Case 35 calls one competing historical account mistaken, allowing a correction/defeat reading. Cases 14, 17 and 24 show taxonomy overlap among ill-typed requests, missing detail, nonfactuality and false premise/granularity labels.

These are unblinded author interpretations, not adjudicated corrections. No original label is changed; no record is dropped, replaced or manually corrected. The primary scores always use the official annotations.

## F. Component contribution

The shared control's raw declared mode matches CFAF's selected mode on **42/42 cases**, including null-answer and invalid-analysis cases. This is an explicitly post-generation diagnostic; it does not change primary scoring or credit failed outputs. It supplies no observed evidence that the explicit gate improves coarse mode selection over prompting with the same assessments. The semantic properties largely determine both choices.

Contracts produce nonempty, selected-mode-consistent text while the control often returns null. That is a useful integration property, but different prompts/output handling confound its causal attribution. Evidence filtering, response contracts and validation are not independently ablated. Quote validation detects altered strings, not entailment; filtering cannot recover an unseen contradiction and may hide it from final generation.

The next ablation should freeze a common typed output schema and reason-text requirement, reuse identical assessments, then separately vary full versus verified-span context, contracts versus unconstrained realization, and validation enabled/disabled. Report semantic-analysis errors, specific reasons, complete answers and formatting independently. Do this on development sources before exposing new groups. **The current 66.7% versus 2.4% comparison does not establish an architectural reasoning advantage.**

## G. Readiness and next steps

**Not ready for frozen independent evaluation.** Blockers are zero live structured ambiguity/contradiction/refuted-premise recognition; 5/42 quotation-invalid analyses; 1/6 positive-class recall; placeholder, competing-role and pronoun-resolution errors; rationale/field inconsistencies; a null-answer control; no independent human support adjudication; and the pre-existing historical guard-test failure.

1. Improve and separately validate uncertainty distinctions using synthetic/development examples, especially competing referents, incompatible claims, missing identities versus placeholders, false premises and scope mismatch. Keep reserved groups untouched. Require consistency between rationale, structured fields and quoted counterevidence.
2. Introduce robust exact span/offset selection without changing this captured run. Keep semantic entailment errors distinct from punctuation/case/markup mistakes; do not silently normalize evidence after scoring.
3. Test complete request fulfilment, with positive enumeration/history examples and negative familiar-name/qualifier cases. Confidence needs independent calibration rather than a reliability assumption.
4. Enforce the same typed binary output schema and nonempty refusal text for all generated systems. Test answerable and abstaining live-format paths before the next freeze. Keep genuine failures visible.
5. Obtain blinded independent human review/adjudication for response support, complete fulfilment and disputed benchmark cases. Current assistant-authored reviews are insufficient for publication-level answer correctness.
6. Resolve the stale historical authorization-presence test in a separate maintenance change while preserving historical evidence. Do not remove artifacts simply to make tests green.
7. Define independence at source level. The dataset has 100 original source groups; ten prior and 42 development groups have been exposed, leaving at most **48 untouched source groups** (30 reserved plus 18 unused). Three hundred perturbation rows are not 300 independent source questions. A genuinely 300-source evaluation needs additional suitable source questions/datasets. Report group counts and preserve development/heldout separation.

The experiment demonstrates a functioning non-oracle FULL path and faithful application of the existing CFAF selector, while showing that the analyzer/integration do not yet support reliable external decisions. No API execution was blocked or simulated, and no reserved-case text was inspected. Correct live ambiguity/contradiction detection, independent human answer-support accuracy, component causality, all-green historical acceptance and 300-source generalization remain unestablished.

### Deliverables

All required files are under `evaluation/refusalbench_semantic_dev/`. Additional files preserve frozen source/prompt hashes, heldout metadata, exact API requests/events, semantic assessments, pipeline traces, raw responses, author reviews, every error and complete case notes. `CHANGED_FILES.txt` distinguishes the semantic additions from unchanged imported prior-pilot files. `validation_audit.json` records final budget, leakage, freeze and preservation checks; `checksums.sha256` covers the delivered files. The final commit SHA is returned with delivery. Nothing is pushed or merged.

Sources: [official dataset/card](https://huggingface.co/datasets/aashiqmuhamed/RefusalBench-NQ), [RefusalBench paper](https://aclanthology.org/2026.eacl-long.321/), [official structured-output documentation](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat), pinned InfoBank source, and the captured local artifacts. Documentation establishes interfaces; measurements and qualified interpretations come from this execution.
