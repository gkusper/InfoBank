"""Assemble the bounded development report without changing primary predictions."""
import collections,datetime as dt,json
from pathlib import Path
from .deadline import ensure,snapshot,limits
from .exposure import ROOT,REPO,SOURCE,metadata_only,eligible,sha,atomic_ledger
from evaluation.refusalbench_span_fix_v1.api_budget import read_jsonl,write_json


def pct(v):return f'{100*v:.1f}%' if v is not None else 'n/a'
def metric_table(items):
 text='| Sample | System | Cases | Accuracy | FULL recall | CFAF recall | Balanced accuracy |\n|---|---|---:|---:|---:|---:|---:|\n'
 for label,summary in items:
  for system in ['semantic_cfaf','shared_control']:
   m=summary['systems'][system];text+=f"| {label} | {system} | {m['n']} | {pct(m['accuracy'])} | {pct(m['full_recall'])} | {pct(m['cfaf_recall'])} | {pct(m['balanced_accuracy'])} |\n"
 return text


def main():
 ensure('final report assembly',90);ledger=json.loads((ROOT/'exposure_ledger.json').read_text());audit=json.loads((ROOT/'validation_audit.json').read_text());api=json.loads((ROOT/'api_usage.json').read_text());events=read_jsonl(ROOT/'global_api_events.jsonl');time=snapshot();begin=limits()['task_started_at_utc']
 completed=[]
 for out in sorted(ROOT.glob('round_*')):
  p=out/'summary.json'
  if p.exists():
   s=json.loads(p.read_text())
   if s['completed']:completed.append((out.name,s))
 paired=json.loads((ROOT/'paired_regression/summary.json').read_text());comparison=json.loads((ROOT/'paired_comparison.json').read_text())
 bykind={}
 for kind in api['kind_counts']:
  group=[e for e in events if e['kind']==kind];bykind[kind]={'calls':len(group),'input_tokens':sum((e.get('usage') or {}).get('prompt_tokens',0) for e in group),'output_tokens':sum((e.get('usage') or {}).get('completion_tokens',0) for e in group),'latency_sum_ms':sum(e['latency_ms'] for e in group),'latency_mean_ms':sum(e['latency_ms'] for e in group)/len(group)}
 api['by_kind_detail']=bykind;write_json(ROOT/'api_usage.json',api)
 # Reconcile inherited historical preparation statistics with the current initial
 # exposure frontier; this does not change the exact filters or any selection.
 metadata=metadata_only(SOURCE);allowed=set(ledger['allowed_development_source_groups']);prior={e['id'] for e in ledger['entries'] if e['first_exposure']=='prior_experiment'};all_exposed={e['id'] for e in ledger['entries']}
 initial_pool=[m for m in metadata if eligible(m) and str(m['source_id']) in allowed and m['id'] not in prior];current_pool=[m for m in metadata if eligible(m) and str(m['source_id']) in allowed and m['id'] not in all_exposed];authorized_total=sum(eligible(m) and str(m['source_id']) in allowed for m in metadata)
 filtering=json.loads((ROOT/'filtering_report.json').read_text());filtering.pop('prior_executed_record_ids',None);filtering.update(prior_known_exposed_record_ids=len(prior),eligible_unused_development_records=len(initial_pool),eligible_unused_development_counts=dict(collections.Counter(m['expected_rag_behavior'] for m in initial_pool)),current_unused_authorized_eligible_records=len(current_pool),total_authorized_eligible_records=authorized_total,eligible_records_in_forbidden_untouched_groups=1234-authorized_total,metadata_reconciliation='Initial-pool statistics recomputed against all prior 82 exposed IDs; post-run pool also reported. Filtering and selected IDs unchanged.');write_json(ROOT/'filtering_report.json',filtering)
 identifiers=['# Selected records by round','','Stable identifiers are full SHA-256 hashes of original record IDs and source-group IDs. Original label-bearing IDs are retained only in trusted selection/scoring artifacts, never in model inputs.','']
 for directory,s in completed:
  rows=read_jsonl(ROOT/directory/'results.jsonl');identifiers += [f'## {directory}','','| Round | Dataset index | Record hash | Source-group hash | Expected | CFAF predicted | Control predicted |','|---:|---:|---|---|---|---|---|']
  for r in rows:identifiers.append(f"| {s['round']} | {r['dataset_index']} | `{r['record_hash']}` | `{r['source_group_hash']}` | {r['expected_mode']} | {r['systems']['semantic_cfaf']['prediction'] or 'ERROR'} | {r['systems']['shared_control']['prediction'] or 'ERROR'} |")
  identifiers.append('')
 (ROOT/'selected_records.md').write_text('\n'.join(identifiers)+'\n',encoding='utf-8')
 quality='| Round | Version | UNRESOLVED profiles | CFAF specific-reason coverage | Control coverage | Invalid CFAF/control outputs | API attempts |\n|---|---|---:|---:|---:|---:|---:|\n'
 for directory,s in completed:quality+=f"| {directory} | {s['version']} | {s['query_profiles_unresolved']}/20 | {pct(s['specific_reason_coverage']['semantic_cfaf'])} | {pct(s['specific_reason_coverage']['shared_control'])} | {s['invalid_output_count']['semantic_cfaf']} / {s['invalid_output_count']['shared_control']} | {s['api_usage']['attempts']} |\n"
 primary=metric_table([(name+' / '+s['version'],s) for name,s in completed]);paired_table=metric_table([('Same 20: baseline v00',completed[0][1]),('Same 20: final v02',paired)])
 exposure_table=f'''| Exposure quantity | Count |
|---|---:|
| Original records | 1600 |
| Eligible after exact filters | 1234 |
| Maximum eligible exposure (50%) | 617 |
| Prior known unique exposed IDs, all categories | {ledger['prior_unique_exposed_records_all_categories']} |
| Prior exposed eligible IDs | {ledger['prior_exposed_unique_eligible_records']} |
| Newly exposed eligible IDs | {ledger['newly_exposed_unique_eligible_records']} |
| Total unique exposed eligible IDs | {ledger['cumulative_exposed_eligible_records']} |
| Remaining unseen eligible IDs | {ledger['remaining_unseen_eligible_records']} |
| Authorized source groups, already exposed before task | 52 |
| Reserved holdout groups preserved | 30 |
| Additional untouched groups preserved | 18 |
| Eligible records within authorized groups | {authorized_total} |
| Unused authorized eligible records at task start | {len(initial_pool)} |
| Unused authorized eligible records after task | {len(current_pool)} |
'''
 report=f'''# Iterative CFAF development under time, exposure and API bounds

## A. Time, scope and completed work

Task start: **{begin}**. Monotonic start and hard cutoff are recorded in time_limits.json. Hard deadline: **{limits()['hard_deadline_at_utc']}**. This report was prepared at **{time['at_utc']}**, after **{time['elapsed_seconds']/60:.2f} minutes**, with **{time['remaining_seconds']/60:.2f} minutes** remaining. Exact inclusive completion after the local commit is in the separate [completion receipt](../../../refusalbench_iterative_dev_v1_completion.json), also linked in the final reply.

Three fresh adaptive development rounds completed, each exactly ten expected FULL and ten expected CFAF records, followed by a separate paired regression on the already-exposed twenty round-01 inputs. No fourth round was started. All selected cases, raw outputs, unsuccessful predictions and invalid outputs remain. There is no interrupted live round. Improvements address general query typing and complete request fulfilment; general internal evidence-contradiction detection is not developed.

The task guard uses cross-process time.monotonic on this Windows host, anchored to the first tool time so initial inspection is included. At 50 minutes it prioritizes reporting and prevents another experiment; at 55 minutes it prevents new API requests; expected-duration margins and bounded subprocess/request timeouts prevent likely overruns. Deadline tests simulate the 55-minute and hard-margin conditions. All {api['attempts']} actual requests began before the 55-minute cutoff. There were no API failures or retries. The study finished its planned experiments before reporting; it did not consume time merely to chase a target score.

## B. Dataset filtering and cumulative exposure

Official dataset is RefusalBench-NQ, pinned revision `b3684f805563e6ce465e7e9b055b840a48f519c2`, original test split of 1600 rows. Original JSONL SHA-256 is `{ledger['official_source_sha256']}`. The official file and annotations were not modified. Metadata-only filtering again gives **1234** eligible records: A exact case-insensitive whole-word contradiction excludes 325, B exact REFUSE_CONTRADICTORY_CONTEXT/P-Contradiction excludes 277, overlap 236, union 366. No related-word or semantic filter was silently added.

{exposure_table}

Every available local branch's RefusalBench selection/provenance/experiment manifests was inventoried and reconciled with the earlier 10-, 42-, 10- and 20-case selected artifacts. The known union is 82 unique IDs, 70 eligible and 12 now-excluded records. No unknown record ID or unexplained additional selection was found. The exposure ledger retains all known IDs, original row indices, eligibility, stable hashes and origins. It conservatively counts selected records even if a past execution failed. Metadata-only annotation inspection does not expose question/context text.

Sixty new eligible IDs were charged durably **before** materializing their passages, for a cumulative **130/1234 (10.53%)**, safely below **617**. The paired replay adds zero new IDs. There are 142 known exposed IDs across all original categories, including the twelve excluded historical records. At least half the eligible dataset remains unseen: in fact 1104 eligible records are unseen, including all eligible records in the separate 48 protected source groups. The ledger's counters were recomputed against original metadata after execution. Record and source-group bounds are separate: spare record capacity never authorizes opening the thirty reserved or eighteen untouched groups.

New selections use seeds 20261028, 20261029 and 20261030, exact two-per-retained-refusal-category quotas, seeded matching/record choice, twenty distinct source groups per round and no record replacement across rounds or prior experiments. Source groups may recur across rounds because only the 52 already-exposed groups are allowed. No selection uses expected model success. No case is replaced after seeing an error. The initial authorized unused pool was {len(initial_pool)} records; {len(current_pool)} remain unused there after this task. Global unseen counts also include forbidden groups.

## C. Round-by-round results

{primary}

All figures use official labels unchanged and all twenty scheduled cases in each denominator. Always FULL and Always CFAF are zero-cost references: both have 50% accuracy and balanced accuracy on every balanced sample; FULL recalls are 100%/0%, CFAF recalls 0%/100%, respectively. They generate no fictional response text. Per-round summaries contain confusion matrices, unnecessary-refusal and failure-to-restrict rates, error counts and raw model declarations.

The fresh samples differ. **55% → 70% → 85% is not a causal improvement estimate**. These are adaptive development observations, not independent holdout results or significance evidence. Round 1 has four control cross-field errors; they remain ERROR rather than repaired refusals. The unchanged old implementation and every unsuccessful round prediction are retained.

{quality}

Specific reason coverage uses one frozen recognizer across all rounds, including an unsupported-premise phrase mapping defined before round 1. It is coverage across ten official CFAF cases, not conditional precision over only recognized explanations. Unknown/generic reasons are not credited as matching causes. The recognizer is an operational text criterion, not independent semantic explanation adjudication. Its limitations and low coverage remain despite richer internal causes.

## D. Identical-input paired regression

The final v02 implementation re-evaluated exactly the twenty already-exposed round-01 query/context pairs with the same official labels, settings and external primary scorer. Runtime input hashes match. This is separate from the three new samples and adds no exposure.

{paired_table}

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

All **{audit['previous_files_protected']}** previously tracked files, the original dataset and original research branch are unchanged. Input audit checked all {api['attempts']} actual payloads: only authorized perturbed text and derived neutral profiles/views/assessments reached the models; no expected labels, explanations, original answers/contexts/queries or label-bearing IDs did. Every one of the eighty case observations shares the same assessment between generators; the control never receives the gate or response contract. Three query-only calls receive only the question. No new trusted metadata association or private evidence is fabricated for this public benchmark.

Verified reference occurrences: {json.dumps(audit['verified_reference_occurrences'],sort_keys=True)}; invalid references zero. Hash/offset/reference validity is not entailment. Candidate copying is not independent grounding proof. Each source policy is checked before model use; extended profiling does not expose restricted source bodies. Mechanical checks passed, while semantic output failures remain explicitly reported.

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

Actual attempts: **{api['attempts']}/360**, all successful, zero failed attempts, zero automatic retries and zero embeddings. Counts: 80 shared main semantic analyses, 80 CFAF generations, 80 control generations and **3 additional query-only profiling calls**. Those include sixty unique new case observations plus twenty paired re-observations, not eighty new records. Main analyses are charged once per observation, not once per system.

Input tokens: **{api['input_tokens']}**. Output tokens: **{api['output_tokens']}**. Sum of measured client API latency: **{api['client_api_latency_sum_ms']/1000:.2f} seconds**. Per-kind token/latency breakdowns, including fallback cost, are in api_usage.json. Model is requested as gpt-4o-mini and returned gpt-4o-mini-2024-07-18, temperature zero, one repetition; generation max 160, main analysis max 1500, query-only fallback max 500. All attempts are journaled before HTTP, including failures had any occurred. Credentials are not printed or committed.

The 360-attempt, 50% record-exposure and source-group limits were never approached or relaxed. No request starts after minute 55. The final implementation was not re-run on unchanged new samples simply to seek better outputs. The one paired run is explicitly a changed-version comparison on fixed already-exposed data.

## I. Selected record identifiers

The following tables include every selected record using the original row index and full SHA-256 hashes. Original label-bearing IDs remain in trusted selection manifests for reproduction; they never enter model inputs. Each round also retains its selection seed, expected behavior, actual responses, correctness and source hashes. ERROR is shown where validation prevents a valid prediction. Paired inputs are identical to round 1 and are separately retained, not counted as another new sample.

'''+ '\n'.join(identifiers[4:])+f'''

## J. Recommendation and completion

The implementation is suitable for another **bounded development experiment**, with the existing governance and exposure safeguards, but is **not ready for a separately frozen independent evaluation**. Generic factual coverage and complete-request checks improved on the fixed already-exposed subset, while official ambiguity/granularity failures and poor fine-cause consistency remain. The tests support preservation of policy mechanics; they do not replace a new live InfoBank validation or independent contextual annotation.

Before independent evaluation, validate new unseen paraphrases and source groups under a separately authorized protocol, strengthen unique-reference/list/milestone coverage and distinguish answer precision from referent ambiguity. Independently review FULL grounding and disputed benchmark assumptions while preserving official primary labels. Do not open the thirty reserved or eighteen untouched groups just because record capacity remains. General internal evidence-contradiction detection remains future work.

All work is on `experiment/refusalbench-iterative-dev-v1`, parent `a6236ba0d4781b22623687387f3a99ca3ddcd0f3`. Completed measurements, failed predictions, code snapshots, tests and exposure ledger are retained. CHANGED_FILES.txt is the exact added-file inventory; checksums.sha256 covers deliverables except itself. The final local commit and inclusive end time are recorded in the external outputs completion receipt and final reply, avoiding a self-referential SHA in this committed report. No push or merge is performed.
'''
 (ROOT/'REPORT.md').write_text(report,encoding='utf-8')
 timing={'task_started_at_utc':begin,'report_prepared_at_utc':time['at_utc'],'elapsed_seconds_at_report':time['elapsed_seconds'],'hard_deadline_at_utc':limits()['hard_deadline_at_utc'],'completed_rounds':len(completed),'paired_cases':20,'final_inclusive_end_time':'See ../outputs/refusalbench_iterative_dev_v1_completion.json after commit','unfinished_live_rounds':[],'time_limit_exceeded':False}
 write_json(ROOT/'execution_timing.json',timing)
 write_json(ROOT/'experiment_manifest.json',{'status':'COMPLETED_EXPERIMENTS_REPORT_READY','parent_commit':'a6236ba0d4781b22623687387f3a99ca3ddcd0f3','branch':'experiment/refusalbench-iterative-dev-v1','rounds':[{'directory':name,'version':s['version'],'cases':20,'api_attempts':s['api_usage']['attempts']} for name,s in completed],'final_version':'v02','paired_baseline':'round_01','paired_final_directory':'paired_regression','scoring_source_sha256':sha(ROOT/'scoring.py'),'api_usage':api,'exposure':{k:ledger[k] for k in ['eligible_records','maximum_exposed_eligible_records','prior_exposed_unique_eligible_records','newly_exposed_unique_eligible_records','cumulative_exposed_eligible_records','remaining_unseen_eligible_records']},'time':timing,'preserved_previous_files':audit['previous_files_protected'],'independent_validation':False,'inferential_significance':False})
 print(json.dumps({'report_minutes':time['elapsed_seconds']/60,'remaining_minutes':time['remaining_seconds']/60,'rounds':len(completed),'api_attempts':api['attempts'],'eligible_exposure':ledger['cumulative_exposed_eligible_records'],'initial_unused_authorized':len(initial_pool),'current_unused_authorized':len(current_pool),'fallback_cost':bykind.get('query_profile')},indent=2))

if __name__=='__main__':main()
