# Real-provider evaluation readiness

Status: `READY_FOR_FULL_CLAUDE_EXPERIMENT_PENDING_EXPLICIT_RUN_COMMAND`

This gate records the 2026-09-04 Anthropic Claude readiness work for the
prepared OpenAI-embedded corpus. A full 630-record Claude experiment was not
run. The only real provider work was the bounded contract smoke, a two-case C3
smoke, and a six-case/30-record readiness pilot. The implementation does not
call a network provider by default and never falls back from a requested
OpenAI or Anthropic run to a mock.

## Fixed configuration

- provider must be explicitly `openai` or `anthropic`;
- OpenAI generation model default: `gpt-4o-mini`;
- Anthropic generation model default: `claude-haiku-4-5-20251001`;
- embedding provider: `openai`;
- embedding model: `text-embedding-3-small`;
- OpenAI temperature: existing call-site value, `0.0` in the actual-pipeline runner;
- Anthropic sampling parameters: omitted by default, with no tools, batch API,
  extended thinking, or structured-response parameter;
- Anthropic default maximum output tokens: `512`, guarded at `<=1024` for real
  smoke and pilot runs;
- Anthropic default maximum automatic retries: `1`;
- generation prompt: `actual-pipeline-answer-v1`;
- routing prompt: `routing-keyword-v1`;
- keyword selection strategy: `infocom-keyword-selector-v2`;
- readiness config: `real-provider-readiness-v2`.

`scripts/run_real_provider_evaluation.py` exposes provider selection,
network approval, cost/request/output/retry guards, `--prepared-manifest`,
`--query-only`, `--dry-run`, `--repetitions`, `--case-ids-file`,
selection-plan generation, `--confirm-readiness-pilot`, and
`--confirm-full-experiment`. An actual OpenAI or Anthropic execution requires
both the provider selection and network-approval flag. Anthropic execution also
requires `EMBEDDING_PROVIDER=openai` semantics and a compatible `OPENAI_API_KEY`
for query embeddings.

## Prepared corpus

The source of truth is
`artifacts/anthropic_provider_readiness/prepared_corpus_openai_20260904/prepare_manifest.json`.
The manifest SHA-256 is
`36880f2500b6a8bc2e38c567994aac557ac75e5cc7c53bd07e8daf47f0c30629`; the
prepared corpus id is `dc7ecb671626dec1`. It points at database
`infobank_eval_claude_prepare_20260904`, Chroma collection
`actual_c50133cf5fe652c9`, OpenAI `text-embedding-3-small` embeddings with
1536 dimensions, 41 documents, 245 chunks/vectors, 253 permission rows, and 41
stored source PDFs. Runtime Chroma/source-storage files are intentionally
ignored by Git; the small manifest is the durable local evidence pointer.

## Query-only execution

Prepared-corpus query-only mode is implemented as
`prepared_corpus_query_only`. It validates the manifest, requires the protected
prepared database name, copies Chroma/source storage into disposable runtime
workspaces, clones MySQL tables into disposable evaluation databases, and wraps
document parsing/chunking/source-storage/Chroma mutation APIs with fail-closed
guards. The prepared DB, source store, and Chroma collection are never used as
write targets for query-time runs.

## Network-free preflight

The prepared query-only dry run used all S1-S6 modes for three repetitions and
made no provider calls. It reported:

- `network_called=false` and `api_key_read=false`;
- `prepared_corpus_mode_available=true`;
- `document_embeddings_reused_without_provider_calls=true`;
- `planned_records=630`;
- `expected_openai_query_embedding_calls=630`;
- `expected_openai_document_embedding_calls=0`;
- `expected_claude_keyword_selection_calls=378`;
- `expected_claude_generation_calls=630`;
- estimated Anthropic cost USD `4.447296`, USD `5.55912` with 25 percent
  margin, within the USD `6.0` cap.

## Real provider evidence

`artifacts/anthropic_provider_readiness/contract_smoke_20260904.json` records
four Claude contract calls: connectivity, system/user role mapping, strict JSON
for the P1 contract, and governed keyword selection. All passed, with request
ids and provider-reported token usage recorded. Keyword-selection latency was
not available in that smoke artifact; answer generation latency is recorded in
the normal provider usage path and stage-timing sidecar.

