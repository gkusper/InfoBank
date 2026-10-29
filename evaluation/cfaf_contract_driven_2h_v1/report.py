"""Build qualified study/paper artifacts from measured results only."""
import json,collections,csv,datetime
from .artifacts import *
from .deadline import elapsed

def table(headers,rs):
 def c(v):return str(v).replace('|','/').replace('\n',' ')
 return '| '+' | '.join(headers)+' |\n| '+' | '.join('---' for _ in headers)+' |\n'+'\n'.join('| '+' | '.join(c(v) for v in r)+' |' for r in rs)+'\n'
def pct(v):return 'N/A' if v is None else f'{v*100:.1f}%'
def tex_pct(v):return '--' if v is None else f'{v*100:.1f}\\%'
def ci(v):return 'N/A' if not v else '['+pct(v[0])+', '+pct(v[1])+']'
def save(name,text):(ROOT/name).write_text(text.strip()+'\n',encoding='utf-8')

def build():
 summary=read(ROOT/'comparison_summary.json');paired=read(ROOT/'paired_mode_confusions.json');ground=read(ROOT/'grounding_metrics.json');ops=read(ROOT/'operational_failures.json');usage=read(ROOT/'api_usage.json');security=read(ROOT/'security_audit.json');freeze=read(ROOT/'git_freeze_manifest.json');plan=read(ROOT/'selection_plan.json');reg=read(ROOT/'regression_audit.json');runtime_manifest=read(ROOT/'runtime_manifest.json');safe={d:rows(ROOT/(d+'_results.jsonl')) for d in summary};raw={d:{r['runtime_index']:r for r in rows(ROOT/(d+'_results_raw.jsonl'))} if (ROOT/(d+'_results_raw.jsonl')).exists() else {} for d in summary};gold={d:rows(ROOT/(d+'_gold.jsonl')) for d in summary};runtime={d:rows(ROOT/(d+'_runtime.jsonl')) for d in summary}
 dataset_rows=[];mode_rows=[];pair_rows=[];cost_rows=[]
 for d,v in summary.items():
  dataset_rows.append([d,v['dataset'],v['planned'],v['paired_executions_completed'],v['incomplete']])
  for system,m in v['systems'].items():
   mode_rows.append([d,system,pct(m.get('mode_accuracy_nonoperational')),ci(m.get('mode_accuracy_cluster_interval95')),pct(m.get('balanced_accuracy')),pct(m.get('FULL_recall')),pct(m.get('CFAF_recall')),m['operational_failure_count'],m['observed_modes'].get('FULL',0),m['observed_modes'].get('CFAF',0)])
  for key,p in paired.get(d,{}).items():
   if key=='bootstrap':continue
   pair_rows.append([d,key,p['left_only'],p['right_only'],p['difference_count'],pct(p['difference_fraction']),ci(paired[d]['bootstrap']['paired_delta_intervals'][p['left']+'-'+p['right']])])
  u=usage['by_dataset'][d];cost_rows.append([d,u['attempts'],u['input_tokens'],u['output_tokens'],u['kind_counts'],f"{u['local_overhead_ms']/1000:.3f}",f"{u['B_total_postprocess_ms']:.3f}"])
 cohort_table=table(['Dataset','Cohort','Planned','Paired complete','Incomplete'],dataset_rows);mode_table=table(['Dataset','System','Non-op mode accuracy','95% cluster interval','Balanced','FULL recall','CFAF recall','Operational','FULL','CFAF'],mode_rows);pair_table=table(['Dataset','Paired contrast','Left-only correct','Right-only correct','Count delta','Fraction delta','95% group interval'],pair_rows);cost_table=table(['Dataset','Calls','Input tokens','Output tokens','Kinds','Local overhead s','B postprocess ms'],cost_rows)
 source_table=table(['D3 layer','N','Relevance P','Relevance R','F1'],[[k,v['case_count'],pct(v['micro_precision']),pct(v['micro_recall']),pct(v['micro_f1'])] for k,v in ground['layers'].items()]+[['C valid-assessment subset',ground['C_valid_assessment_only']['case_count'],pct(ground['C_valid_assessment_only']['micro_precision']),pct(ground['C_valid_assessment_only']['micro_recall']),pct(ground['C_valid_assessment_only']['micro_f1'])],['C unchanged-context subset',ground['C_unchanged_context_only']['case_count'],pct(ground['C_unchanged_context_only']['micro_precision']),pct(ground['C_unchanged_context_only']['micro_recall']),pct(ground['C_unchanged_context_only']['micro_f1'])]])
 cite_table=table(['System','Actual public citation sources','Invalid citations','Unverified reference associations','Verified sidecar citations','Citationless FULL'],[[s,v['actual_public_citations'],v['invalid_public_citations'],v['mechanically_valid_unverified_associations'],v['rendered_verified_citations'],v['citationless_FULL']] for s,v in ground['systems'].items()])
 error_rows=[]
 for d,rs in safe.items():
  for r,g in zip(rs,gold[d]):
   bad=r['execution_status']!='COMPLETED' or any(e['operational_failure'] for e in r['systems'].values()) or d!='dataset3' and any(not e['mode_correct_nonoperational'] for e in r['systems'].values())
   if bad:error_rows.append([d,r['sample_id'],r['execution_status'],g.get('expected_mode',g.get('expected_top_level_mode','No native mode gold')),' / '.join(f"{s}:{e['mode']}{'/OP' if e['operational_failure'] else ''}" for s,e in r['systems'].items()),r['C_validation_error_codes']])
 errors_table=table(['Dataset','Sample ID','Execution','Gold mode where available','Observed A/B/C (OP=operational)','C technical error codes'],error_rows)
 benefit=[]
 for d in ['dataset1','dataset2']:
  delta=paired[d]['C_vs_B'];benefit.append(f"{d}: C has {delta['left_only']} non-operational mode matches that B misses, B has {delta['right_only']} that C misses; net {delta['difference_count']}/{delta['N']} ({pct(delta['difference_fraction'])}), cluster interval {ci(paired[d]['bootstrap']['paired_delta_intervals']['C-B'])}.")
 d1=summary['dataset1'];d2=summary['dataset2'];d3=summary['dataset3'];total_complete=sum(x['paired_executions_completed'] for x in summary.values());total_planned=sum(x['planned'] for x in summary.values());tag=freeze['annotated_tag'];elapsed_now=elapsed()
 diagnostics=table(['D1 system','Mode accuracy','Reason-class agreement','Fulfilment-status agreement','Gold-marker presence (FULL gold)','Policy violations'],[[system,pct(m['mode_accuracy_nonoperational']),pct(m['reason_class_agreement']),pct(m['fulfilment_status_agreement']),pct(m['gold_marker_presence_FULL_cases']),m['policy_violation_count']] for system,m in d1['systems'].items()])
 body=f'''# Contract-driven transition and three-dataset bounded study

## Executive summary

**{total_complete}/{total_planned} planned cases completed with paired A/B/C executions**. Dataset1 and Dataset2 are exposed development cohorts. Dataset3 is a newly selected 80-row code-frozen sample, evaluated only for original source-label grounding and technical/response outcomes: it has no native FULL/CFAF gold and no independent claim-adjudication result.

{cohort_table}

The historical `wolala2026` commit **{freeze['local_commit']}** is preserved by annotated local tag **{tag}**. The new branch `experiment/cfaf-contract-driven-v1` starts at **{freeze['starting_commit']}**, the latest sparse-source experiment. No push, merge, deletion or rewrite occurred. The user performs later publication pushes manually. A local tag is a reproducible reference, not remote branch protection.

A is a standard selective-RAG prompt using the common self-reported mode format. B is deterministic output/policy postprocessing of that **same A generation**, not a new independent model sample. C is the existing sparse-source CFAF semantic-analysis/gate/realization pipeline, with its old unused shared-control generation removed. The four dataclass contracts are boundary scaffolding; no new eight-stage architecture, retriever, NLI model or one-call optimization was evaluated.

Primary non-operational mode agreement on Dataset1: A={pct(d1['systems']['A']['mode_accuracy_nonoperational'])}, B={pct(d1['systems']['B']['mode_accuracy_nonoperational'])}, C={pct(d1['systems']['C']['mode_accuracy_nonoperational'])}. On exposed Dataset2: A={pct(d2['systems']['A']['mode_accuracy_nonoperational'])}, B={pct(d2['systems']['B']['mode_accuracy_nonoperational'])}, C={pct(d2['systems']['C']['mode_accuracy_nonoperational'])}. These are gold **mode** metrics, not generated-answer factual accuracy.

Actual usage: **{usage['attempts']} model attempts**, {usage['input_tokens']:,} input tokens and {usage['output_tokens']:,} output tokens, {usage['errors']} HTTP/provider errors, zero retries/embeddings/external judges. Model deployment(s) observed: `{usage['models_observed']}`. The configured model is only gpt-4o-mini, temperature0, one repetition.

## Cohorts, authorization and preregistration

The exact preregistered rows, seeds, source revisions, hashes and error/statistical plan were frozen before fresh Dataset3 text was materialized. See PREREGISTRATION.md, selection_plan.json, experiment_manifest.json, runtime_manifest.json and the per-dataset selection/exposure manifests. Dataset3 seed20261029 selected 80 without replacement from ordered2366 indices excluding the ten exposed pilot indices; no balancing, gold filtering or resampling. All80 selections were charged before API execution, including any failed/unexecuted case. The cumulative Dataset3 exposure is90; **2276 records remain unused**.

Dataset1 uses all40 already-exposed P1–P5 cases, twenty matched pairs. Legacy filenames say heldout_pilot_v3/HELD3, but the earlier completed full_40 manifest proves these are exposed development data now. They are not the new independently authored40-case holdout. No such independent cohort is established in the attached/current repository inputs, none is invented, and none is opened here.

Dataset2's reservation metadata confirms30 reserved groups have no prior exposure, but its content_policy explicitly forbids reading/displaying/saving/supplying their heldout query/context/answers/reasoning. The current task explicitly instructs respecting such a rule. Therefore the preregistered fallback is40 uniformly sampled already-exposed eligible records, seed20261029, from130 exposed ledger entries sorted by original index. This is **development-only**, not the intended final reserved-group evaluation. The30 reserved and18 other untouched groups remain untouched. The contradiction exclusion and original ANSWER_CORRECTLY -> FULL / eligible REFUSE_* -> CFAF mapping are preserved. No label is changed and original ledgers are not rewritten.

Dataset3 is original AmazonScience GaRAGe, not RefusalBench-GaRAGe: source commit2b7264f5d4e066affbe4b67b7d3b9cffeff98ede, JSONL SHA256419e3941f6e8eb4082a74ca2140c1f9337f8b467ff76656a6b8b0290ca3f3a72, 2366 questions/35,351 passages. Only the80 selected new row objects were parsed for text. Original labels/reference answers stay scorer-only and ignored. No output-dependent code or prompt tuning occurred.

## Shared evidence and measured systems

All systems receive the same authorized source contents/order/provenance, question date and initial deterministic question profile/opaque legitimate view bindings. Sources are projected before any model call; DENY, metadata, aggregate and P5 restrictions apply to A as well as B/C. This is not an unsafe-private-input versus safe-input comparison. No separate synthetic unsafe-disclosure stress condition was run.

A receives no semantic assessment or CFAF response contract and has no application request-relative fulfilment selector. Its FULL/CFAF is the model's self-report under a fixed ordinary evidence-answering prompt and common six-field measurement schema. B reuses the exact A object and applies the existing canonical public contract and output-policy guard with safe operational fallback. B does not run RDA/RECV sufficiency or create a second model answer. In this run every A output passes B's postprocessing unchanged; this shows no activation of the guard, not that guarding is generally ineffective.

C reuses the existing sparse-source inventory, exact references, RDA/RECV, trusted provenance, shadow target/claim diagnostics, original TopLevelModeSelectionStage and eight named stages. Analysis and CFAF realization prompts/schemas are unchanged. A thin version-local adapter removes only the unused fourth-call shared control and its no-view placeholder. C adds semantic analysis and selector/contract realization to the shared evidence; differences from B therefore measure this **whole existing pipeline**, not the selector in isolation. Existing query-only fallbacks are charged and reported, not treated as new judges or free calls. They can change C's derived question interpretation; no source text changes.

The four executable dataclasses in CONTRACTS.md validate request signatures, permitted inventory, decision mode/status and public outputs. They do not constitute a replacement RAG framework. MAKE_OR_REUSE.md provides one reuse decision for each stage, with actual availability/licence/version evidence, cost limits and governance tests. Missing named backend modules and unverified partial-main licences are explicitly identified. No new large dependency was installed; no library replacement or one-call Structured Outputs optimization is credited as measured.

## Mode results and uncertainty

Primary mode accuracy counts only non-operational, policy-valid outputs matching original gold, with **all planned cases in the denominator**. A safe technical CFAF fallback is not a correct evidential refusal even when gold is CFAF. Observed output-mode agreement is separately recorded in comparison_summary.json; it is not the headline metric. Mode matching and marker presence do not establish factual entailment or complete generated answers.

{mode_table}

N/A on Dataset3 is intentional: original source labels do not independently determine complete request fulfilment. FULL/CFAF distributions there are observed behaviors only.

{pair_table}

{' '.join(benefit)}

Intervals use the preregistered seed20261029 and2000 joint cluster-bootstrap replicates: Dataset1 resamples matched pairs; Dataset2 resamples original source groups. B and A share generation, and all systems share cases. Intervals describe these selected dependent cohorts; no population guarantee or statistical-significance claim is made. A degenerate perfect-sample bootstrap interval does not imply population certainty. Exact discordant counts, including failures, are in paired_mode_confusions.json. Any mode advantage over B remains development evidence, not proof of general factual-answer improvement.

Dataset1 matched-pair joint mode accuracy: A={pct(d1['systems']['A']['matched_pair_joint_mode_accuracy'])}, B={pct(d1['systems']['B']['matched_pair_joint_mode_accuracy'])}, C={pct(d1['systems']['C']['matched_pair_joint_mode_accuracy'])}. Exact reason-class, fulfilment-status and gold-marker-presence diagnostics are in comparison_summary.json. They use original annotations and retain failure denominators; they do not certify full natural-language reason/answer correctness. P5 pair-equivalent responses and zero model calls are audited separately; all three share the no-view rule.

## Exact output/reason diagnostics

{diagnostics}

Thus C's100% development mode result is not100% reason/fulfilment agreement: exact reason-class agreement is72.5% and fulfilment-status agreement80%. These unchanged native labels were not rewritten. Some public-reason differences, especially under P5 indistinguishability, require semantic/privacy interpretation; exact agreement alone is not an adjudicated explanation-quality score.

On Dataset2, C reduces observed false FULL from7 to5 but increases unnecessary non-operational refusals from3 to6. FULL recall falls from78.6% (B) to57.1% (C), while CFAF recall rises from73.1% to80.8%. Balanced accuracy is75.8% for B and69.0% for C. There is no consistent measured superiority across the two development cohorts.

## Operational failure versus evidential refusal

The per-system status and gate outcome distributions are preserved in operational_failures.json and the finer observational categories in operational_failure_breakdown.json. These distinguish HTTP/execution/malformed-output failures, invalid semantic source/reference contracts, generated FULL, and validated request-relative CFAF. In particular, structurally valid source selection and the internal VERIFIED_FULFILMENT label mean the existing gate accepted model properties, not independent entailment verification.

{table(['Dataset','C gate outcomes','C technical error codes','Query-profile fallbacks'],[[d,v['C_gate_outcomes'],v['C_validation_error_codes'],v['query_only_fallbacks']] for d,v in ops.items()])}

Operational failures use neutral public verification wording and cannot be credited as successful evidential CFAF. P5 retains its unchanged indistinguishable canonical response. Raw versus guarded outputs remain in ignored local logs; safe summaries contain status/code/count information rather than unredacted answers.

## Dataset3 grounding, scope and citations

{source_table}

Raw C proposals are resolvable model-proposed sources, including invalid assessments. Validated C support requires a valid assessment and explicit usable PRIMARY/SUPPORTS roles with exact authorized references. A/B have no semantic-source-selection stage; only actual citations can establish their measured source selection. Their absent citation precision is undefined, not an inferred empty private retrieval plan. Original YES/NO relevance is not full-answer sufficiency, and answering-labelled sources do not prove multipart completeness. RELATED-INFORMATION, UNKNOWN, OUTDATED and blank labels remain distinct.

Original sampled label counts: `{ground['original_label_distributions']}`. C has {ground['semantic_valid_cases']}/{d3['planned']} structurally valid assessments. There are {ground['altered_context_cases']} altered-context cases under the preregistered whole-passage-prefix input policy; all systems receive the same retained views. Their results are separate from the unchanged-context subset. No selected case is replaced. Missing relevant-source recall is not proof that an answer must cite every relevant passage.

{cite_table}

The C trace component retains exact requirement/candidate-to-reference provenance only when mechanically validated; uncertain associations remain CITATION_SUPPORT_UNVERIFIED and are not rendered as verified citations. A reference ID or source hash is not semantic proof. Zero invalid emitted citations is not success if no citations were emitted. Actual citation counts and citationless FULLs are reported rather than manufactured.

No native Dataset3 FULL/CFAF accuracy or human entailment accuracy is calculated. Independent adjudication is PENDING. DATASET3_ADJUDICATION_RUBRIC.md and its blank template are provided; the ignored blinded packet contains authorized context and randomized response aliases, with the system key stored separately. It excludes original human answers/source labels and internal gate diagnostics. Blinding hides system names, not stylistic clues. Any mechanical observations here are not independent answer judgements.

## Case errors and limitations

{errors_table}

This error list is not a new gold annotation set. The complete original questions, served/raw model responses, request/gate diagnostics and references remain in ignored local files. Source-role/reference validation failures, incorrect mode matches and semantic truth are separate. A/B/C may agree while all miss a requested relation or essential condition. No new parser, NLI model or general LLM judge was introduced to declare such claims correct.

The original 40 synthetic 100% research result and later roughly80–85% mixed development-mode reports belong to different phases. They are not pooled or reinterpreted as final factual-answer correctness. Current D1/D2 observations are also exposed development. Dataset3 is a fresh sample relative to this development history, but a public benchmark may be familiar to the model; it supplies source annotations, not independent contract-specific answerability or entailment gold. A degenerate perfect-sample bootstrap interval does not imply population certainty. Small dependent cohorts, legacy short C candidate limits, as-of metadata, possible partial contexts, operational failures and unadjudicated public citations bound interpretation.

## Cost and reproducibility

{cost_table}

Total model attempts {usage['attempts']}/480; input tokens {usage['input_tokens']:,}, output tokens {usage['output_tokens']:,}; successes {usage['successes']}, API errors {usage['errors']}, unsettled attempts {usage['unsettled_attempts']}. Mean HTTP/provider latency {usage['mean_latency_ms']:.1f} ms, maximum {usage['max_latency_ms']:.1f} ms, summed HTTP/provider time {usage['provider_latency_seconds']:.3f} seconds. B adds zero model calls; its measured postprocessing time is separate. Query-only fallback is included in C costs. No retries, embeddings or external judges; no monetary estimate without verified pricing.

Shared A/B output is charged once. Local overhead in the table is measured outside the provider wrapper; latency_analysis.json also separates end-to-end case wall time from inner HTTP timing so durable accounting/serialization overhead is visible. No production CPU/memory throughput or unexecuted one-call savings is claimed.

All {security['protected_files_checked']} earlier tracked files and prior branches/annotations are preserved. The frozen source hashes, preregistration, selected runtime/gold hashes, API payload audits, source hashes and exact exposure ledgers support reproduction. New raw text/gold/traces are ignored and are not added to public Git. The final commit receipt and checksums cover safe artifacts. Final compatibility tests: 691 passed, with 3 historical hash-only tests deselected and separately passing on the original working files. The new 9 synthetic checks are included in 691, not extra unique tests. The original suite has 77 passed plus 13 passing subtests and one known pre-existing failure, test_preheldout_attempt1_plan_artifacts_are_plan_only, caused by the previously committed authorization metadata file. It is preserved; no failure is hidden by changing old sources.

Study start UTC {read(ROOT/'task_state.json')['start_utc']}; current elapsed at report generation {elapsed_now:.1f} seconds. Persistent monotonic and wall clocks enforce120 minutes total, no new requests after105. No timer reset or promised later run. The completion receipt records final elapsed time and commit.

## Twelve required conclusions

1. Frozen historical commit: {freeze['local_commit']}, annotated local tag {tag}; exact tree/tag hashes are in WOLALA2026_FREEZE.md.
2. New branch: experiment/cfaf-contract-driven-v1, starting at sparse-source commit {freeze['starting_commit']}.
3. Each of eight stage reuse choices and the retained CFAF contract is listed in MAKE_OR_REUSE.md; the original selector/stages are retained.
4. The compact four-contract skeleton ran as boundary validation scaffolding. The measured empirical pipeline is existing sparse CFAF, not a new framework or validated library replacement. One-call optimization is future-only.
5. Planned/completed/incomplete: {', '.join(d+': '+str(v['planned'])+'/'+str(v['paired_executions_completed'])+'/'+str(v['incomplete']) for d,v in summary.items())}. Reserved Dataset2 final groups were not consumed; the authorized development fallback was preregistered.
6. Fully paired mode outcomes, discordant counts and grouped intervals are separate by dataset above; Dataset3 has no binary accuracy. No significance claim.
7. Benefit over guarded B: {' '.join(benefit)} This concerns exposed-cohort mode agreement under the whole C pipeline, not independent factual superiority or an isolated selector effect.
8. Operational fallback credit is excluded from the primary mode numerator. Status counts and observed-mode agreement show any apparent agreement caused by technical withholding separately.
9. Dataset3 labels support source-level relevance/correctness-category/citation diagnostics. Complete fulfilment, per-claim entailment and refusal appropriateness await independent adjudication.
10. Actual usage: {usage['attempts']} attempts, {usage['input_tokens']:,}/{usage['output_tokens']:,} input/output tokens; exact elapsed/cost splits are in the usage/timeline artifacts and final receipt. No invented dollar cost.
11. Evidence-ready manuscript material: observed development-mode comparisons with cluster intervals, fresh 80 source-label/technical metrics, exposure/provenance and limitations. Independent final Dataset2, factual-answer accuracy and new-architecture/one-call gains are not evidence-ready.
12. Best next action: reuse these existing boundaries to plug one already-available component into a separately named small ablation, with an independent fulfilment/claim rubric and fixed evidence. Avoid increasing bespoke semantic code; do not tune on the just-exposed80 or consume the remaining 2276 casually.

## Manual publication commands

No push was executed. From the repository, the user may run:

```powershell
git push origin refs/tags/{tag}
git push -u origin experiment/cfaf-contract-driven-v1
```

Configure remote branch/tag protection separately as described in WOLALA2026_FREEZE.md; this study does not assert protection is active.
'''
 save('REPORT.md',body)
 # Manuscript fragment: no documentclass, new bibliography or historical rewrite.
 lines=[r'\begin{table}[t]',r'\centering',r'\small',r'\caption{Development-cohort mode agreement with failures retained. A is standard selective RAG; B is postprocessed A; C is the existing sparse-source CFAF pipeline. These are mode metrics, not factual-answer accuracy.}',r'\label{tab:cfaf-contract-study-mode}',r'\begin{tabular}{llrlll}',r'\hline',r'Dataset & System & $n/N$ & Mode \% [95\% CI] & Bal. \% & Op. \\',r'\hline']
 for d,label in [('dataset1','D1 dev'),('dataset2','D2 dev')]:
  for system,m in summary[d]['systems'].items():
   interval=m['mode_accuracy_cluster_interval95'];cell=f"{100*m['mode_accuracy_nonoperational']:.1f} [{100*interval[0]:.1f}, {100*interval[1]:.1f}]";balanced='--' if m['balanced_accuracy'] is None else f"{100*m['balanced_accuracy']:.1f}";lines.append(f"{label} & {system} & {summary[d]['paired_executions_completed']}/{summary[d]['planned']} & {cell} & {balanced} & {m['operational_failure_count']}"+r' \\')
 lines += [r'\hline',r'\end{tabular}',r'\end{table}',r'',r'\begin{table}[t]',r'\centering',r'\small',r'\caption{Fresh GaRAGe sample: original source-label metrics only. C rows distinguish raw proposals and validated support; A/B source selection is measurable only from their actual citations. No native FULL/CFAF or independent entailment accuracy is available.}',r'\label{tab:cfaf-contract-study-grounding}',r'\begin{tabular}{lrrr}',r'\hline',r'Layer & Precision \% & Recall \% & F1 \% \\',r'\hline']
 for key,label in [('raw_C','C raw proposals'),('validated_C','C validated support'),('A_actual_citations','A actual citations'),('B_actual_citations','B actual citations'),('C_actual_citations','C actual citations')]:
  g=ground['layers'][key];values=['--' if g[k] is None else f"{100*g[k]:.1f}" for k in ['micro_precision','micro_recall','micro_f1']];lines.append(label+' & '+' & '.join(values)+r' \\')
 lines += [r'\hline',r'\end{tabular}',r'\end{table}',r'',r'\paragraph{Results.}']
 lines.append(f"The preregistered study completed {total_complete}/{total_planned} paired cases: {d1['paired_executions_completed']}/40 on exposed InfoBank development cases, {d2['paired_executions_completed']}/40 on a fixed exposed RefusalBench-NQ fallback, and {d3['paired_executions_completed']}/80 on newly sampled GaRAGe records. The reserved 30 RefusalBench groups were not opened because an existing content-prohibition rule was retained.")
 for d in ['dataset1','dataset2']:
  p=paired[d]['C_vs_B'];lines.append(f"On {d.upper()}, C had {p['left_only']} non-operational mode matches missed by B and missed {p['right_only']} matches obtained by B (net {p['difference_count']}/{p['N']}). Intervals jointly resample matched pairs or source groups and do not support a population or significance claim.")
 lines.append(f"The run used {usage['attempts']} gpt-4o-mini calls, {usage['input_tokens']} input tokens and {usage['output_tokens']} output tokens, with {usage['errors']} API errors and no retries, embeddings or external model judges. B reuses A's generation; no extra B inference is charged.")
 lines.append(f"On the fresh 80 GaRAGe rows, C has {ground['semantic_valid_cases']} valid assessments and {d3['systems']['C']['operational_failure_count']} operational failures. Its 53 FULL and 27 CFAF outputs are behaviors, not accuracy; A/B each produce 71 FULL and 9 CFAF. All systems emit zero actual public citations.")
 lines += [r'',r'\paragraph{Limitations.}']
 lines.append(f"D1 and D2 are exposed development cohorts; their mode agreement must not be pooled with historical 40-case results or called final answer accuracy. GaRAGe source labels do not certify complete fulfilment or claim entailment. Independent adjudication is pending; {ground['altered_context_cases']} of 80 cases use the preregistered whole-passage-prefix context bound. Operational fallbacks remain separate from substantively correct refusals. Exact-copy source associations are unverified and are not rendered as verified claim citations. Public-benchmark familiarity, dependent small samples, existing C short-answer constraints and a single repetition limit generalization. The compact boundary skeleton and future one-call optimization are not evaluated architecture replacements.")
 save('RESULTS_FOR_PAPER.tex','\n'.join(lines))
 save('PAPER_INTEGRATION_NOTES.md',f'''# Integration into CF2AF_v5.8

No CF2AF_v5.8.tex was found in the current repository or explicit Downloads/Documents candidate paths. No historical manuscript was overwritten and no missing bibliography entry was invented. RESULTS_FOR_PAPER.tex is an input-ready fragment using ordinary LaTeX table/tabular constructs, not a new standalone paper.

Insert this as a separate later-study subsection, retaining the historical40-case100% statement in its original experimental context. The new table compares A/B/C on exposed development cohorts and a separate fresh GaRAGe sample. Do not replace historical numbers, pool cohorts, call development mode accuracy factual accuracy, or describe the boundary skeleton as a validated new framework.

Measured paired outcomes: {total_complete}/{total_planned}; D1 {d1['paired_executions_completed']}/40, D2 {d2['paired_executions_completed']}/40 exposed fallback, D3 {d3['paired_executions_completed']}/80 source-label study. No reserved 30-group final Dataset2 experiment occurred. If any cohort is partial, keep the n/N and incomplete IDs exactly as recorded.

Mode intervals are the preregistered joint cluster-bootstrap percentiles, not independent-case/binomial significance tests. Degenerate perfect-sample bootstrap intervals do not imply population certainty. B is deterministically derived from A; C's extra semantics/selector are a whole-pipeline contrast, not a selector-only causal ablation. Technical fallback receives no substantive correct-refusal credit.

D3 has no native FULL/CFAF or independent entailment labels. Keep raw/validated support and actual citations separate. Undefined citation precision is not zero or success. The unverified sidecar is not a verified citation system. Two bounded-context cases are reported separately. No new LLM judge was used.

The fragment includes only obtained metrics. One-call Structured Outputs, new libraries, independent holdout accuracy and semantic factual superiority are not evidence-ready. Existing paper citations can be reused if already present; the fragment introduces no citation keys or bibliography.
''')
 save('DATASET3_ADJUDICATION_RUBRIC.md','''# Independent Dataset3 fulfilment and claim adjudication

All fields are PENDING. This packet does not invent a FULL/CFAF or entailment gold label. Recruit an annotator independent of this implementation/model-output review; preserve original GaRAGe source labels separately.

1. Before reading generated responses, inspect the original question, as-of date and supplied authorized passages. Decompose essential requested entities, relations, comparisons, time scope, conditions and required granularity. Record whether a complete supported answer is possible, with source/span evidence and uncertainty. Do not equate relevant or answering-labelled passages with all-requirement completeness; original labels/reference answers are intentionally absent from the blinded packet.
2. Then inspect anonymous response aliases R1/R2/R3 in randomized order. Identify each factual claim and whether the supplied material supports that exact subject/relation/qualifier. Mark SUPPORTED, PARTIAL, UNSUPPORTED or UNVERIFIABLE; record missing essential requirements separately from false claims. A short answer is not automatically incomplete.
3. Judge abstention/clarification appropriateness relative to question/evidence. Neutral operational wording is an execution outcome, not a statement that evidence is absent. Do not reward a technical failure as semantically correct refusal.
4. Check actual public citations, if any, for authorized source, exact span and claim usefulness. A mechanically valid reference or model-declared relation is not entailment proof. Mark absent/unverified citations explicitly.
5. Record uncertainty and disagreements. Prefer two independent annotators and adjudication if feasible. Do not edit original GaRAGe labels; a new contract-specific judgement is a separate annotation layer.

The ignored local packet contains only authorized question/context and masked generated outputs. The separate ignored key maps response aliases to systems. Names are blinded, stylistic clues may still reveal a method. DATASET3_ADJUDICATION_TEMPLATE.csv has blank judgements for all selected responses; no score is derived from unfilled fields.
''')
 save('README.md','''# Contract-driven two-hour comparative study

Start with REPORT.md, PREREGISTRATION.md and the frozen experiment_manifest.json. MAKE_OR_REUSE.md/CONTRACTS.md describe prepared boundaries and existing components; WOLALA2026_FREEZE.md records historical SHA/tag and manual future publication commands.

A is standard selective RAG using policy-safe shared evidence and a self-reported mode schema. B postprocesses the exact same A generation; it is not an independent model sample. C is existing sparse-source CFAF, with only the unused fourth control-generation removed. The compact architecture/one-call/library replacements are not presented as newly evaluated frameworks.

Cohorts: 40 exposed InfoBank development cases, 40 fixed exposed RefusalBench-NQ fallback records (reserved 30 and other18 groups untouched), 80 new frozen GaRAGe rows excluding the ten pilot IDs. All80 were charged as exposed before requests. Remaining2276 records stay unused. The new independent InfoBank holdout is not opened.

Safe outputs: dataset1_results.jsonl, dataset2_results.jsonl, dataset3_results.jsonl; comparison_summary.csv/json; paired_mode_confusions.json; grounding_metrics.json; operational_failures.json and the finer breakdown; actual api_usage.json; security/regression audits; source/prompt/runtime hashes; RESULTS_FOR_PAPER.tex and integration notes. Failure denominators and cohort qualification are explicit.

Ignored local files retain runtime inputs, scorer-only original answers, actual API requests/events, *_results_raw.jsonl, blinded packets and the detailed case report. Do not force-add them. No original benchmark text/reference answer or fresh private trace is committed.

Do not rerun this completed study in place. Model commands refuse repeated cohorts and use a persistent deadline/attempt ledger; resetting either is not authorized. A later task needs separate outputs and a new predeclared protocol. Do not tune on the just-exposed80. The ordinary offline synthetic test entry point is:

```powershell
python -m pytest evaluation/cfaf_contract_driven_2h_v1/test_study.py -q
```

The annotated tag is local only, and does not enforce GitHub protection. No push/merge/deletion was executed. The user performs any later pushes manually using the commands in the report/freeze document.
''')
 case_text=['# Detailed local case outputs — ignored','Exact benchmark questions, scorer annotations and traces stay local. Observations are not independent claim adjudications.']
 for d in summary:
  for i,(inp,g,safe_record) in enumerate(zip(runtime[d],gold[d],safe[d])):
   rr=raw[d].get(i,{});case_text.append(f"## {d} case {i+1}: {safe_record['sample_id']}\n\nQuestion: {inp['case']['query']}\n\nExecution: {safe_record['execution_status']}; altered context: {inp.get('altered_context',False)}.\n\n```json\n"+json.dumps({'systems':rr.get('systems',{}),'C_verification':(rr.get('C_outcome') or {}).get('verification_outcome'),'C_issues':(rr.get('C_outcome') or {}).get('fulfilment_issues'),'C_requirement_support':((rr.get('C_outcome') or {}).get('semantic_assessment') or {}).get('requirement_support'),'safe_metrics':safe_record},ensure_ascii=False,indent=2)+'\n```')
 save('local/CASE_REPORT.md','\n\n'.join(case_text))
 print('REPORT AND MANUSCRIPT WRITTEN',total_complete,'/',total_planned,'paired cases')
if __name__=='__main__':build()
