# ComponentBasaedCFAF v1.1 - targeted repair and paired development study

## Recommendation

**Keep the combined compact C2 configuration experimental.** The two targeted natural-language InfoBank requests recover, and measured tokens/latency fall. Native mode accuracy nevertheless declines from 80% to 70% on InfoBank and from 70% to 50% on RefusalBench-NQ. C2 has five application failures versus C1's three reference failures and one connection error. Exact quotation checks preserve mechanical integrity; they do not establish semantic support or complete fulfilment.

This is one exposed development comparison: exactly ten fixed InfoBank, ten fixed RefusalBench-NQ and the original ten GaRAGe cases. No new sample/download, QASPER TEST, independent student holdout or protected/unused source group is used. GaRAGe has no manufactured binary gold. There is no pooled accuracy or generalization claim. Qualitative findings are non-independent Codex review.

## Baseline and freeze

Completed v1 HEAD: `ca2e3e111c63fbd67ff8965e5b05f3530a85c8a0`. Its earlier starting base `bfd80bbfe2ccbb251da46bdc22b791dad5b9341f` is not the completed v1. The clean worktree and branch `ComponentBasaedCFAF` were verified before edits. Annotated local freeze tag: `component-cfaf-v1-freeze-20261029T170700Z`; tag object `2736c8247411d43fa3959661fdd8391cf2d9d6dc`. All 66 public component files and nine private original result files are protected by hash. Other worktrees, historical branches/tags and manuscript remain unchanged.

A and fresh C1 load the exact completed-v1 source snapshot in separate processes. B runs the original deterministic guard on the exact A generation with no extra call. C2 loads the new frozen code with explicit CompactSDKProvider injection. All arms use the same question, as-of value, source order, neutral IDs and exact permitted source text. Already-present private application catalogue metadata may bind C2 targets, but no private authority fields reach the model. The input envelopes differ by design: compact requirements versus original inventory/span catalogues. Actual traffic and public references are audited against context/request hashes.

Conservative task start was 2026-10-29 17:07:00 UTC, retained with a monotonic anchor. Code, prompt, schema and tests froze at 17:44:44 UTC, 2264 seconds after start, after preflight passed. Inference began once preparation was complete, before the maximum milestone times. The final completion receipt records actual elapsed time against the 120-minute limit. All 83 model attempts started before the 18:52 UTC no-new-call deadline. No further model calls are required.

Request alias: gpt-4o-mini. All 82 returned responses identify gpt-4o-mini-2024-07-18. Temperature 0; official SDK 1.59.9; strict JSON Schema; retries zero; no JSON repair, second judge, NLI or embeddings. A/C1 output cap 2048; C2 1536 chosen on fictional preflight before inference. All returned finish reasons are stop; one C1 connection failure has unknown token usage. Schema success/stop does not establish answer completeness.

## Execution interruption and recovery

After 14 complete pairs, case 15 C1 persisted CONNECTION_ERROR and its ledger RESULT, while the original controller's 60-second process wait expired. There were 37 settled attempts and no pending Python worker. The new orchestration-only resume script preserved the original clock/counter, skipped every existing or attempted case/system, and executed only never-started work. Frozen worker/runtime/prompt/schema bytes were unchanged. No request was retried and no case was retaken.

The resumed controller waits 120 seconds; SDK timeout remains 45 seconds with zero retries. Two recovered process-wall values (case 15 A/C1) are unknown and excluded, not recorded as zero; internal E2E values remain available. recovery_audit.json records the preserved partial-output hashes and fixed remaining case indices. All 83 attempts are now settled, and all 30 paired cases complete.

## P1: bounded structured request resolution

A small injected StructuredRequestResolver uses a field registry, conservative trusted target names/catalogue titles and separate metadata value typing. It supports file/document type, creation/modification dates and two explicit fields. Target uniqueness, permitted fields, complete obligations, requested precision and current policy/request bindings are required. Ambiguous, denied, missing or stale bindings cannot authorize deterministic FULL. It is not a broad NLP parser.

