"""Write the safe research report and ignored detailed ten-case review."""
import json,csv,collections,datetime
from .artifacts import *
from .deadline import elapsed

def mdtable(headers,rows):
 def cell(v):return str(v).replace('|','/').replace('\n',' ')
 return '| '+' | '.join(headers)+' |\n| '+' | '.join('---' for h in headers)+' |\n'+'\n'.join('| '+' | '.join(cell(v) for v in r)+' |' for r in rows)+'\n'
def pct(x):return 'undefined' if x is None else f'{100*x:.2f}%'
def dump(x):return json.dumps(x,ensure_ascii=False,indent=2)
def save(name,text):(ROOT/name).write_text(text.strip()+'\n',encoding='utf-8')

REVIEWS=read(ROOT/'local/agent_review.json')['cases']

def build():
 selected=rows(ROOT/'selected_records.jsonl');selection=read(ROOT/'dataset3_selection_manifest.json');ds=rows(ROOT/'per_case_diagnostics.jsonl');results=rows(ROOT/'results.jsonl');modes=read(ROOT/'mode_comparison.json');metrics=read(ROOT/'grounding_metrics.json');usage=read(ROOT/'api_usage.json');source=read(ROOT/'source_audit.json');security=read(ROOT/'security_audit.json');reg=read(ROOT/'regression_audit.json')
 write(ROOT/'local/agent_review.json',{'review_type':'Non-independent agent qualitative review after outputs; not human gold or a verifier API','cases':[{'sample_id':r['sample_id'],**v} for r,v in zip(selected,REVIEWS)]})
 write(ROOT/'qualitative_review_summary.json',{'status':'NON_INDEPENDENT_AGENT_REVIEW','human_review':'PENDING','T3_overrefusal_candidates':8,'T3_unsupported_FULL_count':0,'T3_FULL_denominator':0,'control_FULL_cases_with_flagged_unsupported_relations':3,'control_flagged_relations':4,'disputed_control_absence_assertion_cases':1,'no_binary_accuracy_computed':True,'cases':[{'sample_id':r['sample_id'],'flag':v['flag'],'T3_overrefusal_candidate':v['T3_overrefusal_candidate'],'control_flagged_unsupported_relation_count':v['control_unsupported_claims_flagged'],'control_scope_incomplete':v['control_scope_incomplete']} for r,v in zip(selected,REVIEWS)]})
 with (ROOT/'HUMAN_REVIEW_TEMPLATE.csv').open('w',newline='',encoding='utf-8') as f:
  fields=['sample_id','runtime_index','reviewer','reviewed_utc','requirements','complete_supported_answer_possible','T3_appropriate','control_appropriate','T3_unsupported_claims','control_unsupported_claims','citation_entailment','temporal_scope','missing_requirements','reason','adjudication_status'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for i,r in enumerate(selected):w.writerow({'sample_id':r['sample_id'],'runtime_index':i,'adjudication_status':'PENDING'})
 safe_cases=[];full_cases=[]
 for i,(r,entry,d,result,review) in enumerate(zip(selected,selection['records'],ds,results,REVIEWS)):
  out=result['outcome'];systems=d['systems'];support=d['metrics']['analyzer_global_support'];role=d['metrics']['analyzer_primary_supports_roles'];reference_errors=out['reference_audit'].get('errors',[])
  safe_cases.append(f"### Case {i+1}: `{r['sample_id']}`\n\n{review['topic']}. Original row {entry['index_zero_based']} (zero-based), {entry['index_zero_based']+1} (one-based); {r['question_complexity']}; category `{r['question_category']}`; original as-of date {r['question_date']}. All 15 passages retained. T3 {systems['semantic_cfaf']['mode']}, control {systems['shared_control']['mode']}, A0 {d['A0_gate']}. Semantic validity: {d['semantic_valid']}; validation issues: `{reference_errors}`.\n\n{review['judgement']}\n\nRaw proposed global source selection P/R/F1: {pct(support['precision'])}/{pct(support['recall'])}/{pct(support['f1'])}; original correctness distribution {support['correctness_distribution']}. Neither public answer contains a recognized citation. Qualitative flag: `{review['flag']}`; human review pending.")
  item=[f"### Case {i+1}: {r['sample_id']}",f"1. **Identity and row.** `sample_id={r['sample_id']}`; zero-based row {entry['index_zero_based']}; one-based row {entry['index_zero_based']+1}; raw-line SHA-256 `{entry['record_sha256']}`.",f"2. **Original question (verbatim).** {r['question']}",f"3. **Original metadata.** Question date {r['question_date']}; category `{r['question_category']}`; complexity `{r['question_complexity']}`; popularity `{r['question_popularity']}`; sensitivity `{r['question_sensitive']}`; type `{r['question_type']}`. These classification labels were scorer-only.",f"4. **Grounding scope.** 15 original passages; 15 retained; zero omitted; original order. No external retrieval or invented permission distinction.",f"5. **Original relevance/correctness.** Relevance {d['gold_relevance_counts']}; correctness {d['gold_correctness_counts']}. Blank is an original value, not relabelled UNKNOWN.",f"6. **Original human-answer summary.** {review['reference_summary']} Original `answer_validate={r['answer_validate']}`. This annotation validates the dataset reference, not either generated answer.",f"7. **T3 gate and public response.** Gate {out['selected_mode']}; output:\n\n```json\n{dump(systems['semantic_cfaf']['response'])}\n```",f"8. **T3 immediate reason and validity.** Internal reason {out['internal_reason']}; semantic valid={out['semantic_valid']}; reference/schema audit errors {reference_errors}; fulfilment issues {out['fulfilment_issues']}. This reason must not be conflated with the post-run qualitative diagnosis.",f"9. **Shared control public response.**\n\n```json\n{dump(systems['shared_control']['response'])}\n```\n\nGenerator validation errors: {systems['shared_control']['validation_errors']}. Same passages, date, profile and raw semantic assessment; no T3 contract provided.",f"10. **A0 reference.** Gate-only {d['A0_gate']} from the same frozen upstream assessment. No A0 generation or extra model calls; no inference that its ungenerated response would match T3 text.",f"11. **Evidence/citation layers.** Raw global support markers {support['selected_markers']}; PRIMARY/SUPPORTS markers {role['selected_markers']}. Actual public inline citations: T3 {systems['semantic_cfaf']['citation_metric']['selected_markers']}, control {systems['shared_control']['citation_metric']['selected_markers']}; invalid inline citations T3 {systems['semantic_cfaf']['citation_metric']['invalid_citation_count']}, control {systems['shared_control']['citation_metric']['invalid_citation_count']}. Global raw-reference errors {d['invalid_global_span_ids']}. Source labels for proposals:\n\n"+mdtable(['Original marker','Internal view','evidence_relevant','evidence_correct'],[[m['original_marker'],m['source_id'],r['evidence_relevant'][m['original_index_zero_based']],r['evidence_correct'][m['original_index_zero_based']]] for m in rows(ROOT/'runtime_inputs.jsonl')[i]['mapping'] if m['original_marker'] in set(support['selected_markers'])|set(role['selected_markers'])]),f"12. **Requirement support reported by analyzer.**\n\n```json\n{dump(d['requirement_support'])}\n```\n\nOne legacy request item does not prove that this broad or multipart question was completely decomposed. Missing requirements in review: {review['missing']}",f"13. **Unsupported claims and missing relations.** {review['unsupported']} Non-independent flagged control relation count: {review['control_unsupported_claims_flagged']}; T3 generated no requested factual answer and no FULL response.",f"14. **Grounded-answer judgement.** {review['judgement']} T3 over-refusal candidate: {review['T3_overrefusal_candidate']}. This is an agent review, not an original binary label or an independent audit.",f"15. **Original source-label metrics.** Raw global proposals P={pct(support['precision'])}, R={pct(support['recall'])}, F1={pct(support['f1'])}; missing relevant markers {support['missing_relevant_markers']}; selected irrelevant markers {support['irrelevant_selected_markers']}; correctness distribution {support['correctness_distribution']}. These metrics do not establish passage-to-claim entailment. Actual public-citation recall/F1=0; precision undefined because neither answer cites a source.",f"16. **Actual API costs.** Calls {d['api_usage']['calls']}; input tokens {d['api_usage']['input_tokens']}; output tokens {d['api_usage']['output_tokens']}; case elapsed {d['latency_ms']:.1f} ms. All calls stopped normally; no retry, repair or second verifier.",f"17. **Limits and human review.** This exposed pilot case is unsuitable for a later untouched test. Independent completeness, relation/entailment and temporal-scope adjudication remains PENDING. The frozen implementation and original gold were not changed after observing it."]
  if review['quote']:item.append(f"Short original excerpt, `{review['quote']['marker']}`: > {review['quote']['excerpt']}\n\nAttribution: original AmazonScience GaRAGe record `{r['sample_id']}`, pinned commit `{source['commit']}`; CC-BY-NC-4.0. Used only to explain the relation error.")
  full_cases.append('\n\n'.join(item))
 table1=mdtable(['Order','Row 0/1','sample_id','Category','Complexity','Passages','T3','Control','A0'],[[i+1,f"{e['index_zero_based']}/{e['index_zero_based']+1}",r['sample_id'],r['question_category'],r['question_complexity'],15,d['systems']['semantic_cfaf']['mode'],d['systems']['shared_control']['mode'],d['A0_gate']] for i,(r,e,d) in enumerate(zip(selected,selection['records'],ds))])
 table2=mdtable(['Case','YES / NO','ANSWER / RELATED / UNKNOWN / OUTDATED / blank','Global raw sources','PRIMARY SUPPORTS sources','T3 citations','Control citations'],[[i+1,f"{r['evidence_relevant'].count('YES')} / {r['evidence_relevant'].count('NO')}",' / '.join(str(r['evidence_correct'].count(k)) for k in ['ANSWER-THE-QUESTION','RELATED-INFORMATION','UNKNOWN','OUTDATED','']),d['metrics']['analyzer_global_support']['selected_count'],d['metrics']['analyzer_primary_supports_roles']['selected_count'],0,0] for i,(r,d) in enumerate(zip(selected,ds))])
 table3=mdtable(['Layer / system','Precision','Recall','F1','Invalid public citations','Unsupported FULL','Unnecessary deflection'],[[name,pct(m['micro_precision']),pct(m['micro_recall']),pct(m['micro_f1']),'not public citations','not measured','not measured'] for name,m in metrics['layers'].items() if name.startswith('analyzer')]+[['T3 actual public citations','undefined','0.00%','0.00%',0,'0 observed / 0 FULL; rate undefined','8 agent-review candidates; no independent label'],['Control actual public citations','undefined','0.00%','0.00%',0,'3 FULL cases with 4 agent-flagged relation claims','1 agent-review candidate; no independent label']])
 table4=mdtable(['Call kind','Calls','Input tokens','Output tokens','Mean ms','Max ms','API errors'],[[k,v['attempts'],v['input_tokens'],v['output_tokens'],f"{v['mean_latency_ms']:.1f}",f"{v['max_latency_ms']:.1f}",v['errors']] for k,v in usage['by_kind'].items()]+[['TOTAL',usage['attempts'],usage['input_tokens'],usage['output_tokens'],f"{usage['mean_latency_ms']:.1f}",f"{usage['max_latency_ms']:.1f}",usage['errors']]])
 overview=f'''# Dataset3: original GaRAGe ten-case CFAF pilot

## A. Executive summary

All **10 selected cases completed** with 30 successful `gpt-4o-mini` calls, zero API errors and zero retries. T3 generated **0 FULL / 10 CFAF**; the shared control generated **9 FULL / 1 CFAF**. A0 gate-only returned 10 CFAF. These counts are observed modes, **not binary accuracy**.

The central result is an integration limitation: eight semantic assessments omitted roles for some supplied passages, one used an invalid span identifier, and only one assessment passed the existing semantic contract. All 30 provider responses ended with `finish_reason=stop`; none was truncated. The existing T3 gate rejected invalid assessments as designed. Its refusal text often hides that structural failure behind a generic evidence-missing reason. The sole valid assessment missed available candidate support and produced an inappropriate clarification candidate.

Dataset1 tests governed InfoBank fulfilment; Dataset2 tests selective refusal; Dataset3 adds source-labelled, multi-passage evidence-grounded answering, temporal metadata and longer reference answers. Original GaRAGe is usable as Dataset3, but this run does **not** establish that T3 successfully answers its questions. No tested source, prompt, original label or selected case was changed after observing outputs. No second pilot was run.

This committed report contains safe summaries. The ignored local companion `local/REPORT_FULL.md` contains the exact ten questions, both public responses, original-answer summaries, span mappings, requirement diagnostics and 17 review items per case. Original full passages, reference answers, raw traces and unredacted gold remain ignored.

## B. Dataset verification

Official source: [AmazonScience GaRAGe](https://github.com/amazon-science/GaRAGe), commit `{source['commit']}`. Download: [immutable JSONL]({source['download_url']}). Download UTC: {source['downloaded_utc']}. File: `{source['file']}`; **{source['bytes']:,} bytes**; SHA-256 **`{source['sha256']}`**. Parsed 2366 rows, 2366 unique nonmissing IDs, zero duplicates, no dropped records, 35,351 grounding passages. Passage count range {source['grounding_min']}–{source['grounding_max']}, mean {source['grounding_mean']:.3f}; 2329 records have 15 passages. All three evidence-annotation lists align with their grounding lists.

The [ACL Findings 2025 publication](https://aclanthology.org/2025.findings-acl.875/) describes the same 2366-question benchmark with over 35K grounding passages. The pinned repository licence is **CC-BY-NC-4.0**; its bytes are hashed in `source_audit.json`. The full original data was downloaded locally and is excluded from Git.

Observed relevance vocabulary: `{source['annotation_values']['evidence_relevant']}`. Observed correctness vocabulary: `{source['annotation_values']['evidence_correct']}`. In particular, **OUTDATED and the empty string are original values**. Neither is collapsed into UNKNOWN. The exact original fields use `question_false_premise`, `question_seeking`, `question_sensitive`, `question_type`, `question_complexity`, `question_category` and `answer_related_info`. The actual grounding is a list of objects with `cite_N`, `age`, `date`, `provider`. All field names, types, label counts and passage-count distribution are in `source_audit.json` and `GARAGE_SOURCE_AUDIT.md`. Free-text comments and tags remain original; they are not invented categorical labels.

## C. Random selection

Population: all ordered 2366 valid JSONL rows. Python: `{selection['python']}`. Algorithm: `random.Random(20261028).sample(range(2366), 10)`. Zero-based indices: `{selection['indices_zero_based']}`. One-based indices: `{selection['indices_one_based']}`. The selection was persisted at {selection['selected_at_utc']}, before any model outputs or qualitative review. No stratification, balancing, resampling, substitutions or sorting by label occurred. Raw-record hashes use exact original line bytes excluding line terminators.

`dataset3_selection_manifest.json`, its metadata supplement and `dataset3_exposure_ledger.json` record the ten IDs and their provenance. Only these ten records were qualitatively inspected. Structural parsing and metadata-only aggregate statistics were performed on the complete file. The other **2356 records were not used for development diagnosis** and should remain reserved. Dataset1 and Dataset2 ledgers are unchanged.

## D. CFAF integration

Baseline HEAD: `{read(ROOT/'task_state.json')['baseline_commit']}` on `experiment/cfaf-target-claim-alignment-v1`; this work is on `experiment/cfaf-garage-pilot-v1`. The existing T3 integration, RDA/RECV, target and claim diagnostics, all eight named stages and original `TopLevelModeSelectionStage` remain byte-identical. T3 target/claim additions remain shadow diagnostics; this experiment gives them no new gate authority.

The adapter accepts exactly `question`, `question_date`, `grounding`. It preserves the question verbatim and every original passage body, original citation marker and original date/provider/age metadata. Each passage receives a neutral `view-NNNN` ID and an original-marker mapping. The existing deterministic catalogue supplies 430-character windows with 70-character overlap; exact offsets/hashes validate references. Public source metadata is inserted as a short header, with its length recorded so the unchanged passage body can be independently verified. Original as-of date is sent equally to analysis and both generators; the query-only fallback remains query-only and was not needed.

All supplied passages have task-authorized FULL access. `web` and `ent` remain provider metadata; neither creates a denial, ownership claim, authority claim or trusted InfoBank ingestion provenance. No live grounding retrieval or external case-fact search occurred.

Before execution, the adapter declared an input budget of 60,000 tokens using a conservative serialized ASCII-JSON UTF-8 byte-count bound plus 128. Its gold-blind overflow policy is a maximal whole-passage prefix in original order. Every selected case retained all 15 passages, so no altered-context subgroup was needed. Actual provider input token usage was below every recorded bound.

The existing prompts/schema were unchanged. Both generated systems use the newly authorized 512-token generation ceiling; analysis remains 1500, query profiling 500, temperature 0, repetitions 1. The legacy short-answer instruction and T3 verbatim-candidate copying remain in effect and limit long-form completeness. T3 and control share one semantic assessment per case. Control receives no T3 contract. A0 reuses that assessment for a gate decision and has no redundant generation. There were no embeddings, judges, semantic repair calls or second verifiers.

## E. Overall pilot results

Table 1: exact sample order, original indices and observed modes.

{table1}

Table 2: original annotation counts and the three distinct source-selection notions. ANSWER means the exact original `ANSWER-THE-QUESTION` label; RELATED means `RELATED-INFORMATION`. Public citation counts do not include analyzer support spans.

{table2}

Nine generated mode disagreements occurred between T3 and control; T3 and A0 agreed in all ten gate decisions. Nine of ten semantic assessments were invalid. Eight fail `SOURCE_ROLE_COVERAGE_INVALID`; the last fails `UNKNOWN_SPAN_ID:view-0001:span-0004`. The one valid assessment has no supporting candidate. All generated public response objects passed the existing generator validator. The control in case 8 used the noncanonical public reason string MISSING_EVIDENCE; the permissive string schema accepted it. This does not establish that their content, completeness or reason class is correct.

## F. Detailed case-by-case review

These are **non-independent agent observations**, with all human review fields pending. Safe summaries follow; exact questions, both complete outputs and all 17 requested review items are in the ignored local companion.

{{CASE_REVIEWS}}

## G. Evidence-grounding analysis

Table 3: source-level metrics and qualitative limits. The first three layers are **raw analyzer proposals**, including proposals from invalid assessments; they are shared by both systems. They must not be reported as accepted T3 evidence selections. Only one assessment was valid, and it selected no supporting evidence. Metric precision/recall/F1 use the original YES/NO relevance labels; unknown relevance is excluded from TP/FP. A missing selection gives undefined precision, zero recall and zero F1 when relevant sources exist. Recall against every relevant passage is not a demand that an answer cite all passages.

{table3}

Global raw-support micro counts are TP=24, FP=3, FN=95. PRIMARY/SUPPORTS-role and requirement-support proposals give TP=24, FP=4, FN=95. The extra role-layer false positive is an originally irrelevant passage in the final causal question. Invalid-reference diagnostics remain distinct from irrelevant-source selection. The first software-update case uses three originally NO passages for generic workflow benefits; it misses the update-scoped passages. The accounting case has perfect relevance precision for its sole proposed source even though that source is only RELATED-INFORMATION. The final causal case has perfect raw source relevance precision/recall while its sole globally selected source is UNKNOWN. These are direct demonstrations that relevance is not complete-answer sufficiency.

Both public-answer citation layers contain **zero citations**, hence precision is undefined and recall/F1 are 0. Zero invalid inline citations is therefore a vacuous result. Neither system can be said to have selected better public-cited sources; their raw upstream proposals are identical. The unchanged schema has no citation field and the realization prompts do not enforce citation retention. This run is not a reproduction of the paper's RAF or official evaluation pipeline; no such score is claimed.

Qualitative review flags four unsupported relation assertions across three control FULL answers: accounting treatment promoted to risk strategy, a cultural-exchange association transferred across subjects, and two causal/support associations in operator selection. This count is agent judgement, **not** an independent entailment score. The stock-recovery control also makes a disputed absence assertion. T3 generated no FULL answers, so observed unsupported FULL count is 0 over a denominator of 0 and its rate is undefined. Eight T3 refusals are candidates for unnecessary refusal after reviewing supplied evidence/reference summaries; they are not eight independently labelled false refusals.

The failures arise at different layers: available retrieval evidence is often adequate, structural source coverage rejects otherwise promising analyses, one reference is fabricated, shared analysis sometimes misses support or transfers a relation, and public answer generation loses attribution and scope. A valid reference ID only identifies text; it does not prove the claim follows from that text.

## H. FULL/CFAF interpretation

Original `evidence_relevant` supports source-selection scoring. Original `evidence_correct` distinguishes answering, related, unknown, outdated and blank source labels. `evidence_cited` describes the human reference's citations. `answer_validate` refers to the human reference, not generated responses. These labels can support grounding diagnosis and careful qualitative comparison.

They do **not** independently establish complete fulfilment of every part of a broad, comparative, temporal or causal request. No official FULL/CFAF mapping, binary accuracy, false-refusal rate or refusal benchmark score is computed. The two original deflective answers are useful qualitative cases, but were not turned into labels for the other eight. Exact string match was not used as a substitute for grounded-answer review. Use a separate independently adjudicated requirement/completeness rubric before reporting binary accuracy.

## I. Costs and efficiency

Table 4: actual provider usage. Shared upstream analysis is counted once.

{table4}

Total **176,503 input tokens + 7,273 output tokens**; 30/60 allowed attempts; 30 successes; zero API errors; zero unsettled attempts; zero retries. All 30 finish reasons are `stop`. No query-profile fallback, embedding, verifier or judge call occurred. No dollar estimate is provided because current pricing was not verified. Differences from prior experiments' call totals are not claimed as algorithmic savings. Per-case end-to-end latency is in the ignored diagnostics and detailed companion.

Task start UTC: `{read(ROOT/'task_state.json')['start_utc']}`. Monotonic and wall-clock anchors are persisted in `task_state.json`; elapsed at report generation: {elapsed():.1f} seconds. No deadline was reset. The local completion receipt records final elapsed time and commit.

## J. Limitations and verification

This is a ten-case exposed development pilot with random category/complexity and class imbalance, not an independent final test. Public benchmark familiarity is possible. Source-level annotations do not certify complete answers; provider metadata does not reproduce InfoBank governance; no independent human answer, temporal or entailment audit has been done. Inline citations can be absent or non-entailing, while valid span IDs can still be attached to the wrong claim. All evidence remained available, but schema-contract validity failed in nine cases. The short-answer legacy setup is a poor fit for long reference answers. Agent interpretations and proposed failure counts require independent adjudication.

Adapter preflight: 30 tests passed. Scoring: 6 tests passed. Isolated exact-Git-blob regression: **614 passed, 3 hash-only tests deselected**; those hash tests ran on the original working files and **3 passed**. The adapter 30 are included in 614 and are not an additional unique-test count. Original CFAF suite: **77 passed, 13 subtests passed, one known pre-existing failure** in `test_preheldout_attempt1_plan_artifacts_are_plan_only`, which expects a previously committed authorization metadata file to be absent. It was not changed or hidden. Logs/XML and `regression_audit.json` preserve the result.

Security audit: all **985 pre-existing tracked files** match their starting hashes; frozen runtime/source/selection hashes match; all 150 selected passage bodies match the original text; all 30 serialized API payloads passed gold-field and identifier checks; shared passages, dates and semantic inputs match; model/temperature/limits/cap match. Dataset1/Dataset2 ledgers and original branches remain unchanged. A future defense improvement is to explicitly add `sample_id` to the provider key denylist: this run's exact adapter whitelist excluded it and actual payload scans confirm no leak, but the frozen provider was not patched after results. Human review remains PENDING.

## K. Recommendation

1. **Usable as Dataset3:** yes, for source-grounded answering with original passage-level labels and as-of metadata.
2. **Original labels sufficient for grounding:** sufficient for source-label selection metrics and diagnosis; insufficient alone for claim entailment and full-request completion.
3. **Reliable FULL/CFAF mapping without new judgement:** no. Preserve originals and add a separate independently adjudicated completeness layer when authorized.
4. **Observed T3 modes:** 0 FULL, 10 CFAF. A0 gate is also 0/10.
5. **Control difference:** 9 FULL, 1 CFAF; nine generated disagreements. Structural assessment vetoes dominate T3's refusals.
6. **Better-grounded sources:** neither is better by public citations, which are absent; raw analyzer source proposals are shared. High raw relevance precision is not answer adequacy.
7. **Unsupported T3 FULL:** none observed because there were no FULL outputs; this is no positive evidence of grounded answering ability.
8. **Unnecessary refusal:** eight candidates in agent review; no independent false-refusal count is available. The only structurally valid case also appears to miss candidate support.
9. **Before larger evaluation:** in a separately authorized development task, make all-source role coverage explicit and test it on synthetic multi-source fixtures; prevent invalid span IDs; require retained public citations; distinguish source relevance from answering/temporal/relational support; preserve query-scope coverage and conditional forecasts; correct ambiguity reasoning; design independent completeness/entailment adjudication. Keep the current results frozen. Any rerun of these ten would be exposed development evidence, never a new independent result.
10. **Reserve remaining records:** yes. Keep the other 2356 uninspected for later independently planned sampling/testing. Do not consume them to tune fixes discovered here.
'''
 save('REPORT.md',overview.replace('{CASE_REVIEWS}','\n\n'.join(safe_cases)))
 save('local/REPORT_FULL.md',overview.replace('{CASE_REVIEWS}','\n\n'.join(full_cases)).replace('# Dataset3: original GaRAGe ten-case CFAF pilot','# Dataset3: original GaRAGe ten-case CFAF pilot — detailed local companion',1))
 save('README.md','''# Original GaRAGe pilot

Start with REPORT.md for safe findings and local/REPORT_FULL.md for all ten exact questions, complete generated outputs and the 17-item review per case. The local companion is intentionally ignored.

The committed files contain adapter/provider/runner code, tests, hashes, aggregate metrics, exact selected IDs, safe metadata and a pending human-review template. Original data, full passages, reference answers, runtime inputs, unredacted gold, raw outputs and potentially sensitive traces are excluded by this directory's .gitignore. They remain available locally in datasets/, local/ and the explicitly ignored JSONL files.

The ten-case sample and tested implementation are frozen. Do not rerun download_source.py or adapter.py in this completed directory: download preparation is intended only for a fresh task, and the existing selection/results must remain immutable. runner.py refuses repeated freeze/pilot execution. A later authorized reproduction needs its own directory, persistent deadline and explicit call budget; never reset this task's clock or call ledger.

Offline verification from the repository uses the workspace venv Python:

```powershell
python -m pytest evaluation/cfaf_dataset3_garage_pilot_v1/test_adapter.py evaluation/cfaf_dataset3_garage_pilot_v1/test_scoring.py -q
```

The adapter tests require the ignored local runtime and gold files. Source-selection scorer unit tests use synthetic text. Historical regression ran in an exact-Git-blob scratch checkout with API credentials removed. The one known original-suite failure is documented, not repaired in this task.

Artifact map: source_audit.json / GARAGE_SOURCE_AUDIT.md (provenance and vocabulary); dataset3_selection_manifest.json plus selection_annotation_supplement.json (sample and metadata); experiment_manifest.json (pre-run freeze); grounding_metrics.json / mode_comparison.json / api_usage.json (safe results); security_audit.json / regression_audit.json (checks); HUMAN_REVIEW_TEMPLATE.csv (no fabricated human judgements); CHANGED_FILES.txt / checksums.sha256 (safe commit inventory).

Ignored root files runtime_inputs.jsonl, gold_annotations.jsonl, selected_records.jsonl, results.jsonl, per_case_diagnostics.jsonl, api_requests.jsonl and api_events.jsonl retain the original data boundary. Do not git add -f them. No push or merge was performed.
''')
 save('DATASET_REGISTRY.md','''# Canonical dataset registry

| Name | Scientific role | Scope and present status | Restrictions in this task |
| --- | --- | --- | --- |
| Dataset1 — InfoBank | Governed fulfilment across P1–P5 | Original 40 synthetic development cases. Planned independent 60 authored cases (20 development, 40 final) are a separate corpus and were not established/used here. | Do not access independent student-authored reserved cases. Historical compatibility tests use existing fixtures. |
| Dataset2 — RefusalBench-NQ | Selective refusal under perturbed requests/context | Original 1600, filtered 1234; prior eligible exposed 130; reserved 30 source groups plus untouched 18 as recorded in prior ledgers. This is RefusalBench-NQ, not RefusalBench-GaRAGe. | No new sampling, qualitative inspection, model execution or exposure-ledger change. |
| Dataset3 — original AmazonScience GaRAGe | Evidence-grounded answering and source attribution | Official original 2366 records and 35,351 passages. Ten uniformly random records exposed in this pilot; 2356 not used for qualitative development. | Preserve original gold. Reserve remaining records. This ten-case development run is not final independent validation. |

Dataset numbering is stable. Dataset3 is not a RefusalBench adaptation. Dataset1 governance labels, Dataset2 selective-refusal gold and Dataset3 passage annotations are different scientific concepts and are not interchangeable binary labels.
''')
 save('GARAGE_SOURCE_AUDIT.md',f'''# Original GaRAGe source audit

Repository: https://github.com/amazon-science/GaRAGe

Resolved source commit **before** download: `{source['commit']}` (git ls-remote refs/heads/main). The official GitHub commit API independently returned the same SHA. Immutable data URL: {source['download_url']}

Downloaded UTC {source['downloaded_utc']}; `{source['file']}`, {source['bytes']:,} bytes; SHA-256 `{source['sha256']}`. 2366 JSONL rows, 2366 unique IDs, no missing/duplicate IDs, no invalid row silently dropped. Total grounding passages 35,351; min {source['grounding_min']}, max {source['grounding_max']}, mean {source['grounding_mean']:.3f}. Count distribution: `{source['grounding_count_distribution']}`. No evidence-array length mismatches.

Licence: CC-BY-NC-4.0, verified from the same pinned commit; local licence SHA-256 `{source['license_sha256']}`. Publication: [Findings of ACL 2025, pages 17030–17049](https://aclanthology.org/2025.findings-acl.875/), DOI 10.18653/v1/2025.findings-acl.875. This is the original dataset, not RefusalBench-GaRAGe.

Original ordered fields: `{source['original_field_order']}`. All rows have these 21 fields. Actual `grounding` is a list; each selected passage has `cite_N` text and original age/date/provider metadata. Evidence relevance/correctness/citation fields are parallel ordered string lists. Original human answers, comments and tags remain locally intact. Names use the actual `question_` prefixes and `answer_related_info`.

Observed evidence relevance: `{source['annotation_values']['evidence_relevant']}`.

Observed evidence correctness: `{source['annotation_values']['evidence_correct']}`. OUTDATED and blank extend the simplified three-category expectation. Blank is not relabelled UNKNOWN. Original source labels and category spelling/whitespace were preserved.

Observed reference citation labels: `{source['annotation_values']['evidence_cited']}`. Reference validation: `{source['annotation_values']['answer_validate']}`. Question-valid/false-premise/seeking: `{source['annotation_values']['question_valid']}` / `{source['annotation_values']['question_false_premise']}` / `{source['annotation_values']['question_seeking']}`. Sensitivity: `{source['annotation_values']['question_sensitive']}`; dynamism: `{source['annotation_values']['question_type']}`; complexity: `{source['annotation_values']['question_complexity']}`; popularity: `{source['annotation_values']['question_popularity']}`. Full category value counts and types are in source_audit.json. Free-text fields are preserved and are not converted into new class vocabularies.

Only metadata and structure were aggregated over unselected records. No unselected question, passage, reference answer or comment was qualitatively inspected. Original full JSONL, pinned README and licence files are ignored local artifacts.
''')
 save('GARAGE_ADAPTER_SPEC.md','''# Minimal Dataset3 adapter specification

Runtime input accepts exactly question, question_date and grounding. Annotation extraction writes a separate ignored gold file. Sample IDs and category/complexity/gold are never attached to model payloads. The execution runner loads runtime only, not original records or gold. Gold-aware scoring/reporting occurs after the frozen run.

Each original cite_N passage stays in original order. A JSON metadata header contains citation_marker, age, date and provider, followed by newline and the exact unmodified original body. Private mapping records original index/marker, neutral public view-NNNN, raw-body SHA-256, adapted-context SHA-256 and header length. The unchanged catalogue maps neutral views to deterministic span IDs, exact offsets and text hashes. The ignored original/runtime artifacts allow complete reverse mapping. No ranked passage selection or evidence pruning occurs.

FULL authorization follows the user's task permission for all supplied grounding. Provider web/ent is not an access rule, ownership attestation or authority signal. No InfoBank restrictions are fabricated. Original question_date is supplied equally to analysis and both generators as query_context. Original source age/date values are not reinterpreted or repaired. Query-only fallback contains only query and was not invoked.

Predeclared bound: serialized ASCII-JSON UTF-8 bytes +128 <=60000, conservatively bounding input tokens and verified against actual provider usage. Whole-passage original-order prefix is the only overflow policy; oversize first passage causes failure without replacement. All ten selected cases retained all fifteen original passages, so the actual experiment has zero truncation or altered-context cases.

Existing T3 source, prompts, schemas, original selector and eight stages are unchanged. Allowed provider-only generation cap is 512 for BOTH systems, analysis1500/profile500, model gpt-4o-mini, temperature0, repetitions1, <=60 external attempts, no retries/embeddings/judges/verifiers. No provider fallback or second assessment is used. T3 and control see the same gold-free semantic assessment. Control sees no T3 response contract; A0 is gate-only on the same upstream data.

Gold boundary checks combine exact input-key whitelist, original gold-field denylist, pre-call policy binding and actual serialized payload scans for selected/private identifiers. The provider denylist omits the literal sample_id key as an independent defense; the adapter strips it and scans prove it absent in this run. Document this future hardening without modifying the frozen tested provider.

Scoring was implemented post-run and is deterministic source-label diagnosis, not a new model or a tuned runtime. It scores three separate proposal layers (global spans, PRIMARY/SUPPORTS roles, requirement spans) and two actual public-answer citation layers. Known syntaxes: [cite_N], [view-NNNN], [view-NNNN:span-NNNN]. Unknown bracketed IDs are invalid, ordinary year/page numbers are not treated as citations, and implicit support never becomes a public citation. Per-source correctness strings are retained. Invalid assessments' raw proposals are explicitly diagnostic, not accepted T3 support.

Source precision=TP/(TP+FP), recall=TP/(TP+FN), F1=2TP/(2TP+FP+FN), with YES positives, NO negatives and empty relevance unknown. Zero denominators are undefined. Absence of citations with positive reference sources gives recall/F1 zero and precision undefined. No exact-match answer score, official RAF, independent entailment metric or FULL/CFAF accuracy is manufactured. Agent review is labelled non-independent; human review is PENDING.
''')
 print('Reports written; safe bytes', (ROOT/'REPORT.md').stat().st_size,'detailed local bytes',(ROOT/'local/REPORT_FULL.md').stat().st_size)
if __name__=='__main__':build()
