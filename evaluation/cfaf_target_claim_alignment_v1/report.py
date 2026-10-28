"""Render measured cross-branch and paired study report; no API calls."""
from .artifacts import *
from .deadline import elapsed

def pct(v):return 'n/a' if v is None else f'{100*v:.2f}%'
def table(group,configs):
 lines=['| Configuration | Accuracy | Balanced accuracy | FULL recall | CFAF recall | Unnecessary refusal | Failure to restrict | ERROR |','|---|---:|---:|---:|---:|---:|---:|---:|']
 for c in configs:
  m=group[c];lines.append(f"| {c} | {pct(m['accuracy'])} | {pct(m['balanced_accuracy'])} | {pct(m['full_recall'])} | {pct(m['cfaf_recall'])} | {m['unnecessary_refusal_count']} ({pct(m['unnecessary_refusal_rate'])}) | {m['failure_to_restrict_count']} ({pct(m['failure_to_restrict_rate'])}) | {m['errors']} |")
 return '\n'.join(lines)

def render():
 a=read(ROOT/'ablation_results.json');u=read(ROOT/'api_usage.json');s=read(ROOT/'security_validation.json');r=read(ROOT/'regression_audit.json');e=read(ROOT/'source_role_diagnostics.json');m=read(ROOT/'experiment_manifest.json');duration=elapsed()/60
 text=f'''# CFAF Trusted Target and Claim-Evidence Alignment: development report

**Outcome:** metadata DATE_TIME typing is corrected, trusted catalogue and claim provenance are explicit, and a small structured aggregation reuse adapter passes controlled checks. There is **no measured FULL/CFAF accuracy improvement over same-input A0/B3**. T1-T3 remain shadow-only. No correct FULL is newly lost and no additional incorrect FULL is prevented. Useful diagnostic results must be distinguished from classification gains.

The starting commit is `{m['baseline_commit']}` on the preceding RDA branch. Work is isolated on `experiment/cfaf-target-claim-alignment-v1`. All **912** earlier tracked working files and the original `wolala2026` branch remain unchanged. No merge, push or stronger model was used.

## 1. Source inspection and exact lineage

The requested current remote `main` was fetched as `refs/remotes/origin/main`, read-only, at **`8079f29dc3a97273f51b55b2a22f9ff896a2e758`**. Source files were inspected from that exact Git object into a work-directory copy; they were not merged or checked out over the experiment. The ten requested files, including both backend test files, have exact blob IDs, byte SHA-256 and sizes in [remote_source_manifest.json](remote_source_manifest.json). The final audit rereads those Git blobs and finds no hash mismatch.

The concise [CROSS_BRANCH_REUSE_REPORT.md](CROSS_BRANCH_REUSE_REPORT.md) was written **before runtime implementation**. It records dependencies, assumptions and reuse decisions. No external scenario package or student-created case corpus was executed or loaded; the evaluation infrastructure was inspected statically.

## 2. Reused, adapted and rejected functions

The owned-object module's `extract_product_codes`, `_query_product_identifiers`, `_declared_product_aliases`, `contains_purchase_evidence` and `resolve_owned_object_context` were investigated with their tests. Their explicit identifier/alias, cluster, unique-target and clarification design was adapted generically. Product-specific categories, narrative purchase inference and the unique-purchase fallback were not transplanted as universal entity truth. The new component requires authorized catalogue/ingestion metadata.

A dependency-closed pure subset directly reuses `relevance.claim_relation_signals`, `_pattern_hits`, its relation-pattern constant, and `ai_provider._keyword_tokens` / `deterministic_allowed_keyword_matches`. The complete provider module is not imported: it includes SDK, credential and multi-provider concerns unrelated to this deterministic adapter.

`evidence_service.question_source_support`, `answer_source_support`, number/token/identifier helpers and `select_minimal_evidence_sources` were inspected and **adapted**, not imported as hard gates. The full module depends on SQLAlchemy Session, models, policy_engine, action_closure, citds_classifier and controlled-failure configuration. The adapter uses scoped lexical/numeric diagnostics, no threshold veto, no acceptance of a number merely because it appears in the question, no temporal answer correction and no actual evidence pruning. A bounded greedy recommendation replaces combinatorial subset search for diagnostics only.

`AggregateConfig`, `AggregateContribution`, `_public_refusal` and `execute_aggregate` were selectively reused after inspecting the entire small executor and its tests. Only stdlib dependencies and three explicit policy-label constants are supplied. Free-text numeric ingestion is deliberately rejected. Production router/database integration is not copied.

`citation_service.citation_from_chunk` supplies the source association, offsets and hash invariants, while existing neutral span references remain the implementation. Private document URLs/filenames and an unconditional PRIMARY label are not exported. `human_qa_tools` and `external_scenario_corpus` inform the pending-human-judgment, stable-ID, checksum and runtime/gold-separation design. No human annotations or agreement are fabricated.

The selected source manifest records fourteen functions/classes/constants. A controlled test verifies each selected source body matches its exact original UTF-8 source hash. Entire backend modules were not imported without dependency analysis. The full fetched-main SQLAlchemy/router integration suite was not executed; selected pure mechanisms are covered locally.

## 3. Trusted target resolution and reference handling

`trusted_target_resolution.py` operates over policy-permitted catalogue entries. Each entry associates a permitted neutral view with a private application entity key, target type, declared aliases/identifiers and optional edition/ownership facts. Catalogue signatures and view hashes bind the request. Native proof objects prevent an LLM dictionary from declaring itself authoritative; altered bindings/content are rejected. Callers must provide a fresh policy-projected request, and original pre-model access/binding checks remain mandatory.

Explicit authorized identifiers and contiguous declared aliases precede query-target anchors. Multiple related documents may cluster under one object. An owned-type request requires trusted ownership evidence, and a previous edition requires declared version information. A sole retrieved item or a narrative entity mention does not establish a trusted target. States RESOLVED, AMBIGUOUS, UNRESOLVED and NOT_APPLICABLE remain distinct. Candidate counts, titles, identifiers and catalogue anchors are privileged; no new target information is sent to models in this trial.

In cached RefusalBench data, 0/40 cases resolve from trusted application metadata: sixteen are NOT_APPLICABLE and twenty-four UNRESOLVED. This is not evidence that the factual questions are unanswerable. In live data, seven of twenty-four resolve (29.17% overall, 38.89% of eighteen applicable cases), eleven are UNRESOLVED and six NOT_APPLICABLE. There are no live AMBIGUOUS targets. Controlled synthetic examples cover ambiguity, same-title objects, owned-object clusters and editions.

Crucially, **no live case is newly resolved or lost relative to the existing guarded target binding**. The implementation makes association/provenance more explicit and handles synthetic cases beyond the simple pilot, but does not demonstrate an empirical new entity-resolution advantage on this fixed subset. A resolved document association also does not prove that its historical note, role or obligation answers the requested relation.

## 4. Claim-specific relation alignment

`claim_evidence_alignment.py` minimally extends each essential RDA requirement with target/subject dependency, predicate/query span, proposed value/type, qualifiers, temporal scope, authorized support, authority, relation status and remaining uncertainty. Value extraction and relation authority are separate: TRUSTED_STRUCTURED_SOURCE, DETERMINISTIC_TYPED_EXTRACTION, LLM_SEMANTIC_ASSESSMENT and UNRESOLVED cannot be silently interchanged.

All 42 cached and 26 live requirement rows receive a claim record. That is complete **mechanical linkage**, not independently annotated semantic correctness. Cached relation authority contains 25 LLM assessments and seventeen unresolved rows. Live authority contains thirteen LLM assessments, eleven unresolved rows and **two trusted structured field matches**. Those two are the file-type and creation-date fields of an authorized, resolved metadata target.

Application-attested structured claims must match the actual permitted JSON predicate/value/type/subject fields, request signature and content hash. Controlled examples detect wrong object, numeric value, actor/role and count-versus-average use. An LLM object or copied hash cannot fabricate a different structured value. These tests do not imply that arbitrary free-text actor/role or entity/quantity relations are thereby solved.

Per-claim lexical relation and number diagnostics adapt the main helpers without calling overlap entailment. Scoped minimal-evidence recommendations never remove model context or known counterevidence. Original source/span provenance remains deterministic. New claim data stay internal; source permission and original independent sufficiency still govern the existing selector.

The live sample has three label-incompatible FULL decisions. Two receive some claim uncertainty, but **none receives a new lexical relation/numeric alert**. Five correct FULL decisions also receive some uncertainty. Cached data similarly warn on two of four label-incompatible FULLs and eight correct FULLs; the new lexical alerts cover none of those four bad FULLs. These are warning-coverage proxies, not independent unsupported-answer adjudication. They show why lexical diagnostics were not promoted to hard refusal rules.

## 5. Metadata DATE_TIME typing correction

`metadata_value_typing.py` separates access class, requested attribute, value type, precision and supported value. `file_type` remains a compatible metadata requirement with STRING value semantics; `created_at` becomes a DATE_TIME answer kind/value while retaining METADATA access. A trusted metadata field is read only from authorized projected JSON and a validated target association. Calendar parsing rejects invalid dates, and an explicitly requested year can be derived from a trusted timestamp. An ISO-looking date in free text acquires no structured authority.

All **17/17 original authored type sequences now pass**, compared with the preceding 16/17. The original expectations and queries are unchanged, with their source SHA-256 preserved. Seven additional value-validity cases pass. The live profile records one METADATA-to-DATE_TIME representation correction, for the creation-date requirement of the metadata example. It yields a trusted field match but no new mode change, since that case was already correctly FULL.

This is a generic field-schema correction, not a special rule for an exposed question. It is an engineering improvement independent of FULL/CFAF accuracy.

## 6. Paired cached results: incorrect FULL prevented and correct FULL lost

The forty cached observations are the same exposed v02 assessments used by the preceding studies: twenty FULL and twenty CFAF gold labels. A0 and B3 exactly reproduce their prior selected modes. The same semantic JSON, candidate, roles, support/counter IDs and model-visible profile are held frozen; target/claim/type diagnostics are recomputed. No model call occurs in this phase.

{table(a['cached']['systems'],['A0','B3','T1','T2','T3'])}

There are zero target/claim-induced gate changes, zero newly lost correct FULL and zero newly prevented incorrect FULL. `changed_decisions.jsonl` is therefore correctly empty. This is expected under the predeclared shadow policy and must not be presented as a demonstrated reliability gain.

## 7. Limited live results and causal separation

The fixed live set is exactly the preceding 24-case mixed subset: ten original synthetic InfoBank P1-P5 cases plus fourteen already-exposed RefusalBench records; eleven FULL and thirteen CFAF labels. Each permitted case gets one shared upstream analysis. A0, T3 and the independent prompt control generate responses; B3/T1/T2 are gate-only comparisons. The two P5 cases make no calls. Runtime source, prompts, schemas and input hashes were frozen before the first live request and remain unchanged.

{table(a['live']['systems'],['A0','B3','T1','T2','T3','shared_control'])}

Every arm scores **20/24 (83.33%)**. FULL recall is 10/11, CFAF recall 10/13, unnecessary refusal 1/11 and failure to restrict 3/13. All ten InfoBank cases have correct modes, including four contrasting pairs and the P5 pair. RefusalBench contributes 10/14 correct. No source/span/schema or upstream role-coverage error occurs in this fresh run.

The preceding RDA live run scored 19/24 with one invalid upstream role-coverage assessment. Its change to a valid assessment in the new run benefits **A0 and every other arm equally**. That cross-run improvement is upstream inference variability, not an effect of target binding, relation checking or type representation. The new mechanisms do not change a same-input binary decision. Cached/live cases overlap and must not be pooled as independent observations.

T1/T2/T3 remain shadow-only, and T4 was not enabled after looking at labels. The metadata correction is explicitly separated from target resolution and lexical relation checks. No new generation prompt, stronger model or second semantic judge confounds the comparison.

## 8. Reasons and shared-control benefits

A0 and T3 each match five of ten assessable valid refusal-reason targets. The control matches four of six assessable reasons and produces four uncategorized/generic refusals. B3/T1/T2 have no separately generated public explanation score. These are original synthetic reason-class labels or lexical behavior-category proxies, not proof that each explanation is semantically justified. **No reason-correctness improvement over A0 is demonstrated.**

Internal/public reason class and realization agree in 22/22 raw A0/T3 refusal contracts. Text is identical to its internal template in 18/22; the four exceptions are the two P5 cases in each arm, using their canonical no-support sentence. Public responses are nonempty and satisfy mode/status cross-field invariants.

The prompt control receives the same original legitimate query, permitted views, trusted old view association and shared semantic assessment, but no gate decision or response contract. Neither generated system receives new private target/claim diagnostics. Thus equal control performance demonstrates no additional classification benefit here; it does not test whether exposing a carefully sanitized trusted-claim interface to a generator would help in a different ablation.

## 9. API and deterministic computation cost

There are **88/120 model API attempts**, all successful: 22 shared semantic analyses, 44 A0/T3 generations and 22 control generations. No retries, embeddings, query-profile fallback, stronger model or second verifier is used. All 88 responses report gpt-4o-mini-2024-07-18, temperature 0 and one repetition. Limits remain 1500 analysis and 160 generation output tokens.

Actual input/output use is **117,981 / 10,282 tokens**, with **171.778 seconds** summed model-call latency. One separately authorized Git fetch is recorded as a source-inspection transport operation. All model attempts are durably logged before network access, including potential failures.

Target resolution, claim checks and type correction add **zero model calls**. A0 and T3 each correspond to 44 calls/24 cases and the same measured 72,356 input / 7,987 output tokens when shared upstream cost is counted once for a hypothetical deployment. These overlapping totals must not be summed. The reduction from the prior study's 110 comparative calls to 88 reflects one fewer generated comparison arm, not an inference-cost saving caused by the new mechanism.

Observed Stage-5 CPU median is 0.999 ms for A0 and 3.668 ms for T3; median paired difference is 2.643 ms. T3 maximum is 15.730 ms. These sequential single-run timings are descriptive, not an isolated repeated microbenchmark. No monetary price or cost-effectiveness claim is inferred from flat accuracy.

## 10. Structured aggregation feasibility

The small smoke adapter reuses the inspected main executor's policy filtering, contributor deduplication, finite numeric checks and configurable k threshold. Only typed authorized contributions are admitted; denied/metadata-only values are not inspected. Individual rows/identifiers, input values and unnecessary contributor counts are absent from generator context. Below-threshold output matches empty-input output.

New synthetic contributions 17, 31 and 46, plus a duplicate and denied row, produce COUNT=3, SUM=94 and MEAN=31.333333. All three smoke operations and privacy-focused tests pass without a model call. This result is separate from RefusalBench accuracy and does not constitute a production aggregation subsystem. [AGGREGATION_REUSE_REPORT.md](AGGREGATION_REUSE_REPORT.md) lists the trusted metric/unit/period/contributor and policy interfaces still needed for deployment.

## 11. Tests, security and exposure

The new controlled suite passes **65 tests**, covering more than thirty distinct target/claim/value/policy scenarios with new fictional entities and values. It includes unique and ambiguous targets, related documents, editions, mismatched entity/count and actor roles, missing components, qualifier uncertainty, metadata values, structured aggregation, invalid spans, high-confidence unsupported assessments, native-proof forgery, source capabilities and P5 indistinguishability. The main-derived source bodies pass exact provenance checks.

The complete current/prior compatibility run passes **584 tests**, with three byte-hash checks separately passing on the unchanged original working files: 587 distinct current/prior checks in those suites. The original CFAF suite additionally passes 77 tests and thirteen subtests with one known historical failure. That test expects an already committed HELDOUT_RUN_AUTHORIZATION.json to be absent; it is preserved unchanged. Expired archived-clock and CRLF/LF snapshot false failures are explicitly handled in the test process, without rewriting old source or results. There are zero new historical regressions.

Security audit status is **PASS**. All 88 serialized model payloads pass policy/profile/binding and forbidden-field checks. All 24 target/claim diagnostics replay identically from frozen inputs. Two structured metadata claims are backed by whitelisted fields of a resolved target; no LLM Boolean or lexical match is promoted to structured truth. No private catalogue title, identifier, candidate count, target trace or gate output is sent to the control or other model calls. Evidence context is not pruned. Public schemas and source/span references have zero errors. P5 public traces are identical with zero calls.

Source-role agreement remains 6/8, effective-role agreement 6/8 and relation agreement 4/8 against usable original synthetic construction annotations. These labels are exposed construction references, not independent semantic gold. The new source layer does not claim to repair unused incorrect PRIMARY labels or arbitrary free-text relation judgments.

All **912** previous tracked files and original annotations remain byte-identical. No new RefusalBench record is opened: 130 eligible records remain exposed out of 1,234, with 1,104 unseen, thirty reserved and eighteen additional untouched source groups. No student-created independent case set or external scenario package is accessed. The inherited annotation-only Arrow regression ignores reserved question/context fields. Security evidence covers exact contracts, authorized projections, hashes and controlled canaries, not universal natural-language leakage resistance.

## 12. Retain versus shadow-only

Retain the metadata access/value-type separation, native authority/provenance distinctions, exact citation bindings and source-pinned selective reuse. Keep trusted target resolution available where applications actually provide authorized identifiers, aliases, clusters and schema—not as a substitute for semantic interpretation of every plain passage. Retain the aggregation adapter as a secondary structured-input prototype pending the production interfaces listed above.

Keep lexical relation/numeric checks, qualifier/referent interpretations, evidence-minimization suggestions and T1-T3 semantics **shadow-only**. The main helpers cover a small vocabulary geared partly toward owned objects/warranty questions; the RefusalBench subset is mostly general factual prose without authoritative application entity IDs. In the actor/role case the words and role anchors occur but do not establish a unique complete relation. The periodic-table and Oregon cases remain uncertain despite positive model flags. Hard-vetoing generic warnings would also reject correct FULL answers.

A negative classification result does not imply the diagnostics have no value: the metadata field relations are independently grounded and the application boundary is clearer. It does mean this study supplies no evidence for enabling new semantic vetoes or claiming improved independent reliability.

## 13. Before independent InfoBank validation and completion

Future work needs connector-attested entity/edition schemas, requirement-specific structured relation/value records where available, adjudicated target/claim annotations and a frozen decision policy. Arbitrary unstructured role, historical-priority and exhaustive-list entailment remains unresolved by token overlap. Better semantic evidence or an independently evaluated reasoning interface may be needed for those cases, but no stronger model was introduced here. Independent student and reserved-source evaluation should occur only under later authorization, with development choices frozen in advance.

The task began at **2026-10-28 21:29:08 UTC**, with wall time recorded at first inspection and a monotonic anchor calibrated during setup to include the inspection interval. This report was generated after {duration:.2f} minutes. The durable controls stop new large work at 45 minutes, prioritize reporting at 50, stop new API starts at 55 and bound the task by sixty minutes. All API work completed before the cutoffs.

[CHANGED_FILES.txt](CHANGED_FILES.txt) lists the exact new files; [checksums.sha256](checksums.sha256) covers all deliverables except itself. The final local commit SHA and inclusive completion time are recorded in the [completion receipt](../../../cfaf_target_claim_alignment_v1_completion.json) outside the repository and returned to the user, avoiding a self-referential commit hash. No push or merge is performed.
'''
 (ROOT/'REPORT.md').write_text(text,encoding='utf-8');print('Report',len(text.split()),'words; elapsed',round(duration,2),'minutes')
if __name__=='__main__':render()
