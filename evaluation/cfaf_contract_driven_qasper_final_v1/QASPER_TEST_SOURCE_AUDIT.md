# Original QASPER v0.3 test source audit

Official [Hugging Face source](https://huggingface.co/datasets/allenai/qasper/tree/fdc9d8214fbab5dd782958601db4d678e6934a54) revision `fdc9d8214fbab5dd782958601db4d678e6934a54`. The pinned loader source declares version 0.3.0 and the exact original test archive URL. It was read, not executed (its default loader would also download train/dev).

Downloaded 2026-10-29T11:47:42.200791+00:00: [original test/evaluator archive](https://qasper-dataset.s3.us-west-2.amazonaws.com/qasper-test-and-evaluator-v0.3.tgz). Bytes: 3865061; SHA-256 `72a52a41193e2838b8074f80ac074b94f956b84886c36a61c58a7df4171bdd72`.
Test member: `qasper-test-v0.3.json`; 18078957 bytes; SHA-256 `6e29ad410e6e39aa1936017fb965b30a20eb2e7751997f55b97c9d281aa884e5`.

Archive members: ['qasper-test-v0.3.json', 'qasper_evaluator.py', 'README-test.md']. Only exact named members are read with extractfile; no archive paths are extracted blindly. The supplied evaluator is retained as original source but is not executed; this study's primary label mapping is explicitly different from official QASPER answer-string scoring.

Actual nested schema: paper keys ['abstract', 'figures_and_tables', 'full_text', 'qas', 'title']; QA keys ['answers', 'nlp_background', 'paper_read', 'question', 'question_id', 'question_writer', 'search_query', 'topic_background']; answer wrappers ['annotation_id', 'answer', 'worker_id']; answer fields ['evidence', 'extractive_spans', 'free_form_answer', 'highlighted_evidence', 'unanswerable', 'yes_no']. The JSON is a paper-ID mapping, not one question per row. Observed test: 416 papers and 1451 questions.

Full text consists of section-name/paragraph-list objects, with original textual figure/table captions. Images/table bodies are not supplied by this text adapter. Source integrity is mechanical integrity of the full distributed record, not a claim that the PDF was completely reconstructed. Original full papers, question/answer wrappers, worker details and archive are ignored under datasets/ and local/.

License: CC BY 4.0, verified in the pinned official dataset card. Attribution: Pradeep Dasigi, Kyle Lo, Iz Beltagy, Arman Cohan, Noah A. Smith and Matt Gardner (2021), A Dataset of Information-Seeking Questions and Answers Anchored in Research Papers. [Original publication](https://aclanthology.org/2021.naacl-main.365/). The downloaded loader source is not incorporated as experimental code.

Mapping document was written before test download/eligibility inspection. FULL requires valid unanimous answerable annotations, no explicit Boolean disagreement and fully representable original text evidence for every annotation. Every FLOAT SELECTED dependency, empty answerable evidence or unmatched text is conservatively UNKNOWN. Caption availability does not prove image/table content. No pilot-specific semantic exclusion is used.

Disjoint derived classes: {'CFAF': 79, 'FULL': 854, 'UNKNOWN': 518}. Tier counts: {'M': {'CFAF': 76, 'FULL': 834}, 'S': {'CFAF': 3, 'FULL': 20}}. Distinct-paper counts: {'ALL': {'CFAF': 62, 'FULL': 361}, 'M': {'CFAF': 59, 'FULL': 357}, 'S': {'CFAF': 3, 'FULL': 14}}. Unknown reasons may overlap: {'CONTRADICTORY_BOOLEAN_ANSWERS': 43, 'MIXED_UNANSWERABLE_FLAGS': 164, 'NO_ORIGINAL_TEXT_EVIDENCE': 30, 'ORIGINAL_TEXT_EVIDENCE_UNREPRESENTED': 76, 'SOURCE_INTEGRITY_INVALID': 4, 'UNAVAILABLE_NONTEXTUAL_EVIDENCE': 212}. Original nontextual marker appears in 253 questions; 1 distributed paper fails source integrity.

Primary sample pool: Tier M; 80 cases, 40 per class, 80 distinct papers. No sample-size reduction. Overlap with both previous exposed dev pilots: 0 questions. Those dev results remain separate development evidence; no validation substitute was sampled.

All original source SHA values are frozen before model calls. The unchanged A/B/C algorithm sources come from the 160-case study; only the original pilot adapter is reused. See HISTORICAL_IMPORT_AUDIT.json, EXPERIMENT_MANIFEST.json, RUN_MANIFEST.json and SOURCE_PROVENANCE.json.