The new natural-language typed COUNT/SUM/MEAN path validates operation, metric, unit, population, contributor IDs/deduplication, row authorization, finite values, threshold and requested dates. It reuses the pure aggregate executor and verifies the permitted structured snapshot against recomputation. It never promotes numbers found in arbitrary prose to application facts. COUNT additionally requires a countable-metric attestation.

The actual recovered aggregate pilot fixture has permitted prose but no typed numeric rows. It therefore uses one ordinary call and MODEL_ATTRIBUTED support. The recovered two-field metadata case is genuinely trusted and zero-call. The old literal metadata[field]/aggregate[operation] compatibility route retains v1's trust in upstream application snapshot validation; it does not independently reconstruct missing threshold/population provenance. That residual assumption remains explicit.

## P2: exact quotation references

The compact wire proposes sparse local evidence IDs, neutral permitted source IDs and short exact quotations. The application resolves a unique occurrence to offsets, checks supplied authorized membership, source/inventory SHA-256 and request/policy binding, and rechecks public citation/claim associations. Repeated quotes, unknown IDs, nonexistent text and invalid offsets fail. No whitespace/fuzzy/nearest-neighbor repair or model correction is used. Proven decimal aliases remain supported only when they map to real catalogue entries.

REFERENCE_VALID means mechanical reference integrity. MODEL_ATTRIBUTED and SUPPORT_NOT_INDEPENDENTLY_VERIFIED remain separate from APPLICATION_STRUCTURED provenance. A valid quote does not authorize permission or independently establish factual truth. The gate still depends on model-proposed claim/requirement associations for ordinary semantics.

## P3: compact strict proposal

The full internal contracts/gate remain; CompactProposal is the smaller wire boundary. The application supplies authoritative requirements once. The model proposes claims, sparse quotation evidence, missing requirement IDs and an unresolved Boolean. The application derives repeated support fields and links. See SCHEMA_SIMPLIFICATION.md for each old field's gate/security/renderer/audit use and treatment.

Static schema+prompt tokenizer count falls 1558 to 847 tokens. Fictional one/three/six-claim compact examples use 126/340/661 tokens. Both 1024 and 1536 fit; 1536 was frozen to retain margin. These are synthetic preflight counts, not API usage or speed evidence. The model is never asked for final mode or application authority.

A material weakness emerged: mapping a claim to a requirement with no missing ID implicitly asserts complete fulfilment. A limitation-shaped non-answer can therefore become FULL. Deterministic rendering also cannot restore an essential name omitted from public claim text. No post-outcome heuristic, prompt/schema change or benchmark-specific repair was added.

## Native mode outcomes

Operational fallbacks remain failures in the planned ten-case denominator, never successful evidential CFAF. Unnecessary refusal counts successful FULL-gold to CFAF outcomes; failure to restrict counts successful CFAF-gold to FULL outcomes. Recalls include operational failures in the corresponding native class denominator.

| Cohort | System | Correct | Balanced accuracy | FULL recall | CFAF recall | Unnecessary refusal | Failure to restrict | Operational |
|---|---|---|---|---|---|---|---|---|
| InfoBank | A | 10/10 | 100% | 100% | 100% | 0 | 0 | 0 |
| InfoBank | B | 10/10 | 100% | 100% | 100% | 0 | 0 | 0 |
| InfoBank | C1 | 8/10 | 75% | 50% | 100% | 2 | 0 | 0 |
| InfoBank | C2 | 7/10 | 75% | 100% | 50% | 0 | 2 | 1 |
| RefusalBench-NQ | A | 8/10 | 80% | 100% | 60% | 0 | 2 | 0 |
| RefusalBench-NQ | B | 8/10 | 80% | 100% | 60% | 0 | 2 | 0 |
| RefusalBench-NQ | C1 | 7/10 | 70% | 80% | 60% | 0 | 2 | 1 |
| RefusalBench-NQ | C2 | 5/10 | 50% | 60% | 40% | 2 | 2 | 1 |

InfoBank has four native FULL and six CFAF labels; RefusalBench has five of each. Gold labels are unchanged. Case 16's passage gives character inspirations without establishing the requested edition qualifier; C2's refusal still counts wrong under native FULL. Case 12 also merits a label/completeness scope review. These observations do not silently revise the scores.

