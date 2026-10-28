# CFAF Requirement Decomposition and Alignment: critical development report

**Outcome:** the revised RDA + hard-check + shadow-diagnostic configuration B3 preserves original CFAF A0 mode behavior on both paired datasets. It restores the correct compound person/count FULL that strict RECV B1 rejects, but also retains A0's unsupported historical-priority FULL that B1 blocks. Accuracy does not improve over A0. Structural representation and diagnostic honesty improve; broad semantic reliability has not been demonstrated. Keep B3 experimental/shadow-only.

Development acceptance is **qualified**. Security, historical compatibility, the principal multipart regression and no-new-FULL-loss conditions pass. A separately authored synthetic type audit retains a generic metadata-date value-type limitation (16/17 expected type sequences, with all seventeen requirement counts correct). No expected label was changed to make that result pass.

## Starting point, scope and exact architecture

The local starting branch was verified as `experiment/cfaf-request-evidence-verification-v1`, commit `c2ae2f5b8d5c210edbdf242c3d060efcbe8a798b`. The new branch is `experiment/cfaf-requirement-alignment-v1`. All 848 earlier tracked working files retain their SHA-256. The original `wolala2026` branch remains at `5f377de38312fb39c088551f9c74f8b6d4bd5080`.

The eight named stages remain unchanged. Internal Query Profiling now records a query-only RDA enrichment, and Stage 5 consumes/recomputes it to align outputs, resolve authorized spans, apply the source registry per requirement and classify verification authority. Stage 6 still imports the original **unchanged `TopLevelModeSelectionStage`**. No new selector, stronger model, general contradiction detector, general-purpose reasoning pipeline or compulsory second model call was added.

New runtime files are `requirement_decomposition.py`, `requirement_alignment.py`, `rec_v2.py` and the version-local `integration.py`. Provider, deadline, runner and preparation files make execution bounded and reproducible. The old semantic analyzer prompt/schema, legacy model-visible request profile, permitted projection, query-only fallback, public generation prompts and six-field output schema remain unchanged. The RDA profile is internal; it is not an extra model-visible source of benchmark information.

## 1. Why strict RECV rejected the correct World Cup answer

The legacy profiler represented a WHO + HOW MANY question as one AGGREGATE_COUNT requirement. The complete candidate names James Rodriguez and six goals. The semantic assessment supplies an identity/composite answer form for that whole candidate. Strict RECV compares it with the single numeric requirement and emits RECV-ANSWER-TYPE. This is a decomposition/alignment interface failure, not missing evidence.

The runtime contains no World Cup IDs, names, goal counts or expected decisions. Synthetic regressions use different entities, quantities and wording. The focused benchmark case appears only in evaluator/preflight diagnostics and the scoped review.

## 2. Multipart representation and provenance

RDA reuses the familiar requirement fields and adds stable sequential IDs, exact query offsets/text, required answer kind, operation, explicit qualifiers, proposed dependencies, cardinality, precision, resolution status and legacy parent IDs. Every query span is validated against the unchanged original query and its SHA-256. Requirements correspond to output obligations, not every noun or modifier.

The person/count request now has an identity requirement and a count requirement; the pronoun proposes a dependency from the latter to the former. WHO + WHEN, COUNT + AVERAGE, parallel attributes and three-part questions are also covered by the finite grammar. A university in a founding-year question remains an internal subject, not an extra user-visible output. Ordinary WHEN wording does not demand an exact day. Capitalized proper-name uses of First/Last and `not only` constructions remain unresolved non-required qualifier interpretations rather than invented priority obligations.

On the forty cached natural questions RDA identifies 42 output elements, compared with the older coarse profile's merged obligations. On the 24 live questions it identifies 26. These are measured representation counts, **not independent requirement-recall gold**. The additional synthetic audit has seventeen authored expectations: all seventeen essential-output counts and query provenances match, while sixteen answer-type sequences match.

The retained mismatch concerns file type plus creation date metadata: two obligations and the `created_at` field survive, but both use generic METADATA answer kind rather than refining the date value to DATE_TIME. The original authored expectation is preserved. This audit was additional to the passing preflight and was completed while the frozen live experiment was running; the live implementation was not altered after seeing it. The gap does not merge outputs or change measured modes, but prevents a claim that the value-type representation is complete.

