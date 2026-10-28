# Iterative CFAF development under time, exposure and API bounds

## A. Time, scope and completed work

Task start: **2026-10-28T18:49:27+00:00**. Monotonic start and hard cutoff are recorded in time_limits.json. Hard deadline: **2026-10-28T19:49:27+00:00**. This report was prepared at **2026-10-28T19:27:12.001881+00:00**, after **37.75 minutes**, with **22.25 minutes** remaining. Exact inclusive completion after the local commit is in the separate [completion receipt](../../../refusalbench_iterative_dev_v1_completion.json), also linked in the final reply.

Three fresh adaptive development rounds completed, each exactly ten expected FULL and ten expected CFAF records, followed by a separate paired regression on the already-exposed twenty round-01 inputs. No fourth round was started. All selected cases, raw outputs, unsuccessful predictions and invalid outputs remain. There is no interrupted live round. Improvements address general query typing and complete request fulfilment; general internal evidence-contradiction detection is not developed.

The task guard uses cross-process time.monotonic on this Windows host, anchored to the first tool time so initial inspection is included. At 50 minutes it prioritizes reporting and prevents another experiment; at 55 minutes it prevents new API requests; expected-duration margins and bounded subprocess/request timeouts prevent likely overruns. Deadline tests simulate the 55-minute and hard-margin conditions. All 243 actual requests began before the 55-minute cutoff. There were no API failures or retries. The study finished its planned experiments before reporting; it did not consume time merely to chase a target score.

## B. Dataset filtering and cumulative exposure

Official dataset is RefusalBench-NQ, pinned revision `b3684f805563e6ce465e7e9b055b840a48f519c2`, original test split of 1600 rows. Original JSONL SHA-256 is `d1bddaec4fdb7e0e2e7bf9a520ef104c3758800fc16769ac6e34baef0d90d1ed`. The official file and annotations were not modified. Metadata-only filtering again gives **1234** eligible records: A exact case-insensitive whole-word contradiction excludes 325, B exact REFUSE_CONTRADICTORY_CONTEXT/P-Contradiction excludes 277, overlap 236, union 366. No related-word or semantic filter was silently added.

| Exposure quantity | Count |
|---|---:|
| Original records | 1600 |
| Eligible after exact filters | 1234 |
| Maximum eligible exposure (50%) | 617 |
| Prior known unique exposed IDs, all categories | 82 |
| Prior exposed eligible IDs | 70 |
| Newly exposed eligible IDs | 60 |
| Total unique exposed eligible IDs | 130 |
| Remaining unseen eligible IDs | 1104 |
| Authorized source groups, already exposed before task | 52 |
| Reserved holdout groups preserved | 30 |
| Additional untouched groups preserved | 18 |
| Eligible records within authorized groups | 681 |
| Unused authorized eligible records at task start | 611 |
| Unused authorized eligible records after task | 551 |


Every available local branch's RefusalBench selection/provenance/experiment manifests was inventoried and reconciled with the earlier 10-, 42-, 10- and 20-case selected artifacts. The known union is 82 unique IDs, 70 eligible and 12 now-excluded records. No unknown record ID or unexplained additional selection was found. The exposure ledger retains all known IDs, original row indices, eligibility, stable hashes and origins. It conservatively counts selected records even if a past execution failed. Metadata-only annotation inspection does not expose question/context text.

Sixty new eligible IDs were charged durably **before** materializing their passages, for a cumulative **130/1234 (10.53%)**, safely below **617**. The paired replay adds zero new IDs. There are 142 known exposed IDs across all original categories, including the twelve excluded historical records. At least half the eligible dataset remains unseen: in fact 1104 eligible records are unseen, including all eligible records in the separate 48 protected source groups. The ledger's counters were recomputed against original metadata after execution. Record and source-group bounds are separate: spare record capacity never authorizes opening the thirty reserved or eighteen untouched groups.

New selections use seeds 20261028, 20261029 and 20261030, exact two-per-retained-refusal-category quotas, seeded matching/record choice, twenty distinct source groups per round and no record replacement across rounds or prior experiments. Source groups may recur across rounds because only the 52 already-exposed groups are allowed. No selection uses expected model success. No case is replaced after seeing an error. The initial authorized unused pool was 611 records; 551 remain unused there after this task. Global unseen counts also include forbidden groups.

## C. Round-by-round results

