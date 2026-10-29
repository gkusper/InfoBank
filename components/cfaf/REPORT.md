# ComponentCFAF v1: implementation and bounded development report

A runnable isolated package has been delivered on **ComponentBasaedCFAF**, based on **bfd80bbfe2ccbb251da46bdc22b791dad5b9341f**. The normal generative route makes one actual gpt-4o-mini request and renders deterministically. No-view and explicit structured routes work with zero calls. This is an engineering prototype with documented functional gaps, not evidence of general answer-quality superiority or a production-ready authorization service.

The new package contains **531 new meaningful runtime lines plus 167 copied runtime lines** (698 total; 826 AST statements, 808 physical lines). New code, copied code and adapters are counted separately. The historical static local import closure has 60 files and 4636 meaningful lines; this comparison includes differing semantics/integrations and is not an equivalent-functionality reduction claim. External libraries and all transitive environment packages remain visible in the manifests.

The completed one-call pilot uses 30 already-exposed development cases and **56 actual model requests**, 28 A and 28 C1; B adds none. C1's mode agreement is **8/10 versus A/B 10/10 on InfoBank**, and **7/10 versus A/B 8/10 on RefusalBench-NQ**. GaRAGe has no native binary FULL/CFAF gold, so no accuracy is fabricated. Three GaRAGe C1 outputs fail local span validation; transport succeeds. The code/prompt/schema were not tuned after these results.

## Isolation, base and delivered runtime

Before writing code, Git status, worktree list, local/remote-tracking refs and freeze tags were inspected. The required branch did not exist and was created in a separate worktree from the last completed contract-driven study commit. No remote state is assumed from local results. The two earlier worktrees remain at a22b027741a2e412f7e898783c558928077c85a4 and 18491f48ac94f9be3ebb84db8b12ecd5c14dda40; their tracked files and all prior refs are protected by the final audit. wolala2026 and all freeze tags remain unchanged. No reset, clean, rebase, merge or push was performed.

A dedicated Python 3.12.14 environment, temporary directory, package cache, model-cache path and result directory were used. The initial default-temp ensurepip bootstrap failed; task-local TEMP/TMP resolved it. The legacy backend's Pydantic 1.10.24/FastAPI/Chroma pins were not changed. The package uses Pydantic 2.12.3 and OpenAI SDK 1.59.9 in its own environment. A second legacy-only environment supplies pyarrow for old metadata-filter tests without changing frozen component dependencies.

Concurrency inventory showed no other active research execution; the preceding QASPER run in this chat had completed and been committed. No foreign process was stopped. No QASPER questions, source documents, annotations, model outputs or gold were used in this implementation. Its worktree/manuscript/results remain protected. No new benchmark was downloaded or sampled; protected InfoBank student holdout and RefusalBench 30+18 source groups remain unopened.

The package is under components/cfaf, with contracts, Protocol interfaces, profiling, pipeline, gate, deterministic renderer and swappable adapters. Runtime imports no dataset scorer or versioned experiment-runner chain. The offline demo runs on fictional data without a database server, web interface, optional NLP model or network request. The constructor accepts profiler, retriever, governance, proposal provider, local shadow checker and renderer components.

## Contracts, governance and one-call behavior

ARCHITECTURE.md maps the eight logical stages to the actual components. Authorization and safe projection occur before retrieval, indexing or the model call. The reused pure projection removes DENY/nonpublic data, limits metadata fields and uses authorized aggregate views. Neutral IDs are assigned after filtering. Authenticated principal, purpose, policy/revocation version and private mapping remain application-controlled and are not supplied as model authority.

The early query-only profile retains exact spans and required parts. The model may refine UNKNOWN value types and add anchored requirements; it cannot silently delete/weaken explicit requirements. DAG and ID checks use graphlib. The minimum handles AND segmentation and explicit pronoun-result dependencies; equality checks catch an inconsistent person/count binding. These are mechanical constraints, not semantic proof. OR is explicitly unresolved. The pilot exposes a title-conjunction false split, which remains recorded.

The SDK returns a single strict internal LLMProposal containing anchored requirements, sparse source roles, typed claims, claim–span links, missing parts and interpretation limits. It does not request a final FULL/CFAF decision or trusted permission/provenance field. The final gate retains the historical first-failing-assessment decision principle, with new nonempty-request/execution/policy preconditions. A successful gate is labelled GATE_ACCEPTED_FULL rather than independently verified truth.