Paired InfoBank correctness: five both correct, two C2-only, three C1-only. RefusalBench: three both, two C2-only, four C1-only, one neither. Case 15 C2-only includes a C1 connection failure and is not evidence of semantic repair. Fresh same-configuration C1 differs from the historical original C1 in four served modes; the old outputs document variability and are not substituted for fresh results. The complete change set is compared, with no isolated-rule causal or statistical generalization claim.

## GaRAGe and reference reliability

All ten A/B outputs are FULL. C1 has seven FULL and three operational CFAF fallbacks; C2 also has seven FULL and three operational CFAF fallbacks. Neither has a successful evidential CFAF in this cohort. No GaRAGe accuracy, balanced accuracy, FULL recall or invented answerability gold is reported.

Fresh C1 invalid-span errors occur on cases 21, 24, 26. The original v1 pilot's three span-error cases were 22, 24, 26. On those original three regressions C2 fails on 22, succeeds on 24 and still fails on 26; fresh C1 succeeds on 22 and fails on 24/26. Eliminating the model's span-ID field therefore did not establish reduced reference-format failure.

C2 has QUOTE_NOT_FOUND on cases 13, 21, 22, 26, plus APPLICATION_VALIDATION_ERROR on case 4. Offline reparse of case 4's saved response reproduces INVALID_MISSING_REQUIREMENT: natural-language text was supplied instead of a requirement ID in missing. This diagnosis uses the same frozen expansion function, with no new call or output repair. Case 13 proposes substantive quotation text absent from a title-only view and is correctly withheld. C2 has five application failures versus C1's three application failures; C1's separate connection error makes four total operational failures. Reference reliability did not improve.

All 61 released C1/C2 citation links mechanically revalidate: C1 28 model-attributed links, C2 31 model-attributed links plus two application-structured metadata-field links. Zero mechanically invalid public citations were accepted. This is a boundary-check result, not semantic correctness. Omitted sources remain NOT_ASSESSED (85 per system); assessed roles are C1 34 PRIMARY, one CONTEXTUAL, two IRRELEVANT; C2 34 PRIMARY, two IRRELEVANT. These are model assessments, not independent annotations.

## Actual resource use

| System | Attempts | Reported input | Reported output | Provider sum s | E2E sum s | E2E median s | E2E max s |
|---|---|---|---|---|---|---|---|
| A | 28 | 72,131 | 3,164 | 98.497 | 99.154 | 2.645 | 7.033 |
| C1 | 28 | 99,008 | 9,735 | 216.446 | 217.225 | 4.675 | 57.841 |
| C2 | 27 | 44,892 | 5,494 | 104.382 | 105.104 | 3.290 | 8.091 |

The primary all-planned comparison retains every outcome. C1 reported token totals omit the unknown usage of its connection failure; missing usage is not true zero. Its provider time includes 57.779 seconds for that failure. C2 also has an extra zero-call metadata case. Therefore all-arm percentages are not clean like-for-like efficiency estimates. Reported aggregate output reduction is 43.56%, with those caveats. C2's summed provider time still exceeds ordinary A (104.382 versus 98.497 seconds); C2 is not claimed faster than ordinary RAG.

The secondary comparison uses 26 identical cases where both C arms actually generated and returned provider usage. It excludes two P5 cases, the extra C2 metadata shortcut and the C1 connection failure. It retains local gate failures when a provider response exists. Input tokens fall 97,434 to 43,983 (54.86%); output 9390 to 5373 (42.78%). Provider sum falls 152.872 to 100.723 seconds (34.11%). Internal E2E sum falls 153.565 to 101.416 seconds (33.96%). Paired C2-C1 E2E differences have mean -2.006 seconds and median -1.454 seconds. Common-set E2E medians are 4.675 to 3.386 seconds, maxima 10.332 to 8.091. Provider medians are 4.657 to 3.357 seconds, maxima 10.299 to 8.063. This is an observed one-run reduction with worse mode outcomes, not a production or population guarantee.