| Sample | System | Cases | Accuracy | FULL recall | CFAF recall | Balanced accuracy |
|---|---|---:|---:|---:|---:|---:|
| round_01 / v00 | semantic_cfaf | 20 | 55.0% | 10.0% | 100.0% | 55.0% |
| round_01 / v00 | shared_control | 20 | 55.0% | 50.0% | 60.0% | 55.0% |
| round_02 / v01 | semantic_cfaf | 20 | 70.0% | 60.0% | 80.0% | 70.0% |
| round_02 / v01 | shared_control | 20 | 75.0% | 70.0% | 80.0% | 75.0% |
| round_03 / v02 | semantic_cfaf | 20 | 85.0% | 90.0% | 80.0% | 85.0% |
| round_03 / v02 | shared_control | 20 | 85.0% | 90.0% | 80.0% | 85.0% |


All figures use official labels unchanged and all twenty scheduled cases in each denominator. Always FULL and Always CFAF are zero-cost references: both have 50% accuracy and balanced accuracy on every balanced sample; FULL recalls are 100%/0%, CFAF recalls 0%/100%, respectively. They generate no fictional response text. Per-round summaries contain confusion matrices, unnecessary-refusal and failure-to-restrict rates, error counts and raw model declarations.

The fresh samples differ. **55% → 70% → 85% is not a causal improvement estimate**. These are adaptive development observations, not independent holdout results or significance evidence. Round 1 has four control cross-field errors; they remain ERROR rather than repaired refusals. The unchanged old implementation and every unsuccessful round prediction are retained.

| Round | Version | UNRESOLVED profiles | CFAF specific-reason coverage | Control coverage | Invalid CFAF/control outputs | API attempts |
|---|---|---:|---:|---:|---:|---:|
| round_01 | v00 | 17/20 | 0.0% | 0.0% | 0 / 4 | 60 |
| round_02 | v01 | 4/20 | 30.0% | 0.0% | 0 / 0 | 60 |
| round_03 | v02 | 0/20 | 10.0% | 10.0% | 0 / 0 | 61 |


Specific reason coverage uses one frozen recognizer across all rounds, including an unsupported-premise phrase mapping defined before round 1. It is coverage across ten official CFAF cases, not conditional precision over only recognized explanations. Unknown/generic reasons are not credited as matching causes. The recognizer is an operational text criterion, not independent semantic explanation adjudication. Its limitations and low coverage remain despite richer internal causes.

## D. Identical-input paired regression

The final v02 implementation re-evaluated exactly the twenty already-exposed round-01 query/context pairs with the same official labels, settings and external primary scorer. Runtime input hashes match. This is separate from the three new samples and adds no exposure.

| Sample | System | Cases | Accuracy | FULL recall | CFAF recall | Balanced accuracy |
|---|---|---:|---:|---:|---:|---:|
| Same 20: baseline v00 | semantic_cfaf | 20 | 55.0% | 10.0% | 100.0% | 55.0% |
| Same 20: baseline v00 | shared_control | 20 | 55.0% | 50.0% | 60.0% | 55.0% |
| Same 20: final v02 | semantic_cfaf | 20 | 75.0% | 70.0% | 80.0% | 75.0% |
| Same 20: final v02 | shared_control | 20 | 80.0% | 80.0% | 80.0% | 80.0% |


CFAF fixed six initial errors and regressed on two initially correct cases: nine remained correct and three remained incorrect. The control fixed six, regressed on one, retained ten correct and three incorrect. The final CFAF gains FULL recall from 10% to 70% on those fixed inputs, while CFAF recall falls from 100% to 80%; the baseline's conservative refusal behavior is no longer mistaken for complete discrimination. The control's four initial invalid outputs disappear in the paired run. These are single-run version comparisons, not a significance test, blinded independent evaluation or isolation of one component. Temperature zero does not remove model variability, and these inputs were already used in development diagnosis.

Paired error/transition records are in paired_comparison.json. The same-source comparison provides more direct evidence than cross-round accuracy, but does not prove broad generalization. The final control reaches 80% versus CFAF 75% on this subset, and both reach 85% on round 3; no blanket CFAF accuracy advantage is claimed.

## E. Exact implementation changes

The original eight named stages and original TopLevelModeSelectionStage are preserved. External policy projection, metadata authorization/revocation, source visibility, permitted granularity, deterministic spans, response contracts and public/internal trace separation remain separate from model judgments. Previous source modules and results are immutable; new versions are under versions/.