Sparse omissions remain NOT_ASSESSED. Selected support requires explicit PRIMARY/SUPPORTS assessment and valid grounding. Unassessed inventory does not prove absence, exhaustive lists or earliest/latest scope. The local span catalogue uses 600-character windows, exact offsets and hashes. Decimal aliases normalize only to a unique real index on the same source and are logged; nonexistent indexes stay invalid. There is no nearest-span repair.

The normal path uses gpt-4o-mini, temperature 0, one repetition and 2048 output tokens for the entire proposal. A has the same output ceiling and exact authorized question/context/as-of/profile inputs. All observed live completions use gpt-4o-mini-2024-07-18. The SDK has zero automatic retries and no hidden format-repair loop. Timeout, refusal, truncation, interruption, HTTP errors and application validation have distinct statuses. No stronger model, embedding service, external judge, second verifier or optional NLI model ran.

FULL rendering concatenates accepted claim texts without another model call. Provenance separates REFERENCE_VALID, MODEL_ATTRIBUTED and SUPPORT_NOT_INDEPENDENTLY_VERIFIED; structured shortcuts are marked APPLICATION_STRUCTURED. Merely examined sources are listed separately. Claim-ID attribution does not depend on equality between the complete public answer and a candidate string. CFAF publishes a controlled safe template rather than a factual partial answer. Operational fallback is separate from evidential refusal.

Zero-call structured shortcuts are intentionally narrow: an exact metadata[field] or aggregate[operation] request, matching one authorized structured view. Natural-language metadata/aggregate requests remain restricted until a trusted target/scope integration is added. This limitation causes the two InfoBank C1 misses below; it is not hidden as an accuracy improvement. The aggregate helper reuses the existing threshold/contributor executor. The memory quota is debited once in prepare; guard/renderer never debit again. A consumed query ID cannot trigger another generation. Production needs durable atomic quota/policy state and authenticated callbacks.

## I. Isolated renderer ablation: no new inference

Thirty previously exposed records were registered. Nineteen have a saved valid historical assessment and generation contract usable for an isolated replay. Two P5 no-view cases have no generation contract; nine original GaRAGe cases lack the required saved valid assessment/contract combination and are explicitly not applicable. No selected record was replaced.

| Measure | Saved historical generator | Deterministic compatibility renderer |
|---|---:|---:|
| Eligible saved contracts | 19 | 19 |
| Exact contract matches | 19/19 | 19/19 |
| New analysis calls for this ablation | 0 | 0 |
| New generation calls for this ablation | 0 | 0 |

Old raw generations and assessments remain preserved in ignored local storage. The deterministic path shows exact contract realization without needing to regenerate; it shows **no measured improvement over already valid historical realizations**. Its compatibility adapter copies the old six-field contract, while the new one-call proposal path uses claim-linked PublicResponseContract rendering. Old public contracts did not instrument claim citations, so no citation-support gain is assigned to this ablation. The old 512-token generation and new one-call 2048-token proposal are not treated as a controlled latency/accuracy comparison.

## II. Frozen one-call pilot: 30 exposed cases

Selection is fixed before API execution: first completed pair from each InfoBank P1–P5 family (10), first ten fixed previously exposed RefusalBench manifest positions (10), and all ten original GaRAGe pilot positions. There is no new random sample or new exposure record. Closed source/runtime manifests and raw source hashes are checked. The original GaRAGe contexts retain all 15 provided units per case; no original pilot truncation or new context truncation occurs. All systems receive the same permitted content/order. Gold and original identifiers remain scorer-only.

A is the standard selective-RAG generation. B mechanically/policy guards that exact A response and makes no independent sample or model request. B does not receive C1's requirement-sufficiency gate. Both use schema/mode/nonempty/blocked-content checks appropriate to their public schema. A/B do not emit C1's structured claim/span field, so their public citation validity is uninstrumented; C1's additional structured-reference checks are part of the changed configuration. This is not a selector-only or wholly identical-output-schema ablation.

| Cohort, N=10 each | A mode accuracy | B mode accuracy | C1 mode accuracy | C1 balanced | C1 operational failures |
|---|---:|---:|---:|---:|---:|
| InfoBank exposed P1–P5 | 100% (10/10) | 100% (10/10) | 80% (8/10) | 75% | 0 |
| RefusalBench exposed development | 80% (8/10) | 80% (8/10) | 70% (7/10) | 70% | 0 |
| Original GaRAGe pilot | Not measurable | Not measurable | Not measurable | Not measurable | 3 |