SDK provider time includes response parsing. Internal E2E starts before preparation and excludes interpreter/client construction. Process-wall includes startup, with 29 known A/C1 values versus 30 C2; those unequal populations are not used for the paired speed claim. Identical timing wrappers leave frozen source bytes unchanged. C1 has 24,576 cached input tokens; A/C2 none. Token savings do not equal invoiced dollar savings; no monetary/current-price claim is made.

| System | Attempt N | JSON bytes sum | Median bytes | Max bytes | Provider median s | Provider max s |
|---|---|---|---|---|---|---|
| A | 28 | 16094 | 201.5 | 1762 | 2.709 | 7.010 |
| C1 | 28 | 37317 | 924.5 | 3263 | 4.754 | 57.779 |
| C2 | 27 | 22868 | 536 | 2662 | 3.404 | 8.063 |

The failed C1 attempt has zero returned response bytes because no body was returned, not because output was more efficient. Configured C2 cap 1536 is separate from actual output usage. All 82 returned finish reasons are stop; no observed truncation. Successful schema/finish status still permits incomplete semantic answers.

Separate local phase totals across all 30 cases:

| System | Gate ms | Renderer ms | Public validator ms |
|---|---|---|---|
| A | 0.000 | 0.000 | 0.000 |
| C1 | 21.511 | 2.830 | 2.508 |
| C2 | 13.731 | 4.822 | 4.054 |

B adds zero calls/tokens and 0.694 ms total local guard processing (median 0.018 ms, max 0.088 ms). It inherits A's generation cost: deployed B costs A plus this local step. A has no CFAF gate/renderer; zero phase entries there mean not applicable.

Actual attempts: A 28, C1 28, C2 27, B zero additional, total 83/100, all settled. Both P5 cases use zero calls in every applicable arm and identical public responses. Complete C2 metadata is the third zero-call case. No case/system is attempted twice. Optional N0/R0/S0 and factorial ablations are NOT_RUN. Effects cannot be attributed separately to profiling, resolver, reference format or schema.

## Answer quality and refusal semantics

Codex, the implementer, screened all 30 C2 public outcomes using the actual query, permitted passage text for native cases and cited text with surrounding windows for GaRAGe. This is non-independent, unblinded and not an exhaustive every-source adjudication. A/B/C1 have no new independent answer-quality scores. Flags below are diagnostic observations, not percentages or relabelled targets. Full text/traffic stays private under local/CASE_REPORT.md; qualitative_review.json contains public paraphrases.

- Request completeness: cases 2/8 publish statements of missing information as FULL; 18 omits the requested person despite the private value/citation; 23 lists hosting options with little comparison; 25 substitutes a general practice for the particular risk-management account.
- Unsupported assertions: 19 infers necessary counterfactual consequences from actual infrastructure facts; 20 extrapolates a national century-scale trend from limited examples; 28/30 add causal explanations not established by cited text.
- Entity/subject/relation mismatch: 25 replaces a specific obligation with a general acquisition practice; 30 converts selection and an operating-model description into approval causes.
- Temporal/geographic overgeneralization: 20 expands state examples to the full country/century. Forecast conditions matter in 27, and potential/current framing and adverse evidence in 28.
- Missing qualifiers: 27 merges predictions without attribution and a material condition on the extreme forecast. The edition qualifier in 16 is a native-label scope concern; 28/30 retain causal uncertainty.
- Valid citations: every public C link resolves mechanically. C2's 31 model-attributed links remain independently semantically unverified. Two metadata links have application-structured provenance, which does not authenticate the host's metadata as real-world truth.

The CFAF renderer and final validator enforce approved internal reason/realization templates and reject factual answer text copied into a restricted response. Operational fallbacks are explicitly OPERATIONAL, not credited as evidential refusals. Actual C1/C2 public outputs pass internal/public consistency checks. This does not establish that every model-declared missing obligation is semantically correct, and it does not rescue false FULL decisions.

## Tests, governance and simplicity