`artifacts/anthropic_provider_readiness/two_case_smoke_selection_plan_20260904.json`
selects `S1-Q6` and `S3-Q2`. The C3 smoke ran two records and passed with no
technical failures, one generation call, one keyword-selection call, two query
embeddings, and zero document parse/chunk/embed/index operations.

`artifacts/anthropic_provider_readiness/six_case_readiness_selection_plan_20260904.json`
selects `S1-Q6`, `S3-Q2`, `S4B-Q7`, `S1-Q4`, `S4B-Q6`, and `S6-Q4`. The
readiness pilot ran all five modes once, for 30 records, and passed with no
runtime errors or technical failures. Its operation counters were:

- document PDF parse: `0`;
- document chunking: `0`;
- document keyword extraction: `0`;
- document embedding: `0`;
- Chroma add/upsert: `0`;
- corpus seed: `0`;
- query embedding: `30`;
- keyword selection: `14`;
- generation: `21`.

Provider usage for the 30-record pilot was 37,625 input tokens, 4,826 output
tokens, 42,451 total tokens, zero generation retries, and an estimated local
Claude cost of USD `0.061755` from recorded tokens. The payload-boundary check
passed: C2/C3 had zero restricted-text leaks, prohibited-document-id exposures,
and prohibited text-fragment exposures. Expected P1/baseline exposures were
reported separately and did not count as guarded payload-boundary failures.

## Prepared-base integrity

The prepared base stayed stable before and after the readiness pilot:
documents `41 -> 41`, chunks `245 -> 245`, permissions `253 -> 253`, policy
rules `0 -> 0`, audit logs `0 -> 0`, audit links `0 -> 0`, Chroma count
`245 -> 245`, source fingerprint
`0767ea22c80bfc84bfd11e67bbfdd6f9ec93adc3905a1f590aaa8e9cb6c3ba4f`
unchanged, and Chroma fingerprint
`c9e5eda708dcf9d8e200821180b28584c948b14e25f958979ad9b28a7e3a5501`
unchanged. Disposable database clones were dropped after each group. Some
runtime workspace directories were retained on Windows because Chroma held file
locks during cleanup; they are under ignored `evaluation/results/**` paths and
are not part of the committed evidence.

## Full-run projection

`artifacts/anthropic_provider_readiness/full_experiment_projection_from_pilot_20260904.json`
projects the 30-record pilot to the 630-record experiment with a factor of 21:
294 keyword selections, 441 generations, 189 skipped generations, 630 query
embeddings, zero document embeddings, 735 actual-basis provider operations, and
819 guard-basis provider operations. The recorded-token projection is 790,125
input tokens and 101,346 output tokens, for USD `1.296855`, or USD
`1.62106875` with 25 percent margin.

## Command shape

The next full Claude run should use the prepared query-only path, not the
legacy seeded path:

```powershell
backend_python\.venv_r1a\Scripts\python.exe scripts\run_real_provider_evaluation.py `
  --prepared-manifest artifacts\anthropic_provider_readiness\prepared_corpus_openai_20260904\prepare_manifest.json `
  --query-only --provider anthropic --allow-network-provider `
  --generation-model claude-haiku-4-5-20251001 `
  --embedding-provider openai --embedding-model text-embedding-3-small `
  --modes C0_VECTOR_ONLY C1_VECTOR_ROUTING P1_PROMPT_ONLY_GOVERNANCE C2_PERMISSION_FILTERED C3_FULL_ROLE_AWARE `
  --repetitions 3 --confirm-readiness-pilot --confirm-full-experiment `
  --max-provider-request-attempts <approved-full-run-limit> `
  --max-provider-output-tokens 1024 --max-provider-retries 1 `
  --max-anthropic-estimated-cost 6.0 `
  --output <ignored-output> --cache-dir <ignored-cache>
```

This document is readiness evidence only. It is not an instruction to run the
full experiment without explicit human approval.

`READY_FOR_FULL_CLAUDE_EXPERIMENT`