## 3. Requirement-level candidate and evidence alignment

Alignment proposes exact candidate fragments for each requirement. Names use the frozen analyzer's entity proposals, numbers use token shapes narrowed by the requested unit, dates use temporal tokens, and Boolean/attribute candidates use conservative patterns. All fragment offsets must resolve back to the unchanged candidate. Multiple possible fragments remain visible. Matching text or type is explicitly not semantic entailment.

The live compound case produces the fragments James Rodriguez and six. The year 2014 elsewhere in the candidate does not displace the count because the requested unit is goals. Both fragments are type-compatible proposals, linked by a proposed entity/quantity association. A source-clause heuristic can detect a potential mismatch in controlled examples with two people and different quantities, but its output remains soft and never proves a relation merely from co-occurrence.

Supporting span IDs are inherited through explicit parent mappings and resolved in the permitted views. An EXACT_TYPED_REQUIREMENT mapping is distinguished from COARSE_INHERITED_ASSESSMENT. A new child does not obtain independently scoped semantic evidence just because a parent claimed completeness. Frozen support, referent, completeness and relation properties are retained with their LLM origin.

All **61 proposed prose fragments** across the two datasets pass exact-offset validation; 23 of those are live proposals. All 68 represented query spans validate. This is mechanical consistency, not 61 independently correct semantic alignments. Cached mapping contains 37 exact and five coarse rows; live mapping contains nineteen exact and seven coarse rows.

Native requirement-keyed application candidates permit hard checks for a demonstrably missing component or incompatible native value type. The real model interface still uses prose candidates; those structured rules are tested but not claimed as empirically successful live corrections. Failure to extract a prose fragment remains soft uncertainty rather than proof of omission.

## 4. Hard versus soft authority

Hard failures arise from authoritative access/view facts, invalid references or rejected assessment contracts, explicitly absent output, demonstrably missing structured components, incompatible native types and a trusted source rule explicitly forbidding the asserted use. An absent candidate means output is absent; it does not prove the underlying fact does not exist. P5 no-view behavior remains the identical canonical public response.

Soft checks include inferred prose type, historical first/only priority, exhaustive lists, referent identity, proposed entity/quantity association, source defaults requiring further semantic evidence and LLM completeness/relation properties. A typed Boolean is never relabeled deterministic proof. These checks record COVERED, PARTIALLY_COVERED, NOT_COVERED or UNKNOWN with justification provenance. UNKNOWN is not proof of fact absence.

The original independently validated v02 sufficiency and permission conditions remain mandatory. B2/B3 never promote an A0 refusal. New soft diagnostics do not automatically veto an otherwise valid original decision. Thus B3 can retain FULL while the new alignment coverage is UNKNOWN: the support basis remains the original model assessment, and the new warning is visible in shadow mode. This is a declared risk tradeoff, not a conversion of uncertainty into newly proven support.

Hard policy reasons take precedence over soft ambiguity for B2/B3; other existing semantic reasons remain intact. The complete contracts are in [RDA_SPEC.md](RDA_SPEC.md) and [HARD_SOFT_VERIFICATION_SPEC.md](HARD_SOFT_VERIFICATION_SPEC.md).

## 5. Paired cached results and correct FULL preservation

The first study reuses exactly the forty previously exposed cached v02 assessments used in the earlier RECV experiment: twenty FULL and twenty CFAF labels. A0 reproduces the saved original modes and B1 reproduces the prior strict combined RECV modes. Every candidate, semantic field, role, supporting/counter reference and model-visible profile is frozen. RDA spans, output obligations, fragment proposals, per-child capabilities and authority classification are recomputed. This phase makes zero model calls.

| Configuration | Accuracy | Balanced accuracy | FULL recall | CFAF recall | Unnecessary refusal | Failure to restrict | ERROR |
|---|---:|---:|---:|---:|---:|---:|---:|
| A0 | 80.00% | 80.00% | 80.00% | 80.00% | 4 (20.00%) | 4 (20.00%) | 0 |
| B1 | 80.00% | 80.00% | 75.00% | 85.00% | 5 (25.00%) | 3 (15.00%) | 0 |
| B2 | 80.00% | 80.00% | 80.00% | 80.00% | 4 (20.00%) | 4 (20.00%) | 0 |
| B3 | 80.00% | 80.00% | 80.00% | 80.00% | 4 (20.00%) | 4 (20.00%) | 0 |

