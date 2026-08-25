# Corpus-scale stress development measurement

## Scope

`evaluation/c_gate.py` preserves the 12 A2 target documents and all 24 A2 gold queries, then adds deterministic, increasingly numerous controlled distractors to reach 50, 250, and 1000 documents. Target facts, pages, document IDs, and questions are unchanged at all sizes. Every size has a versioned manifest, config hash, corpus hash, deterministic IDs, and source hashes.

The runner compares `ROUTING_OFF` with `KEYWORD_ROUTING`. Governance is conceptually fixed to the same permitted synthetic corpus in both modes. It executes an isolated lexical/IDF retrieval proxy and produces no answer text. These are deterministic routing microbenchmark measurements, not actual InfoBank pipeline, answer-quality, hallucination, production-throughput, or provider-quality claims.

Command:

```powershell
$env:AI_PROVIDER='deterministic-mock'
backend_python\.venv_r1a\Scripts\python.exe scripts\run_c_gate.py --output artifacts\c_gate
```

## Measured run (2026-08-19)

| Docs | Mode | Recall@3 | Precision@3 | Found | Mean rank | Mean candidates | Hard-negative inclusion | False exclusions | Gold-document retrieval completeness | Answer/unsupported evaluation | Gold-page retrieval correctness | Gold-document retrieval coverage | Routing P50/P95 ms | Retrieval P50/P95 ms | Total P50/P95 ms |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 50 | ROUTING_OFF | 1.000000 | 0.466667 | 1.000000 | 1.066667 | 50.000000 | 1.000000 | 0 | 1.000000 | NOT_EVALUATED | 0.916667 | 1.000000 | 0.1872 / 0.2437 | 1.7814 / 1.8544 | 1.9745 / 2.1889 |
| 50 | KEYWORD_ROUTING | 1.000000 | 0.466667 | 1.000000 | 1.066667 | 16.666667 | 0.233333 | 0 | 1.000000 | NOT_EVALUATED | 0.916667 | 1.000000 | 0.2008 / 0.2459 | 1.4111 / 1.5254 | 1.6149 / 1.7635 |
| 250 | ROUTING_OFF | 1.000000 | 0.466667 | 1.000000 | 1.066667 | 250.000000 | 1.000000 | 0 | 1.000000 | NOT_EVALUATED | 0.916667 | 1.000000 | 0.8194 / 0.9504 | 10.7191 / 11.4942 | 11.5448 / 12.2928 |
| 250 | KEYWORD_ROUTING | 1.000000 | 0.466667 | 1.000000 | 1.066667 | 83.333333 | 0.233333 | 0 | 1.000000 | NOT_EVALUATED | 0.916667 | 1.000000 | 0.8781 / 1.2689 | 9.1089 / 9.9238 | 10.0408 / 10.8800 |
| 1000 | ROUTING_OFF | 1.000000 | 0.466667 | 1.000000 | 1.066667 | 1000.000000 | 1.000000 | 0 | 1.000000 | NOT_EVALUATED | 0.958333 | 1.000000 | 3.2127 / 3.3947 | 89.9117 / 106.8954 | 93.2292 / 109.9781 |
| 1000 | KEYWORD_ROUTING | 1.000000 | 0.466667 | 1.000000 | 1.066667 | 333.333333 | 0.233333 | 0 | 1.000000 | NOT_EVALUATED | 0.958333 | 1.000000 | 3.4465 / 3.5648 | 83.0572 / 110.9772 | 86.4537 / 114.5022 |

Routing preserved Recall@3 and reduced candidate counts, but Precision@3 and mean target rank did not improve. Gold-page retrieval correctness is below 1.0 because the proxy may select a different page within a correct multi-page target document. No answer was generated, so answer correctness and unsupported-answer rate are `NOT_EVALUATED`; no production answer-quality or hallucination improvement is claimed. Wall-clock latency is machine-specific and will vary between runs.

Raw records and manifests are under ignored `artifacts/c_gate/scale/`. Tests verify the output directory is ignored.
