# ComponentCFAF v1.1 (experimental)

The targeted repair is implemented and tested. The combined compact configuration reduces measured token and latency cost, but native mode accuracy regresses. Keep it experimental. See [the detailed paired report](results/v1_1/REPORT.md), [component comparison](results/v1_1/COMPONENT_COMPARISON.md), [schema audit](results/v1_1/SCHEMA_SIMPLIFICATION.md) and the [30-case aggregate outcomes](results/v1_1/paired_results.jsonl).

Four public contract responsibilities and eight logical stages remain. The host supplies authenticated policy, source views and request context. Ordinary completion attempts at most one gpt-4o-mini request; protected no-view and complete trusted structured paths use zero. Deterministic local gate/rendering follows the untrusted proposal. Mechanically valid citations do not independently verify entailment or request completeness.

## Install and run offline

Tested Windows environment: Python 3.12.14, Pydantic 2.12.3, OpenAI SDK 1.59.9, httpx 0.28.1. Third-party versions are unchanged from v1; own package is 0.1.1. From the repository root, use a dedicated Python 3.12 environment. The existing task interpreter is:

```powershell
$componentPython = 'C:\Users\EKKE\Documents\Codex\2026-10-28\files-pasted-by-the-user-codex\work\component-cfaf-v1\venv\Scripts\python.exe'
& $componentPython -m pip install -r 'components/cfaf/requirements.lock'
& $componentPython -m pip install --no-deps --no-build-isolation -e 'components/cfaf'
& $componentPython 'components/cfaf/examples/v1_1_demo.py'
& $componentPython -m pytest 'components/cfaf/tests' -q
```

Initial installation needs network access. A new environment must already have the build dependencies needed by --no-build-isolation (setuptools); the task's pinned environment does. Keep the legacy backend environment separate. On restricted Windows hosts, a task-local TEMP/TMP directory may be needed before venv/ensurepip.

The demo uses fictional data only, requires no API key, database, UI or NLP/NLI model, and makes zero external calls. It demonstrates five paths:

1. Natural-language two-field metadata FULL, zero calls.
2. Permitted typed SUM aggregate FULL, zero calls.
3. Incomplete metadata request CFAF, zero calls.
4. Protected no-view P5 CFAF, zero calls.
5. Ordinary content FULL, exactly one mocked SDK transport request, mechanically valid quote citation.

Demo output order is metadata, incomplete, aggregate, P5, ordinary. The final path demonstrates the real SDK interface with mock transport, not live accuracy. The older fictional `examples/offline_demo.py` remains available; original v1 tests are unchanged. Current component tests: 86 pass (54 original plus 32 new). Isolated historical results and explicit exclusions/pre-existing failure are in results/v1_1/regression_audit.json.

## Application integration

Construct `Pipeline(governance, provider, ...)` with authenticated `LegacyGovernance` resolver/current callback, `Authority`, `RawSource` and query. The structured resolver is a replaceable Protocol dependency. Private target aliases/catalogue metadata bind natural-language metadata; the typed aggregate contract supplies metric, unit, authorized rows/contributors, population, threshold and period. Details: [structured resolver specification](results/v1_1/STRUCTURED_REQUEST_RESOLVER.md).

For the measured experimental C2 configuration explicitly supply `component_cfaf.compact.CompactSDKProvider`. It uses strict CompactProposal, exact quotations, cap1536, temperature0, no retries or second judge. `SDKProvider` remains available for compatibility with the larger wire schema/cap2048; accuracy of that provider combined with the current new resolver/gate is an untested hybrid. Fresh measured C1 uses the immutable completed-v1 tag, not current source with the old provider.

SDKProvider/CompactSDKProvider read OPENAI_API_KEY from the environment; never place keys in source/reports. A new charged query needs a new request ID. `result.response` is public and `result.private_trace` is private. No-view/complete trusted requests should not construct a semantic shortcut from untrusted model output. The memory quota, callback authority and catalogue interfaces need production service integration.

The literal `metadata[field]` / `aggregate[operation]` compatibility paths retain v1's upstream authorized-snapshot trust. The new natural-language typed aggregate route independently checks rows/threshold/scope. Permitted prose aggregates remain ordinary model-attributed evidence, never trusted numeric operations. Exact quotes establish reference integrity only; model-declared completeness and semantic support remain fallible.

## Completed experiments and reproducibility

Completed v1: `ca2e3e111c63fbd67ff8965e5b05f3530a85c8a0`. Annotated local freeze tag: `component-cfaf-v1-freeze-20261029T170700Z`. Its preserved [v1 report](REPORT.md), source, prompts, schema, original tests and results belong to that tree. Do not mistake the earlier bfd80bb starting base for completed v1.

The fresh v1.1 comparison uses exactly the same thirty exposed cases: ten InfoBank, ten RefusalBench-NQ and ten original GaRAGe. No QASPER TEST, new sample or protected holdout. Actual attempts: A28, fresh C1 28, C2 27, B zero additional; total83 including one C1 connection error. All results are fresh. One orchestration interruption was resumed without repeating any attempted request; see recovery_audit.json. InfoBank mode accuracy C1 80% to C2 70%; RefusalBench 70% to 50%. Both C arms have three GaRAGe operational fallbacks and seven FULL outputs, without fabricated binary gold.

These exact study commands were used (audit record, **do not rerun the closed live study**):

```powershell
& $componentPython 'components/cfaf/tools/v1_1/schema_preflight.py'
& $componentPython 'components/cfaf/tools/v1_1/regression.py'
& $componentPython 'components/cfaf/tools/v1_1/freeze.py'
& $componentPython 'components/cfaf/tools/v1_1/run.py'
# Only after the documented interruption, on the original state/counter:
& $componentPython 'components/cfaf/tools/v1_1/resume.py'
```

The closed task state and immutable manifest block rematerialization or repeated inference. Source/context/prompt/schema hashes, reported token usage, primary and both-reported-pair latency, validation costs and native confusions are in results/v1_1/. Raw questions, gold, traffic and full case report stay ignored in results/v1_1/local/ and original results/local/. Public reporting tools do no inference, but require that private task state and clock; they are the record of this bounded run, not a generic portable benchmark CLI. Public checksums and the adjacent completion receipt identify delivered files and final commit. A future live study requires separate authorization and a new manifest/result folder.

## Manual publication

Local branch is exactly `ComponentBasaedCFAF`. No automatic push or merge. After review, the user can run from this worktree:

```powershell
git push -u origin ComponentBasaedCFAF
# Optional: publish the annotated baseline freeze tag too.
git push origin component-cfaf-v1-freeze-20261029T170700Z
```