B3 loses zero correct FULL and prevents zero additional incorrect FULL relative to A0. Relative to B1 it restores the correct person/count FULL and reintroduces the incorrect historical-priority FULL. FULL recall returns from 75% to 80%; CFAF recall returns from 85% to 80%. Accuracy and balanced accuracy remain 80%.

## 6. Live paired results and incorrect FULL prevention

The frozen live sample has 24 already-exposed cases: ten original synthetic InfoBank P1-P5 cases plus fourteen RefusalBench records, with eleven FULL and thirteen CFAF labels. It includes the compound regression, historical-priority uncertainty, ambiguous referents and relevant-but-insufficient evidence. The same cases are used for every arm. Each permitted case receives one shared upstream assessment; A0/B1/B3 and the prompt control generate responses from the identical input information. B2 is gate-only. Two P5 cases make no calls.

| Configuration | Accuracy | Balanced accuracy | FULL recall | CFAF recall | Unnecessary refusal | Failure to restrict | ERROR |
|---|---:|---:|---:|---:|---:|---:|---:|
| A0 | 79.17% | 80.07% | 90.91% | 69.23% | 1 (9.09%) | 3 (23.08%) | 1 |
| B1 | 79.17% | 79.37% | 81.82% | 76.92% | 2 (18.18%) | 2 (15.38%) | 1 |
| B2 | 79.17% | 80.07% | 90.91% | 69.23% | 1 (9.09%) | 3 (23.08%) | 1 |
| B3 | 79.17% | 80.07% | 90.91% | 69.23% | 1 (9.09%) | 3 (23.08%) | 1 |
| shared_control | 79.17% | 80.07% | 90.91% | 69.23% | 1 (9.09%) | 3 (23.08%) | 1 |

All systems score 19/24. B3 and A0 have identical gate decisions: ten of eleven FULL cases and nine of thirteen CFAF cases are correct; one invalid upstream assessment remains ERROR. B1 instead has nine correct FULL and ten correct CFAF cases. B3's balanced accuracy is 80.07%, compared with B1's 79.37%; the difference is the class-weighted tradeoff, not a net accuracy improvement.

B3 prevents **zero** new incorrect FULL compared with A0, and loses **zero** previously correct FULL. B1 blocks the unsupported first-working periodic-table answer but also rejects the complete scorer/count answer. B3's shadow policy retains both original FULL decisions. The same two unique records appear in cached and live studies; the four phase-specific observations are not independent examples.

All ten InfoBank cases achieve correct modes in every arm, including all four contrasting matched pairs and the P5 non-disclosure pair. The fourteen RefusalBench cases score 9/14 (64.29%) in each arm. No significance or independent-validation claim is made.

## 7. Unnecessary refusal and completeness

Compared with B1, B3 reduces unnecessary refusal from 25% to 20% on cached FULL cases and from 18.18% to 9.09% on live FULL cases. Failure to restrict increases correspondingly from 15% to 20% cached and from 15.38% to 23.08% live. Compared with A0, both rates are unchanged.

Cached revised coverage contains five COVERED, nineteen NOT_COVERED and eighteen UNKNOWN rows. Live coverage contains two COVERED, eleven NOT_COVERED and thirteen UNKNOWN rows. No PARTIALLY_COVERED row occurs in these observations, although the state remains supported by the implementation. These conservative shadow counts are not the final selector decisions and must not be presented as measured independent semantic completeness.

The existing refusal on the Traveling Wilburys/award-premise question remains. It is a FULL-labeled case where the model overlooks distributed member names and the query also includes an unsupported award premise. Original annotations are unchanged. B3 does not remove original sufficiency checks to improve recall.

## 8. Causal attribution and original CFAF comparison

The old semantic JSON, proposed answer and references remain byte-equivalent within every comparison. New internal query decomposition, fragment alignment and hard/soft authority are application computations, not a new upstream LLM analysis. Upstream prompts and schemas were frozen before the first live call; all runtime source hashes remain unchanged throughout the trial.

