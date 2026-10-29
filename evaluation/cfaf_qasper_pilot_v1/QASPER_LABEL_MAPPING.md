# QASPER gold mapping (declared before model execution)

The source is the original QASPER v0.3 development JSON, not flattened Hugging Face rows. Each paper contains multiple `qas`; each question contains multiple answer wrappers. The original fields are preserved unchanged in ignored local files. The inference adapter imports no annotation mapping module.

An annotation requires a Boolean `unanswerable`. For an answerable annotation exactly one answer representation must be usable: nonempty extractive spans, a nonempty free-form answer, or Boolean `yes_no`. Both `yes_no=true` and `yes_no=false` are usable; `null` means that this answer type was not selected. Non-Boolean yes/no, malformed spans, multiple answer types, or an unanswerable annotation carrying an answer are ambiguous.

A question is FULL only when all its annotations are valid, answerable, and have a usable reference representation. A question is CFAF only when all annotations are valid and unanswerable. Missing, invalid or conflicting annotations yield UNKNOWN. This conservative handling of invalid annotations does not discard disagreement to manufacture consensus. In the actual dev file all 75 UNKNOWN cases are disagreements; no invalid representations were found.

Observed pool: 870 FULL, 60 CFAF, 75 UNKNOWN, 1005 questions across 281 papers. There are 1764 answer annotations. The yes/no field is null in 1556, true in 105, and false in 103 annotations. UNKNOWN cases are excluded only from binary sampling.

Selection uses Python `random.Random(20261029)`, taking five without replacement from the FULL pool sorted by `(paper_id, question_id)`, followed by five from the similarly sorted CFAF pool. There is no rejection or replacement. The resulting sample happens to contain ten distinct papers, satisfying the source-diversity preference without conditioning the random draws. This deliberately balanced sample does not estimate the natural QASPER class distribution.

Stable record SHA-256 hashes canonical sorted-key, ASCII JSON with compact separators of the original paper ID, complete original question object including annotations, and the paper's original document fields excluding all other QAs. Full original data and annotations remain ignored. Selection manifest hashes and original IDs are public metadata, never model inputs.