Before freeze, all 86 component tests pass: 54 preserved original tests plus 32 new parametrized cases. The immutable completed-v1 snapshot separately passes 54. Fictional coverage includes metadata single/two fields and value/access typing; target ambiguity/denial; COUNT/SUM/MEAN; wrong metric/unit; contributor deduplication/threshold/dates; stale hashes/revocation; exact/missing/repeated quotations; bad source IDs and safe aliases; missing requirements/multipart dependencies; title conjunctions; source roles; provider refusal/truncation; deterministic rendering/wrong refusal text; P5 equality and one/zero calls. Existing interchangeable-retriever, quota and payload-isolation tests remain unchanged. Tests catch explicit contract violations; they do not prove all natural-language completeness errors are caught.

Isolated historical compatibility: 691 pass, three full-cache metadata tests explicitly deselected to avoid reading unused/protected RefusalBench records. Their exact names/reason are in regression_audit.json. No test was altered. The older original suite has 77 passes plus 13 subtests and one known pre-existing failure: a committed HELDOUT_RUN_AUTHORIZATION.json conflicts with a plan-only assertion. That archived file is preserved. Scratch-only newline representation changes and archived timer rebasing are documented; prior worktrees and annotations are untouched. This is not a claim that every historical test passes unconditionally.

Actual-traffic audit checks exact context/as-of/order, prompt/schema against freeze, one attempt per system/case, no private gold/authority payload fields, no second judge/model, source freeze hashes and P5 equality. All supplied forbidden-marker checks find zero disclosures, and publication links validate. These bounded checks are not a proof against every sensitive inference or a substitute for authenticated application policies.

Meaningful runtime grows 698 to 917 (+219): 750 owned, 167 copied. Physical lines 808 to 1042; AST statements 826 to 1128; functions/methods 55 to 72; bytes 49,397 to 69,713. Eighteen runtime files, eight injected ports, nine concrete components. Adapter counts are a subset, not additive. The historical static closure is 60 files / 4636 meaningful lines with broader/different functionality, not an equivalent replacement-size claim; it is not imported at runtime. Third-party library source is excluded from owned runtime, not claimed absent.

No new mandatory runtime dependency. Pydantic 2.12.3, OpenAI 1.59.9, httpx 0.28.1 remain fixed; only own package version becomes 0.1.1. tiktoken 0.12.0 is development-only in a separate tools environment, not imported by runtime. No optional NLP/NLI model is installed/used. Redundant requirement/source/hash/span/support/rationale serialization is removed or locally derived; semantic uncertainty remains explicit.

## Reproduction and delivery

README.md documents installation, current tests and the five paths in examples/v1_1_demo.py. The final ordinary path makes exactly one mocked SDK request and zero external calls. This demonstrates the interface, not live accuracy; the live evidence is the frozen 83-attempt run. Benchmark context, gold, complete outputs and sensitive traces remain ignored in results/local/ and results/v1_1/local/. Public results contain aggregate metrics, hashes, diagnostics and paraphrases only.

Completed run/resume commands are documented for audit; do not rematerialize or retune these exposed cases. Fresh reproduction of inference needs a new authorized study/manifest, not overwriting this result. Offline demo/tests remain runnable. CHANGED_FILES.txt lists exact changes from completed v1. checksums.sha256 covers the new public result folder and changed component files excluding itself/private caches. The adjacent completion receipt records final SHA, elapsed time, checksum integrity and clean worktree. Original v1 reports/checksums/manifests remain unchanged and refer to the freeze-tag tree. No push or merge.

## Complete paired outcomes

Case numbers below are one-based (JSON index + 1). No raw question or gold text is reproduced. OP marks an operational CFAF-shaped fallback, not an evidential refusal success.

