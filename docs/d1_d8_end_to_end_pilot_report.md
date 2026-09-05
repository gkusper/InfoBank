# D1-D8 End-to-End Pilot Report

## 1. Executive Summary

A full MariaDB-backed D1-D8 development pilot was completed on branch
`d1-d8-end-to-end-pilot`.

The run used the frozen engineering inputs:

- `evaluation/fixtures/document_rag_v2.yaml`
- `data/benchmarks/evidence_unit_v1/cases.jsonl`
- `data/benchmarks/evidence_unit_v1/gold.jsonl`

The real run produced 53 measured result records: 21 D1-D5 document-RAG records
and 32 D6-D8 EvidenceUnit action-reconstruction records. D6-D8 passed all
post-fix deterministic metrics. D1-D5 role-aware mode conformed on all 7 pilot
cases, while the standard and governance-only baselines exposed expected
limitations. These are development-pilot results after observing baseline
failures, not held-out benchmark results.

## 2. Starting Repository State

- Accepted source branch: `mailex-d1-d8-benchmark`
- Accepted source commit: `324c14d0e647037e0e1699cf90ad59a9e694a186`
- Implementation branch: `d1-d8-end-to-end-pilot`
- Initial accepted branch status: clean after `git pull --ff-only`

## 3. MariaDB and Evaluation Environment

- Operating system: Windows 11, build `10.0.26200`
- Python: `3.12.13`
- Database: `infobank_eval`
- Host and port: `127.0.0.1:3307`
- MariaDB server: `11.4.12-MariaDB-ubu2404`
- Chroma path: `backend_python/chroma_eval`
- Environment file: `backend_python/.env.eval`
- Docker CLI: unavailable in this shell, but MariaDB was already reachable at
  `127.0.0.1:3307`

No API key, database password, or token was serialized in result artifacts.

## 4. Frozen Benchmark

| Input | Count | SHA-256 |
| --- | ---: | --- |
| `document_rag_v2.yaml` | 7 D1-D5 pilot cases | `a058b7a16f877e5f6ceaae7d76b0f04b64c6522cc88871eb617c141325fddabd` |
| `cases.jsonl` | 32 EvidenceUnit runtime cases | `75f1580a254abb37b036398889b0647be3dd0eaa389c2bac2a33370622931d7b` |
| `gold.jsonl` | 32 hidden scoring rows | `214b26e87777efbc650404698c452de2cec0f3ad4ff907e448228fc61ff1c02e` |

EvidenceUnit coverage was 10 D6, 10 D7, 10 D8, and 2 D8_NONCLOSING cases.

## 5. Implementation Changes

- Added `evaluation/run_d1_d8_pilot.py` and
  `evaluation/run_d1_d8_pilot.ps1` as the combined top-level runner.
- Added `evaluation/load_evidence_fixtures.py` to load EvidenceUnit benchmark
  cases into MariaDB while preserving benchmark evidence IDs.
- Added deterministic scorers for document-RAG and EvidenceUnit results.
- Added unit tests for loader isolation, no gold leakage, D7 browser-history
  behavior, query-time filtering, stale-state rejection, and generic D8
  relation/closure handling.
- Updated `backend_python/evidence_service.py` with generic action
  reconstruction fixes: broader request signals, browser/activity evidence kept
  contextual, explicit `relation_key` grouping, later-only closure linking, and
  non-closing progress/future-commitment handling.

The frozen benchmark inputs and gold labels were not changed.

## 6. D1-D5 Execution

The document phase used `document_rag_v2`, top-k `4`, one repetition, embedding
model `text-embedding-3-small`, generator model `gpt-4o-mini`, and temperature
`0.0`.

Retrieval was computed once per case and reused across
`standard_rag`, `governance_only_rag`, and `role_aware_rag`. The
`pilot_inspection.json` check reported identical candidate lists for all three
modes in all 7 cases.

| Mode | Records | Behavioral conformance | Permitted-answer correctness | Literal protected-marker disclosure | Generation calls | Skipped generation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `standard_rag` | 7 | 0.285714 | 0.571429 | 0.714286 | 7 | 0 |
| `governance_only_rag` | 7 | 0.285714 | 0.285714 | 0.285714 | 5 | 2 |
| `role_aware_rag` | 7 | 1.000000 | 0.428571 | 0.285714 | 3 | 4 |
| all modes | 21 | 0.523810 | 0.428571 | 0.428571 | 15 | 6 |

