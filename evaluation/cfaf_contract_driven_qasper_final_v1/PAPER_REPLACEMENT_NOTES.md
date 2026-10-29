# Integration notes for the next CF2AF manuscript revision

Verified source: `C:\Users\EKKE\Downloads\CF2AF_v5.9.tex`, SHA-256 `8f4c1387d41d43e62c3d3e81cd1507036ab4edfd60d19bc563910ed28025dee3`. This task does not modify it. Line anchors below refer to this exact source, not an arbitrary future revision.

1. Replace original lines 478–609 (the complete Bounded Three-Dataset Comparative Study section, ending before Discussion at 610) with RESULTS_FOR_PAPER_QASPER.tex. The existing Dataset1/Dataset2 results subsection, including its table and numerical discussion, is copied verbatim after newline normalization; its hash is in PAPER_SOURCE_AUDIT.json.
2. Original registry line 488 and scope line 491 now identify Dataset3 as QASPER. Archive old GaRAGe as Archived Dataset3-v1 – GaRAGe Grounding Study; do not rename historical manifests.
3. Original methods lines 495–506 now describe original QASPER TEST provenance, preregistered strict annotation mapping, 40+40 Tier M paper-first sampling, pilot FTS5 context and paper-cluster intervals. Do not retain the claim that Dataset3 lacks binary gold; it now has explicitly derived labels, not guaranteed truth.
4. Original Dataset3 subsection/tables at 539–578 are replaced by measured QASPER mode/evidence/operational results. Old GaRAGe source-relevance percentages remain only in the archive, not in QASPER results.
5. Original cost table/paragraph at 579–601 must distinguish retained historical 221 calls from new QASPER calls. The revised total spans separate runs; it is not the number of calls issued by this task.
6. Replace original limitations at 603–607 with the fragment limitations: exposed D1/D2 versus new test cohort, deterministic but fallible annotation mapping, Tier M-only selection, textual eligibility, retrieval loss, public benchmark familiarity and absent independent adjudication. No new one-call/component claim is supported.

Additional exact textual updates outside the replaced section are necessary to avoid contradictions:

- Abstract line 85: replace the GaRAGe-specific final sentences with: A new 80-question QASPER test cohort, balanced under preregistered original-annotation labels and using multiple-annotator consensus, gave CFAF 67.50% mode agreement versus 78.75% for guarded RAG; 8 CFAF outputs were operational failures. The new QASPER evaluation used 241 model attempts. Dataset1/2 results remain imported exposed-development evidence. This strengthens auditable answerability measurement without establishing general factual-answer superiority or independently verified entailment.
- Discussion line 627: retain the unchanged D1/D2 comparison, replace the GaRAGe-only statement with the QASPER result above and its paired C-minus-B difference -11.25 percentage points (95% paper-cluster interval -21.25 to -1.25). Explain that label agreement and answer completeness differ.
- Efficiency line 645: retain original synthetic latency figures as historical; replace the old 462-call/160-case sentence with retained D1/D2 221 calls plus new QASPER 241 attempts, 462 across the revised presentation. Do not call the new task a rerun of all 160 cases.
- Conclusion line 655: retain exact D1/D2 values; replace the GaRAGe claims with measured QASPER mode/call/error results, identify Tier M and strict textual selection, and preserve the no-general-superiority/no-independent-entailment limitation.

The fragment introduces tab:qasper-test-modes and retains the existing three-dataset development table and cost labels. Remove old garage-mode-distributions/garage-grounding references when integrating; do not delete their archived study artifacts. Add an appropriate bibliography reference to Dasigi et al. (2021), A Dataset of Information-Seeking Questions and Answers Anchored in Research Papers, NAACL, pp. 4599–4610, DOI 10.18653/v1/2021.naacl-main.365, using the manuscript’s own citation conventions.

No current manuscript source, bibliography, PDF or historical report is overwritten. Integration/review belongs to the next manuscript revision.
