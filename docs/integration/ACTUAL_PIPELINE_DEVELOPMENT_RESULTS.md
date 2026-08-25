# Gold-blind actual-pipeline development results

Status: `ACTUAL_PIPELINE_DEVELOPMENT_EVALUATION`

This is a small deterministic synthetic development run, not final E1, not a holdout result, and not a generalization claim. No dataset, scorer, configuration, code, or result was frozen. Human gold QA and the 40-response citation audit remain pending.

## Architecture and sealing

- Runner: `infobank-actual-pipeline-runner-v1`; scorer: `infobank-actual-pipeline-scorer-v1`.
- Provider/model: `deterministic-mock` / `infobank-deterministic-extractive-v1`; no network provider call.
- Runtime: isolated `infobank_eval_actual` MariaDB database, isolated Chroma directories/collections, isolated source-storage directories, deterministic evaluation identities and UUIDs.
- Production modules used: page-aware PDF extraction/chunking, source storage, provider interface, routing, policy engine, relevance roles, controlled failure, aggregate executor, and shared citation construction.
- Query inputs and gold annotations are separate JSONL files. The runner imports no gold loader and accesses no expected class, gold reason, source/page label, or reference answer.
- Raw JSONL is written and SHA-256 sealed before post-run scoring. The seal records raw/config/query/corpus hashes, exact commit, provider/model, timestamp, and run ID. Scorer output references the sealed raw SHA-256.
- Actual wall-clock timings remain in raw records and a timing sidecar. A timing-independent deterministic projection matched across the two complete runs: `5ffbdc2620ef28785f6a9a7bd82bfef7993e4dfdcd9151f814f8e1cab69eccbc`.

## Development calibration

Two C3 configurations ran over all 20 development inputs. The rule required zero safety findings, then maximized permitted-answer accuracy and output-class accuracy, then preferred lower top-k. Selected config: top-k 4, minimum support 0.35, hash `e6d904a383a3ab7b83081637b155bb38ad02cb8100edca61f4dedd199b748ac4`. Candidate holdout, MailEx candidate holdout, and frozen D1-D8 were not read.

## Corrected C0-C3 table

| Mode | Output class accuracy | Reason accuracy | Permitted-answer accuracy | False/unsupported-answer rate | Citation document coverage | Page correctness | Safety findings | Mean wall-clock ms | Provider input/output tokens | Generation skipped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C0 vector only | 0.10 | 0.00 | 0.17 | 1.00 | 0.50 | 0.25 | 4 | 38.51 | 2108 / 299 | 0/20 |
| C1 vector+routing | 0.10 | 0.00 | 0.33 | 1.00 | 0.60 | 0.30 | 6 | 31.59 | 1757 / 298 | 0/20 |
| C2 permission-filtered | 0.70 | 0.70 | 0.50 | 0.14 | 0.50 | 0.83 | 0 | 155.25 | 636 / 136 | 14/20 |
| C3 full role-aware | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 1.00 | 0 | 117.41 | 860 / 80 | 16/20 |

The latency values are measured local wall-clock observations for one run and are not deterministic performance guarantees. Token counts are explicitly labelled deterministic local provider estimates; retries and cost are zero. C0/C1 safety findings arise from intentionally removing governance in an isolated synthetic ablation and do not represent a production route.

## Citation development failure taxonomy and correction

Initial development runs exposed three classes of citation error: correct document with an irrelevant same-document page, citation attached to an insufficient-evidence refusal, and denominator mismatch for aggregate sources that intentionally emit no individual citation. The development-only corrections were query-overlap plus vector-distance page reranking, an authority/conflict secondary signal, role-aware citation selection, suppression of irrelevant citations on no-answer/refusal paths, and separation of page-bearing citation expectations from aggregate provenance. Runtime never receives gold page numbers.

After correction, the 20-case C3 development run measured document coverage, page correctness, support precision, and citation coverage at 1.00. This perfect value is confined to the deterministic generated development fixture. It is not substituted for the pending deterministic preselection and human audit of 40 responses.

## Comparison with deprecated contract simulation

The old D-GATE table remains in `D_GATE_REPORT.md` for provenance only. It built some outputs, retrieval traces, citations, safety counters, and timing/usage values from gold or formulas. The corrected runner instead executes Chroma, MariaDB policy resolution, routing, roles, controlled failure, aggregation, generation, and citations before the scorer opens gold. The two result tables must not be merged.

## Reproducibility and limitations

Two complete C0-C3 runs produced identical timing-independent content hashes. Their full raw hashes were `b14a7f50a18d7f9e6968d8e9f59de481ae43609831b7548c998b98df6d9752b2` and `d67c22467358404f72da9e52d3a9c3b78fa05d975967723dd3a36010fbd1f5c3`; the difference is expected because actual wall-clock timings are retained separately. Both runs had zero runtime errors in C3. Generated output is ignored under `artifacts/actual_pipeline/`; no raw result, database, Chroma file, PDF, or source-storage payload is tracked.

Limitations: 20 synthetic development cases, deterministic embeddings/generation, no concurrency/load claim, no external provider quality claim, no human-validated gold, no human citation audit, no candidate-holdout result, and no final E1.
