"""Descriptive report assembly from frozen observations and explicit posthoc reviews."""
import collections,hashlib,json
from pathlib import Path
from .execute import ROOT,REPO,freeze_hashes
from .prepare_dataset import SOURCE,sha,dump
from evaluation.refusalbench_span_fix_v1.api_budget import read_jsonl,write_json

def pct(x):return f'{100*x:.1f}%' if x is not None else 'not applicable'

def main():
 f=json.loads((ROOT/'filtering_report.json').read_text());m=json.loads((ROOT/'filtered_selection_manifest.json').read_text());summary=json.loads((ROOT/'summary.json').read_text());audit=json.loads((ROOT/'validation_audit.json').read_text());usage=json.loads((ROOT/'api_usage.json').read_text());generation=json.loads((ROOT/'generation_manifest.json').read_text());records=read_jsonl(ROOT/'results.jsonl');reviews=read_jsonl(ROOT/'postrun_reviews.jsonl');cases=read_jsonl(ROOT/'selected_cases.jsonl');events=read_jsonl(ROOT/'api_events.jsonl')
 bykind={}
 for kind in ['semantic_analysis','semantic_cfaf','shared_control']:
  selected=[e for e in events if e['kind']==kind];lat=[e['latency_ms'] for e in selected]
  bykind[kind]={'calls':len(selected),'input_tokens':sum((e.get('usage') or {}).get('prompt_tokens',0) for e in selected),'output_tokens':sum((e.get('usage') or {}).get('completion_tokens',0) for e in selected),'latency_sum_ms':sum(lat),'latency_mean_ms':sum(lat)/len(lat),'latency_min_ms':min(lat),'latency_max_ms':max(lat)}
 usage.update(by_kind=bykind,worker_wall_clock_ms=generation['wall_clock_ms'],legacy_summary_latency_warning='Per-system metrics generation_latency_ms contains the shared case duration (analysis plus both generations), not marginal system generation latency. Use by_kind API timings for operational comparison.');write_json(ROOT/'api_usage.json',usage)
 primarytable='| System | N | Accuracy | Balanced accuracy | FULL recall | CFAF recall |\n|---|---:|---:|---:|---:|---:|\n'
 labels={'always_full':'Always FULL','always_cfaf':'Always CFAF','semantic_cfaf':'Semantic CFAF v2.1','shared_control':'Shared control'}
 for key in ['always_full','always_cfaf','semantic_cfaf','shared_control']:
  s=summary['systems'][key];primarytable+=f"| {labels[key]} | {s['n']} | {pct(s['accuracy'])} | {pct(s['balanced_accuracy'])} | {pct(s['full_recall'])} | {pct(s['cfaf_recall'])} |\n"
 categorytable='| Official category | Eligible globally | Selected | CFAF correct | Control correct |\n|---|---:|---:|---:|---:|\n'
 for category,count in f['eligible_counts_by_original_behavior'].items():
  a=summary['systems']['semantic_cfaf']['per_category'][category];b=summary['systems']['shared_control']['per_category'][category];categorytable+=f"| {category} | {count} | {a['n']} | {a['correct']} | {b['correct']} |\n"
 exclusions='| Rule | Excluded records |\n|---|---:|\n'+f"| A: exact whole word contradiction | {f['filter_A_excluded']} |\n| B: official contradictory behavior OR P-Contradiction | {f['filter_B_excluded']} |\n| A and B overlap | {f['A_B_overlap']} |\n| A only | {f['A_only']} |\n| B only | {f['B_only']} |\n| Union excluded | {f['total_excluded_union']} |\n| Retained | {f['eligible_records']} |\n"
 related='| Word (audit only) | All records containing word | Total occurrences | Eligible records containing word |\n|---|---:|---:|---:|\n'
 for word,counts in f['related_word_audit_only'].items():related+=f"| {word} | {counts['records']} | {counts['occurrences']} | {counts['eligible_records']} |\n"
 source='https://huggingface.co/datasets/aashiqmuhamed/RefusalBench-NQ/tree/b3684f805563e6ce465e7e9b055b840a48f519c2'
 errortable='| Case (zero-based) | Official expected | CFAF | Control | Attribution / interpretation |\n|---:|---|---|---|---|\n'
 for r,review in zip(records,reviews):
  if any(not s['correct'] for s in r['systems'].values()):
   errortable+=f"| {r['runtime_index']:02d} | {r['official_expected_behavior']} | {r['systems']['semantic_cfaf']['prediction']} ({'correct' if r['systems']['semantic_cfaf']['correct'] else 'wrong'}) | {r['systems']['shared_control']['prediction']} ({'correct' if r['systems']['shared_control']['correct'] else 'wrong'}) | {', '.join(review['error_attribution'])} |\n"
 report=f'''# RefusalBench-NQ non-contradiction development pilot

## Outcome

The unchanged latest InfoBank Semantic Integration v2.1 was evaluated on twenty newly selected official RefusalBench-NQ records, ten expected FULL and ten expected CFAF. CFAF obtained 10/20 mode decisions correct (50%); shared control 12/20 (60%). CFAF refused all twenty cases, matching the Always CFAF reference exactly. Its 100% CFAF recall therefore does not demonstrate useful discrimination. No API/schema/reference execution failure explains this result. The main transfer limitation is the bounded InfoBank query profiler, with additional evidence-sufficiency and benchmark-interpretation issues.

This is a filtered, stratified development experiment on third-party benchmark data within already exposed source-question groups. It is not performance on the complete RefusalBench-NQ benchmark, not untouched-group validation, and not proof that removing contradiction cases makes the benchmark easier or harder. No inferential significance calculation was performed.

## A. Dataset, exact filters and selection

Official source: [RefusalBench-NQ pinned revision]({source}), revision `b3684f805563e6ce465e7e9b055b840a48f519c2`, original test split of 1,600 records. The preparation used the existing official pinned cached JSONL, not a modified export, with original SHA-256 `{f['original_file_sha256']}`. The source file was read only and its SHA-256 rechecked after preparation and completion. The official source was not overwritten or deleted. Online metadata-page retrieval was unavailable; provenance relies on the previously downloaded pinned artifact and its recorded bytes, not a claimed new network download.

{exclusions}

Filter A is exactly `re.search(r"\\bcontradiction\\b", implementation_reasoning or "", re.IGNORECASE)`. No synonyms, plurals or semantic heuristics were silently added. Filter B is exactly `expected_rag_behavior == "REFUSE_CONTRADICTORY_CONTEXT"` OR `perturbation_class == "P-Contradiction"`. Thus B excludes low-intensity contradiction-class records even when the behavior label is ANSWER_CORRECTLY. The two rules overlap and must not be added as if disjoint.

{related}

There are {f['eligible_FULL']} eligible ANSWER_CORRECTLY and {f['eligible_CFAF']} eligible REFUSE records. Source-question groups before and after global filtering are both {f['source_groups_before']}. Related-word counts are annotations-only audits, not new exclusion rules. One selected false-premise explanation contains the word contradictory; this is permitted by the exact filter and involves a query premise, not a newly developed passage-contradiction detector.

{categorytable}

The intended design was feasible without relaxation. Seed 20261028 drives sorted-category/source candidates, seeded category-slot/source-group bipartite matching, within-group new-record choice and final order. All twenty selected original record IDs are new relative to 62 previously executed IDs. All twenty source_id values are distinct and belong to the union of the original ten-pilot groups and the 42 semantic-development groups (52 previously exposed groups; the later span pilot is a subset). Thirty reserved holdout groups and eighteen additional untouched groups remain excluded. There were {f['eligible_unused_development_records']} eligible unused records within that allowed development boundary. No case was selected from expected model performance or dropped after output inspection.

Global preparation parses only explicit source/id/category/reasoning annotation columns. Reserved/untouched question, context and answer text is not materialized as Python objects or emitted. Only the frozen twenty selected records are decoded in full. selected_cases.jsonl retains their unchanged official annotations; filtered_selection_manifest.json lists their exact original IDs, source groups and dataset indices. This file is trusted scoring data, never runtime input. runtime_inputs.jsonl has exactly perturbed_query and perturbed_context per row. A label-free hash authorization prevents substitution before execution.

## B. Implementation, separation and tests

The public-context adapter imports `evaluation.infobank_semantic_integration_v2.integration.run_governed` directly from parent commit `b00fb8d98c177760d8d76cbf99779a4092a1e1be`. It supplies the unchanged perturbed passage as FULL-authorized public content, with neutral local identifiers. It creates no private records, metadata, gold answers, privileged evidence roles or synthetic trusted metadata bindings. Existing query profiling and unresolved states are preserved. The eight pipeline stages, original `TopLevelModeSelectionStage`, span catalogue/resolver, strict nonempty output contract and validated candidate-copy path are unchanged. No older CFAF implementation is substituted and no classifier or contradiction improvement is made using these twenty labels.

Preparation, execution and scoring are separate processes. The worker reads authorized two-field runtime rows, not selected cases, original labels, reasoning, original queries/contexts/answers, verifier votes or label-bearing record IDs. Derived profiles, neutral spans, permitted views and model assessments are computed only from those two strings plus fixed public-context constants. Both generators receive exactly the same query, views, profile, binding statuses and semantic assessment. Only CFAF receives its response contract. The control receives no selected gate mode or fulfilment flag. All sixty transmitted payloads were audited, and all twenty generator pairs shared identical assessments. No trusted metadata binding was invented.

Before live calls, 227 functional tests passed: 33 new filtering/selection/adapter tests plus 194 earlier semantic/span/InfoBank tests. Historical CFAF regressions in a disposable exact-current-Git-blob checkout passed 77 test functions plus 13 subtests, with the previously documented `test_preheldout_attempt1_plan_artifacts_are_plan_only` failure: it expects an authorization file to be absent although that file is committed. No historical artifact was deleted to make it pass. All 584 earlier tracked files, the original annotations and wolala2026 branch are preserved. The official dataset checksum is unchanged.

Runtime/source/prompt/schema/scoring hashes, selection IDs and runtime authorization were frozen before the first live request. The worker refuses output overwrite and changed runtime files. Errors would remain ERROR in every twenty-case denominator, never be filled into a successful CFAF refusal. There were no errors requiring that path in this run.

## C. Primary results

{primarytable}

CFAF confusion matrix: gold FULL → FULL 0, CFAF 10; gold CFAF → FULL 0, CFAF 10. Unnecessary refusals 10/10 (100%); failures to restrict 0/10 (0%). Shared control: gold FULL → FULL 4, CFAF 6; gold CFAF → FULL 2, CFAF 8. Unnecessary refusals 6/10 (60%); failures to restrict 2/10 (20%). Both constant references cost zero calls and generate no fictitious response text. All official labels remain unchanged, including questioned labels.

The detailed case-by-case table, both actual responses, original behavior, correctness, explanation quality and each error discussion are in case_level_analysis.md. Original IDs and selected records are in selected_cases.jsonl and the selection manifest. The following table lists every case with an official binary error; individual causal notes in the case report distinguish the two systems.

{errortable}

## D. Why CFAF collapsed to Always CFAF

Eighteen of twenty questions receive query-profile resolution UNRESOLVED. The current conservative English grammar was built around InfoBank aggregate, metadata, record/content and action requests; common who/where/when NQ phrasings often receive no recognized requirement. The unchanged sufficiency stage consequently cannot assert complete fulfilment. Nine of the ten official FULL errors include REQUEST_SCOPE_UNRESOLVED. In cases 03 (Matthew/Luke), 08 (Paul Hogan) and 12 (Lori McKenna), it is the sole blocker despite a valid sufficient assessment and grounded candidate. These are especially clear query-profile transfer failures.

This does not explain every error alone. The cultural-centre query (07) is classified DOCUMENT_CONTENT because the lexical rule also matches state, but the context is only a multi-state membership list, not an explicit central-geography answer. Cases 06, 09, 15, 17 and 19 involve missing/partial support judgments or extra interpretation requirements as well as unresolved scope. Case 01 combines an unresolved profile with SUFFICIENT support and an UNESTABLISHED premise. The original selector applies these upstream assessments consistently; no selector defect or changed decision principle was observed.

CFAF's correct refusal for the tennis placeholder (05) is not evidence of correctly detecting missing identity: the analyzer incorrectly calls the unnamed top-seeded player a sufficient answer to who. The unresolved query profile happens to restrict it. Shared control then copies the placeholder as FULL, which is supported text but incomplete fulfilment. This illustrates why exact spans and copied candidates do not establish that the user's requested identity was supplied.

The analyzer also often describes nonfactual, ambiguous or false-premise cases as generic missing evidence. The married-bachelor query (10) is not explicitly identified as a false premise; the two-song query (14) is described as ambiguous in rationale while structured query_status remains SPECIFIED. These are semantic interpretation/representation limitations, not malformed JSON or a reason to improve generic internal-contradiction detection during this task.

## E. Refusal reasons, FULL grounding and output consistency

The frozen inherited lexical refusal-category recognizer is used unchanged for both generated systems. CFAF yields 0 recognized correct specific categories out of ten official CFAF cases. Control yields 1/10, the two-song ambiguity (14). Its conditional precision among recognized categories is 1/1, but that 100% must not be confused with 10/10 coverage or justified explanation correctness. Generic/unrecognized reasons number 10 for CFAF and 9 for control among all ten expected-CFAF cases. The inherited recognizer misses valid paraphrases such as the decade-trend gap (11) and redacted-name explanation (16); its unknown result is not proof the prose is wrong. Coarse EVIDENTIAL reason labels do not distinguish the benchmark's five requested causes.

CFAF produces no FULL responses, so its grounded-FULL answer rate is not measurable, not perfect. Shared control produces six FULL responses. In explicit post-run report-author agent review, four are judged textually supported and complete under a stated interpretation (03, 08, 12, 18), one makes an unestablished actor-to-role bridge (01), and one is supported but incomplete because it repeats an unnamed placeholder (05). Case 18 is still an official failure to restrict despite the passage explicitly attaching Joe Spano to the queried role; identity-versus-name ambiguity is discussed without rewriting its label. These judgments are unblinded and non-independent, not new human gold annotations or API-judge measurements. Original_answers are not treated as perturbed-answer gold. Independent review is required before claiming answer-support accuracy.

There are zero malformed/nonempty-answer schema failures and zero invalid span references. All requested 10 support-span, 24 source-role grounding and 9 per-requirement reference occurrences resolve mechanically to exact permitted source slices. Missing semantic support in a valid analysis is different from an invalid reference. Valid quote provenance does not prove entailment or completeness.

Three control responses (00, 14, 19) declare CFAF while setting fulfilment_status FULL. The existing schema permits that combination; the one-way validator rejects FULL with non-FULL status but does not enforce the converse. These semantic field inconsistencies are reported separately from JSON schema errors and are not repaired or used to change primary predictions. One additional control response (06) declares CFAF and then supplies the requested artist list from explicitly invoked general knowledge; this is a prose/mode disagreement and a supplied-context boundary violation. Case 07 adds a geographical claim absent from its passage. Both remain in raw outputs and the review artifact. Private-data leakage is not asserted for this public benchmark; unsupported evidence use is a separate problem.

## F. Benchmark interpretation and residual scope

Every official label is scored as given. Several passages/questions support more than one reasonable judgment: the DuckTales context omits the actor-to-role link (01); the cultural-centre list does not establish geographical centrality (07); a substitute-good definition contains no concrete example (09); the movable-type passage says nothing about a second book, and absence does not establish a false premise (13); early experimental vaccines and later availability are distinct milestones (15); container versus present geographical location changes the tablet query (17); the Joe Spano role is named despite a same-name actor in another role (18); and factory rights do not establish political control (19). These concerns do not authorize changing gold, removing cases or presenting alternative accuracy as the primary result.

The exact filters are not a semantic guarantee of contradiction-free passages. The selected married-bachelor false-premise query deliberately retains a query-level logical incompatibility because the exact-word/category filters do not exclude it. The vaccine passage's two dates concern different stages, not necessarily contradictory claims. The two songs and same-name actors describe different entities/roles rather than two incompatible facts about one object. No selected case was silently dropped on a residual-conflict judgment. No general-purpose contradiction detector was improved, and broader conflict screening remains outside this experiment.

## G. Historical descriptive comparison

| Earlier development run | Sample/treatment | CFAF accuracy | Balanced accuracy | Shared-assessment control accuracy | Material limitation |
|---|---|---:|---:|---:|---|
| First pilot | 10 cases, all ambiguous-query refusals; original UNKNOWN-role bridge | 100% | not applicable | not run | No FULL cases; no evidence of discrimination |
| 42-case semantic development | 6 FULL, 36 CFAF across seven categories; quote-based earlier analyzer | 66.7% | 45.8% | 2.4% | Five CFAF execution/validation errors; 35 shared-control errors/null outputs |
| Span-reference fix | 5 FULL, 5 CFAF, ten new records including contradiction class | 70% | 70% | 70% | Different selection and earlier semantic stages |
| Current filtered v2.1 pilot | 10 FULL, 10 CFAF, no A/B-excluded records | 50% | 50% | 60% | Bounded InfoBank profiler; eighteen unresolved questions |

These treatments differ in selection, class balance, semantic implementation and output contracts. Although all use the pinned third-party dataset, source groups were already development-exposed and selected record IDs differ. No causal effect of filtering or claim of easier/harder/full-benchmark representativeness follows. The InfoBank v2 experiment's 40/40 known-fixture mode score did not establish general-question transfer; this run exposes that gap.

## H. Actual usage and reproducibility

Actual requests: {usage['actual_attempts']} of a hard cap 75; {usage['successes']} successful, {usage['errors']} errors. Twenty analyses are shared once between twenty CFAF and twenty control generations. No retries, embeddings or extra model judges. Model returned `gpt-4o-mini-2024-07-18`, requested gpt-4o-mini, temperature zero, one repetition, analysis limit 1500, generation limit 160. Input tokens {usage['input_tokens']}; output tokens {usage['output_tokens']}. Summed client API latency {usage['summed_call_latency_ms']/1000:.2f} seconds; worker wall time {generation['wall_clock_ms']/1000:.2f} seconds. Per-kind actual token/latency counts are in api_usage.json. Legacy per-system summary generation_latency_ms uses the shared case duration including analysis and both generators, so it is not isolated per-system generation latency; use the explicitly grouped API timings instead.

Payloads are journaled before HTTP, outcomes and raw text after response, with response IDs, models, usage and latency. Credentials are not printed or committed. Filtering/sampling, runtime authorization, preparation hashes, source/prompt/schema/scoring freeze, raw worker outputs, trusted scored outputs and posthoc reviews are separate artifacts. The source dataset and all 584 earlier tracked files are unchanged. Current code/prompts and all primary scoring logic stayed frozen throughout the live run. Supplemental contextual judgments are explicitly posthoc and do not rewrite primary scores. CHANGED_FILES.txt is the exact commit file list; checksums.sha256 covers deliverables excluding itself. Final commit identification is supplied after committing this report to avoid a self-referential commit hash inside the committed file.

## I. Next recommendation

The current implementation is not ready for a larger non-contradiction-focused RefusalBench evaluation as a broadly usable question-answering system. Its CFAF behavior is indistinguishable from Always CFAF in this sample. Before another frozen run, develop and test general factual who/where/when and compositional request interpretation on separate authorized development examples, with explicit distinctions between parser uncertainty and actual evidence insufficiency. Do not patch these twenty expected labels, silently restore an older architecture or open reserved holdout groups.

Next priorities relevant to InfoBank are request coverage, requested identity versus placeholder descriptions, per-requirement completeness, coarse-versus-specific refusal reasons, context-bound generation and cross-field contract consistency. Independent contextual annotation is needed for questionable benchmark labels and FULL fulfilment while preserving official primary scoring. Keep policy projection, unchanged selector, span provenance and label-blind control separation. Freeze any revised implementation before larger development evaluation; untouched groups and the thirty reserved groups remain protected until separately authorized. General internal evidence-contradiction detection remains future work.
'''
 (ROOT/'REPORT.md').write_text(report,encoding='utf-8')
 manifest=json.loads((ROOT/'experiment_manifest.json').read_text());manifest.update(status='COMPLETED',generation_status=generation['status'],actual_api_usage=usage,official_source_unchanged=sha(SOURCE)==f['original_file_sha256'],frozen_code_unchanged=freeze_hashes()==manifest['code_sha256'],posthoc_review_scope='Unblinded non-independent report-author agent review, separate from frozen primary scoring; no labels or predictions edited',posthoc_review_sha256=sha(ROOT/'postrun_review.py'),report_code_sha256=sha(ROOT/'make_report.py'),results_sha256=sha(ROOT/'results.jsonl'),previous_files_preserved=584);write_json(ROOT/'experiment_manifest.json',manifest)
 assert manifest['official_source_unchanged'] and manifest['frozen_code_unchanged']
 print('Detailed report and per-case analysis complete; original annotations and frozen primary scores preserved.')

if __name__=='__main__':main()