- **v00 / round 1:** unchanged finalized InfoBank semantic-integration-v2.1. The new task runner adds only deadline/budget accounting and a uniform external scorer. It imports the current implementation, not an older CFAF architecture.
- **v01 / round 2:** query_profile.py adds query-only WHO, WHERE, WHEN, WHAT, WHICH, quantity, duration and compositional answer typing while preserving InfoBank aggregate, individual-record, metadata, document-content and action intents. A generic WHO is not automatically a private individual-record request. implementation.py clarifies named identity, requested role/milestone and evidence support; it derives specific internal reasons from structured analysis while keeping governance restrictions highest priority. contracts.py validates both FULL→FULL status and CFAF→non-FULL status. Invalid raw outputs are retained as errors, and one system's invalid output no longer discards its valid peer.
- **v02 / round 3:** query_profile.py recognizes fronted questions, factual yes/no, WHY and explicit instance requests. Its constrained query-only fallback is used only when deterministic interpretation remains unresolved and permitted evidence exists. The schema has no answer or FULL/CFAF field. Requirement text/targets must be copied query spans; a validated query-bound profile is rechecked before subsequent model calls. Profile output may remain UNRESOLVED. implementation.py adds per-requirement answer form, identity identification, relation/essential-qualifier support, completeness, referent resolution and a structured semantic refusal cause. A description cannot fill a name request, an associated entity cannot fill an unsupported role relation, a definition cannot fill a requested concrete instance, and partial requirements cannot yield FULL. These properties are combined with permission and existing sufficiency conditions before the unchanged selector.

v02 also separates factual questions about fictional subjects from subjective/counterfactual requests and unsupported year qualifiers. provider_v2.py/runner_v2.py are new controller files supporting the extra query-only stage; earlier provider/runner sources and round snapshots remain intact. The external scoring.py hash is identical across all versions. Each source_version.json contains exact prompts, schemas, settings and source hashes, and each fresh round includes frozen_source copies. Full code/prompt changes can be inspected there rather than inferred from scores.

These are conceptual fixes supported by multiple failures and synthetic controls, not case-ID rules or embedded benchmark answers. Test entity names and examples are newly constructed. Official labels/reasoning/original answers never enter an evaluated model. No general internal contradiction detector is added or tuned. Existing legacy conflict handling is unchanged.

## F. Tests, security and source preservation

Initial framework/earlier tests passed 108 functions. v01 and relevant existing governance tests passed 111; version compatibility tests passed 170; final acceptance passed **268** functions, including prior semantic/span/InfoBank tests, new version tests and deadline/budget checks. Counts overlap and must not be summed as independent coverage. Historical original CFAF regression tests in a disposable exact-Git-blob checkout passed **77 functions plus 13 subtests**, with the same known authorization-presence test failure: `test_preheldout_attempt1_plan_artifacts_are_plan_only` expects an artifact to be absent although it is committed. No artifact was removed to make it pass.

Controlled functional tests cover aggregate FULL versus individual restriction, metadata FULL versus body restriction, hidden/no-source equality, policy/whitelist change invalidation, ambiguous target binding, generic factual types, multiple requirements, unnamed identity, role linkage, concrete instances, referent ambiguity, query-only fallback and independent per-system validation. Controlled semantic test doubles validate governed plumbing, not live model accuracy. No new forty-case InfoBank API experiment is claimed here.

All **621** previously tracked files, the original dataset and original research branch are unchanged. Input audit checked all 243 actual payloads: only authorized perturbed text and derived neutral profiles/views/assessments reached the models; no expected labels, explanations, original answers/contexts/queries or label-bearing IDs did. Every one of the eighty case observations shares the same assessment between generators; the control never receives the gate or response contract. Three query-only calls receive only the question. No new trusted metadata association or private evidence is fabricated for this public benchmark.

Verified reference occurrences: {"requirement_support": 56, "source_role": 109, "supporting_spans": 62}; invalid references zero. Hash/offset/reference validity is not entailment. Candidate copying is not independent grounding proof. Each source policy is checked before model use; extended profiling does not expose restricted source bodies. Mechanical checks passed, while semantic output failures remain explicitly reported.

## G. Remaining errors and explanation limits

The round-specific error_analysis.md files classify all primary errors; diagnostics.json additionally flags output consistency, query profiling, entity/relation interpretation, requested identity/completeness, incorrect/unrecognized refusal causes and semantic support concerns even when the binary prediction is correct. These routing flags are not independent semantic gold. Qualitative notes are unblinded report-author agent judgments; no extra model judges or label correction were used.

Important remaining failures include:

- **Unresolved references still yield false FULLs.** Round 2 chooses an original work over a same-title adaptation and supplies locations for two candidate films without resolving the deictic request. Round 3 selects a single Oregon reinstatement event despite multiple dates, and selects one actor role while omitting another role in the same show. True cited facts do not establish unique/complete fulfilment.
- **Structured completeness can be confidently wrong.** In the final version, complete_answer/referent_resolved/relation-supported fields are true in those false-FULL cases. These fields improve auditability and deterministic checks but remain semantic model judgments, not proofs.
- **Requested coverage is still overgeneralized.** The paired run extrapolates a national century-long trend from a limited set of states/events. It also gives both periodic-table composers where the official label requires ambiguity refusal. The first/unique qualifier and complete evidence coverage require review.
- **Unnecessary abstention persists.** A decade-level vaccine availability statement is rejected for lacking an exact date that was not explicitly requested. Definition questions with unsupported edition wording mix a resolved profile with contradictory granularity flags. Band membership distributed across a narrative remains difficult, especially when an unsupported award presupposition is added.
- **Fine refusal reasons remain weak.** Missing evidence/precision is sometimes encoded as referent ambiguity; unsupported factual qualifiers are sometimes called nonfactual. Richer fields and templates did not make cause recognition reliable: round 3 specific reason coverage is only 1/10 for each system, while final paired CFAF coverage is 3/10. Reason quality must not be inferred from correct mode alone.
- **Benchmark labels can be debatable.** Some official FULL questions add unsupported dates, editions or award assumptions, while some ambiguity labels permit a reasonable qualified/list interpretation. All labels and denominators remain unchanged. Such concerns are documented separately, not used to discard cases or inflate scores.

No comprehensive independent answer-support accuracy is asserted. FULL candidates, their supporting spans, per-requirement properties and raw prose remain available for expert review. Neither zero invalid references nor improved mode recall establishes factual or complete response correctness.

## H. API usage and operational limits

Actual attempts: **243/360**, all successful, zero failed attempts, zero automatic retries and zero embeddings. Counts: 80 shared main semantic analyses, 80 CFAF generations, 80 control generations and **3 additional query-only profiling calls**. Those include sixty unique new case observations plus twenty paired re-observations, not eighty new records. Main analyses are charged once per observation, not once per system.

Input tokens: **323053**. Output tokens: **33667**. Sum of measured client API latency: **555.15 seconds**. Per-kind token/latency breakdowns, including fallback cost, are in api_usage.json. Model is requested as gpt-4o-mini and returned gpt-4o-mini-2024-07-18, temperature zero, one repetition; generation max 160, main analysis max 1500, query-only fallback max 500. All attempts are journaled before HTTP, including failures had any occurred. Credentials are not printed or committed.

The 360-attempt, 50% record-exposure and source-group limits were never approached or relaxed. No request starts after minute 55. The final implementation was not re-run on unchanged new samples simply to seek better outputs. The one paired run is explicitly a changed-version comparison on fixed already-exposed data.

## I. Selected record identifiers

The following tables include every selected record using the original row index and full SHA-256 hashes. Original label-bearing IDs remain in trusted selection manifests for reproduction; they never enter model inputs. Each round also retains its selection seed, expected behavior, actual responses, correctness and source hashes. ERROR is shown where validation prevents a valid prediction. Paired inputs are identical to round 1 and are separately retained, not counted as another new sample.

## round_01