InfoBank has four FULL and six CFAF labels: A/B predict all correctly; C1 has two FULL→FULL, two FULL→CFAF and six CFAF→CFAF. Its two unnecessary refusals are legitimate natural-language aggregate/metadata requests blocked by the narrow structured boundary. RefusalBench has five FULL and five CFAF labels: A/B give five correct FULL, three correct CFAF and two false FULL; C1 gives five correct FULL, two correct CFAF and three false FULL. No operational fallback receives correct-CFAF credit.

Paired InfoBank correctness: both B/C1 correct 8, B-only 2, C1-only 0. RefusalBench: both 7, B-only 1, C1-only 0, neither 2. No non-inferiority, significance or general superiority claim is made from these tiny exposed cohorts. The new schema, prompting, validation and call layout change together. There is no newly executed old two-call-C control under identical conditions, and no pooled accuracy across datasets.

Non-operational FULL counts are A/B 4, 7 and 10 versus C1 2, 8 and 7, respectively. These are availability counts, **not verified useful or factually complete answers**. Independent factualness, support correctness and fulfilment accuracy are not measured. The InfoBank literal full-sentence marker diagnostic is retained in the scorer summary but not interpreted as factual accuracy: supported paraphrases can fail its exact substring criterion.

## Content, fulfilment and citation diagnostics

All thirty C1 outputs/questions were reviewed with A excerpts, displayed claim references and targeted complete-context checks. This is **non-independent, unblinded agent review**, not an external judge or exhaustive expert annotation. Original labels are preserved, no case is removed and no alternative tuned accuracy is substituted. Detailed notes, complete responses, source windows and gold stay in ignored results/local/CASE_REPORT.md and qualitative_review.json. Public qualitative_review_summary.json gives scope and aggregate flags.

The review finds concrete remaining limitations:

- In the title-only volcano case, C1 supplies a specific latest-event year unsupported by the provided title; A withholds. A mechanically valid reference does not establish the fact. The local explicit exhaustiveness hints do not cover every linguistic form of latest-event requests.
- A single appearance event is promoted to a decade-wide trend, and a few state examples become a century-wide trend. Both can pass local acceptance while failing request completeness.
- A song-title conjunction is split into artificial requirements, yielding an extra title fragment. The conservative local profiler is not a semantic parser.
- Familiar band-member names are expanded beyond the exact wording in the shown excerpt; one cited window does not contain every named entity. Another answer preserves mode gold while an edition qualifier is not explicitly supported. Gold mode and content support are separate.
- A cricket answer adds a geographic location by treating an opposing team's name as a location; C1 avoids that unsupported addition. A/B's better mode score therefore does not prove better factualness on every answer.
- GaRAGe examples concatenate partly redundant hosting-model descriptions, heterogeneous financial forecasts and time periods, or add causal/evaluative language to accounting/operator-selection facts. One forecast drops a stated assumption. C1 also assigns at least one stock-related claim to a small window about a different policy subject.

C1 publishes **35/35 mechanically valid claim-reference links**: 2 InfoBank, 9 RefusalBench, 24 GaRAGe. That 100% existence/hash/offset validity is **not semantic support correctness**. The examples above expose gaps even with reference-valid labels. A/B free-text source markers are not instrumented as structured claim citations and are not assigned an artificial zero. No independently verified useful-FULL percentage, factual accuracy, completeness score or citation-support percentage is claimed.

## Operational failures

There are three C1 application-validation failures, all in the ten-case GaRAGe cohort, caused by nonexistent source/span catalogue references. Decimal aliases are supported only for a real index; these failures are not silently repaired. They receive a neutral operational response, not successful evidential-CFAF credit. All 56 provider requests return successful, complete Structured Outputs; no provider refusal, timeout, truncation or HTTP error occurs. Those states are nevertheless tested independently with the official SDK over mock transport. No retry, resampling or post-output inference change follows the failures.

## Resource use

| System | Actual attempts | Input tokens | Output tokens | Summed SDK-provider seconds |
|---|---:|---:|---:|---:|
| Standard A | 28 | 72131 | 2972 | 69.410 |
| Guard B | 0 extra | 0 extra | 0 extra | Local postprocessing only |
| Component C1 | 28 | 100803 | 10367 | 140.951 |
| Total new pilot | **56** | **172934** | **13339** | **210.361** |

