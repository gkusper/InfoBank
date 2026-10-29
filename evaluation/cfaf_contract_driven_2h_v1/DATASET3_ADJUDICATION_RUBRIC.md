# Independent Dataset3 fulfilment and claim adjudication

All fields are PENDING. This packet does not invent a FULL/CFAF or entailment gold label. Recruit an annotator independent of this implementation/model-output review; preserve original GaRAGe source labels separately.

1. Before reading generated responses, inspect the original question, as-of date and supplied authorized passages. Decompose essential requested entities, relations, comparisons, time scope, conditions and required granularity. Record whether a complete supported answer is possible, with source/span evidence and uncertainty. Do not equate relevant or answering-labelled passages with all-requirement completeness; original labels/reference answers are intentionally absent from the blinded packet.
2. Then inspect anonymous response aliases R1/R2/R3 in randomized order. Identify each factual claim and whether the supplied material supports that exact subject/relation/qualifier. Mark SUPPORTED, PARTIAL, UNSUPPORTED or UNVERIFIABLE; record missing essential requirements separately from false claims. A short answer is not automatically incomplete.
3. Judge abstention/clarification appropriateness relative to question/evidence. Neutral operational wording is an execution outcome, not a statement that evidence is absent. Do not reward a technical failure as semantically correct refusal.
4. Check actual public citations, if any, for authorized source, exact span and claim usefulness. A mechanically valid reference or model-declared relation is not entailment proof. Mark absent/unverified citations explicitly.
5. Record uncertainty and disagreements. Prefer two independent annotators and adjudication if feasible. Do not edit original GaRAGe labels; a new contract-specific judgement is a separate annotation layer.

The ignored local packet contains only authorized question/context and masked generated outputs. The separate ignored key maps response aliases to systems. Names are blinded, stylistic clues may still reveal a method. DATASET3_ADJUDICATION_TEMPLATE.csv has blank judgements for all selected responses; no score is derived from unfilled fields.
