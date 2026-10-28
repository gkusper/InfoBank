# Canonical dataset registry

| Name | Scientific role | Scope and present status | Restrictions in this task |
| --- | --- | --- | --- |
| Dataset1 — InfoBank | Governed fulfilment across P1–P5 | Original 40 synthetic development cases. Planned independent 60 authored cases (20 development, 40 final) are a separate corpus and were not established/used here. | Do not access independent student-authored reserved cases. Historical compatibility tests use existing fixtures. |
| Dataset2 — RefusalBench-NQ | Selective refusal under perturbed requests/context | Original 1600, filtered 1234; prior eligible exposed 130; reserved 30 source groups plus untouched 18 as recorded in prior ledgers. This is RefusalBench-NQ, not RefusalBench-GaRAGe. | No new sampling, qualitative inspection, model execution or exposure-ledger change. |
| Dataset3 — original AmazonScience GaRAGe | Evidence-grounded answering and source attribution | Official original 2366 records and 35,351 passages. Ten uniformly random records exposed in this pilot; 2356 not used for qualitative development. | Preserve original gold. Reserve remaining records. This ten-case development run is not final independent validation. |

Dataset numbering is stable. Dataset3 is not a RefusalBench adaptation. Dataset1 governance labels, Dataset2 selective-refusal gold and Dataset3 passage annotations are different scientific concepts and are not interchangeable binary labels.