| Case | Cohort | A | B | Fresh C1 | C2 |
|---|---|---|---|---|---|
| 1 | InfoBank | FULL | FULL | FULL | FULL |
| 2 | InfoBank | CFAF | CFAF | CFAF | FULL |
| 3 | InfoBank | FULL | FULL | CFAF | FULL |
| 4 | InfoBank | CFAF | CFAF | CFAF | OP:APPLICATION_VALIDATION_ERROR |
| 5 | InfoBank | FULL | FULL | CFAF | FULL |
| 6 | InfoBank | CFAF | CFAF | CFAF | CFAF |
| 7 | InfoBank | FULL | FULL | FULL | FULL |
| 8 | InfoBank | CFAF | CFAF | CFAF | FULL |
| 9 | InfoBank | CFAF | CFAF | CFAF | CFAF |
| 10 | InfoBank | CFAF | CFAF | CFAF | CFAF |
| 11 | RefNQ | CFAF | CFAF | CFAF | CFAF |
| 12 | RefNQ | FULL | FULL | FULL | CFAF |
| 13 | RefNQ | CFAF | CFAF | CFAF | OP:APPLICATION_VALIDATION_ERROR |
| 14 | RefNQ | FULL | FULL | FULL | CFAF |
| 15 | RefNQ | FULL | FULL | OP:CONNECTION_ERROR | FULL |
| 16 | RefNQ | FULL | FULL | FULL | CFAF |
| 17 | RefNQ | FULL | FULL | FULL | FULL |
| 18 | RefNQ | FULL | FULL | FULL | FULL |
| 19 | RefNQ | CFAF | CFAF | CFAF | FULL |
| 20 | RefNQ | FULL | FULL | FULL | FULL |
| 21 | GaRAGe | FULL | FULL | OP:APPLICATION_VALIDATION_ERROR | OP:APPLICATION_VALIDATION_ERROR |
| 22 | GaRAGe | FULL | FULL | FULL | OP:APPLICATION_VALIDATION_ERROR |
| 23 | GaRAGe | FULL | FULL | FULL | FULL |
| 24 | GaRAGe | FULL | FULL | OP:APPLICATION_VALIDATION_ERROR | FULL |
| 25 | GaRAGe | FULL | FULL | FULL | FULL |
| 26 | GaRAGe | FULL | FULL | OP:APPLICATION_VALIDATION_ERROR | OP:APPLICATION_VALIDATION_ERROR |
| 27 | GaRAGe | FULL | FULL | FULL | FULL |
| 28 | GaRAGe | FULL | FULL | FULL | FULL |
| 29 | GaRAGe | FULL | FULL | FULL | FULL |
| 30 | GaRAGe | FULL | FULL | FULL | FULL |


## Explicit answers to the seventeen final questions

### 1. What was the exact completed v1 commit?

`ca2e3e111c63fbd67ff8965e5b05f3530a85c8a0`, frozen by annotated tag `component-cfaf-v1-freeze-20261029T170700Z`. The earlier bfd80bb base is not completed v1.

### 2. Which files changed?

CHANGED_FILES.txt is the exact parent-relative list. Runtime changes cover contracts, local projection, SDK hook, profiling, gate, pipeline, renderer and interfaces; compact.py and structured_resolver.py are new. New fictional tests/demo, v1_1 experiment/reporting tools/results, README and own-package version changes are included. Existing tests/results/manifests are untouched.

### 3. How many additional runtime lines were required?

219 meaningful lines: 698 to 917 total, of which 750 are owned and 167 copied. Physical/AST/function/byte counts are also reported to expose dense formatting.

### 4. Which existing components were reused?

Pure projection, contributor deduplication/threshold aggregate executor, selector, interchangeable retrievers, quota, Protocol DI, role/type/dependency gate, deterministic renderer, Pydantic contracts, graphlib and official SDK transport. No large historical semantic framework is imported.

### 5. Did the two natural-language structured cases improve?

Yes: cases 3/5 become FULL. Case 5 is zero-call trusted two-field metadata. Case 3 is one-call model-attributed permitted aggregate prose; typed rows are absent, so no trusted numeric operation was fabricated. Fictional typed aggregate zero-call paths are separately tested.

### 6. Did any correct FULL or CFAF decision regress?

Yes. InfoBank cases 2/8 change correct CFAF to false FULL; 4 becomes operational failure. RefusalBench 12/16 change native-correct FULL to CFAF, 13 becomes operational and 19 changes correct CFAF to false FULL. Case 20 remains false FULL in both. Case 14 improves; 15 has C1 provider failure and cannot establish semantic gain. Native accuracy declines 80 to 70% / 70 to 50%.

