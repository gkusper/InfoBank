# InfoBank CFAF Semantic Integration v2: query scope and metadata binding

## Outcome and interpretation

Status: completed ten-case pilot and forty fresh full-run observations. This is a development/regression study using previously exposed synthetic InfoBank cases. It is not independent validation, a new holdout or evidence of broad natural-language generalization. One repetition is used. The pilot and full experiment use the same frozen `semantic-integration-v2.1` implementation, model and prompts; the full experiment executes all forty observations fresh, with no pilot or v1 output reuse.

| System | Mode accuracy | Balanced accuracy | FULL recall | CFAF recall | Unnecessary CFAF | Failure to restrict | Pairs both correct |
|---|---:|---:|---:|---:|---:|---:|---:|
| semantic_cfaf | 100.0% | 100.0% | 100.0% | 100.0% | 0 | 0 | 20/20 |
| shared_control | 100.0% | 100.0% | 100.0% | 100.0% | 0 | 0 | 20/20 |


## 1. What caused P2 failures, and what changed?

Semantic v1 jointly inferred request scope and evidence sufficiency. Its analyzer sometimes emitted INDIVIDUAL even while extracting the correct aggregate count and marking it sufficient. The deterministic selector then correctly rejected the misprofiled request. The targeted repair separates query-only profiling from source reasoning. A conservative English grammar emits explicit count, sum, average, other aggregate, individual record, metadata, content, action or unresolved requirements before retrieval. It receives no access flags, labels or answers. It preserves mixed requirements: a supported average does not authorize listing individual records. An adjective such as 'individual' in 'how many individual invoices' is not itself a request to list them.

The semantic analyzer now evaluates each existing requirement and its supporting spans; it does not output or override request_scope. Every requirement must be supported, policy-compatible and grounded in primary evidence before the existing unchanged `TopLevelModeSelectionStage` can select FULL. A count does not establish an average; this semantic distinction still depends on the evidence assessor, and the functional negative test supplies an explicitly missing-average assessment. See query_profile_spec.md and the actual grammar for its bounded coverage.

## 2. What caused P3 failures, and how does binding work?

V1 exposed the authorized metadata values but omitted titles and identifiers, leaving no trustworthy target-to-view association. The model consequently treated metadata as unrelated to the requested document. The legacy retrieval structure supplied only ranked candidates, not an authoritative target assertion. V2 extends that interface with private catalogue resolution AFTER authorization projection. It matches the target phrase extracted from the actual query against explicit retrieval_aliases, or the ordinary source title used solely as an internal catalogue label for legacy records. It requires a unique authorized target match. Neither a single retrieved item nor the presence of metadata alone is sufficient.

The model sees only neutral view IDs and TRUSTED_QUERY_TARGET, UNRESOLVED or AMBIGUOUS status. Private titles, aliases, original IDs and match counts stay local. The assertion establishes association, never sufficiency or broader access. Requested metadata fields must still be whitelisted, present, supported and accompanied by valid primary spans. Wrong targets, multiple matches, missing fields and body-text requests are tested as restrictions. A policy, whitelist, source-content or target change invalidates the old assertion. Forged binding objects and modified query profiles are rejected before external calls. No case ID, expected answer, family, variant or original evidence annotation participates in profiling or association.

This is an in-process experimental retrieval contract, not authenticated production retrieval or cryptographic attestation. It assumes the local catalogue is legitimate and correctly named. Exact lexical matching and bounded target extraction are limitations. It deliberately does not restore private titles to metadata content or invent a binding to recover a benchmark score. See metadata_binding_spec.md.

## 3. Architecture and security

The eight pipeline stage names remain, and the original top-level selector is imported unchanged. All 536 previously tracked files, including every v1 result and original annotations, retain their initial working-byte SHA-256. FULL exposes authorized content; AGGREGATE only aggregate_view; METADATA only whitelisted scalar fields; DENY/non-public sources no view or binding. Neutral IDs are allocated after filtering. A hidden source does not change permitted match cardinality. Span catalogues, hashes and character offsets refer exclusively to permitted view text. Runtime answers, fixture roles, relations, evidence states, gold and case/pair/family identifiers are excluded from model inputs.

Every external call revalidates the request profile, policy snapshot, permitted projection and exact binding. The two generators receive identical query, views, profile, binding and shared semantic assessment. The control never receives the gate decision, fulfilment flag or CFAF response contract. Both use the existing strict six-field response schema and nonempty answer contract. P5 uses the identical deterministic zero-view response for both systems, without external calls; public trace objects are response-only whitelist objects. Internal audit records may distinguish no source from hidden DENY.

Security status: PASS. No observed forbidden model-input exposure, protected-content leak, unauthorized span or invalid binding. P5 equality checks: 4 pairs, all passed. Verified reference occurrences: {"requirement_support": 16, "source_role": 32, "supporting_spans": 24}. Binding statuses: {"TRUSTED_QUERY_TARGET": 28, "UNRESOLVED": 4}. These metrics cover exact forbidden strings, binding provenance, span resolution and public equality; arbitrary paraphrased disclosure is not automatically measurable.