The compound answer restoration cannot be uniquely credited to decomposition alone. A classification-only counterfactual that stops treating an inferred global prose type as an authoritative veto can independently recover A0's mode. RDA separately repairs the two-obligation representation and exposes exact person/count fragments. These structural and decision-authority effects are distinguished in the diagnostics; a factorial accuracy effect of each individual mechanism was not measured.

B2 and B3 have identical mode policy by design. B3 adds visible semantic warnings; B2 has no separately generated public answer or explanation score. B4 was not enabled after inspecting labels, and the existing optional second-pass verifier remained disabled. Source default ADDITIONAL_EVIDENCE_REQUIRED uses become semantic warnings under the declared revised authority policy, while explicitly FORBIDDEN uses stay hard. This is recorded separately from the unchanged registry itself.

Fresh live model inference differs from older cached inference, so cross-phase accuracy differences cannot be attributed to RDA. Generation variability is retained in raw outputs, but all contract/response validations pass; no formatting repair or parsing gain is credited. The one missing source-role assessment remains an error for all arms, not a successful refusal.

## 9. Source capability and evidence-role diagnostics

The seventeen-rule source-capability registry is imported unchanged, with identical file SHA-256. It is applied to each RDA requirement using trusted provenance independently of model-inferred roles. Browser visits versus obligations, invoiced amounts versus payment, aggregate versus individual use and metadata versus body access retain their claim-relative meanings. Missing/untrusted provenance remains UNKNOWN and is not a blanket veto.

There are zero rule-recomputation errors. Live cited support has four PERMITTED and twelve UNKNOWN capability occurrences; cached support has thirty UNKNOWN occurrences. These are reference uses, not independent ground-truth facts. Eight usable original synthetic source annotations give 6/8 model/effective role agreement and 4/8 relation agreement, unchanged by the revised enforcement. Some unused contextual evidence retains an incorrect PRIMARY model label despite an unusable relation. RefusalBench has no independently usable trusted source-role gold here.

Source mechanics and provenance tests pass, including seventeen registry cases and a multi-requirement visit/obligation test. No observed mode difference is attributable to source-rule expansion or new provenance. This does not validate every connector/source exception in production.

## 10. Reasons, errors and remaining limitations

A0 and B3 have five reason matches among nine assessable valid gold-CFAF refusals; B1 has five matches among nine assessable reasons plus one uncategorized historical-qualifier refusal. The prompt control has four matches among six assessable reasons and three generic/uncategorized refusals. B2 generates no explanation. These are original synthetic reason-class labels or lexical RefusalBench category proxies, not proof of semantic justification. No measured reason-accuracy improvement over A0 is claimed.

Across 35 raw A0/B1/B3 refusal contracts, internal/public reason class and realization agree 35/35. Public text exactly matches the internal template in 29/35; the six exceptions are the two deterministic P5 cases in each arm, which intentionally use the canonical no-support sentence. This does not repair incorrect upstream ambiguity/evidence interpretations.

Residual label-incorrect FULL answers remain visible. Oregon has reinstatements in 1978 and 1984: RDA records multiple temporal candidates and unresolved `it`, but shadow policy retains A0 FULL. The actor-role case has multiple entity/role candidates and remains a soft uncertainty. The periodic-table case flags both multiple identities and an unsupported first-working qualifier, while retaining FULL under A0's original support claim. No general contradiction detector or forced selection of a preferred answer was introduced.

The global cricket-statistic case returns `source_assessments=[]` for a supplied view and fails SOURCE_ROLE_COVERAGE_INVALID. It scores ERROR across all configurations. There is no retry or semantic-output repair.

The additional metadata-date type mismatch is explicitly retained. More generally, finite query/fragment grammar, coarse inherited parent support, ambiguous entity proposals, temporal/number token ambiguity and incomplete relation predicates prevent claims of general semantic alignment. The clause-association heuristic is not an entailment model. Qualified development acceptance and shadow-only use are appropriate.

## 11. Tests, security, exposure and API cost

The final new suite passes **72 tests**. The full current/prior compatibility run passes **519 tests**, with three byte-hash tests run separately on the unchanged real working files; all three pass. Thus 522 distinct current/prior checks pass across these suites. The original CFAF suite additionally passes 77 tests and thirteen subtests, retaining one known historical failure.

