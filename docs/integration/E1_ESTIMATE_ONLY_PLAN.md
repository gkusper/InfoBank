# E1 estimate-only plan

Status: `DO_NOT_RUN_FINAL_E1_YET`

This is a network-free planning artifact. It is not a dataset freeze, provider
approval, provider result, final E1, or publication result. The estimator does
not read an API key, initialize a network adapter, or use internet pricing.

## Locally established scope

The estimator reads the current ignored pre-freeze candidate instead of using
hard-coded counts. The current manifest declares 90 total query candidates;
45 candidate-holdout queries across three packages are selected. Their source
manifest contains 15 candidate-holdout PDFs and 30 pages. Source hashes and
observed PDF page counts are verified before an estimate is produced.

The base modes are the repository's actual evaluation modes:

1. `C0_VECTOR_ONLY`;
2. `C1_VECTOR_ROUTING`;
3. `C2_PERMISSION_FILTERED`;
4. `C3_FULL_ROLE_AWARE`.

The optional scale subset is separate. It reads the local 1000-document C-GATE
manifest, verifies its corpus hash by reconstructing the local deterministic
corpus, and covers its 24 queries in `ROUTING_OFF` and `KEYWORD_ROUTING` (48
cases). It is development-only scale evidence and is never added to base E1
unless `--include-scale-subset` is explicit.

## Current network-free estimates

| Scenario | Queries | Modes | Repeats | Cases | Input tokens | Output tokens | Total tokens | Embedding operations | Generation operations | Cache hits / misses | Provider requests | Retry budget | Artifact estimate | Runtime | Cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| Base | 45 | 4 | 1 | 180 | 180472 | 92160 | 272632 | 181 | 180 | 135 / 406 | 406 | 180 | 1667040 bytes | `UNKNOWN` | `null` |
| Base | 45 | 4 | 2 | 360 | 360944 | 184320 | 545264 | 362 | 360 | 270 / 812 | 812 | 360 | 3334080 bytes | `UNKNOWN` | `null` |
| Base | 45 | 4 | 3 | 540 | 541416 | 276480 | 817896 | 543 | 540 | 405 / 1218 | 1218 | 540 | 5001120 bytes | `UNKNOWN` | `null` |
| Optional scale subset | 24 | 2 | 1 | 48 | 197308 | 24576 | 221884 | 49 | 48 | 24 / 121 | 121 | 48 | 1047792 bytes | `UNKNOWN` | `null` |

Token counts are transparent local upper-bound estimates: Unicode character
count divided by four, at most 4096 context tokens and 512 output tokens per
case. Controlled failures may skip generation. They are not provider-billed
usage. Embedding operations count one corpus batch plus one query call per case;
the input-count field in the machine bundle separately counts embedded pages
and queries. The cache estimate assumes a cold, repeat-scoped cache: repeated
query embeddings across modes hit inside one repeat, while keyword and
generation requests are conservatively treated as misses.

No local pricing configuration or latency assumption was supplied. Therefore
`pricing_status=NO_LOCAL_PRICING_CONFIG`, cost is `null`, and
`provider_runtime_estimate=UNKNOWN`. A local pricing file must contain complete
entries for `gpt-4o-mini` (input/output per million) and
`text-embedding-3-small` (input per million). `--max-estimated-cost` is rejected
unless that complete local configuration is present. An optional local average
latency produces only `LOCAL_LATENCY_ASSUMPTION`, never a measurement claim.

## Cache, resume, failure and sealing rules

The implemented cache identity uses operation namespace, input hash, provider,
model, prompt version and evaluation-config hash. For a future approved
multi-repeat run, each repeat must use a distinct ignored cache root so that a
repeat is an independent provider execution. A cache may resume only the same
run/repeat identity with identical frozen input and configuration hashes.

Current generation has at most one explicit retry after its initial request;
the estimate reports that upper budget. Keyword or embedding failure has no
additional evaluator retry budget and must fail the repeat. The current runner
does not support record-level continuation of a partial raw file. A failed
repeat must remain sealed off from scoring and be restarted under a fresh run
identity; successful provider cache entries may be reused only when the frozen
identity is unchanged.

Every successful repeat must write all query/mode raw records, then seal the raw
JSONL with dataset, query, corpus, config, code, provider/model and raw-file
hashes before the scorer receives gold. Partial or unsealed output is not
scoreable. All planned cases and repeats must be retained. No post-result case,
mode, repeat, retry, or scale-subset cherry-picking is permitted.

## Proposed freeze and run order

1. Resolve MailEx licence/redistribution and complete human gold, annotation,
   second-annotation, agreement/adjudication, citation and no-health review.
2. Apply accepted corrections without tuning against candidate holdout.
3. Rerun deterministic candidate, reconciliation, security, SkipDocker and
   full Docker/API gates.
4. Human-approve exact dataset, QueryInput, GoldAnnotation, scorer,
   controlled-failure config, provider/model, prompts, cache policy and code
   hashes; then create separately authorized immutable freeze records.
5. Approve a local pricing config, maximum cost, run count, optional scale
   inclusion and network-provider execution.
6. Execute base modes in fixed C0, C1, C2, C3 order for each approved repeat.
   Seal each complete raw repeat before any scoring.
7. If separately approved, execute and seal the representative scale subset;
   never merge it into the base denominator.
8. Score only after all approved raw runs are sealed. Preserve every result and
   document failures without selecting favorable repeats.

## Estimate-only commands

Run from the repository root after regenerating/validating the ignored
pre-freeze candidate:

```powershell
$modes = 'C0_VECTOR_ONLY','C1_VECTOR_ROUTING','C2_PERMISSION_FILTERED','C3_FULL_ROLE_AWARE'
backend_python\.venv_r1a\Scripts\python.exe .\scripts\run_real_provider_evaluation.py --estimate-only --repeats 1 --modes $modes --include-scale-subset --output .\artifacts\pre_freeze\e1_estimate_only\e1-r1.json
backend_python\.venv_r1a\Scripts\python.exe .\scripts\run_real_provider_evaluation.py --estimate-only --repeats 2 --modes $modes --output .\artifacts\pre_freeze\e1_estimate_only\e1-r2.json
backend_python\.venv_r1a\Scripts\python.exe .\scripts\run_real_provider_evaluation.py --estimate-only --repeats 3 --modes $modes --output .\artifacts\pre_freeze\e1_estimate_only\e1-r3.json
```

Each command writes JSON plus adjacent CSV. Current JSON SHA-256 values are:

- one repeat with separate scale estimate: `6cb63190b4e93de69b89c51b0e5a6c94bed373d7472ac4b949acc16ad025b338`;
- two repeats: `be5e43187c1a054b9107d731384ede751267f22cba7bee1bf4234cbc2046127c`;
- three repeats: `0dba74c10d00df417945e34ed89dd9fac842ed1dad0aebb76dbd47485a548a47`.

The bundle is ignored under `artifacts/pre_freeze/e1_estimate_only/`.

## Human decisions still required

Gábor or assigned authorities must decide MailEx licence and redistribution,
gold-QA ownership, primary/secondary annotators, IAA metric and threshold,
adjudicator, citation auditors, manual no-health signer, screenshot acceptance,
provider/model, local price evidence, cost cap, repeat count, scale inclusion,
freeze identifiers and final network execution. None is approved by this plan.

`DO_NOT_RUN_FINAL_E1_YET`