## 4. Regressions and new synthetic tests

The prior semantic/span/governed suites pass 131 tests. The new suite passed 61 tests before API execution and 63 after two additional post-run boundary checks, including the thirty constructed scenarios. The historical CFAF suite, run from exact current-HEAD Git blobs in a disposable checkout, passes 77 tests plus 13 subtests, with the same known `test_preheldout_attempt1_plan_artifacts_are_plan_only` failure because its supposedly absent authorization artifact is committed. No new security or structural regression remains. Initial Windows sandbox TEMP permission failures and archive-induced newline/checksum differences are preserved in diagnostic logs; a workspace temp directory and exact git cat-file extraction resolved those environmental artifacts. Frozen originals were not changed, and historical 360 generation/40 embedding calls were not repeated.

The new dataset contains ten aggregate examples, ten metadata examples and ten negative/adversarial examples with new names, values, document types and wording. Expected behavior comes from documented construction rules before system execution. Query parsing, projection, binding, reference resolution, all eight stages and the selector actually execute. All thirty profile and mode expectations pass. Semantic responses are controlled test doubles, not live model inference. Therefore 30/30 is functional coverage of governed plumbing under specified upstream assessments, not measured semantic accuracy, independent validation or additional real-API observations. Negative controls include a count that cannot answer an average, mixed disclosure requirements, missing fields, wrong/ambiguous targets, body text, hidden DENY, no source and unresolved intent.

## 5. Ten-case real-API pilot

Requested first pairs from P1 through P5 were used. CFAF accuracy 100.0%; shared-control accuracy 100.0%. Pilot attempts: 24, hard cap 40. Required P2/P3 behavior and all security/infrastructure gates passed before full execution.

| Pilot pair | CFAF A/B | Control A/B |
|---|---|---|
| H3PAIR_P1_01 | FULL / CFAF | FULL / CFAF |
| H3PAIR_P2_01 | FULL / CFAF | FULL / CFAF |
| H3PAIR_P3_01 | FULL / CFAF | FULL / CFAF |
| H3PAIR_P4_01 | FULL / CFAF | FULL / CFAF |
| H3PAIR_P5_01 | CFAF / CFAF | CFAF / CFAF |

No frozen pilot prompt was silently changed or replayed. Models use gpt-4o-mini, temperature zero, analysis limit 1500 and generation limit 160, one shared analysis for each nonempty-view case. P5 is logged as a deterministic no-model path.

## 6. Full forty-case results and comparison

| Family | Original fixture CFAF | Semantic v1 | Semantic v2 | Shared control v2 |
|---|---:|---:|---:|---:|
| P1 | 8/8 | 8/8 | 8/8 | 8/8 |
| P2 | 8/8 | 4/8 | 8/8 | 8/8 |
| P3 | 8/8 | 4/8 | 8/8 | 8/8 |
| P4 | 8/8 | 8/8 | 8/8 | 8/8 |
| P5 | 8/8 | 8/8 | 8/8 | 8/8 |


CFAF FULL recall changed from 50.0% in v1 to 100.0%; CFAF recall changed from 100.0% to 100.0%. Unnecessary refusals changed from 8/16 to 0/16; failures to restrict from 0/24 to 0/24. Per-family counts, conditional rates, confusion matrices and matched-pair results are in full_40_summary.json and pair_level_results.json. The original fixture-labelled treatment had privileged, predeclared roles, sufficiency information and some answers; its historical 100% mode score is not equivalent to runtime inference. V1 control was 87.5% and v1 CFAF 80%; stochastic run differences and changed upstream inputs prevent attributing all differences solely to a single code change. No significance claim is made.

## 7. Error attribution and explanation correctness

No binary mode errors in this run. This does not establish absence of semantic or explanation errors.

Source-role agreement with historical fixture roles, evaluated only post hoc, is 24/32. A correct binary decision can coexist with a wrong role, rationale or candidate. Request profiling, bindings, role inference, sufficiency, selection, generation and validation are recorded separately in raw observations and semantic_diagnostics.json. No selector source modification is involved; cases rejected because an upstream property is wrong remain upstream failures.

Among correctly restricted cases, CFAF public reason-class matches are 24/24; control 15/24. V1 corresponding values were 16/24 and 8/23. V2 derives governance/privacy reasons from requested detail versus permitted views, instead of always emitting an evidential abstention. Missing evidence, unresolved target and missing permitted fields retain evidential explanations. Governance/granularity and forbidden-body causes are logged separately. Correct class matching does not establish every fine-grained explanation sentence: those text-cause judgments require human review. The shared schema still allows arbitrary string reason/realization values, so a literal string such as 'null' is a reason-semantic error rather than an invalid JSON answer; any occurrence is retained and scored.

## 8. FULL-answer fulfilment

Mode accuracy is not answer correctness. 32/32 emitted FULL responses satisfy the narrow simple-fact coverage checks against permitted token, count, metadata-field or action/date content. Uncertain paraphrases remain manual-review cases. All answer reviews explicitly require independent human review; no broad semantic answer-accuracy percentage is asserted. CFAF additionally verifies exact copying of its generated semantic candidate, but copying alone does not establish truth. A FULL response on a gold-restricted query is separately recorded as no established complete fulfilment. The synthetic adversarial tests show that trusted binding alone never authorizes missing fields or body content.

