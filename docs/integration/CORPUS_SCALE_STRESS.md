# Corpus-scale stress development measurement

## Scope

`evaluation/c_gate.py` preserves the 12 A2 target documents and all 24 A2 gold queries, then adds deterministic, increasingly numerous controlled distractors to reach 50, 250, and 1000 documents. Target facts, pages, document IDs, and questions are unchanged at all sizes. Every size has a versioned manifest, config hash, corpus hash, deterministic IDs, and source hashes.

The runner compares `ROUTING_OFF` with `KEYWORD_ROUTING`. Governance is conceptually fixed to the same permitted synthetic corpus in both modes. Generation is a deterministic mock. These are development measurements, not production throughput or external-model-quality claims.

Command:

```powershell
$env:AI_PROVIDER='deterministic-mock'
backend_python\.venv_r1a\Scripts\python.exe scripts\run_c_gate.py --output artifacts\c_gate
```

## Measured run (2026-08-19)

| Docs | Mode | Recall@3 | Precision@3 | Found | Mean rank | Mean candidates | Hard-negative inclusion | False exclusions | Answer correct | Unsupported | Citation correct | Citation coverage | Routing P50/P95 ms | Retrieval P50/P95 ms | Total P50/P95 ms |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 50 | ROUTING_OFF | 1.000000 | 0.466667 | 1.000000 | 1.066667 | 50.000000 | 1.000000 | 0 | 1.000000 | 0.000000 | 0.916667 | 1.000000 | 0.1872 / 0.2437 | 1.7814 / 1.8544 | 1.9745 / 2.1889 |
| 50 | KEYWORD_ROUTING | 1.000000 | 0.466667 | 1.000000 | 1.066667 | 16.666667 | 0.233333 | 0 | 1.000000 | 0.000000 | 0.916667 | 1.000000 | 0.2008 / 0.2459 | 1.4111 / 1.5254 | 1.6149 / 1.7635 |
| 250 | ROUTING_OFF | 1.000000 | 0.466667 | 1.000000 | 1.066667 | 250.000000 | 1.000000 | 0 | 1.000000 | 0.000000 | 0.916667 | 1.000000 | 0.8194 / 0.9504 | 10.7191 / 11.4942 | 11.5448 / 12.2928 |
| 250 | KEYWORD_ROUTING | 1.000000 | 0.466667 | 1.000000 | 1.066667 | 83.333333 | 0.233333 | 0 | 1.000000 | 0.000000 | 0.916667 | 1.000000 | 0.8781 / 1.2689 | 9.1089 / 9.9238 | 10.0408 / 10.8800 |
| 1000 | ROUTING_OFF | 1.000000 | 0.466667 | 1.000000 | 1.066667 | 1000.000000 | 1.000000 | 0 | 1.000000 | 0.000000 | 0.958333 | 1.000000 | 3.2127 / 3.3947 | 89.9117 / 106.8954 | 93.2292 / 109.9781 |
| 1000 | KEYWORD_ROUTING | 1.000000 | 0.466667 | 1.000000 | 1.066667 | 333.333333 | 0.233333 | 0 | 1.000000 | 0.000000 | 0.958333 | 1.000000 | 3.4465 / 3.5648 | 83.0572 / 110.9772 | 86.4537 / 114.5022 |

The citation-correctness value is below 1.0 because the lexical retriever may select a different page within a correct multi-page target document; citation coverage measures target-document coverage separately. Wall-clock latency is machine-specific and will vary between runs.

Raw records and manifests are under ignored `artifacts/c_gate/scale/`. Tests verify the output directory is ignored.
