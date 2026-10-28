# CFAF null-response and span-reference fix: balanced 10-case pilot

**Engineering result:** all 40 generated outputs have nonempty answer text and valid common schemas; all **8/8 requested evidence references** resolve exactly to original text. All ten semantic results pass structural/reference validation. These facts do not establish correct semantic reasoning.

**Development result:** CFAF and the corrected shared control both score **7/10 accuracy, 70% balanced accuracy, FULL recall 3/5 and CFAF recall 4/5**. Their mode choices agree on all ten cases. The contradiction case still produces an unjustified FULL answer. Both systems restrict two positive-labelled questions because of unsupported qualifiers. The original decision rules are unchanged.

The work was time-boxed to the user's 30-minute limit. Started 2026-10-28 14:24:55 UTC. Actual model execution: 2026-10-28T14:35:55.921680+00:00 to 2026-10-28T14:37:27.848985+00:00, 91.927 seconds. Total elapsed delivery time is returned in the final message.

## A. Null-response root cause and correction

The previous shared-control outputs were traced through outbound semantic assessment, prompt, response format, raw API response, worker output, parser and scorer. **35/42 application JSON answer fields were already null in raw API message content**, which exactly matches worker raw output. All calls returned JSON strings and stopped normally. No refusal text was lost by an adapter or parser; these are not null transport messages, token truncations or safety-refusal envelopes.

All 35 null outputs received a semantic `answer_candidate: null`. The old prompt asked for an explanation but did not explicitly distinguish absence of a factual candidate from user-visible refusal text. Generation used `json_object`, with no typed public schema. Thus null was syntactically permitted, although contrary to the intended nonempty-answer/scorer contract. The evidence is consistent with the model copying the absence of a candidate into public answer. Model-internal causation cannot be proven from logs; the confirmed source defect is the under-specified/un-enforced public response contract. The scorer correctly rejected null under its documented policy.

The fix applies to **all four generated systems**: one strict six-field JSON Schema, answer type string, binary mode enum FULL/CFAF, required fields, no extra properties, and explicit common instructions requiring nonempty public answer text in both modes. A null semantic candidate must not be copied to public answer. Local validation also rejects empty/whitespace text. The shared control still chooses its mode freely. Invalid raw outputs would remain errors; none is silently filled or replaced.

In this new pilot the shared control produces **10/10 valid nonempty answers, including six CFAF explanations**, with 0 null answers. All other systems also have 0 null/invalid outputs. This establishes the observed engineering behavior on these ten cases, not a universal reliability rate. Two CFAF FULL outputs retain literal string `"null"` in optional metadata fields; public answer text is valid, and these metadata values are preserved rather than converted. The schema currently permits optional free-form strings; semantic metadata typing can be tightened separately.

See `null_response_root_cause.md` and `null_response_evidence.json`. The frozen 42-case responses, report and scores are unchanged and were not rescored.

## B. Deterministic span references

`span_references.py` segments each original string into 430-character windows with 70-character overlap. Each catalogue record contains neutral source_id, stable span_id, start_offset, end_offset and source digest. Offsets are **zero-based, half-open Python Unicode character offsets**, not byte offsets. No source character, punctuation, capitalization, quotation mark, ellipsis or Markdown marker is normalized or corrected. Windows can cut words; overlap preserves full coverage, and the original complete context is also supplied to analysis.

The model returns supporting and contradicting span-ID arrays. Code validates that each ID/source exists, offsets are valid, source digest is unchanged and the record exactly matches the deterministic catalogue. Quotes are obtained only as `original_context[start:end]`. An invalid reference invalidates analysis explicitly; another span is never substituted. Repeated identical text retains the selected span's actual offset rather than the first textual occurrence.

Both supporting and contradicting references are resolved and retained. Any identified counterevidence reaches the existing fulfilment checker; the unit test shows it blocks FULL even if the model asserts SUFFICIENT. The analyzer can still fail to identify counterevidence, as it does in live case 8. Existence of a reference does not establish entailment, sufficiency, PRIMARY role or correct mode.

**Live validity: 8 requested references, 8 valid, 0 invalid; exact extraction 8/8.** Three analyses request no spans because they find no relevant support; these are not counted as extra successful references. All ten analyses are structurally valid. No contradicting span is selected in the live sample. Two supporting references are retained in the ambiguous-song case, but its uncertainty is misclassified.

