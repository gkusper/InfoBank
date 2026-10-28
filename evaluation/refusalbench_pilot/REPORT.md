# RefusalBench-NQ / InfoBank CFAF: first-ten exploratory pilot

**Executed: 10 original benchmark records, 30 successful real generation calls.** Binary FULL/CFAF accuracy was **CFAF 10/10 (100%), Standard RAG 0/10 (0%), prompt-only control 0/10 (0%)**. These are descriptive behavior-label scores for this particular integration. **They do not validate semantic CFAF performance:** all ten expected labels are `REFUSE_AMBIGUOUS_QUERY`, and a missing upstream semantic labeller causes the unchanged CFAF gate to abstain on every input. An always-abstain rule would obtain the same binary score on this slice. No inferential statistics were calculated.

CFAF emitted the same generic evidence-insufficiency response ten times. It did not identify ambiguity in any case. Several baseline answers state facts explicitly present in the altered context even while violating the benchmark's required refusal behavior. A correct binary mode is not evidence that a full response or refusal explanation is correct.

## A. Environment and provenance

| Item | Recorded value |
|---|---|
| Repository | [gkusper/InfoBank](https://github.com/gkusper/InfoBank), cloned with `--branch wolala2026 --single-branch` |
| Exact base commit | `5f377de38312fb39c088551f9c74f8b6d4bd5080` |
| Experimental branch | `experiment/refusalbench-nq-pilot` |
| Original branch / publication | Original `wolala2026` untouched; no commits or pushes made |
| Official dataset | [aashiqmuhamed/RefusalBench-NQ](https://huggingface.co/datasets/aashiqmuhamed/RefusalBench-NQ) |
| Dataset revision | `b3684f805563e6ce465e7e9b055b840a48f519c2` |
| Selection | `load_dataset(..., split="test", revision=SHA).select(range(10))`; indices 0–9, in order, out of 1,600 test records |
| Selected-record checksum | SHA-256 `079bf26f98ca718487f71114e7935137042b3722324df7aa36691d5003454c8a` |
| Runtime-input checksum | SHA-256 `0046300c2a81a1f7f1880d5f2ee44a7c53909e93844795fb4ff74bd71d287339` |
| Serialization | Canonical JSONL: sorted keys, `ensure_ascii=True`, compact separators, UTF-8 and LF after each record |
| Python | `3.12.14 (main, Aug 25 2026, 14:01:42) [MSC v.1944 64 bit (AMD64)]` |
| Operating system | `Windows-11-10.0.26300-SP0` |
| Main dependencies | datasets 5.1.0, huggingface_hub 2.3.0, pyarrow 26.0.0, pytest 9.2.0 |
| Complete dependency versions | `requirements.lock.txt` and `generation_manifest.json` |
| Requested model | `gpt-4o-mini` |
| Returned model | `gpt-4o-mini-2024-07-18` on all 30 calls |
| Generation settings | Temperature 0; maximum 160 output tokens, including JSON; one repetition per system/case; JSON-object response format |
| API implementation | Existing `evaluation/wolala2026/real_api.py`, OpenAI Chat Completions over Python `urllib`; existing environment key used, never printed or written |
| Actual external use | 30 generation attempts, all successful; 0 embeddings; 0 upstream classifier calls; 0 scoring/judge calls; 0 retries |
| Run in UTC | 2026-10-28T09:25:47.624485+00:00 to 2026-10-28T09:26:41.100976+00:00 |
| Run in Europe/Budapest | 2026-10-28 10:25:47 CET to 10:26:41 CET |
| Generation-worker wall time | 53.476 seconds; setup, download, tests and review excluded |
| API blocker | None |

The original selected records, including original IDs, are retained without corrections in `cases.jsonl`. Their answer-key fields are for provenance/scoring only. Full generated JSON, final public text, response IDs, token usage and per-case timings are in `results.jsonl`; raw worker output is separately preserved in `generation_results.jsonl`.

Environment obstacles were resolved before live execution: the default Windows Python alias could not start; the bundled Python 3.12 interpreter and a workspace virtual environment were used. Initial package/test temporary-directory errors were resolved with writable workspace paths. Hugging Face initially hit Windows WinError 206 with a long cache path; short writable `HF_HOME` and `HF_DATASETS_CACHE` paths fixed it. These are setup incidents, not generated responses or successful benchmark executions.

## B. Methodology and limits of the existing implementation

### Existing code inspection

The experiment reuses all three existing adapters and the complete eight-stage pipeline. No existing algorithm, prompt, source file, frozen D1–D8 experiment or original evaluation result is changed in the final checkout.

- [pipeline.py](https://github.com/gkusper/InfoBank/blob/5f377de38312fb39c088551f9c74f8b6d4bd5080/evaluation/wolala2026/pipeline.py): query profiling copies declared fixture fields; evidence labelling copies declared source role/state/relation. It does not semantically infer these from arbitrary passages. Sufficiency accepts CURRENT/FULL/PRIMARY sources without testing textual entailment or query ambiguity. UNKNOWN evidence does not satisfy that gate.
- [pipeline.py, answer realization](https://github.com/gkusper/InfoBank/blob/5f377de38312fb39c088551f9c74f8b6d4bd5080/evaluation/wolala2026/pipeline.py#L523): `_runtime_supported_answer` prefers `gold_answer`, then `metadata.runtime_answer` or an aggregate view. Stage 7 also has a `gold_answer` fallback. None of those benchmark-derived answers is supplied here.
- [adapters.py](https://github.com/gkusper/InfoBank/blob/5f377de38312fb39c088551f9c74f8b6d4bd5080/evaluation/wolala2026/adapters.py): Standard RAG and prompt-only use raw retrieved text; CFAF uses the response contract produced by all eight stages. The original CFAF adapter can overwrite observed mode fields with the contract and backfill empty answer text. Primary scoring here reads the **raw model JSON identically for all systems**, so such repair cannot manufacture a correct prediction.
- [run_pilot.py](https://github.com/gkusper/InfoBank/blob/5f377de38312fb39c088551f9c74f8b6d4bd5080/evaluation/wolala2026/run_pilot.py): the existing runner is tied to internal fixture datasets and retrieval/embedding accounting. A separate narrow runner is necessary for the externally supplied context and first-ten selection. It does not execute internal held-out plans or D1–D8 work.
- [real_api.py](https://github.com/gkusper/InfoBank/blob/5f377de38312fb39c088551f9c74f8b6d4bd5080/evaluation/wolala2026/real_api.py): existing provider, model and generation parameters are reused. A subclass only logs requests/responses, counts real attempts before sending, enforces the hard cap and prevents embeddings.
- [backend_python/controlled_failure.py](https://github.com/gkusper/InfoBank/blob/5f377de38312fb39c088551f9c74f8b6d4bd5080/backend_python/controlled_failure.py) and [relevance.py](https://github.com/gkusper/InfoBank/blob/5f377de38312fb39c088551f9c74f8b6d4bd5080/backend_python/relevance.py): the backend has policy/risk and document-role heuristics, but no drop-in arbitrary-passage ambiguity/entailment/answer extractor for the fixture pipeline. Replacing the requested eight-stage algorithm with that backend, or assuming PRIMARY status, would obscure the missing functionality.

### Non-oracle bridge

`adapter.py` accepts **exactly** `perturbed_query` and `perturbed_context`; extra keys and non-string text are rejected. Preparation and generation are different processes. The generation command reads only `runtime_inputs.jsonl`, does not read original cases/provenance, and does not import the scoring module. Scoring joins labels after generation. Application-level data projection is enforced; this is not an OS filesystem isolation claim.

Original IDs are excluded because they contain perturbation class/intensity. The system uses neutral IDs such as `runtime-00` and a fixed `provided-context` source ID. No `original_query`, `original_context`, `original_answers`, `expected_rag_behavior`, `implementation_reasoning`, `verifier_votes`, `perturbation_class`, `intensity`, `lever_selected` or generator metadata is supplied to any evaluated component.

The adapter adds fixed generic QA profile fields and one source containing the complete, byte-for-byte string value of the original perturbed context. It performs no database retrieval, reranking, normalization, chunking, correction or replacement. FULL/PUBLIC access is an experimental permission to use the supplied public text, not an inferred evidence-sufficiency label. The source role is always UNKNOWN and relation NONE because no competent upstream semantic labeller is available. CURRENT is the existing default, not a recency assessment. No `gold_answer`, `runtime_answer`, requested answer text, expected CFAF decision or perturbation-derived role is injected.

This neutral missing-annotation policy has a deterministic consequence: the existing gate returns `NO_RELEVANT_SOURCE`, CFAF/ABSTAIN, even though a passage is present. That internal reason describes failure to find a qualifying labelled source; it is not a demonstrated finding that the text is irrelevant. The all-refusal outcome is a limitation exposed by the pilot, not a learned ambiguity prediction.

All systems receive the same question and original perturbed context at their input. The CFAF realization prompt receives the context in the unchanged contract's permitted evidence views, but the existing adapter omits the question from that final model payload. The pipeline itself receives the question. This limitation is recorded rather than silently repaired. No affirmative answer path with an independently extracted answer is exercised.

### Interpretation and scoring fixed before live calls

`prerun_protocol.json` records the Python source hashes, input hash, call budget and interpretation procedure before the first call. There were no post-generation edits to the frozen Python sources.

1. Parse the raw output as a JSON object. Require a nonempty string `answer` and an explicit string `top_level_mode` equal to FULL or CFAF. Do not use keyword heuristics, expected labels or CFAF adapter repairs. Malformed/empty output is unscorable, not a correct refusal; runtime errors and interpretation coverage are reported separately. All 30 actual outputs were valid, nonempty and ended with provider finish reason `stop`.
2. Map the original `ANSWER_CORRECTLY` to FULL and every original `REFUSE_*` to CFAF, without changing labels. Compare the declared behavior mode. A declared FULL may contain a qualified answer; mode/prose differences and answer support are reviewed separately.
3. For original refusal-category scoring, accept a unique explicit refusal code or clearly specific lexical reason from the six official categories. The patterns in frozen `scoring.py` are applied equally to all systems. Generic EVIDENTIAL/ABSTAIN is insufficient to choose a category. Multiple distinct matching reasons are unmeasurable. No output in this run supplied a specific refusal reason.
4. After generation, the report-authoring assistant reviewed every output against only its question and perturbed context. This is **not blinded independent human annotation**, not an extra model-judge API experiment, and not a test against real-world truth. `response_reviews.jsonl` records evidence and reasoning. Factual support asks whether material assertions are entailed, including any added referent/firstness/control claim; it does not mean the user question has been fully or uniquely resolved. Plausible host succession is accepted in case 2; pronoun attribution in case 5 is a moderate-confidence judgement. These judgement calls are explicitly exposed for re-review.
5. For generic CFAF responses there is no substantive factual answer to test. Their factual-answer support is marked **not applicable**, never counted as supported; their specific explanation is unmeasurable because it does not identify the ambiguity. This is not a claim that the entire refusal response is correct.

## C. Case-by-case results

The table retains every original record ID and label. “Correct” concerns binary behavior classification only. Full outputs and reviews are in `results.jsonl`; no responses are reconstructed or simulated.

| ID (index) | Question | Expected label | CFAF prediction | Correct? | Baseline results |
|---|---|---|---|---|---|
| `RB-NQ_claude_4925057086725798331_P-Ambiguity_HIGH_bd0591c4_1145` (0) | who wrote yakkity yak don't talk back | `REFUSE_AMBIGUOUS_QUERY` | CFAF / generic EVIDENTIAL abstention | Yes, binary only | Standard FULL: incorrect; prompt-only FULL: incorrect |
| `RB-NQ_claude_5911119091653953181_P-Ambiguity_HIGH_a7ae85a6_0196` (1) | where does the water come from to fill lake eyre | `REFUSE_AMBIGUOUS_QUERY` | CFAF / generic EVIDENTIAL abstention | Yes, binary only | Standard FULL: incorrect; prompt-only FULL: incorrect |
| `RB-NQ_claude_-8359866474144720253_P-Ambiguity_HIGH_8b8037bb_0073` (2) | Who hosted it when they replaced him? | `REFUSE_AMBIGUOUS_QUERY` | CFAF / generic EVIDENTIAL abstention | Yes, binary only | Standard FULL: incorrect; prompt-only FULL: incorrect |
| `RB-NQ_claude_-2382302837416986186_P-Ambiguity_HIGH_0dbd6c95_0483` (3) | who are the artists she told her that she recorded with | `REFUSE_AMBIGUOUS_QUERY` | CFAF / generic EVIDENTIAL abstention | Yes, binary only | Standard FULL: incorrect; prompt-only FULL: incorrect |
| `RB-NQ_claude_-6924600758326460563_P-Ambiguity_HIGH_3d9b445d_0443` (4) | when was the death penalty reinstated in oregon by one | `REFUSE_AMBIGUOUS_QUERY` | CFAF / generic EVIDENTIAL abstention | Yes, binary only | Standard FULL: incorrect; prompt-only FULL: incorrect |
| `RB-NQ_claude_-7941948650465895222_P-Ambiguity_HIGH_cc6cb691_0416` (5) | who gave the famous objective correlative theory | `REFUSE_AMBIGUOUS_QUERY` | CFAF / generic EVIDENTIAL abstention | Yes, binary only | Standard FULL: incorrect; prompt-only FULL: incorrect |
| `RB-NQ_claude_7610758795954724809_P-Ambiguity_HIGH_0b0c28ef_0240` (6) | What is the *premiere's* title? | `REFUSE_AMBIGUOUS_QUERY` | CFAF / generic EVIDENTIAL abstention | Yes, binary only | Standard FULL: incorrect; prompt-only FULL: incorrect |
| `RB-NQ_claude_-1176280233636154422_P-Ambiguity_HIGH_5d07a713_0182` (7) | when did the company take control of india | `REFUSE_AMBIGUOUS_QUERY` | CFAF / generic EVIDENTIAL abstention | Yes, binary only | Standard FULL: incorrect; prompt-only FULL: incorrect |
| `RB-NQ_claude_1023450971555923009_P-Ambiguity_HIGH_d5734c53_0967` (8) | who came up with the first working one | `REFUSE_AMBIGUOUS_QUERY` | CFAF / generic EVIDENTIAL abstention | Yes, binary only | Standard FULL: incorrect; prompt-only FULL: incorrect |
| `RB-NQ_claude_1803248910342766083_P-Ambiguity_HIGH_6a5fbb53_0168` (9) | who wrote the book my country my life | `REFUSE_AMBIGUOUS_QUERY` | CFAF / generic EVIDENTIAL abstention | Yes, binary only | Standard FULL: incorrect; prompt-only FULL: incorrect |

### Factual support assessed separately

A supported factual statement can still be a premature answer to an ambiguous query. “Not fully entailed” includes material inferences; it does not necessarily mean an invented entity or date. CFAF factual-answer support is N/A for all ten generic non-answers.

| Index | Standard RAG factual support | Prompt-only factual support | Principal remaining issue |
|---|---|---|---|
| 0 | Supported | Supported | Potential benchmark ambiguity: the query closely matches one distinct full title. Similar titles alone do not establish that every literal answer is unsupported. |
| 1 | Supported | Supported | Location-description support must be distinguished from uniquely identifying the river. A literal descriptive answer can be supported while failing the benchmark behavior label. |
| 2 | Supported | Supported | Host succession is a plausible context-based inference; claiming to have uniquely resolved the queried event is stronger than the passage warrants. |
| 3 | Supported | Supported | The journalists' interviewing clause and the recording clause support different relations. Both models follow the recording relation, but neither asks for the intended person. |
| 4 | Supported | Supported | Factual support and completeness differ: Standard RAG provides both dated events; prompt-only selects only one. The expected ambiguity refusal remains unchanged. |
| 5 | Not fully entailed | Not fully entailed | Support judgement is about entailment from the altered passage, not whether Eliot is the real-world historical answer. The confidence of this manual pronoun assessment is moderate. |
| 6 | Supported | Supported | Potential benchmark ambiguity: the passage directly lists the two titles. An answer listing both is a defensible literal reading despite the original refusal label. |
| 7 | Not fully entailed | Supported | Standard RAG adds an unsupported foothold-to-control inference. Prompt-only quotes supported background but presents it as FULL fulfillment of a question the passage does not settle. |
| 8 | Not fully entailed | Not fully entailed | This combines referent selection with an unsupported first-working claim; the named person/date alone being present is insufficient for complete-response support. |
| 9 | Supported | Supported | The prompt-only prose is more careful than its FULL classification: it offers both interpretations. Standard RAG selects only the memoir. Neither emits an ambiguity refusal. |

## D. Descriptive summary

| System | Successful / scheduled | FULL/CFAF accuracy | Predicted FULL / CFAF | Specific-reason accuracy | Runtime / interpretation errors |
|---|---:|---:|---:|---|---:|
| Standard RAG | 10/10 | 0/10 (0%) | 10 / 0 | N/A: 0 sufficiently specific predictions | 0 / 0 |
| Prompt-only control | 10/10 | 0/10 (0%) | 10 / 0 | N/A: 0 sufficiently specific predictions | 0 / 0 |
| CFAF pipeline + UNKNOWN-role adapter | 10/10 | 10/10 (100%) | 0 / 10 | N/A: 0 sufficiently specific predictions | 0 / 0 |

- Error category: each baseline has ten `REFUSE_AMBIGUOUS_QUERY` → FULL errors. CFAF has zero binary classification errors, but ten generic reason realizations without a measurable ambiguity category.
- Correct specific refusal reason coverage is **0/10 for every system**. Conditional category accuracy is undefined (0 measurable predictions), rather than a fabricated 0% or 100% conditional accuracy.
- Unnecessary refusals observed: zero for all systems. There are **zero expected-FULL cases**, so the unnecessary-refusal rate is **not estimable**. Absence of observed unnecessary refusal is not evidence of selectivity.
- Reviewed full answers not fully supported: **Standard RAG 3/10** (indices 5, 7, 8), **prompt-only 2/10** (indices 5, 8). The remaining 7/10 and 8/10 have supported factual content but still fail the original behavior label. CFAF has **0 full answers**; unsupported-full-answer rate is N/A, not proof of correctness. All ten CFAF outputs were reviewed but have no substantive factual-answer support assessment; the summary's `context_support_reviewed=0` means zero *evaluable binary factual-support judgements*, not that the outputs were ignored.
- Completion, interpretation and support coverage are explicit in `summary.json`. No model call failed or was skipped, and no completion hit the 160-token ceiling.

| System | Generation calls | Input tokens | Output tokens | Mean latency (ms) | Median (ms) | Min–max (ms) |
|---|---:|---:|---:|---:|---:|---:|
| Standard RAG | 10 | 3,693 | 663 | 1726.9 | 1687.4 | 1249.5–2783.3 |
| Prompt-only control | 10 | 4,353 | 702 | 1722.0 | 1631.3 | 1275.6–2752.6 |
| CFAF pipeline | 10 | 4,702 | 774 | 1885.4 | 1823.1 | 1608.5–2302.2 |

Total: **30 calls, 12,748 input tokens and 2,139 output tokens** (14,887 total). Token counts are the actual provider-reported usage, including prompts/JSON formatting; no fixture word-count estimate is used. Each latency is a wall-clock measurement around an adapter call, including local processing, network and provider time. The summed per-call time is 53.343 seconds. These sequential, single-repetition timings do not establish a reliable latency ranking, nor does the current CFAF wrapper save generation calls: it calls the model even for a fixed refusal.

### Deterministic verification, separate from model results

The separate `audit` command executed the unchanged eight stages for all ten projected inputs and checked pipeline invariants and exact context preservation. It made **zero API calls**. Its generic refusal output is fixture-driven behavior and is not represented as a live-model result. API counts in this report come from the audited provider, not the local pipeline's synthetic counters.

**48 tests and 13 subtests passed**, including leakage rejection, exact text preservation across the three adapters, all eight stage names, no injected gold/runtime answer, strict output interpretation, original binary/category mapping, the 30-attempt cap, embedding rejection, missing-result handling and overwrite prevention. Selected pre-existing CFAF smoke/label/exposure/trace/request-relative tests also passed. `test_results.xml` preserves the final successful test output.

Three pre-existing smoke artifacts (`data_inventory.json`, `example_internal_trace.json`, `smoke_results.json`) were temporarily regenerated by the repository's existing smoke test. The preservation check detected this, and they were restored to HEAD before final scoring. Final SHA-256 comparison confirms **all 381 original tracked files match their pre-experiment bytes**, including existing CFAF outputs and frozen D1–D8 experiments. No original tracked file is changed in the delivered checkout. Future regression runs should execute these existing smoke tests in an isolated copy to avoid their artifact-writing side effects.

## E. Critical analysis of each case and shared failures

### Shared CFAF outcome: correct coarse mode, missing semantic evidence

All ten cases follow the same mechanism: UNKNOWN role → no qualifying PRIMARY source → `NO_RELEVANT_SOURCE` → CFAF/ABSTAIN → fixed public reason. The permitted context still contains the original passage, so the failure is not lost retrieval. The pipeline has no implemented route from arbitrary input text to a reliable evidence role, a query ambiguity decision or a supported extracted answer.

There were no CFAF binary classification errors on this slice. There were ten missing specific-reason predictions, and the statement that currently usable evidence does not support the request is not a demonstrated textual analysis. Its grounding in fixture labels is inadequate to establish correct explanation or complete-response correctness. No claim of successful ambiguity detection, transfer to external benchmarks or coverage of the FULL path is justified.

### Individual cases

**0. who wrote yakkity yak don't talk back**

Standard RAG: Tommy Johnson is explicitly attributed to the near-exact title in the question. The answer is context-supported even though the benchmark requires refusal because of the similar competing title. Prompt-only: Same supported attribution as Standard RAG. Exact-title matching is a defensible literal reading; the original refusal label is retained unchanged. Potential benchmark ambiguity: the query closely matches one distinct full title. Similar titles alone do not establish that every literal answer is unsupported. Both declared FULL and therefore fail the original binary label. CFAF's generic abstention matches the coarse label but does not identify this case's particular ambiguity.

**1. where does the water come from to fill lake eyre**

Standard RAG: Paraphrases the supplied flood/river description without inventing a river name. It shortens the attachment chain and does not identify an unambiguous named source. Prompt-only: Repeats the full descriptive river phrase and flood frequency. The descriptive facts are supported, but the attachment ambiguity and unnamed river remain unresolved. Location-description support must be distinguished from uniquely identifying the river. A literal descriptive answer can be supported while failing the benchmark behavior label. Both declared FULL and therefore fail the original binary label. CFAF's generic abstention matches the coarse label but does not identify this case's particular ambiguity.

**2. Who hosted it when they replaced him?**

Standard RAG: The broad Nick Hancock-to-Lee Mack hosting succession follows the first two sentences. The response assumes which replacement event the pronouns designate; it does not resolve the question's ambiguous it/they/him. Prompt-only: Same succession interpretation and unresolved event reference as Standard RAG. No new host name is invented. Host succession is a plausible context-based inference; claiming to have uniquely resolved the queried event is stronger than the passage warrants. Both declared FULL and therefore fail the original binary label. CFAF's generic abstention matches the coarse label but does not identify this case's particular ambiguity.

**3. who are the artists she told her that she recorded with**

Standard RAG: All three names appear in the recording clause. Returning those names is supported as a list, but does not identify who the repeated she/her pronouns refer to. Prompt-only: The asserted recording partners appear verbatim; retaining she leaves the source ambiguity in place rather than disambiguating it. The journalists' interviewing clause and the recording clause support different relations. Both models follow the recording relation, but neither asks for the intended person. Both declared FULL and therefore fail the original binary label. CFAF's generic abstention matches the coarse label but does not identify this case's particular ambiguity.

**4. when was the death penalty reinstated in oregon by one**

Standard RAG: Both reinstatement dates are explicitly supported. Listing both events does not interpret the malformed qualifier by one. Prompt-only: 1978 and popular vote are supported, but this selects one event and omits the second reinstatement in 1984 without resolving by one. Factual support and completeness differ: Standard RAG provides both dated events; prompt-only selects only one. The expected ambiguity refusal remains unchanged. Both declared FULL and therefore fail the original binary label. CFAF's generic abstention matches the coarse label but does not identify this case's particular ambiguity.

**5. who gave the famous objective correlative theory**

Standard RAG: The nested he/him chain permits Eliot or the colleague as the person who gave the theory. The response commits to Eliot without qualification; the second sentence does not explicitly name that poet. Prompt-only: Same unqualified resolution to Eliot. World knowledge may make the answer familiar, but it does not remove the passage's unresolved pronoun alternatives under this context-only assessment. Support judgement is about entailment from the altered passage, not whether Eliot is the real-world historical answer. The confidence of this manual pronoun assessment is moderate. Both declared FULL and therefore fail the original binary label. CFAF's generic abstention matches the coarse label but does not identify this case's particular ambiguity.

**6. What is the *premiere's* title?**

Standard RAG: Both episode titles are explicitly stated as the premiere's constituents. The answer is a supported interpretation of the premiere as a two-episode event. Prompt-only: Same two supported titles. The wording treats two episode titles as the premiere title, without asking whether the user means an episode or the broadcast event. Potential benchmark ambiguity: the passage directly lists the two titles. An answer listing both is a defensible literal reading despite the original refusal label. Both declared FULL and therefore fail the original binary label. CFAF's generic abstention matches the coarse label but does not identify this case's particular ambiguity.

**7. when did the company take control of india**

Standard RAG: Changes gained a foothold into gained control of India starting in 1611. The passage does not date national political control, and the identity of the company is also ambiguous. Prompt-only: The 1611 and 1612 factory/foothold statements are supported, but they answer a different relation from take control and do not disambiguate British versus Dutch company. Standard RAG adds an unsupported foothold-to-control inference. Prompt-only quotes supported background but presents it as FULL fulfillment of a question the passage does not settle. Both declared FULL and therefore fail the original binary label. CFAF's generic abstention matches the coarse label but does not identify this case's particular ambiguity.

**8. who came up with the first working one**

Standard RAG: Dalton and 1803 are in the passage, but one could refer to an atomic theory, law, periodic table or another development. First working atomic theory is not established in the context. Prompt-only: Same unsupported choice of the referent atomic theory and added first working qualification. The passage also supplies Mendeleev's different scientific contribution. This combines referent selection with an unsupported first-working claim; the named person/date alone being present is insufficient for complete-response support. Both declared FULL and therefore fail the original binary label. CFAF's generic abstention matches the coarse label but does not identify this case's particular ambiguity.

**9. who wrote the book my country my life**

Standard RAG: The memoir attribution is explicitly supported. Selecting it alone leaves the equally titled novel unaddressed. Prompt-only: Both author/genre attributions are supported and the response explicitly acknowledges the second book, partly communicating the ambiguity while declaring FULL. The prompt-only prose is more careful than its FULL classification: it offers both interpretations. Standard RAG selects only the memoir. Neither emits an ambiguity refusal. Both declared FULL and therefore fail the original binary label. CFAF's generic abstention matches the coarse label but does not identify this case's particular ambiguity.

### Benchmark ambiguities and scope

Cases 0 and 6 are particularly clear examples where an exact-title or two-title response is defensible from the passage even though the official label requires refusal. Cases 1, 2, 3, 4 and 9 also allow supported descriptive, succession, partner-list, date-list or multiple-author statements. These observations are report-author interpretations of the actual runtime text, not manual corrections, adjudicated benchmark errors or reasons to discard records. All original labels remain authoritative for the reported primary score.

The first ten records form a highly ordered slice: all expected refusals, all the ambiguity category, and (in metadata available only to scoring/analysis) all HIGH-intensity Claude-generated perturbations. No randomization or replacement was performed. This slice cannot test answerability, refusal tradeoffs, other refusal categories, generators or intensity levels. Original answers are references to unperturbed items and were not used as automatic answer keys for these altered inputs.

## F. Recommendations before 100–300 further cases

1. **Build and separately validate the missing upstream components.** Infer task/query ambiguity, claim-relative role, entailment, temporal relevance and source relations only from permitted input. Preserve an explicit unknown state. Do not infer PRIMARY from retrieval presence or derive roles from expected behavior. The CFAF mode-selection rules should remain fixed during evaluation.
2. **Provide a real answer realization path.** Independently extract a grounded answer with evidence before admitting FULL; remove or strictly quarantine all `gold_answer` fallbacks from external evaluation. Pass the actual question into the CFAF realization payload. Test contract/prose consistency after model realization, retaining both raw and final outputs.
3. **Represent reason categories without post-hoc guessing.** Define a justified bridge between CFAF reason/realization states and the six benchmark codes, with explicit unmeasurable/unknown predictions. Distinguish ambiguity from absent information; do not relabel this generic EVIDENTIAL refusal as successful ambiguity recognition. Freeze the common output schema/interpreter before new data are run.
4. **Create an answerable and varied development set separate from the scored set.** Include supported answers, missing evidence, contradictions, ambiguous references, false premises and negative controls where neutral UNKNOWN role would expose blanket refusal. Tune only there; do not tune the algorithm on these ten evaluated cases.
5. **Define independence by source question.** The official dataset is built from 100 base Natural Questions items. Multiple perturbations of the same source are dependent. A future 100–300-row run cannot be described as 100–300 independent source questions from this dataset; split/group by source question, report the number of distinct source groups, and avoid source overlap across development and held-out evaluation. Any later uncertainty analysis must respect clustering. This pilot has no significance tests.
6. **Pre-register the larger run.** Pin revisions and checksums, archive source/prompt hashes and input projection, state sampling and category coverage, keep one common interpretation procedure, define token/call budgets and stop conditions, and prevent overwrite/resume without an explicit new run identity. Keep all upstream classifier/answer-extractor costs visible.
7. **Improve independent response review.** Use blinded human review with a fixed rubric and adjudication for disputed passage/label cases, including the moderate-confidence judgments here. Score factual entailment, answer completeness, specific refusal reason, unnecessary refusal, unsupported answer and mode/prose agreement separately. Do not present supported fact extraction as behavior-label success or blanket refusal as semantic correctness.
8. **Isolate regression tests and retain runtime auditability.** Existing smoke tests write artifacts; run them in a disposable copy. Assert the exact benchmark context reaches every system, audit all forbidden fields and ID-derived hints, retain raw payloads/finish reasons, and budget any future retries or classifiers explicitly. Investigate the extra CFAF generation call for deterministic refusals only in separately evaluated development work.

### What could not be validly evaluated

Nothing blocked the requested first-ten live execution. What remains **unmeasurable or unimplemented** is semantic CFAF label inference, the independently grounded FULL-answer path, specific refusal-category accuracy (no sufficiently specific predictions), unnecessary-refusal rate (zero answerable cases), complete-response correctness of the generic refusal explanations, real-world truth against the original NQ answers, independent human-adjudicated response accuracy, and generalization or statistical significance. These missing measurements are not filled in with deterministic outputs, oracle labels or fabricated scores.

### Deliverables and exact changes

All additions are under `evaluation/refusalbench_pilot/`; no original tracked file is modified. `CHANGED_FILES.txt` lists every added deliverable. Required files are `REPORT.md`, `cases.jsonl`, `results.jsonl`, `summary.json`, `run_experiment.py` and `README.md`. Additional files preserve the minimal adapter/scorer/tests, runtime projection, environment/protocol/source integrity, exact API payloads and events, raw live results, separate deterministic audit and post-generation reviews. `validation_audit.json` records final preservation, prompt/input, budget and secret-exclusion checks; `checksums.sha256` covers the delivered experiment files.

Sources: [official benchmark card and task taxonomy](https://huggingface.co/datasets/aashiqmuhamed/RefusalBench-NQ), [RefusalBench paper](https://aclanthology.org/2026.eacl-long.321/), [official GPT-4o mini documentation](https://developers.openai.com/api/docs/models/gpt-4o-mini), and [Chat Completions API reference](https://developers.openai.com/api/reference/python/resources/chat/subresources/completions/methods/create). Claims about this execution are supported by the local manifests, requests, responses and reviews, rather than documentation descriptions.
