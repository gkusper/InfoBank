# ComponentCFAF v1

A small runnable CFAF reference implementation: four application contracts, one untrusted structured proposal, local gating and deterministic claim-linked publication. The normal generative path uses at most one gpt-4o-mini request. No-view and explicit structured paths can use zero. See ARCHITECTURE.md, MAKE_OR_REUSE.md, MIGRATION.md and REPORT.md for the actual implementation and limits.

## Tested environment and commands

Tested on Windows PowerShell with Python 3.12.14, Pydantic 2.12.3 and official OpenAI SDK 1.59.9. The legacy backend environment is separate. In this task, the dedicated interpreter is:

```powershell
$componentPython = 'C:\Users\EKKE\Documents\Codex\2026-10-28\files-pasted-by-the-user-codex\work\component-cfaf-v1\venv\Scripts\python.exe'
```

From the `InfoBank-ComponentBasaedCFAF` worktree, the following installation/demo/test operations were exercised:

```powershell
& $componentPython -m pip install --no-build-isolation -e 'components/cfaf[test]'
& $componentPython -m pip install --no-index -r 'components/cfaf/requirements.lock'
& $componentPython 'components/cfaf/examples/offline_demo.py'
& $componentPython -m pytest 'components/cfaf/tests' -q
```

The lock consistency command above uses already installed packages and no index; initial installation requires network access. For a new checkout, create a dedicated Python 3.12 environment, install requirements.lock, then install this package with `--no-build-isolation -e components/cfaf`. Do not upgrade the legacy environment. On restricted Windows hosts, create a task-local TEMP/TMP directory before venv/ensurepip; the initial default-temp bootstrap failed here and succeeded with isolated temporary storage.

The offline demo uses fictional data and a deterministic synthetic proposal. It makes **zero external calls**; it demonstrates the pipeline, not live-model accuracy. Two concrete retrievers are tested through the same contract/gate. No database server, web UI or optional model is needed.

## Application usage

Construct Pipeline with an authenticated LegacyGovernance resolver/current callback and either a synthetic provider or SDKProvider. The host supplies Authority, RawSource and query. A source's access decision is application authority, never an LLM field. SDKProvider reads OPENAI_API_KEY from the environment; do not place keys in source or reports. `result.response` is public; `result.private_trace` is private. SDK calls are not retried. A new request ID is required for a newly charged query.

The standard answer path returns accepted claim text and explicit provenance labels; a reference-valid citation is not independently verified support. Generic natural-language metadata/aggregate requests remain conservatively restricted in v1; explicit `metadata[field]` and `aggregate[operation]` syntax handles the local structured shortcut. The memory quota and callback resolver require production replacements for durable, authenticated service use.

## Bounded research runs already completed

These exact task-local commands were exercised after frozen preparation:

```powershell
& $componentPython 'components/cfaf/tools/prepare.py'
& $componentPython 'components/cfaf/tools/renderer_ablation.py'
& $componentPython 'components/cfaf/tools/live_smoke.py' --allow-live
& $componentPython 'components/cfaf/tools/score.py'
```

The live command requires explicit --allow-live, OPENAI_API_KEY, a verified local task state and concurrency clearance. `--concurrent-experiment` records NOT_RUN_CONCURRENT_EXPERIMENT and makes no request. The completed result directory refuses rematerialization/repeated inference. **Do not rerun these exposed cases to tune this version.** A future experiment needs a new named result directory, separately authorized closed manifest and new preregistration.

The optional API smoke is real: 30 previously exposed paired cases, 56 actual requests, 28 A and 28 C1; B adds none. It uses no QASPER or protected holdout content. Full raw inputs, gold, requests, responses and the case report remain ignored under results/local/. The public delivery contains aggregate results and integrity metadata.

Freeze hashes are in results/freeze.json, exposure accounting in results/exposure_manifest.json, API totals in api_usage.json, and code/dependency counts in component_manifest.json/code_size_report.json. checksums.sha256 covers the public delivery; the adjacent completion receipt supplies the final commit. The original manuscript and prior worktrees/refs remain unchanged.

## Manual publication

Local branch: `ComponentBasaedCFAF`, deliberately retaining the requested spelling. From this worktree:

```powershell
git push -u origin ComponentBasaedCFAF
```

No automatic push or merge is performed.