Synthetic tests cover all five prior failure forms. A separate zero-API representation replay over the five already exposed previous contexts verifies complete character coverage and exact extraction, including the altered quote/case/punctuation/ellipsis/formatting patterns. It does not rerun models or recompute previous predictions/scores. See `previous_pattern_replay.json` and `span_reference_validation.json`.

The existing eight stages and actual top-level mode selector are reused unchanged through the prior semantic entry point. The new module only maps validated references to its existing evidence-span representation. No gold answer, perturbation metadata or expected behavior reaches the analyzer/generator. No decision rule was tuned to the selected labels.

## C. Automated tests and preservation

**70 tests pass:** the complete prior 43-test semantic experimental suite plus 27 targeted tests. Coverage includes null/empty CFAF text, nonempty explanations/FULL answers, common schema, missing/invalid IDs, source mismatch, invalid/counterfeit offsets, unchanged source hashes, exact Unicode/punctuation/Markdown extraction, multiple/overlapping spans, repeated-substring offsets, retained counterevidence, leakage rejection, unchanged FULL/CFAF behavior and frozen-file preservation. Tests use synthetic responses only and incur no real API calls.

The relevant original CFAF regression suite runs in an isolated exact-Git-blob copy: **77 passed test functions, 13 passed subtests, one known historical failure**. The old plan-only guard asserts absence of an authorization file already committed at the research base. This same previously documented failure remains; no historical artifact was removed to make it green. No new regression is observed. Both XML reports are delivered separately.

All 444 previously tracked files, including both prior RefusalBench experiments, original CFAF code, frozen D1–D8 and publication results, retain exact byte hashes. Only new files under `evaluation/refusalbench_span_fix_v1/` are added. The original branch is not changed, pushed or merged.

## D. New balanced development pilot

### Selection and execution

Base: `f8aaf117764c919993fd076143793c8f8fbe0bb8`; working branch `experiment/cfaf-span-ref-fix-v1`. Official RefusalBench-NQ revision `b3684f805563e6ce465e7e9b055b840a48f519c2`, seed `20261028`. Five ANSWER_CORRECTLY and five distinct refusal categories are selected before new outputs exist. All ten are previously unexecuted records from ten distinct groups within the existing 42 development groups. **No reused record, reserved group or extra untouched group is used.** Metadata-only selection precedes materialization of these ten full records.

Inputs contain exactly perturbed_query/perturbed_context. Original label-bearing IDs, annotations, original answers and explanations remain in trusted selection/scoring only. The same original query/context reaches all systems; CFAF final realization uses permitted program-extracted spans and the actual question. One semantic analysis per case is shared by CFAF/control.

Model `gpt-4o-mini`; returned version `gpt-4o-mini-2024-07-18`; temperature 0; one repetition; output limits 160 for generation and 1,500 for analysis. Source/prompt/schema/projection/scoring hashes are frozen before execution. **50 real API attempts: 10 analysis + 40 generation; hard cap 60; no retries, embeddings or extra judges.** All calls succeed and finish with stop. No outputs are simulated or silently repaired.

Cases SHA-256: `54fe025c056a65686d327e0c27892fa6a925e1e83a93894ae157df3e9f2fb0a2`. Runtime SHA-256: `910f6a68808240117b38e655af24e36cd2c82c0eefa16828329a997aefe2ac4c`. Complete settings/dependencies/hashes are in the manifests and protocol.

### Case-by-case binary results

FULL/CFAF correctness uses the original labels unchanged. The case number maps to original ID/question/context in cases.jsonl and selection_manifest.json. Full generated answers and separate contextual reviews are in `RESPONSES.md`, `results.jsonl` and `response_reviews.jsonl`.

| Case / question | Original expected | Standard RAG | Prompt-only | CFAF | Shared control |
|---|---|---|---|---|---|
| 0: What is the weight of Puerto Rico's power source? | `REFUSE_FALSE_PREMISE_IN_QUERY` | FULL | CFAF | CFAF | CFAF |
| 1: who is the second edition of valley of the dolls based on | `ANSWER_CORRECTLY` | FULL | FULL | CFAF | CFAF |
| 2: who played cory's older brother on boy meets world after winning Best Actor? | `ANSWER_CORRECTLY` | FULL | FULL | CFAF | CFAF |
| 3: Which member of the Committee of Five wrote most of the Declaration of Independence? | `ANSWER_CORRECTLY` | FULL | FULL | FULL | FULL |
| 4: If West Bengal had never been partitioned from Bengal, must Prafulla Chandra Ghosh have still become the first chief minister? | `REFUSE_NONFACTUAL_QUERY` | FULL | CFAF | CFAF | CFAF |
| 5: who wrote i'm in the mood for dancing and what was their inspiration? | `REFUSE_GRANULARITY_MISMATCH` | FULL | FULL | CFAF | CFAF |
| 6: who is often associated with printing the first book using moveable type in germany | `ANSWER_CORRECTLY` | FULL | FULL | FULL | FULL |
| 7: who wrote this song | `REFUSE_AMBIGUOUS_QUERY` | FULL | FULL | CFAF | CFAF |
| 8: where are the cones in the eye located | `REFUSE_CONTRADICTORY_CONTEXT` | FULL | FULL | FULL | FULL |
| 9: who does brant daugherty play in pretty little liars | `ANSWER_CORRECTLY` | FULL | FULL | FULL | FULL |

