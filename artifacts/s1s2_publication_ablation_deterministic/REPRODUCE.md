# Reproduce S1/S2 Frozen Deterministic C0-C3 Ablation

Package SHA-256: `83a9bb2394946b378af4efe2445be1e6e7095a60f5c14f6206ea1405f275bcd1`

Code-state tracked diff SHA-256: `dc290b7d83dad8f730000011e4506069c22ab08e220a3029416e2ef941bf96eb`

Provider: `deterministic-mock`

Run order: C0, C1, C2, C3.

Use the frozen package inputs under `artifacts/s1s2_freeze/S1_S2_JOURNAL_BENCHMARK_V2/actual_pipeline_inputs/`. Use fresh MariaDB databases named `infobank_eval_s1s2_frozen_<config>_20260825_pubdet`, fresh Chroma directories, and fresh source-storage directories. Do not run a network provider.

This run generated one canonical measured run per configuration and did not perform tuning, reruns for selection, code changes, gold changes, scorer changes, or benchmark changes.