| Round | Dataset index | Record hash | Source-group hash | Expected | CFAF predicted | Control predicted |
|---:|---:|---|---|---|---|---|
| 1 | 631 | `a01105f5f919e2e72826e52fc9c5add71e70aa09ba8bff56a417bc55763a7c5e` | `1b2fe5b0f8fa331f85ce5a136c108d94bbd035cff5b946598d3d412d1b7f5179` | FULL | CFAF | FULL |
| 1 | 251 | `3371b2528ab2d0247d5c12ad97c8110382604b8db23a4ce1043bed2522296fde` | `a0bca584e638a463f81404fef9f87c0ba4d6f958aef867ebafef1272f1cb6c71` | CFAF | CFAF | CFAF |
| 1 | 1320 | `1fdfd8e30114564b28b64c4a90c7b37479b07a1f58b68088dd4a7696bbe8afd4` | `670f6e4495bcf174bb461adf4d81abe655205030786b2414af4a55229ea32123` | CFAF | CFAF | CFAF |
| 1 | 694 | `b36c1f06cc307ac35872a7d4ffb7168edcf10f452ff662bfbbcae14d8525bb11` | `5d17e57ac0aadd68d1dc1298c4f52a1e8f6f59f5b1114ad7c2a2510f6f82a82c` | FULL | CFAF | CFAF |
| 1 | 1149 | `b24c6e9eb3de76149f39b27cf2d83d38983de4103b3d1a132610235d98af0835` | `61c9cbd7539e1932dccf55ceaa8941b1a5e91fbeadb605348deebe9f79faddde` | FULL | CFAF | CFAF |
| 1 | 1236 | `5796a2ee0d676df8818dbd6638c88bea0bcc7657d095f6de80237aee2afac026` | `f8a65bd0d1d457429789a971b4e63b3b1ea476fbc4e41dd75f0c75445837cd23` | CFAF | CFAF | FULL |
| 1 | 1408 | `114d417c99c7849caa38834a25d9188aae87275cf639c987325e91c9b688e67d` | `88929af592f55c6f6ea7a34907ca4a90fc6f6e5fe88deac932ed4696514380cb` | FULL | CFAF | CFAF |
| 1 | 135 | `08c5e731c82951c458c904799558683960034590f4f5b7d6d07ed54012c400b1` | `d8b15605c412f0ebe4e2eb085435cf709f6e38dfe21fcc80e2cc536c9633ca8e` | CFAF | CFAF | CFAF |
| 1 | 1112 | `20a0dd6385fb803c9bac883a30e7770aee14562781d40a553bd5ae82fb3d5fab` | `0cddb77171877f819cf7d8c7c45c3d714f1e8dbfcabac37de3b3fe268eba6895` | CFAF | CFAF | CFAF |
| 1 | 28 | `abec95bcfd854c3f93f51876e4a4d23cf83c26de54cb3f424e1d45bb4e03ad02` | `a1500bb4cdf963794c8b8126362b1ecc9a4ce0d82b71d869c0702271b2b5e598` | FULL | CFAF | FULL |
| 1 | 1477 | `57f57f7a892abe953eda916a2b53b66de88885a4848413d904b07b4badb1b125` | `e1fa5d79a91d6dec19c35d4ea377b0323ded1519397e63313919a377665b6cbd` | FULL | FULL | FULL |
| 1 | 848 | `befa23ff9bf25b0ba12a31bce4e47f1a2dc3586f80b767f195dd76ed34f0a039` | `dc2df9fe055f2142d6b28699960343199a06ee66a975f985814773390d9bee4e` | CFAF | CFAF | CFAF |
| 1 | 828 | `103b67edf036f79a9a24bae7638fa486e76383a2d32373537c78c4e39f280867` | `20001ecbdcbcaa6ff258f3b9a303a10aaaba1fbb0cfaececa9eaf3654e5d442b` | FULL | CFAF | CFAF |
| 1 | 1041 | `0409145933a7d8ff5ef5b5466ddbee32e5a06a9205f079ba2a4e2f9c19eedb4f` | `c7a848af9cbd6751b90f821a77981945f041f263224b8039d58e25a75a84f2d5` | CFAF | CFAF | ERROR |
| 1 | 1234 | `490d1a133457a00a977541c716d4043b0a4ecc7674e87ec501bffabe9b6f034a` | `ab4b006d3f4228385fd67b0c5cdeeee9ac1db9ddddef72acac46b24409a2a8e9` | FULL | CFAF | FULL |
| 1 | 312 | `a7086ebad8c79250dfd480ef74fa6f501176b210389b6495a7ced93212454bb8` | `c46a5b1bb00de58429568117979f238a7a0816cc5028ef2daa934185bc2ae08e` | CFAF | CFAF | CFAF |
| 1 | 621 | `ea60c4a27c0aeb79cc34eab4af0f35de9069165f9b6bfa9467ecce54d0ccfd41` | `c310a1334ae382b2e99bc51e47b13b2c7459aa554b338be878bd463a2e520cc0` | FULL | CFAF | ERROR |
| 1 | 319 | `0471a5fb79cf3d6605ae51d1dcb8e41797ab5e4fb4c93407483fe3c0340b4bc2` | `bee99491553510ddf4422fceeadd9f57cd59b6658b6855d0f8c386887b2b13c1` | CFAF | CFAF | ERROR |
| 1 | 1529 | `a8ea811f5976a405d231dd8b852d1e36411fec1b00b0e20447cf7980f7dd814f` | `fad6f2103650a361574f8f9c2316d629c308f4c6609d57e756f15fbd7e47ec0e` | CFAF | CFAF | ERROR |
| 1 | 550 | `c97a262d9f336dfb9de36025d7f0fded54386688f171b81afa0feb4292cbb192` | `4e16e2921724cd0810f6c51ba9094f779e63a3c5c459d47d2b48b584eff7a41f` | FULL | CFAF | FULL |

