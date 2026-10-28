"""Render the measured development report; no external calls."""
from .artifacts import *
from .deadline import elapsed

def pct(x):return 'n/a' if x is None else f'{100*x:.2f}%'
def table(group,configs):
 lines=['| Configuration | Accuracy | Balanced accuracy | FULL recall | CFAF recall | Unnecessary refusal | Failure to restrict | ERROR |','|---|---:|---:|---:|---:|---:|---:|---:|']
 for c in configs:
  m=group[c];lines.append(f"| {c} | {pct(m['accuracy'])} | {pct(m['balanced_accuracy'])} | {pct(m['full_recall'])} | {pct(m['cfaf_recall'])} | {m['unnecessary_refusal_count']} ({pct(m['unnecessary_refusal_rate'])}) | {m['failure_to_restrict_count']} ({pct(m['failure_to_restrict_rate'])}) | {m['errors']} |")
 return '\n'.join(lines)

def render():
 a=read(ROOT/'ablation_results.json');u=read(ROOT/'api_usage.json');r=read(ROOT/'regression_audit.json');s=read(ROOT/'security_validation.json');e=read(ROOT/'source_role_diagnostics.json');m=read(ROOT/'experiment_manifest.json');now=elapsed()
 text=f'''# CFAF request-evidence verification: development report

**Result:** deterministic RECV exposed a useful qualifier check but did not improve overall development accuracy. On forty cached assessments, B prevented one label-incorrect FULL and lost one correct FULL. On the thirty-case paired live pilot, B lost one correct FULL and prevented no additional incorrect FULL. Source rules changed no measured decision. The optional selective-verifier trigger scan found zero eligible cases. This version should remain an experimental/shadow control rather than become the unconditional default.

All experiments used **gpt-4o-mini**, temperature 0, one repetition. All {u['attempts']} successful network responses reported `gpt-4o-mini-2024-07-18`. No stronger model, embedding, retry or model judge was used.

## A. Architecture

Starting branch was `experiment/refusalbench-iterative-dev-v1`, verified at `{m['baseline_commit']}`. Work is isolated on `experiment/cfaf-request-evidence-verification-v1`. The `wolala2026` branch remains at `{r['historical_branch_commit']}`. All {r['protected_prior_files']} pre-existing tracked working files retain their original SHA-256. Previous experimental observations and gold labels were preserved.

The eight named stages remain QUERY_PROFILING, CANDIDATE_RETRIEVAL, ACCESS_AND_SAFETY_RESOLUTION, EVIDENCE_LABELLING, SUFFICIENCY_AND_PERMITTED_OUTPUT, TOP_LEVEL_MODE_SELECTION, RESPONSE_REALIZATION, and VALIDATION_TRACE_AND_FEEDBACK. Within Stage 5, the new `assess` component computes independent request-coverage and source-capability diagnostics and combines the enabled constraints with the existing sufficiency/policy conditions. It produces validated request fulfilment for the existing claim assessment. Stage 6 imports the **unchanged** original `TopLevelModeSelectionStage`.

Access permission, evidential role, support, request completeness, top-level mode and public realization remain separate. The selector permits FULL only when all enabled essential fulfilment conditions pass. RECV does not grant access, manufacture support or promote a previously unsupported request. Explicitly identified counterevidence remains a veto. General internal contradiction detection was not introduced.

`integration.py` is a version-local continuation of v02. The upstream analysis prompt, query profiler/fallback, semantic schema, generator prompts and six-field public response schema are unchanged. A0 and B use exactly the same policy projection and semantic assessment; generator differences are limited to the gate-produced response contract. A1/A2 are deterministic decision ablations without separate public generation. The shared prompt control receives the same question, permitted views, query profile, target bindings and assessment; it receives no gate decision or new internal verification result.

## B. Implementation

`request_evidence_coverage.py` reuses existing requirement IDs and request types. It enriches them with answer type, conservative relation family, explicit first/earliest/last/latest/only/unique qualifiers, complete-list wording and explicitly requested precision. It distinguishes named identity from description, scalar count from average/sum, content from metadata, individual from aggregate, and ordinary temporal answers from explicit range/day requirements. An ordinary WHEN question does not acquire an exact-calendar-day requirement.

For each requirement, RECV checks assessment validity, one-to-one mapping, candidate availability, authorized span resolution, grounded PRIMARY/SUPPORTS use, known counterevidence, typed support, answer form, completeness, referent resolution, relation/qualifier properties, view scope and semantic-field consistency. Coverage states are COVERED, PARTIALLY_COVERED, NOT_COVERED and UNKNOWN. UNKNOWN is not evidence that a fact does not exist. Results carry request/assessment hashes, supporting references, specific rule codes and serializable structured diagnostics.

A verified span establishes provenance and exact source text; it does **not** prove arbitrary natural-language entailment. A typed semantic relation remains an analyzer attestation. Every coverage row explicitly records that it is not a deterministic entailment proof. First/only/list completeness cannot be established merely by finding a matching name or date. The old combined Boolean lacks independently scoped qualifier evidence, so these cases can remain UNKNOWN.

The configurable source registry contains seventeen versioned rules covering browser visits versus obligations/actions/completion, email requests versus completion, invoice issuance/amount versus payment, receipts versus universal obligation closure, task notes versus completion, aggregate versus individual disclosure, and metadata versus body content. Capability states distinguish PERMITTED, FORBIDDEN, ADDITIONAL_EVIDENCE_REQUIRED and UNKNOWN. Uses needing additional evidence become CONTEXTUAL for the asserted requirement unless another authorized PRIMARY source supplies the missing relation.

Source provenance is a trusted application object bound to neutral view ID, source type and content hash. The original synthetic InfoBank ingestion fields are explicitly trusted **test provenance**. No production connector authentication was demonstrated. RefusalBench general documents remain unattested/UNKNOWN, which alone is not a veto. Restricted aggregate/metadata source types follow authoritative policy projection. Document-body text cannot declare its own trusted source type. These conservative default rules are configurable; a more specific authenticated completion record can justify an application-specific capability. The pilot does not validate every source exception.

Existing refusal reasons retain precedence when v02 already blocks fulfilment. Newly added failures identify the exact requirement and rule. Public messages distinguish an unverified answer form, unresolved qualifier/list coverage, internally inconsistent assessment or insufficient source capability. Internal diagnostics, policy provenance and source identities are excluded from the public trace. [RECV_SPEC.md](RECV_SPEC.md) and [SOURCE_CAPABILITY_RULES.md](SOURCE_CAPABILITY_RULES.md) define the interfaces and limitations.

## C. Regression verification

The final current-and-prior compatibility run passed **448 tests**, including **67 new tests**; two byte-hash tests were deliberately run separately against the unchanged real working files and both passed. Thus 450 distinct current/prior checks passed across those suites. The original CFAF suite additionally passed 77 tests and thirteen subtests, with one known historical failure.

The known failure is `test_preheldout_attempt1_plan_artifacts_are_plan_only`: it expects an already committed `HELDOUT_RUN_AUTHORIZATION.json` to be absent. The authorization file and old test were left unchanged. This is not a new regression.

The initial isolated run reported four environment-dependent failures: two old task-clock/budget tests used an expired historical deadline, and two byte-hash checks compared recorded CRLF working bytes with normalized LF Git blobs. The final compatibility process reanchors only the archived clock inside the test process, preserves all old sources, and runs those two hash-only checks on the unchanged real working files. Both the initial and corrected results are retained. Historical tests that can write artifacts ran in a disposable exact-Git-blob checkout with the API key removed.

New tests exercise supported FULL, missing identity/date/quantity, wrong answer form, incomplete multipart requests, first/only/last uncertainty, ordinary WHEN precision, aggregate and metadata FULL, restricted individual/body views, missing/UNKNOWN evidence, all seventeen default capability rules, claim-relative roles, stale/untrusted provenance, additional supporting sources, invalid spans, DENY/P5 isolation, gold exclusion, public/internal separation, cross-field invariants, bound focused attestations and the durable API/deadline limits. There are **zero new regressions**.

## D. Controlled ablation results

The primary cached study uses forty already-exposed RefusalBench v02 assessments: iterative round_03 and the prior paired regression, twenty each. It contains twenty FULL and twenty CFAF gold labels. A0 exactly reproduces the previously saved selected modes. No model call occurred in this phase.

{table(a['cached']['systems'],['A0','A1','A2','B'])}

The cached changes are fully attributable to RECV: the first-working periodic-table qualifier becomes UNKNOWN, preventing a label-incorrect FULL; the World Cup scorer-plus-goal-count answer is incorrectly rejected by the type check. A2 changes no decision. B makes exactly the A1 changes. The two new refusals trade one improvement for one regression; neither accuracy nor balanced accuracy improves.

The fixed live sample contains ten original synthetic InfoBank cases (the first existing matched pair in each of P1-P5) and all twenty already-exposed round_03 RefusalBench cases. It has fourteen FULL and sixteen CFAF labels. Selection, runtime input hashes, code, prompts, schemas, settings and optional triggers were frozen before live calls. The upstream assessment is generated once per case and replayed identically for A0/B and the control. P5 makes no calls. This phase is separate from the cached study; overlapping records are never pooled as independent observations.

{table(a['live']['systems'],['A0','A1','A2','B','shared_control','C'])}

A1/A2 entries are gate-only decisions. C is an explicitly reused B result after a zero-trigger scan, not a new set of verified model answers. Two invalid upstream assessments remain ERROR for every system and every primary denominator. The raw pipeline can complete and display a CFAF response, but that does not earn a successful-refusal credit.

On the ten InfoBank cases all configurations and the control achieve 10/10 mode correctness. All four contrasting FULL/CFAF matched pairs behave correctly; the fifth pair is the P5 no-disclosure pair and is also correct. On the twenty RefusalBench cases, A0/A2 score 70%, A1/B/C 65%, and the shared control 75%. A0/B have respective FULL recall 80%/70% and CFAF recall 60%/60% on that subset, with two shared ERROR cases. This is not evidence of general performance on new data.

The only live gate change is the same World Cup record already identified in the cached study. It is one unique exposed example observed twice, not two independent correct-FULL losses. No incorrect FULL is newly prevented in the live sample. [changed_decisions.jsonl](changed_decisions.jsonl) records every changed configuration, unsatisfied requirement and rule; no gold labels or interpretations were changed.

Coverage diagnostics identify 41 requirement elements in the forty cached cases: 20 COVERED, 18 NOT_COVERED, 2 PARTIALLY_COVERED, and 1 UNKNOWN. The thirty live profiles yield thirty elements: 13 COVERED, 16 NOT_COVERED, and 1 PARTIALLY_COVERED. These counts include no-view and invalid-assessment cases and are **not** independently annotated requirement recall. In particular, the inherited profiler can collapse a multipart WHO-and-HOW-MANY question into one count requirement; the element count does not certify a complete decomposition.

## E. Selective verification and cost

The optional implementation uses the same gpt-4o-mini with at most 500 output tokens. Its predeclared trigger requires B UNKNOWN, an otherwise fully supportable A0 request, no source veto, no failed mechanical check, and only the declared relation/qualifier/list/consistency uncertainties. Focused results bind the exact request signature and assessment hash, retain existing authorized span IDs, and cannot override access restrictions, false mechanical checks or known counterevidence.

**Zero of thirty cases triggered.** No focused model call, extra C generation or verifier token cost occurred. C therefore reuses B exactly. The implementation and controlled tests exist, but empirical verifier quality, false-positive effects and cost per corrected decision are **not estimated**. The zero-trigger result also exposes trigger blindness: wrong positive completeness/referent flags can leave no uncertainty for the selective verifier to see. Already-refused v02 cases are intentionally outside this narrow optional trigger.

Measured total usage is {u['attempts']}/170 external attempts, all successful at the HTTP/provider level, with zero retry/error/embedding attempts. There were 28 semantic-analysis calls, one existing query-only fallback, 28 A0 generations, 28 B generations and 28 independent-control generations. Actual input/output usage is **{u['input_tokens']:,} / {u['output_tokens']:,} tokens**; summed network-call latency is **{u['summed_api_latency_ms']/1000:.3f} seconds**. All raw messages, token use, model versions and latencies are preserved.

The paired experiment uses {u['calls_per_case_experiment']:.3f} calls per case because it generates three responses while sharing upstream analysis. A0 and B each correspond to 57 calls/30 cases (1.9 per case) when their shared upstream cost is counted once for a deployment. Their respective input/output totals are 90,490/10,007 and 90,492/10,010 tokens. These hypothetical per-system totals overlap and must not be added to the actual experiment total. Deterministic controls add no LLM call. B Stage 5 has median {u['B_stage5_cpu_ms']['median']:.3f} ms and maximum {u['B_stage5_cpu_ms']['max']:.3f} ms locally; A0 also computes disabled diagnostics, so this is not an isolated incremental CPU comparison. No unverified monetary price was used, and no cost-effectiveness claim is justified by the negative reliability result.

## F. Error analysis and source-role diagnostics

**Correct FULL lost:** the World Cup question asks both who scored most and how many goals. The passage and candidate support James Rodriguez and six goals. The inherited profile preserves a single AGGREGATE_COUNT requirement, while the analyzer gives an identity/composite answer form. RECV's strict numeric form check blocks the complete answer. This is an interface/decomposition error, not missing evidence. The measurement was retained; no rule was silently weakened after seeing the outcome.

**Incorrect FULL prevented in cached data:** the periodic-table passage supports Mendeleev and Meyer independently composing tables in 1869, but does not independently establish the stronger first-working qualifier in the candidate. RECV records unresolved qualifier coverage. This result supports a targeted check, not a general ability to infer historical priority.

**Incorrect FULL still accepted live:** the Oregon passage contains reinstatements in 1978 and 1984; listing both does not resolve the terse request's intended event. The Brant Daugherty passage contains both Noel Kahn and a guest role named Mike, while the answer selects only Noel Kahn. In each case the model marks completeness and referent resolution true. Valid citations and consistent positive flags do not prove complete fulfilment, and neither case triggers C.

**Unnecessary refusal already present in A0:** the Lord's Prayer Boolean candidate is directly supported, but its relation/qualifier Boolean is false. The Traveling Wilburys assessment overlooks distributed member names; the query also includes an unestablished Grammy premise, making the official FULL interpretation questionable. Original labels remain unchanged. These errors are upstream limitations, not improvements or regressions caused by RECV.

**Two ERROR cases:** global-average television air dates and global cricket hat-trick statistics return an empty `source_assessments` list despite a supplied source. The inherited parser rejects `SOURCE_ROLE_COVERAGE_INVALID`. References themselves are not forged. No retry, repair or successful-refusal credit was introduced.

The source registry recomputation audit found zero application mismatches. Live cited support contains four PERMITTED and twelve UNKNOWN capability occurrences; cached support contains twenty-nine UNKNOWN occurrences. These are reference occurrences, not independent facts. UNKNOWN provenance never becomes a blanket veto. Source-only A2 blocks zero previously accepted answers, so it prevents zero false FULL and loses zero correct FULL in these samples.

Against eight usable original synthetic source-role annotations, both upstream and effective roles agree 6/8 (75%); relations agree 4/8. P1B and P4B retain PRIMARY model labels despite contextual fixture roles. They already lack usable supporting relations/citations and already refuse, so source constraints on asserted support do not repair those unused role labels. The seventeen controlled rule tests demonstrate mechanics, while this small pilot does not establish broad empirical source-capability accuracy. RefusalBench has no trusted source-type/role gold usable for that claim.

Of twelve valid gold-CFAF refusals, A0 and B match the assessable construction/lexical reason target in 4/12 cases (3/6 InfoBank reason classes and 1/6 RefusalBench category proxies). The control has four matches among six assessable reasons and six uncategorized/generic refusals. A1/A2 generate no explanation and receive no invented explanation score. Lexical category matches are proxies, not proof of correct justification. P1B/P3B/P4B show that a correct refusal mode can still carry the wrong reason class.

Internal/public reason class and realization agree 33/33 across A0/B refusals. Public text exactly matches the internal template in 29/33; the four exceptions are the two deterministic P5 cases in each system, which intentionally use the identical canonical no-support sentence. This is not a semantic reason-class conflict. The scoped review in [qualitative_review.jsonl](qualitative_review.jsonl) is non-independent and does not cover every factual proposition in every FULL answer.

## G. Security and exposure

All 113 serialized model payloads pass the current policy/profile/binding guard, forbidden-field scan and frozen-input checks. A0/B share the exact assessment/projection in all thirty cases. The control never receives the selected mode, response contract or new verification result. No original benchmark IDs, expected labels, evaluator answers, forbidden document body or hidden-source count is sent to a model. Public responses remain nonempty, satisfy the common six-field schema and preserve mode/fulfilment cross-field invariants. There are zero invalid/unauthorized span references and zero new public-schema errors. The two upstream role-coverage failures are separately visible and count as errors.

Both P5 public traces are exactly equal for A0 and B, including the control response; there are zero P5 API calls. Aggregate and metadata projections remain limited to permitted values/fields, and DENY sources remain absent. The original selector and all 789 protected prior files remain byte-identical.

No new RefusalBench record was exposed: the inherited ledger remains **130 eligible exposed / 1,234 eligible**, with **1,104 unseen**, a 617-record ceiling, thirty reserved source groups and eighteen additional untouched groups. Selection reads only previously committed exposed inputs. One inherited regression reads the official source with an explicit annotation-only Arrow schema; ignored passage fields are not materialized or inspected. Reserved/untouched question/context content and student-created independent InfoBank cases were not opened. The preparation manifest's no-official-source-open statement describes preparation, while this annotation-only regression read is explicitly recorded in the final audit.

The security audit validates exact contracts, provenance, fixture canaries and trace equality. It does not establish universal resistance to paraphrased leakage or arbitrary adversarial natural-language input. No access restriction was weakened.

## H. Scientific interpretation

The cached A0/A1/A2/B comparisons use identical frozen semantic inputs. The live comparisons share upstream inference and fixed prompts/schemas; their sole mode change is attributable to RECV. Source constraints cause no change. Cross-run changes between cached and fresh inference must not be attributed to the deterministic gate. There are no formatting gains: public schemas are valid throughout, while the two semantic-coverage errors remain penalized.

The material is exposed, adaptively developed data: forty original synthetic InfoBank cases were already used before this task, and all RefusalBench records were already exposed. The two phases overlap, the InfoBank observations are paired, and the sample is small. No significance, independence or production generalization claim is made. The study demonstrates auditable deterministic mechanics and exposes their limits; it does not demonstrate a net reliability improvement for the combined default.

## I. Recommendation and completion

Keep the current experiment available for shadow diagnostics and controlled further development. Mechanical provenance/span/view checks and explicitly authenticated source-capability constraints are useful safeguards, but the full conservative B gate should **not** become the unconditional default on this evidence. Repair multipart profile/support alignment, validate answer forms at requirement scope, improve missing-evidence versus ambiguity reasons, and obtain claim-relative trusted connector metadata before broader use. Evaluate selective-verifier triggers against confidently wrong positive flags and false refusals on development material before spending reserved evaluation data.

Independent evaluation should use the still-reserved source groups and student-created InfoBank cases only under later authorization, with frozen decomposition, rules, trigger policy and primary scoring. It should measure both false FULL prevention and correct FULL loss, plus explanation quality and actual added calls.

The task began at **2026-10-28 20:02:32 UTC**, using the wall start recorded at first inspection and a monotonic anchor initialized during setup and calibrated back to that start. The complete inspection interval is included. This report was generated after {now/60:.2f} minutes. The provider enforces 170 attempts and a 55-minute new-request cutoff; the task deadline is sixty minutes. API execution completed well before the cutoffs. The final completion receipt records inclusive end time and commit SHA. No push or merge was performed.

[CHANGED_FILES.txt](CHANGED_FILES.txt) lists every new committed file. [checksums.sha256](checksums.sha256) covers all deliverables except itself. The final commit SHA is reported to the user and in the completion receipt outside the repository to avoid a self-referential commit hash. The code, frozen manifests, raw observations, tests, negative findings and limitations are retained for review.
'''
 (ROOT/'REPORT.md').write_text(text,encoding='utf-8')
 print('Report written',len(text.split()),'words; elapsed',round(now/60,2),'minutes')
if __name__=='__main__':render()