The two P5 no-view cases use zero A/C1 requests. Maximum actual C1 requests per selected case is one. The isolated renderer ablation adds zero calls. Total selected-case wall sum is 212.313 s; measured work outside the SDK-provider wrapper is 1.953 s. The provider timer includes the SDK request/response and local proposal parsing, so it is not a pure wire-transport measurement or full task CPU time. All installation, inspection, testing, reporting and commit time remains included in the separate two-hour task bound/completion receipt.

C1 uses more input/output tokens and more summed request latency than A in this run despite using one call. Provider-reported cached input tokens are 25600 for C1 and 0 for A; application model-cache hits are zero. This does not prove a speedup over historical two-call C or isolate cold/warm provider behavior. No monetary price or non-inferiority estimate is inferred. No local NLI model was loaded: optional model load time, memory, truncation and cold/warm benchmarks are NOT_RUN rather than fabricated measurements.

## Tests, regressions and acceptance

The new suite passes **54 tests**, including 300 historical-selector differential states in one test, Hypothesis hidden/absent cases, dense/sparse 1/5/15/30 sources, explicit role requirement, empty/cyclic/missing requirements, multipart person/count binding, metadata date versus access kind, threshold aggregate scope, DENY/P5, revocation/cache scope, invalid/alias/stale references, prohibited publication, quota accounting, retriever substitution and exactly one official-SDK transport attempt. Optional NLI is absent and core import/demo still work.

Before freeze, a property test exposed false dependence of the fixed P5 template on a short denied string matching contract enum text. The adapter now excludes denied records before projection/search and the canonical no-view/CFAF response is validated independently of private-string coincidence. This offline repair precedes all live outputs. No inference source changed after freeze.

Historical regressions run only in disposable copied Git sources and a dedicated legacy environment with credentials removed. The advanced run passes 691 tests; three initially fail because pyarrow is missing, then all three pass separately after installing pyarrow 26.0.0 in the **legacy-only** environment. Thus all 694 advanced checks pass across the two recorded runs. The original suite on exact committed LF bytes passes 77 tests and 13 subtests, retaining one known pre-existing failure: test_preheldout_attempt1_plan_artifacts_are_plan_only expects the already committed HELDOUT_RUN_AUTHORIZATION.json to be absent. The archived file is preserved. Earlier scratch-only CRLF checksum failures are resolved by using exact Git bytes for that suite; no historical source or protocol is edited.

A local git-clone attempt failed because the restricted Windows MSYS shell could not initialize. Regression setup therefore used git cat-file and a disposable copy of Git metadata; it did not request extra access or mutate the source repository. Existing working-byte hash tests and exact committed-protocol-byte tests use the appropriate separate scratch representation. Full logs/XML and regression_audit.json retain the failures and their environment-only resolutions.

**Acceptance:** the engineering reference path is delivered and exercised offline and through real one-call API requests. Explicit zero-call paths, sparse/reference contracts, interchangeable retrievers and governance tests work. Quality acceptance remains limited: natural-language structured-view fulfilment, semantic dependency/support completeness, temporal/qualifier handling and three invalid references need later, separately preregistered development. Memory-only quota and policy callbacks need real service integration. No statistical equivalence, general factual superiority or production readiness is claimed.

## Artifacts and local publication

- README.md provides exercised install, offline-demo, test and explicit bounded-live commands. ARCHITECTURE.md, MAKE_OR_REUSE.md and MIGRATION.md document actual boundaries, reuse, licenses and limitations.
- component_manifest.json and code_size_report.json account for copied/new runtime, adapters, tools, tests, docs and the complete isolated environment. results/freeze.json fixes configuration, prompts, schemas, source files and selected input/gold hashes; exposure_manifest.json records zero newly opened records.
- api_usage.json, results/pilot_summary.json, renderer_ablation.json and qualitative_review_summary.json contain aggregate observations. Full papers/contexts, questions, original gold, raw API traffic, model outputs, case notes and private traces remain ignored under results/local/.
- security_audit.json verifies actual payload equality, forbidden-field exclusion, frozen code, protected worktrees/refs and source privacy. checksums.sha256 covers the public delivery. The adjacent completion receipt records final SHA, clean branch, elapsed wall time, protected-state checks and manual push command.

Only a local commit is produced. The manuscript remains unchanged. To publish later from the isolated worktree: `git push -u origin ComponentBasaedCFAF`. This command is provided for the user and is not executed automatically.