That historical failure, `test_preheldout_attempt1_plan_artifacts_are_plan_only`, expects an already committed HELDOUT_RUN_AUTHORIZATION.json to be absent. It was not modified. Initial isolated failures from the archived expired task clock and LF/CRLF snapshot hashes were resolved by reanchoring only the test-process clock and checking real working bytes. All historical sources/results remain unchanged. The separate 16/17 synthetic type audit is a reported current experimental limitation, not hidden inside a claim that all type expectations pass.

Tests cover the required output forms, dependencies, multipart/attribute/list/qualifier distinctions, native missing components, person/count mismatch warnings, approximate precision, unknown semantics, no promotion of original refusals, known counterevidence, invalid spans, DENY/aggregate/metadata/P5 isolation, gold exclusion, unchanged stages/selector, per-requirement source rules, reason priority and the 120-attempt/55-minute limits.

Security audit status is PASS: all 110 serialized payloads pass the policy/profile/binding guards and forbidden-field scan. Every compared arm shares the exact upstream assessment/projection in all 24 cases. The control receives no gate contract, selected mode or private RDA diagnostics. Public schemas and cross-field mode/status invariants have zero new errors, all source/span references are authorized, and P5 public traces are identical with zero calls. No arbitrary-language leak-resistance or entailment proof is claimed.

No new RefusalBench record was exposed. The ledger remains **130 eligible exposed / 1,234 eligible**, with **1,104 unseen**, thirty reserved and eighteen additional untouched source groups. Student-created independent InfoBank cases were not opened. The inherited metadata-filter regression reads annotation columns only through an explicit Arrow schema; reserved/untouched question/context fields are ignored. All 848 previous tracked files, including earlier studies and gold annotations, are unchanged.

Actual usage is **110/120 external attempts**, all successful at the HTTP/provider level: 22 shared semantic analyses, 66 A0/B1/B3 generations and 22 prompt-control generations. No profile fallback, retry, embedding, stronger model or optional verifier call occurred. All responses report gpt-4o-mini-2024-07-18, with temperature 0 and one repetition. Actual input/output totals are **140,404 / 11,425 tokens**; summed network-call latency is **210.065 seconds**.

RDA adds zero model calls. A0 and B3 each correspond to 44 calls/24 cases in a hypothetical deployment, with the same measured 72,365 input and 7,999 output tokens; these per-system totals overlap in shared upstream cost and must not be summed. B3 Stage 5 has median 1.273 ms and maximum 4.698 ms locally, but A0 also computes disabled diagnostics, so this is not an isolated incremental CPU benchmark. No USD price or cost-effectiveness claim is inferred. The actual comparative trial uses 4.583 calls/case to evaluate several public generators fairly.

## 12. Recommendation and completion

Retain RDA as an **experimental/shadow Stage-5 component**, with authoritative access/reference/output-structure checks enforced and uncertain semantics visible. Do not enable selected soft vetoes merely because the exposed periodic-table case benefits. Before broader/default use, refine metadata value typing, evaluate requirement-scoped semantic support and antecedent relations, calibrate diagnostic noise, and test on genuinely reserved independent material under later authorization.

The experiment demonstrates a generic repair to the representation of the compound answer and avoids an unnecessary strict-type rejection. It does not improve A0's measured accuracy, prevent additional wrong FULL answers or establish independent entailment. It also makes the cost of shadow policy explicit: the old historical-priority false FULL remains. These limitations and the synthetic type mismatch remain in the committed evidence.

The task began at **2026-10-28 20:57:19 UTC**. A wall start was recorded at first inspection, and the monotonic anchor was calibrated during setup to include that entire interval. This report was generated after 23.96 minutes. Persistent deadlines enforce reporting priority at 50 minutes, no new API start after 55 and a sixty-minute hard bound. API execution completed well before these cutoffs.

[CHANGED_FILES.txt](CHANGED_FILES.txt) lists the exact new files. [checksums.sha256](checksums.sha256) covers all deliverables except itself. The inclusive end time and final local commit SHA are recorded in the [completion receipt](../../../cfaf_requirement_alignment_v1_completion.json) outside the repository and returned to the user, avoiding a self-referential commit hash. No push or merge is performed.
