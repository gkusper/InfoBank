# A-GATE Phase A2 synthetic development corpus

## Purpose and boundary

The A2 corpus exercises routing, retrieval confounders, evidence sufficiency, conflict, and wrong-object rejection without using personal, project, email, browser-history, health, frozen reviewer, or production data. It is development evidence only and is not the final reviewer dataset v2.

The tracked corpus specification lives in `evaluation/a_gate_phase2.py`. Generated PDFs and run outputs live under ignored `artifacts/a_gate_phase2/` so hashes and result bundles cannot be mistaken for source code or committed reviewer evidence.

## Composition

- 12 deterministic two-page PDF documents.
- Three device families: television, router, and printer.
- Four document types per family: guide/install, warranty, support, and an intentionally conflicting bulletin.
- 24 queries: eight per family.
- Case coverage: answerable, multi-document, no-answer, conflict, and hard-negative/wrong-object.

Every query specifies:

- stable query ID and text;
- object family and object ID;
- case type and expected output mode;
- fixed routing keywords for model-free ablation;
- gold document IDs and gold pages when an answer is supported;
- hard-negative document IDs;
- reference fact or explicit refusal reason.

All names, serial families, addresses, warranties, support facts, receipts, and conflicts are fictional. `192.0.2.1` is used as documentation-only address space. The generator sets fixed PDF metadata and emits a manifest with per-file SHA-256, byte size, page count, object fields, corpus/query counts, schema version, and evaluation configuration hash.

## Reproduction

Run from the repository root with the project quality-gate Python interpreter:

```powershell
backend_python/.venv_r1a/Scripts/python.exe scripts/run_a_gate_phase2.py --output artifacts/a_gate_phase2
```

The runner emits:

- `manifest.json` and `queries.json`;
- the 12 PDFs under `corpus/`;
- `semantic_cooccurrence_graph.json`;
- paired raw records in `raw_results.jsonl`;
- `summary.json`, `summary.csv`, and `summary.md`;
- `w1_owned_object_trace.json`;
- `w2_warranty_support_trace.json`.

Only measured latency fields are nondeterministic. Corpus definitions, PDF payloads, hashes, graph structure, query specifications, routing decisions, retrieval tie-breaking, workflow structure, and configuration hashes are deterministic.