The literal protected-marker metric counts marker appearance even in Full and
Mixed-primary cases where the marker is permitted. In the Metadata and Deny
cases, role-aware mode produced no protected-marker answer disclosure and no
generator prompt exposure. The Full case produced the correct answer in all
three modes. Mixed-primary produced the primary answer in all three modes;
role-aware mode also preserved the expected source-role conformance. The
Contextual-only case was restricted by role-aware mode and was incorrectly
answered by the two baselines.

## 7. D6-D8 Execution

The EvidenceUnit phase loaded each case through the evaluation-only MariaDB
loader and then called the production service path:

```text
backend_python.evidence_service.reconstruct_action_list
```

The default isolation strategy is one deterministic evaluation user per case
plus cleanup after each case. The loader excludes EvidenceUnits later than the
case `query_time`, preserves evidence IDs, creates explicit `PolicyRule` rows
from runtime `access_mode`, and does not pass `gold.jsonl` fields into the
runtime database rows.

The EvidenceUnit phase produced 32 records and used `external_llm_calls = 0`.

## 8. Baseline Evidence Diagnostic

Before production action-logic fixes, the frozen 32 EvidenceUnit cases produced
22 failures:

| Metric | Baseline |
| --- | ---: |
| D6 open-action accuracy | 0.000000 |
| D7 browser-only false-action rate | 0.000000 |
| D8 closure-status accuracy | 0.000000 |
| D8_NONCLOSING open-status accuracy | 0.000000 |
| EvidenceUnit role accuracy | 0.562500 |
| OPEN/CLOSED/ABSENT status accuracy | 0.312500 |
| Action F1 | 0.000000 |
| Triplet consistency | 0.000000 |

Baseline failure classes were:

- `D6_001` to `D6_010`: obligation not recognized.
- `D8_001` to `D8_010`: closure not recognized or not linked.
- `D8_NONCLOSING_001` and `D8_NONCLOSING_002`: open item lost or non-closing
  evidence mishandled.

## 9. Post-Fix Evidence Diagnostic

After generic implementation corrections, all 32 EvidenceUnit cases passed.

| Metric | Post-fix |
| --- | ---: |
| D6 open-action accuracy | 1.000000 |
| D6 action recall | 1.000000 |
| D7 browser-only false-action rate | 0.000000 |
| D7 contextual-role accuracy | 1.000000 |
| D8 closure-status accuracy | 1.000000 |
| D8 primary/contrastive linking accuracy | 1.000000 |
| D8_NONCLOSING open-status accuracy | 1.000000 |
| EvidenceUnit role accuracy | 1.000000 |
| OPEN/CLOSED/ABSENT status accuracy | 1.000000 |
| Action precision / recall / F1 | 1.000000 / 1.000000 / 1.000000 |

## 10. Metrics

Triplet consistency:

| Complete triplets | Correct | Rate | Failed seed IDs |
| ---: | ---: | ---: | --- |
| 10 | 10 | 1.000000 | none |

OPEN/CLOSED/ABSENT confusion matrix after fixes:

| Expected | Observed OPEN | Observed CLOSED | Observed ABSENT |
| --- | ---: | ---: | ---: |
| OPEN | 12 | 0 | 0 |
| CLOSED | 0 | 10 | 0 |
| ABSENT | 0 | 0 | 10 |

API usage for the real combined run:

| Phase | Embedding calls | Generation calls | Prompt/input tokens | Completion/output tokens | Total tokens | External LLM calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| D1-D5 document-RAG | 12 total embedding calls: 5 fixture-index, 7 query | 15 | 7436 | 269 | 7705 | 15 generation calls |
| D6-D8 EvidenceUnit | 0 | 0 | 0 | 0 | 0 | 0 |

## 11. Per-Case Failures

Post-fix EvidenceUnit failures: none.

Real D1-D5 document-RAG behavioral failures:

| Case | Mode | Expected class | Observed output | Main symptoms |
| --- | --- | --- | --- | --- |
| `METADATA_01` | `standard_rag` | `metadata_only_answer` | `full_answer` | Protected answer disclosure and generator exposure |
| `METADATA_01` | `governance_only_rag` | `metadata_only_answer` | `governance_no_content` | No permitted answer; controlled-failure mismatch |
| `DENY_01` | `standard_rag` | `deny_refuse_or_abstain` | `full_answer` | Protected answer disclosure and generator exposure |
| `DENY_01` | `governance_only_rag` | `deny_refuse_or_abstain` | `governance_no_content` | Controlled-failure mismatch |
| `AGG_SAFE_01` | `standard_rag` | `aggregate_answer` | `full_answer` | Aggregate-safe answer marker not matched; generator exposure |
| `AGG_SAFE_01` | `governance_only_rag` | `aggregate_answer` | `full_answer` | Aggregate-safe answer marker not matched |
| `AGG_INDIVIDUAL_01` | `standard_rag` | `aggregate_only_restriction` | `full_answer` | Protected individual marker disclosed |
| `AGG_INDIVIDUAL_01` | `governance_only_rag` | `aggregate_only_restriction` | `full_answer` | Controlled-failure mismatch |
| `CONTEXT_ONLY_01` | `standard_rag` | `controlled_failure` | `full_answer` | Contextual-only bait answered |
| `CONTEXT_ONLY_01` | `governance_only_rag` | `controlled_failure` | `full_answer` | Contextual-only bait answered |

## 12. Tests

Commands:

```powershell
.\backend_python\.venv_eval\Scripts\python.exe -m unittest evaluation.tests.test_document_rag_pilot_runner evaluation.tests.test_d1_d8_evidence_loader_and_action_logic -v
.\backend_python\.venv_eval\Scripts\python.exe -m unittest discover -s evaluation\tests -v
```

Results:

- Targeted runner/EvidenceUnit modules: 28 tests, OK, 7.015 s.
- Full evaluation suite: 61 tests, OK, 7.458 s.
- Observed warnings were deprecation warnings from dependencies and existing
  timestamp helpers; no test failed or skipped.

## 13. Reproduction Commands

Fresh Windows PowerShell reproduction:

```powershell
git clone https://github.com/gkusper/InfoBank.git
cd InfoBank
git checkout d1-d8-end-to-end-pilot

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\evaluation\bootstrap_reproduction.ps1 -PrepareEvalDatabase -RunUnitTests -RunPilotCheck

# For a clean repeated run:
.\evaluation\bootstrap_reproduction.ps1 -ResetEvaluationState -SkipPackageInstall -RunPilotCheck

# Preflight only:
.\evaluation\run_d1_d8_pilot.ps1 -CheckOnly

# Complete local integration without OpenAI generation:
.\evaluation\run_d1_d8_pilot.ps1 -MockGeneration

# Real D1-D5 generation plus deterministic D6-D8:
$env:OPENAI_API_KEY = "<set outside the repository>"
.\evaluation\run_d1_d8_pilot.ps1
```

Expected successful record counts are 21 D1-D5 document-RAG records, 32 D6-D8
EvidenceUnit records, and 53 combined records.

## 14. Limitations

- Production action logic was corrected after observing the development pilot
  baseline, so post-fix D6-D8 numbers are not held-out performance.
- The current MailEx-derived EvidenceUnit pilot is small.
- D7 uses synthetic browser/search-history counterfactuals.
- D8 labels are InfoBank-specific open/closed action labels.
- The current benchmark has no cancelled examples, although generic cancellation
  handling is covered by unit tests.
- The real D1-D5 run used one provider, one generator model, and one repetition.
- D1-D5 uses LLM-backed generation; D6-D8 remained deterministic.

## 15. Next Experimental Step

The implementation is ready for a larger development run if the D1-D5 baseline
failures above are accepted as expected baseline behavior and the role-aware
D1-D5 behavior is reviewed. Recommended next steps are:

- Run the full D1-D5 40-case x 3-mode x 3-repetition experiment.
- Expand D6-D8 toward 40 matched seeds.
- Build and reserve a held-out evaluation set before further action-logic
  tuning.