### Metrics

| System | N | Accuracy | Balanced accuracy | FULL recall | CFAF recall | Null/invalid |
|---|---:|---:|---:|---:|---:|---:|
| Always FULL | 10 | 50% | 50% | 100% | 0% | 0 |
| Always CFAF | 10 | 50% | 50% | 0% | 100% | 0 |
| Standard RAG | 10 | 50% | 50% | 100% | 0% | 0 |
| Prompt-only | 10 | 70% | 70% | 100% | 40% | 0 |
| CFAF + span references | 10 | 70% | 70% | 60% | 80% | 0 |
| Shared-assessment control | 10 | 70% | 70% | 60% | 80% | 0 |

| System | Unnecessary refusal | Failure to restrict | Correct specific reason coverage |
|---|---:|---:|---:|
| Standard RAG | 0/5 (0%) | 5/5 (100%) | 0/5 |
| Prompt-only | 0/5 (0%) | 3/5 (60%) | 0/5 |
| CFAF + span references | 2/5 (40%) | 1/5 (20%) | 1/5 |
| Shared-assessment control | 2/5 (40%) | 1/5 (20%) | 1/5 |

CFAF/control confusion matrices are gold FULL → 3 FULL, 2 CFAF; gold CFAF → 1 FULL, 4 CFAF. Standard is FULL → 5/0 and CFAF → 5/0. Prompt-only is FULL → 5/0 and CFAF → 3/2. All ERROR cells are zero; full matrices are in confusion_matrices.json. No inferential significance is calculated.

Specific-reason coverage uses the same frozen lexical interpreter as before, applied to valid public answer text for every system. A correct coarse mode with an incorrect or mixed reason never earns specific-reason credit. This conservative lexical measure can miss a semantically useful explanation without canonical wording: shared case 4 explicitly explains the hypothetical limitation, but its wording is unmapped. No post-hoc keywords are added to improve the score.

### Response support and semantic errors

Behavior labels do not provide complete gold answers for altered contexts. Gold-backed grounded-answer accuracy and independent human-adjudicated correctness therefore remain unmeasurable. All 40 outputs have separate unblinded report-author contextual reviews; these are not blinded human annotations or extra judge API results. Material assertions, complete request fulfilment and mode/prose agreement are separate fields; uncertain judgments stay null.

| System | Declared FULL | Material assertions not fully supported | Clearly grounded complete core FULL | Mode/prose disagreements |
|---|---:|---:|---:|---:|
| Standard RAG | 10 | 3 | 2 | 2 |
| Prompt-only | 8 | 3 | 2 | 0 |
| CFAF + span references | 4 | 2 | 2 | 0 |
| Shared-assessment control | 4 | 2 | 2 | 0 |

These are diagnostic author annotations, not independent answer-accuracy estimates. In particular, Gutenberg is named, but the source does not explicitly establish the first-book-in-Germany assertion; the fully correct behavior label does not prove that stronger generated claim. Two positive cases add an unsupported second-edition/award qualifier, creating legitimate scope questions about an expected FULL answer. Labels are unchanged, and no adjudicated correction is claimed.

**Remaining CFAF/control errors:** cases 1 and 2 refuse original ANSWER_CORRECTLY records because the added edition/award constraints are not established. Case 8 answers FULL despite explicit inside/outside-retina contradiction. In case 7, coarse CFAF is correct but the internal cause is granularity_gap while its own rationale says ambiguous. The shared control gives the clearer ambiguity explanation. Representation is valid throughout; these are semantic interpretation/sufficiency/reason errors, not formatting failures.

The absence of a weight in case 0 is described as missing information rather than the official false-premise category. Case 5 correctly withholds unsupported inspiration but likewise uses missing information rather than the original granularity category. Complete and exact evidence extraction does not guarantee any of these category interpretations.

