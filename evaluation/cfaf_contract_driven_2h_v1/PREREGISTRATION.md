# Preregistration: bounded contract-driven comparative study v1

Declared before opening the new Dataset3 inputs and before model requests. Exact rows/groups/IDs and seeds are in selection_plan.json. SHA-256 of this file and that plan are fixed in experiment_manifest.json before materialization.

## Cohorts and boundaries

Dataset1: exactly the 40 previously exposed P1–P5 synthetic cases, 20 matched pairs, in evaluation/wolala2026/data/heldout_pilot_v3/cases.jsonl. The HELD3/heldout filename is historical: the previous full_40 manifest proves all were already used. This is development evaluation, not the new independent authored 40-case holdout. No newly authored holdout is established/used.

Dataset2: the reserved 30 groups remain untouched because reserved_holdout_manifest.json explicitly says no heldout query/context/answers/reasoning may be read/displayed/saved/supplied. The current task explicitly instructs obeying such a prohibition. Fixed fallback: random.Random(20261029).sample on the 130 exposed eligible ledger entries sorted by original dataset_index, n=40. No new group or record, no stratification or replacement. This cohort is development-only. The 18 other untouched groups also remain untouched. Original ANSWER_CORRECTLY -> FULL, eligible REFUSE_* -> CFAF; exclusion/mapping remain unchanged.

Dataset3: original pinned AmazonScience GaRAGe commit 2b7264f5d4e066affbe4b67b7d3b9cffeff98ede, JSONL SHA256 419e3941f6e8eb4082a74ca2140c1f9337f8b467ff76656a6b8b0290ca3f3a72. Exactly 80 uniformly sampled rows from ordered range(2366) excluding the ten exposed pilot indices, using random.Random(20261029).sample. Indices are already recorded in selection_plan.json without opening fresh text. Only after code freeze, materialize those rows, persist original IDs/raw-line hashes and charge all80 into a new exposure ledger before requests. No original question/passage/reference from other fresh rows is parsed. No resampling or label/complexity filtering. No native FULL/CFAF gold; no binary accuracy or invented human entailment label.

## Three systems

A: standard selective RAG generation over the shared policy-authorized evidence, initial deterministic question profile and legitimate opaque source bindings. The six-field common measurement schema asks the model to self-report FULL/CFAF. No semantic assessment, response contract or application fulfilment selector is supplied. This is a measured prompt baseline, not a claim about every possible standard RAG.

B: deterministic postprocessing of the exact same A generation. Same evidence/access projection, strict existing public vocabulary/output-policy checks and safe operational fallback; no second call and no request-relative fulfilment selector. No genuinely denied private content is exposed in A. No separate unsafe synthetic-disclosure stress experiment is planned.

C: existing sparse-source semantic analysis, RDA/RECV gate/original selector and contract realization. Analysis/schema and CFAF generation prompt are unchanged. A thin measurement copy removes only the unused previous shared-control generation, so the study has three calls, not four, per nonempty case. The four small dataclass boundary contracts are validation scaffolding; the measured pipeline is existing code, not a newly implemented architecture. R1 reference alias repair remains off. Any C query-only model fallback is retained, charged and reported; this derived extra interpretation is part of C and is not claimed as an isolated selector effect.

All three receive identical legitimate source contents, order, policy projection, source provenance and question date. C adds model semantics and selection/realization; a benefit over B would be a whole-pipeline difference, not proof of the selector alone. No unmeasured private inventory diagnostics reach either generator. No output-dependent input adjustment or new library replacement.

## Retrieval and limits

No embeddings or external fact retrieval. Use supplied/frozen evidence snapshots. D1 authorized views preserve FULL/AGGREGATE/METADATA/DENY/P5 rules. D2 uses the full original perturbed context as one authorized supplied view; if it cannot fit the fixed input budget, record operational input-budget failure, without truncation/resampling. D3 reuses the previous gold-blind adapter: all passages preferred; maximal whole-passage prefix in original order within 60000 conservative serialized-JSON UTF8-byte token upper bound +128. Keep omitted markers and altered-context status; report altered contexts separately. No label-based source selection.

Model gpt-4o-mini only; temperature0; one repetition; analysis1500, generation512 for A and C, existing query fallback500. Hard480 external attempts including failures; no retries, extra judge or verifier. Expected base456 calls after known no-view skips; retained margin24 for existing query-only fallback. If a budget/time/network blocker stops execution, keep all planned IDs and report every unfinished case. Never lower sample sizes after outcomes.

## Order, failures and persistence

Run priority D1, then D2, then D3; within each case generate A once, postprocess B, then C analysis/realization. Complete paired case before next case. Save each raw outcome immediately to ignored storage and later create safe summaries. P5/no-authorized-view cases use the same canonical deterministic response for all systems, zero calls, preserving hidden/absent indistinguishability. HTTP, malformed JSON, source-role/reference failure, generation-contract failure and missing execution are separate outcomes. Operational CFAF is never counted as a substantive correct refusal. No model repairs or output-driven tuning/reruns.

## Metrics and analysis

D1/D2 primary mode metric: non-operational agreement with original FULL/CFAF gold, denominator all planned cases, including failure/unexecuted cases as incorrect. Also report observed output-mode agreement separately, confusion matrices with operational/error outcomes, class recalls, balanced accuracy, false FULL/failure-to-restrict and unnecessary refusals; do not confuse mode agreement with factual answer correctness. Compare reason class/fulfilment status where original gold exists; marker presence is a diagnostic, not an independent entailment proof. D1 keeps matched pairs; P5 byte-equivalent responses and zero-call behavior are audited. Exact protected-value checks bound policy violations, broader paraphrase disclosure is not automatically certified.

D2 is exposed development fallback, no independent final-evaluation claim. Group bootstrap by original source group; D1 bootstrap by matched pair. Fixed statistical seed20261029, 2000 replicates; include paired B-C/A-C correctness deltas and intervals, exact discordant counts, no significance claim. CIs describe these selected cohorts, not a population guarantee.

D3 original label distributions are scorer-only. Report raw analyzer proposals, validated support and actual inline/rendered public citations separately, relevance precision/recall/F1 and exact correctness-label distributions, operational statuses, source hashes, response length and costs. A/B source selection is measurable only via their actual citations; absent citations do not imply a hidden selection. C's unverified candidate-group trace is not a public verified citation. No requirement to cite all relevant sources; no mode accuracy without new independent adjudication. Provide a blinded independent review rubric with empty judgement fields. No model judge and no invented qualitative labels for eighty cases.

Report every planned/evaluated/incomplete ID, C-vs-B paired outcomes, actual calls/tokens/latency and local overhead, cohort dependence, public-benchmark familiarity and no human entailment audit. Preserve historical40 100% result and later 80–85% mixed development-mode reports as distinct phases, never pooled as final answer accuracy.

## Time and publication

Hard120 minutes from persisted wall/monotonic start; by35 freeze/sample/executable ready; stop new configurations/code100, new requests105, reporting/local commits105–118, hard stop120. Execution may begin earlier once prerequisites are met. No clock reset or promised later work. Prepare only observed metrics in RESULTS_FOR_PAPER.tex and integration notes; no invented bibliography or overwrite of unavailable CF2AF_v5.8. No push/merge/deletion; user performs any future pushes manually. A local annotated tag is a reproducible reference, not GitHub branch protection.