### 7. Were invalid span-ID failures reduced?

The new wire cannot emit span IDs, but overall reference/application reliability did not improve. Fresh C1 has three invalid-span failures; C2 has four quote-not-found and one invalid missing-ID failure. GaRAGe operational counts stay three versus three with a different pattern. One original failing case recovers, one remains failed, one fails although fresh C1 succeeds.

### 8. Were invalid citations ever accepted?

Zero mechanically invalid released links in the 61-link C1/C2 audit. Valid quotes still accompany incomplete or unsupported FULL claims; semantic entailment remains independently unverified.

### 9. Did token usage fall?

Yes. Reported all-arm output 9735 to 5494 (43.56%), with unknown failed-C1 usage and one additional C2 zero-call route. On 26 both-reported generative pairs, input falls 97,434 to 43,983 (54.86%) and output 9390 to 5373 (42.78%). This does not establish monetary savings or maintained answer quality.

### 10. Did real latency improve?

Observed C2 versus C1 latency falls: on the 26 comparable pairs, provider sum 152.872 to 100.723 s (34.11%) and E2E 153.565 to 101.416 s (33.96%); paired median difference -1.454 s. The all-planned comparison also includes a 57.779-second C1 connection failure. C2 is not faster in summed provider time than ordinary A. No significance or generalization claim.

### 11. Is the system still one-call/zero-call as intended?

Yes: ordinary paths at most one attempt; complete trusted typed/no-view paths zero. A28/C1 28/C2 27/B0 additional =83 settled attempts, no retake or retry. Both P5 cases have zero calls and identical public outcomes; complete C2 metadata is the additional zero route.

### 12. Are public refusal reasons consistent with internal causes?

Yes for tested canonical CFAF/operational realization and actual C1/C2 public validation. Factual copied text is withheld. This checks internal reason/text consistency, not semantic refusal correctness; false FULL remains a separate defect.

### 13. Do all existing governance and P5 tests pass?

All 54 preserved component tests plus 32 new tests pass; frozen v1 passes 54; applicable historical compatibility passes 691. Three full-cache metadata tests are explicitly NOT_RUN and one original-suite pre-existing archive failure remains. No blanket claim that all historical tests pass.

### 14. What limitations remain in semantic entailment and request completeness?

No independent semantic entailment/completeness checker. Compact implicit missing/status convention can accept non-answer claims; public text can omit an essential typed value; causal, counterfactual and trend qualifiers remain vulnerable. Exact quotes establish integrity only. Native labels may also contain scope defects.

### 15. Which improvements are ready to retain as default?

The bounded typed resolver and deterministic quote verifier are retainable, tested, replaceable building blocks subject to documented host-authority assumptions. These results do not justify the complete C2 configuration as general default. No production/default rollout is performed. The current SDKProvider combined with new resolver/gate is an untested hybrid for live accuracy; fresh C1 is the immutable tag, not that hybrid.

### 16. What must remain experimental?

Compact implicit completion/missing convention, prose-aggregate interpretation, ordinary model attribution and combined C2. Literal compatibility keeps upstream snapshot trust. Memory quota, catalogue and policy callback adapters require production integration. Optional NLI/ablation conditions are NOT_RUN.

### 17. What exact evidence supports the recommendation?

Immutable v1 tag/source hashes; frozen prompt/schema/preflight; 86 current and 54 snapshot test passes; isolated historical logs/exceptions; exactly 30 fresh paired outcomes and 83 settled attempts; unchanged context hashes/gold; native regressions and five C2 application failures; 61 mechanically valid released links; 26-pair token/latency measurements; explicitly non-independent qualitative findings. This supports a bounded engineering result and negative combined-default recommendation, not a general performance or isolated causal claim.

## Final status

All 30 cases complete and all 83 attempts settled. No post-outcome runtime/prompt/schema edits, retries or optional ablations. Required reports, test exceptions, actual resource accounting and negative findings are preserved. Final local commit and clean-worktree verification are recorded in the adjacent completion receipt. No push or merge.