## round_02

| Round | Dataset index | Record hash | Source-group hash | Expected | CFAF predicted | Control predicted |
|---:|---:|---|---|---|---|---|
| 2 | 274 | `d5d0d89bcc3870bdc48fedd7295bd3fda5807b106173d5da2593c8be9ad08942` | `a0800ac7e9b8b9c14a98558626ee869d81a721a00bacd800e22bc9dec2fd88fa` | FULL | CFAF | CFAF |
| 2 | 1200 | `10c460df8fb823cfb23f1eb31340d7b7fe16aa6863dc95be9ba6eedc65959b80` | `bee99491553510ddf4422fceeadd9f57cd59b6658b6855d0f8c386887b2b13c1` | CFAF | FULL | FULL |
| 2 | 964 | `627aea4a93000f8562b644bc110888e6f596ddd691f56f2c828b0cc8240eb59a` | `61c9cbd7539e1932dccf55ceaa8941b1a5e91fbeadb605348deebe9f79faddde` | CFAF | CFAF | CFAF |
| 2 | 982 | `a13650b061a18f3e2c728e4e9b89e92ee12b14e22cf1416dde1bbc801bf8a289` | `acdf316a9a8e380e80a75d7b2ea514abea144d676e06f5973a794f76b2f577e1` | CFAF | CFAF | CFAF |
| 2 | 1344 | `4b350ed96dd3636a2b0f21638a85578aa30a0a1f770bf8e24ebacd20364625ce` | `f8a65bd0d1d457429789a971b4e63b3b1ea476fbc4e41dd75f0c75445837cd23` | FULL | FULL | FULL |
| 2 | 339 | `a87e469abc142b0f681a1a7fecdecaf2d2a2a647ea8470a639345f0148c22615` | `2267cb933404a6c7cbafa721612a3d76d706525c45853ba1cd36ab879ded7f87` | CFAF | CFAF | CFAF |
| 2 | 1089 | `984330b6e80d7acfe4ab84c4c56c64668be7b976ca43893a850b284a8cfb120d` | `de1a00e0fd2eedd955e432ec8ce16a2778e6d6dd0c8b3b0a73e37592dc92d955` | FULL | CFAF | FULL |
| 2 | 60 | `c8460616efd34eda5b929e0ea62c7f9e31765b88a54eb3436b931b23e68090ce` | `c1a969818581351f399c73bfe6be064cdb8b9465a54b00914ad785fba0a17d97` | CFAF | FULL | FULL |
| 2 | 1500 | `68189b95b7895abdef9683450668518d4945ba303fbb3f1aa54d11035081b8f0` | `20001ecbdcbcaa6ff258f3b9a303a10aaaba1fbb0cfaececa9eaf3654e5d442b` | CFAF | CFAF | CFAF |
| 2 | 1493 | `fb6a983906882268dab0c7aa2a3ab4b667e3418487ae92300dab9f1f07b90ff4` | `9087cf504fa73eb7c52518a029485637c89e26adf5d3264f69f096e277860f50` | FULL | FULL | FULL |
| 2 | 396 | `ebfe3ac4142b9fc53b31d8b82c40f8308c47bb2dfba77297a3687ced3caffb69` | `28ff2512dbcb04095e53b0539e1ba591dda4947b6d57e12dc3d035a27ad68af2` | FULL | FULL | FULL |
| 2 | 995 | `2990d8f41cf35559a22f9abc602bb542177527f14d023a0341bb6dc2b20f9a4f` | `593d2f7555acb2ca2fc38b7582b56dc9620f7195c8685863beda74c85243d187` | CFAF | CFAF | CFAF |
| 2 | 1076 | `69ea6e4ac2dd46acd9947d078834518ed5e2994ff7ab62b7184db433e1e6ad30` | `325730505979e34d3d5512b621682edaeb9aab175fcbb8f77af43fa54b83b6c0` | FULL | FULL | FULL |
| 2 | 363 | `d89b1e7899e8525fe910e82e19c9acad488a0dc0590e7765707d88419db595da` | `47e5440ff6ed6812e720b79bbf661b86832cc9a7c4b55b1dc0dc736df71dea82` | CFAF | CFAF | CFAF |
| 2 | 1007 | `da6af9021602ed450790858bc9a36e4048a9a361ef15af2c9342088207857052` | `932eba002778d33441f91d185365ac3a3a5d4ee0a8d7845579e60b7afde934d9` | FULL | CFAF | CFAF |
| 2 | 1078 | `41761274a52e4da39f8a79223b393b7cee2549679cd53886036580b25d25341c` | `ab4b006d3f4228385fd67b0c5cdeeee9ac1db9ddddef72acac46b24409a2a8e9` | FULL | CFAF | CFAF |
| 2 | 393 | `4cfc52f7f9f63a7e3beb9e603f2e60993b13a6cc6d1e763d853b62380d0f1cef` | `a0bca584e638a463f81404fef9f87c0ba4d6f958aef867ebafef1272f1cb6c71` | CFAF | CFAF | CFAF |
| 2 | 1496 | `9928de4b83913ac968dd23579198bf2d3fcf18c781ac681cac94587bb38a83bb` | `1b2fe5b0f8fa331f85ce5a136c108d94bbd035cff5b946598d3d412d1b7f5179` | CFAF | CFAF | CFAF |
| 2 | 1546 | `f2e46a1da64ede850009fabef5cb1e6aa271d9632bfc20947eedf73c6f5a6e96` | `46e3c9af69f3468a54d61b84b3344100219d5f83cef933157f434d02fe3380a5` | FULL | FULL | FULL |
| 2 | 1190 | `7403c02a2c35b98b8a8371b417bf0f7b944039b9d6954d46bf903d328080876e` | `88929af592f55c6f6ea7a34907ca4a90fc6f6e5fe88deac932ed4696514380cb` | FULL | FULL | FULL |

