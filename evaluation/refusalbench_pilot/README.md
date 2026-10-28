# RefusalBench-NQ first-ten integration pilot

This directory contains a completed exploratory experiment and its evidence.
Read `REPORT.md` for results and limitations. This is a conservative UNKNOWN-role
adapter to the existing CFAF pipeline, not a new semantic refusal algorithm.

## Reproduce

Start from InfoBank commit `5f377de38312fb39c088551f9c74f8b6d4bd5080` on a separate
experimental branch. Copy this directory into `evaluation/refusalbench_pilot/`.
Use Python 3.12 and install `requirements.lock.txt` into an isolated environment.
The existing OpenAI provider uses the Python standard library; no OpenAI SDK is
required. Set `OPENAI_API_KEY` in the environment without putting it in files.

Run each command in a separate process from the repository root:

```powershell
python evaluation/refusalbench_pilot/run_experiment.py prepare --revision b3684f805563e6ce465e7e9b055b840a48f519c2 --output-dir work/refusalbench-rerun
python evaluation/refusalbench_pilot/run_experiment.py audit --output-dir work/refusalbench-rerun
python -m pytest evaluation/refusalbench_pilot/test_refusalbench.py -q -p no:cacheprovider --basetemp work/pytest-refusalbench
python evaluation/refusalbench_pilot/run_experiment.py generate --output-dir work/refusalbench-rerun
python evaluation/refusalbench_pilot/run_experiment.py score --output-dir work/refusalbench-rerun
```

The selected dataset must have exactly the original first 10 records, in order.
No filtering, shuffling, hand correction, chunking or substitute retrieval is
performed. `prepare` and `generate` refuse to overwrite their existing artifacts.
Never rerun generation in this delivered directory. A new directory is a NEW
experiment with its own API usage, not a retry of this one. Temperature 0 does
not guarantee identical future outputs; provider metadata is recorded.

On Windows, use short cache paths inside a writable workspace if Hugging Face
fails with WinError 206 (long file names). Set `HF_HOME` and `HF_DATASETS_CACHE`
before `prepare`. If sandbox temporary directories are unavailable, set `TEMP`
and `TMP` to a writable `work/tmp` directory. The actual run used Python 3.12.14;
the bundled interpreter was used because the default Windows Python alias did
not run. Package installation used a workspace virtual environment.

## Leakage boundary and unchanged systems

- `cases.jsonl` preserves the original selected records for provenance and
  scoring. It contains answer-key fields. NEVER supply it to the worker/model.
- `runtime_inputs.jsonl` contains exactly `perturbed_query` and
  `perturbed_context`. Extra fields are rejected. Original record IDs encode
  perturbation metadata, so only opaque runtime indices are used inside systems.
- All three existing adapters are called directly, unchanged. Each receives the
  same query and the same complete context. The CFAF pipeline itself receives
  the query; its existing contract-only realization prompt omits the query and
  carries the original context in permitted evidence views. This is documented
  as an existing integration limitation, not silently fixed here.
- `adapter.py` supplies generic QA configuration, full permission to the public
  supplied passage, UNKNOWN evidence role, NONE relation, and the existing
  CURRENT state default. It supplies neither `gold_answer` nor `runtime_answer`.
- The evidence role is unavailable because the fixture pipeline cannot infer
  semantic support from arbitrary natural language. The unchanged gate chooses
  CFAF. This is not evidence of ambiguity recognition or selective answering.
- Model calls use the existing prompts and provider: `gpt-4o-mini`, temperature
  0, 160 maximum output tokens, one repetition. There are no embeddings,
  classifier calls, retries, additional judges or model-based grading calls.
- `scoring.py` is imported only by the separate `score` command. The same strict
  JSON mode interpretation is used for every system. CFAF adapter repairs do not
  determine primary classification. Review mode/prose consistency separately.

This is application-level data separation, not an OS filesystem security
sandbox. The evaluated components and API prompts receive only projected input
and fixed adapter configuration; files are not physically inaccessible to all
Python code. The exact outbound payloads are included for audit.

## Artifacts and measurements

`dataset_provenance.json` pins dataset/repository revisions, original IDs, input
hashes and original source hashes. `original_tracked_sha256.json` audits every
pre-existing tracked file, including frozen evaluations. `prerun_protocol.json`
freezes Python source hashes and the interpretation procedure before API use.

`api_requests.jsonl` logs exact model payloads without authentication headers.
`api_events.jsonl` logs response metadata, measured latency and reported tokens.
`generation_results.jsonl` is the raw live worker output. `results.jsonl` adds
post-generation scoring and any response reviews. `generation_manifest.json`
contains environment, settings, counters, versions and execution times.

`deterministic_audit.jsonl` is a SEPARATE local pipeline audit: its zero actual
API calls and fixture counters must not be represented as real-model results.
`test_results.xml` contains offline tests; their synthetic provider responses
are not benchmark responses.

`summary.json` counts missing/invalid predictions separately and reports their
coverage. Token counts come from successful API responses, not word counts.
End-to-end latency is measured per system/case with `perf_counter`; no statistical
inference, significance test, cost estimate or extrapolation is performed.

## Post-generation response review

`response_reviews.jsonl`, if present, is a manual review by the report-authoring
assistant, not a blinded independent human annotation or an additional API
judge. It records context evidence, whether the complete response is supported,
mode/text consistency and case-specific concerns. References to real-world
truth are outside the measured scope: altered benchmark context is authoritative
for this pilot. Generic refusal text can be non-specific and unsupported as a
complete explanation even when its binary mode matches the benchmark label.

To reproduce reviewed summaries offline, retain `response_reviews.jsonl` with
`cases.jsonl`, `generation_results.jsonl`, provenance and protocol files and run
`score`. For a NEW live rerun, create NEW reviews after generation; do not copy
these reviews onto different generated responses. `REPORT.md` describes each
case and distinguishes literal context support, resolving the user's question,
and agreement with the benchmark's original behavior label.
