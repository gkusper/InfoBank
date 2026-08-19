# A-GATE Phase A2 W1 and W2 workflows

## W1 — owned-object onboarding

The runnable W1 trace uses the four synthetic `TV-AURORA-41` documents. It executes deterministic PDF generation, source checksum verification, page-aware extraction, stable page-bounded chunking, deterministic keyword proposal, reviewer keyword merge, one explicit user correction (`owned-object`), association of all sources with one owned object, and page-addressable source-view verification.

The machine trace contains document ID and generated filename, source SHA-256, page/chunk counts, stable chunk IDs, automatic and reviewed keywords, correction delta, object link, and source-view assertions. It contains no absolute path or source content. A run passes only if all sources are page-addressable, chunk IDs are unique, a user correction is recorded, and every document resolves to the same synthetic object.

## W2 — multi-document warranty and support

The runnable W2 trace uses the `KEYWORD_ROUTING` evaluation records for four reviewer-facing cases:

1. answerable multi-document setup and support, requiring both guide and support evidence;
2. insufficient evidence for a fact absent from the corpus;
3. conflicting warranty evidence, producing a constrained answer and escalation rather than silently choosing a duration; and
4. a wrong-object warranty hard negative, refusing to transfer `TV-AURORA-41` terms to `TV-AURORA-99`.

The machine trace records expected/actual output mode, candidate and retrieved document IDs, page/chunk citations for gold sources, controlled-failure gate and reason, conflict detection, wrong-object rejection, safe message, and per-case PASS/FAIL. Insufficient-evidence and conflict results are selected by the shared `controlled_failure.select_rag_output_mode` policy rather than a demonstration-only output shortcut. It uses no external provider or live database.

## Execution result

The A2 local run produced `PASS` for both workflows. These are implementation demonstrations over synthetic development evidence, not end-user usability validation and not final reviewer-dataset results.