### Actual cost and latency

| Component | Calls | Input tokens | Output tokens | Mean incremental latency (ms) |
|---|---:|---:|---:|---:|
| Shared semantic analysis | 10 | 9,766 | 1,707 | 2489.2 |
| Standard RAG generation | 10 | 5,683 | 667 | 1703.9 |
| Prompt-only generation | 10 | 6,343 | 684 | 1629.8 |
| CFAF + span references generation | 10 | 6,010 | 624 | 1649.1 |
| Shared-assessment control generation | 10 | 8,154 | 718 | 1694.1 |

Total provider usage: **35,956 input + 4,400 output = 40,356 tokens**, with 50/60 permitted attempts used. Analysis is shared rather than counted twice. All finish reasons are stop; no retries, embeddings, extra validation calls or truncations occurred. Per-case tokens, latency, response IDs, schemas, reference catalogues and raw responses are preserved in the logs. This is a single-repetition development pilot, not a latency ranking or significance analysis.

## E. Comparison with the frozen 42-case experiment

| Failure type | Previous observation | New engineering result / remaining issue |
|---|---|---|
| Null public answers | 35/42 shared-control outputs already null at API level | 0/10 shared-control and 0/40 overall null answers; common typed contract applied before generation |
| Quote/reference representation | Five generated-quote mismatches | No generated quote text; 8/8 requested IDs resolve exactly, 0 invalid IDs; five historical forms covered by synthetic/extraction replays |
| Semantic misunderstanding | Ambiguity/contradiction and reason confusion | Still present: case 7 rationale/structured cause disagree; case 8 contradiction ignored |
| FULL/CFAF decision | Overrestriction and unsupported FULL | Still present: two positive-labelled refusals and one contradictory-context FULL |
| Specific refusal reason | Coarse refusal often had wrong cause | CFAF and shared control each have only 1/5 correct reason coverage under the frozen lexical rule, for different cases |
| Shared-control fairness | Most abstention responses unscorable | All control responses are now valid public text, enabling a direct within-sample comparison |

The samples differ in class balance, records and context perturbations. **The new 70% aggregate accuracy is not compared with the previous 66.7% as an estimate of improvement.** The representation/schema fixes are supported by source inspection, deterministic tests and the new observed format/reference validity. No old score or response was rewritten.

Within the new ten-case sample, CFAF and shared-control mode choices agree on all ten inputs, with the same primary metrics. This is no evidence of an explicit-gate reasoning advantage. The control independently chooses modes and may give a partial factual answer plus an explanation; CFAF realizes its fixed contract. Differences in response detail remain visible.

## F. Next recommendation

The output/reference path is ready for a **larger development-only diagnostic experiment**, provided the known semantic failures remain explicit and independent evaluation is not claimed. The targeted null and quotation-representation blockers are resolved in this pilot. They are not evidence of a validated semantic system.

Before an expensive broader semantic run, focus on: structured ambiguity versus granularity distinctions; detected counterevidence and contradictory claims within a single span; consistency between rationale and structured fields; positive FULL recall under auxiliary qualifiers; and independent complete-answer/entailment review. Consider sentence-aware/subspan references for convenience, without changing original text or weakening source binding. Tighten optional metadata enums to prevent literal `"null"` strings, without retroactively normalizing this capture.

The fair shared-assessment comparison is now operational at the public-response level. Keep a common enforced schema and one shared analysis per case. Better specific-reason codes and human adjudication would reduce lexical-scoring ambiguities. Preserve the existing reserved groups and untouched sources. This remains development work, not readiness for a frozen independent 300-case evaluation.

### Deliverables and preservation

Only new files under evaluation/refusalbench_span_fix_v1/ are added. Full generated responses are in results.jsonl and RESPONSES.md; separate contextual assessments are in response_reviews.jsonl. The root-cause evidence, reference validation, synthetic tests/XML, original regression XML, selection/protocol/source hashes, exact API logs, complete pipeline traces and checksums are supplied. CHANGED_FILES.txt lists exact additions; validation_audit.json records preservation/leakage/budget checks. The final local commit SHA is returned with delivery. No push or merge occurs.

Sources: [official RefusalBench-NQ dataset](https://huggingface.co/datasets/aashiqmuhamed/RefusalBench-NQ), [official structured-output API documentation](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat), pinned local source and preserved raw API artifacts. All measured outcomes above come from the actual new run; prior data is used only for diagnosis and representation replay.
