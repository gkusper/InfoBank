# Revised three-dataset comparative presentation

Dataset3 is now QASPER original v0.3 TEST. Dataset1 and Dataset2 are exact imports of exposed-development results; they were not rerun. The old 160-case study is preserved as **Archived Dataset3-v1 – GaRAGe Grounding Study**, with original files, names and results unchanged.

| Cohort | Gold FULL/CFAF | Status | A accuracy | B accuracy | C accuracy | C balanced accuracy | C−B paired points (95% interval) |
|---|---:|---|---:|---:|---:|---:|---|
| Dataset1 InfoBank, N=40 | 16/24 | Retained exposed development | 80.00% | 80.00% | 100.00% | 100.00% | +20.00 (+10.00, +30.00) |
| Dataset2 RefusalBench-NQ, N=40 | 14/26 | Retained exposed development fallback | 75.00% | 75.00% | 72.50% | 68.96% | −2.50 (−13.16, +7.89) |
| Dataset3 QASPER TEST, N=80 | 40/40 | New Tier M text-eligible test subset | 78.75% | 78.75% | 67.50% | 67.50% | −11.25 (−21.25, −1.25) |

Historical intervals retain their original matched-pair/source-group procedures; new QASPER uses 2000 jointly resampled paper clusters, seed 20261029. Accuracy means non-operational mode agreement with the applicable labels, not independently adjudicated factual correctness. There is no pooled accuracy. Dataset1's 100% C mode accuracy coexists with 72.5% reason agreement and 80% fulfilment agreement. Dataset2 remains development evidence, with no new reserved content opened.

The frozen A/B/C source and prompts are unchanged from `bfd80bbfe2ccbb251da46bdc22b791dad5b9341f`. The original pilot paper adapter is unchanged; it supplies a whole paper or gold-blind FTS5/BM25 subset consistently to A/B/C. QASPER paper granularity and context bounds differ from old GaRAGe. The later one-call/component implementation is not evaluated. Thus identical inference algorithms do not make all source conditions identical or all cohorts newly independent.

QASPER mapping yields FULL 854, CFAF 79, UNKNOWN 518 of 1451 questions in 416 papers. Tier M offers 834 FULL and 76 CFAF; all 80 sampled cases are M and from distinct papers, with no overlap with twenty earlier validation-pilot papers. Tier S was not sampled and has no performance estimate. All 80 cases completed; no resampling/relabeling followed outputs.

C has eight operational failures (three invalid span references, five missing required CFAF realizations), versus zero A/B. They receive no primary correctness credit. C-only mode wins number five, B-only wins fourteen. Of forty FULL cases, one loses some human union evidence in retrieval, but none loses every complete annotation evidence set. Seventy-six inputs are full papers and four retrieved subsets. C's internal passage-overlap macro P/R/F1 is 45.32/52.21/41.24%; this is not entailment or answer correctness. Agent semantic review of all eighty cases is explicitly non-independent.

| Resource cohort | Calls | Input tokens | Output tokens |
|---|---:|---:|---:|
| Retained Dataset1 | 96 | 112672 | 12811 |
| Retained Dataset2 | 125 | 156620 | 17348 |
| New QASPER only | 241 | 2302206 | 38873 |
| Revised presentation across dates | 462 | 2571498 | 69032 |

New QASPER uses 787.311 summed provider seconds plus 42.291 seconds of measured non-transport case processing. Dataset1/2 use zero new calls. No GaRAGe metrics or usage are counted as the replacement Dataset3. No stronger model, retry, embedding, external judge or second semantic verifier was used.

The replacement strengthens an auditable answerability test, while producing a negative result for frozen CFAF on this cohort. Derived consensus can be wrong; strict filtering, balancing, retrieval, pretrained-model benchmark familiarity and absent independent adjudication limit interpretation. See REPORT.md for fourteen explicit research answers, confusions, qualitative examples and operational details. RESULTS_FOR_PAPER_QASPER.tex and PAPER_REPLACEMENT_NOTES.md prepare the next manuscript revision without editing CF2AF_v5.9.tex.