## 9. Actual API usage and reproducibility

Total actual external attempts: 120; successes 120, errors 0. Input tokens 120919, output tokens 14599. Per-kind counts: {"semantic_analysis": 40, "semantic_cfaf": 40, "shared_control": 40}. Observed model versions: {"gpt-4o-mini-2024-07-18": 120}. Summed client call latency 244.78 seconds, not end-to-end user latency or model-only speed. No automatic retries or embeddings. Shared analysis is charged once. Full-run observations are fresh and not mixed with pilot/v1 outputs. Manifests freeze runtime, prompts and scoring source hashes; old dependencies are additionally protected by the previous-file snapshot. Raw payloads/outcomes, strict schema, caps, deterministic no-model paths and cache policy are logged. Credentials are excluded.

The experiment is on `experiment/infobank-semantic-integration-v2`, parent `5a95abe933cda134ff4f1be0e82614df6934d987`. CHANGED_FILES.txt lists every committed file; checksums.sha256 covers deliverables excluding itself. The final commit SHA is provided in the completion reply after committing this report, avoiding a self-referential commit hash inside its own contents. No push or merge is authorized or performed.

## 10. Limitations before independent validation

The targeted corrections are evaluated on known synthetic development cases; even perfect fixture scores would not establish generalization. Query interpretation uses a bounded English grammar, not a general multilingual parser. Metadata resolution assumes trustworthy local catalogue labels and exact target matching. Binding is policy-aware association, not proof of evidence sufficiency. Controlled synthetic tests do not evaluate an LLM's semantic inference on those new examples. Primary evidence roles and per-requirement support still depend on model judgments. Reason classes are easier to validate than complete explanations, and simple fact checks do not replace independent answer adjudication. One repetition does not estimate run-to-run variability.

Before independent evaluation, freeze a new unseen entity/source set with annotations established independently of this implementation, validate real principal-scoped retrieval and revocation, broaden query paraphrases/compositional requirements, test malicious and ambiguous catalogue inputs, and independently adjudicate complete answers and explanation causes. Preserve the current permission projection, requirement accounting, span checks, shared-control independence and P5 indistinguishability tests. Generic contradiction detection remains outside this iteration.

## Additional critical interpretation

Both systems reached 40/40 mode correctness and 20/20 correct matched pairs, so this run shows no incremental binary-accuracy advantage of the deterministic gate over the shared-assessment control. It does show recovery of useful FULL behaviour under the governed upstream representation: P2 and P3 each changed from 4/8 to 8/8 for CFAF, while P1, P4 and P5 remained 8/8. The control benefits from the same improved profiles and target bindings. This is a joint integration revision, not a factorial ablation: the control prompt also explicitly requests appropriate reason classes and warns that a missing statement is not proof of nonexistence. Its P1 change cannot be attributed only to query scope or metadata binding.

CFAF refusal-class coverage improved from 16/24 to 24/24. The control improved from 8/23 to 15/24, retaining nine wrong/null reason-class values despite correct modes. Fine-grained wording remains a human-review task. There were no observed wrong binary decisions, malformed/nonempty-answer failures or live API errors in v2. All 32 emitted FULL texts passed the simple permitted-fact checks; this remains narrower than independent answer adjudication.

A post-run audit compared the actual transmitted payloads for all forty nonempty-view case observations across pilot and full phases (eight plus thirty-two). Every analysis and generator used identical query/profile/views/bindings within its case; both generators used the identical assessment, and all control inputs omitted the response contract and gate flags. All 120 external attempts were audited (24 pilot, 96 full); ten zero-view observations across phases made no external calls. Full-run source-role agreement was 24/32 against fixture roles used only after the run.

## Remaining role and scoring limitations

All four contextual P1 browser-history sources and all four contextual P4 coordination notes were labelled PRIMARY/NONE by the model rather than the fixture CONTEXTUAL role. Across all four non-P5 restricted families there were 16 PRIMARY/NONE assignments. Those inconsistencies are preserved, not repaired to gold. Overall support and per-requirement support remained missing and no grounded candidate was supplied, so the gate correctly restricted the answers. The perfect binary score therefore conceals a systematic evidence-role labelling weakness: v2 role agreement is 24/32, compared with 23/32 in v1. This is a semantic diagnostic failure, not a malformed schema or protected-data exposure. Improving role consistency needs a separately versioned development iteration and independent annotations.

Primary mode and matched-pair scoring was frozen before the live pilot/full run. Supplemental role agreement, refusal-class and simple-fact checks are explicitly post-hoc descriptive diagnostics in post_run_analysis.py; they do not change primary mode outcomes, generation outputs or previous v1 scores. The supplement is hashed in the completed manifest, not presented as a preregistered frozen scoring method. Neither the shared-control equality in mode accuracy nor the CFAF reason-class advantage establishes general superiority beyond these known cases.