## round_03

| Round | Dataset index | Record hash | Source-group hash | Expected | CFAF predicted | Control predicted |
|---:|---:|---|---|---|---|---|
| 3 | 223 | `794a1dd1f364e2ab681701bbb4fe33d332cb434c902ea4543e0782ac34aa4c37` | `d8b15605c412f0ebe4e2eb085435cf709f6e38dfe21fcc80e2cc536c9633ca8e` | FULL | FULL | FULL |
| 3 | 1592 | `dbf30f42129615e07c13dc26ced878d0902f80531c1c2c54a2cf7d0748071ab7` | `2f30ece2d11682a40f853e9e777154f3707292394ce1fc704ead09720d8c5b1a` | FULL | FULL | FULL |
| 3 | 591 | `722d9d3c2d6fab56d7bfde7bc8c171bf4db7bbc293aa6722872b0aca7183ea2f` | `acdf316a9a8e380e80a75d7b2ea514abea144d676e06f5973a794f76b2f577e1` | CFAF | CFAF | CFAF |
| 3 | 1048 | `5255d9fbf225344ca4fd81651974f22bdbd094bfaa4969a1cf1f1cde8da009fb` | `fc43fa4028a21525f883e96089cb0d29383676fd0623e68d3e08514f79c88602` | CFAF | CFAF | CFAF |
| 3 | 176 | `a5162ac8226ec29b84003683adf04d40600b5de52ec309a8d1306d05b50ff927` | `e1fa5d79a91d6dec19c35d4ea377b0323ded1519397e63313919a377665b6cbd` | CFAF | CFAF | CFAF |
| 3 | 387 | `e23e39f8982845e3bf69f8661462d6e9846800cf6856b6abe391dfe313749c54` | `0cddb77171877f819cf7d8c7c45c3d714f1e8dbfcabac37de3b3fe268eba6895` | CFAF | FULL | FULL |
| 3 | 554 | `e37278b1fe8a33f0ff745ea93c7f55908b75763cad5c03987d201ebb3e486638` | `7012e5e57d295301f777610fee65654ab9779d3fe918fd3a4c76a0601cfe55bd` | FULL | FULL | FULL |
| 3 | 731 | `979591bb79fc8851997015aba3574cac8b56a81db42c985269096de201603b63` | `63d07c714f1c6acd57fdce94120b557e1dd4cef5a20aef361c387b82155b61ab` | CFAF | CFAF | CFAF |
| 3 | 1023 | `5495f5a4101d13fedf6fcd61383364319d9ee27b31548c6798a0dda9a38d6da1` | `5d17e57ac0aadd68d1dc1298c4f52a1e8f6f59f5b1114ad7c2a2510f6f82a82c` | FULL | CFAF | CFAF |
| 3 | 1243 | `5dfaa94a619fd442ca623175d7fbe5aa8221af67f89d8507402eba2184eea3e2` | `695319449a926007dc884bbd4e7bc02dc97d575a893764bf4cd68d3106714128` | CFAF | FULL | FULL |
| 3 | 527 | `7f6533a5dc48ae7ce763e807031bd1911174592d433e6f8061b4e926d0c1eba3` | `dc2df9fe055f2142d6b28699960343199a06ee66a975f985814773390d9bee4e` | CFAF | CFAF | CFAF |
| 3 | 1489 | `36d169427c99be995b3f0f7c9510631e6fb961c3839501304afa92e915d32f17` | `6ab71b7aad309e8bc0bca55724d868667df151964ce375064447b952745451a2` | FULL | FULL | FULL |
| 3 | 1197 | `192394a603ffa28b1dcbab87476a660f21a61229386fb2fdb5f5a8b5d19a0f55` | `c1a969818581351f399c73bfe6be064cdb8b9465a54b00914ad785fba0a17d97` | FULL | FULL | FULL |
| 3 | 1346 | `9ab389c10c608be00a1bba87352f5615e9feddff9d67fe8bce1b96a1a5b3c65a` | `712477111b824e7bfde4a83b15027cdb245fbcafb27ffb5a13d06b2cbe1a0926` | FULL | FULL | FULL |
| 3 | 1569 | `96f4b7eb7b9ac8f7f8298aa549b1f290f9314533d67fa9d4b29e462d56d688ef` | `fad6f2103650a361574f8f9c2316d629c308f4c6609d57e756f15fbd7e47ec0e` | CFAF | CFAF | CFAF |
| 3 | 29 | `5ccd03c09dcb91342ded3f7ef3c1c8912f7020e07fb90b7802c0dc98c3ee6656` | `2b5793f6a837f7fb1d1d1d6ffaa732e83a4f676959dcb1dd639dfc70cc88308e` | FULL | FULL | FULL |
| 3 | 254 | `144ed133d4a54b2ee27ec4e7566fa9d6f335c6713010a264ab82a548b810d80b` | `de1a00e0fd2eedd955e432ec8ce16a2778e6d6dd0c8b3b0a73e37592dc92d955` | CFAF | CFAF | CFAF |
| 3 | 1390 | `c63746b53f6bd94e417526238634c98c45fd27d449147a1094a2f09c0b717d01` | `585e817c5b601533b179777708549aa3758cd9f1e693bda138d97153a4681764` | CFAF | CFAF | CFAF |
| 3 | 678 | `3e04c607a133ce76fa470437127ec32417c3d16c3a849990e9afc52556081100` | `c46a5b1bb00de58429568117979f238a7a0816cc5028ef2daa934185bc2ae08e` | FULL | FULL | FULL |
| 3 | 563 | `c72215e31e6e689e17405a6a3ffff64c77161bcf4777cb970d32044e95f320fa` | `61c9cbd7539e1932dccf55ceaa8941b1a5e91fbeadb605348deebe9f79faddde` | FULL | FULL | FULL |


## J. Recommendation and completion

The implementation is suitable for another **bounded development experiment**, with the existing governance and exposure safeguards, but is **not ready for a separately frozen independent evaluation**. Generic factual coverage and complete-request checks improved on the fixed already-exposed subset, while official ambiguity/granularity failures and poor fine-cause consistency remain. The tests support preservation of policy mechanics; they do not replace a new live InfoBank validation or independent contextual annotation.

Before independent evaluation, validate new unseen paraphrases and source groups under a separately authorized protocol, strengthen unique-reference/list/milestone coverage and distinguish answer precision from referent ambiguity. Independently review FULL grounding and disputed benchmark assumptions while preserving official primary labels. Do not open the thirty reserved or eighteen untouched groups just because record capacity remains. General internal evidence-contradiction detection remains future work.

All work is on `experiment/refusalbench-iterative-dev-v1`, parent `a6236ba0d4781b22623687387f3a99ca3ddcd0f3`. Completed measurements, failed predictions, code snapshots, tests and exposure ledger are retained. CHANGED_FILES.txt is the exact added-file inventory; checksums.sha256 covers deliverables except itself. The final local commit and inclusive end time are recorded in the external outputs completion receipt and final reply, avoiding a self-referential SHA in this committed report. No push or merge is performed.
