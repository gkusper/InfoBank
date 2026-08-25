# R1B Evaluation Tooling Inventory

## Donor references inspected

- `origin/d1-d8-end-to-end-pilot` at `e6a3cd032a3e431899bda56632ffc1389b636f15`
- `origin/d1-d8-large-scale-final-evaluation` at `5bb2cc742e105cc3238b022130126947c04bcd35`

For every candidate below, the two donor refs contain the same Git blob. Each file was inspected once by content and verified by blob ID on both refs. No fixture, benchmark record, frozen result, publication artifact, or research-specific report was copied.

## Candidate classification

| Donor branch | Donor path | Purpose | Runtime dependencies | Data/fixture dependencies | Classification | Reason | Destination |
|---|---|---|---|---|---|---|---|
| Both inspected refs | `evaluation/__init__.py` | Package marker | None | None | REFACTOR_AND_REUSE | The package concept is generic, but the donor docstring claims document-RAG ablations. | `evaluation/__init__.py` with provider-neutral scope |
| Both inspected refs | `evaluation/backend.py` | Resolve repository/backend paths | Python stdlib | Repository layout only | REFACTOR_AND_REUSE | The helper is reusable; its documentation was neutralized and no production mutation is allowed. | `evaluation/backend.py` |
| Both inspected refs | `evaluation/fixture_schema.py` | Parse paper evaluation fixtures | Pydantic, PyYAML | YAML/JSON fixtures, benchmark-specific users/documents/cases and protected markers | KEEP_RESEARCH_ONLY | Fixture integration belongs to the later reviewer-dataset task and would pull research schema assumptions into common main. | None |
| Both inspected refs | `evaluation/manifest.py` | Capture Git/runtime/run metadata | Python stdlib, package metadata | Clean-state report and donor generation config | REFACTOR_AND_REUSE | Git identity and deterministic manifest ideas are generic; donor fields are tied to document-RAG clean-state and models. | `evaluation/manifest.py` with version/checksum/freeze protection |
| Both inspected refs | `evaluation/schemas.py` | Donor result dataclasses and JSONL | Python stdlib | Raw questions, raw chunks, prompts, answers, D1-D8 mode labels | REFACTOR_AND_REUSE | Generic records are useful, but raw protected content and paper-mode schemas are unsuitable for common logging. | `evaluation/schemas.py` with sanitized manifest/run records and C0-C3 labels only |
| Both inspected refs | `evaluation/usage_logging.py` | Merge provider usage counters | Python stdlib | OpenAI response shape | REFACTOR_AND_REUSE | Token/latency/error accounting is generic; the OpenAI-specific adapter was removed. | `evaluation/usage_logging.py` |
| Both inspected refs | `evaluation/run_case.py` | Execute standard/governance/role-aware paper modes | Donor `modes` and schemas | Paper mode semantics, generator and policy services | KEEP_RESEARCH_ONLY | Complete evaluation mode execution is explicitly outside R1B and will be rebuilt only after reviewer datasets and gates are approved. | None |
| Both inspected refs | `evaluation/run_suite.py` | CLI suite runner | Donor fixture loader, clean-state helper, OpenAI generator | Fixture paths, result paths, mock paper cases | REJECT | It mixes research fixture orchestration, paper mode claims, real-provider capability, and result creation that R1B must not integrate. | None |
| Both inspected refs | `evaluation/retrieval.py` | Shared embedding/Chroma retrieval | Backend OpenAI/Chroma runtime | Live collection, question text, document identifiers | KEEP_RESEARCH_ONLY | It can make real provider calls and would prematurely implement the evaluation pipeline. Only checksum/context-hash concepts are retained generically. | None |
| Both inspected refs | `evaluation/tests/test_harness.py` | Validate D1-D8 ablation harness | `unittest`, donor evaluation modules | Paper modes and raw denied-content examples | KEEP_RESEARCH_ONLY | Tests assert research-mode behavior and carry raw fixture-like content. Generic serialization, sanitization and freeze-protection tests were written independently. | `evaluation/tests/test_evaluation_core.py` for generic contracts only |

## Mandatory exclusions confirmed

The common foundation does not contain:

- `data/benchmarks/**`
- `evaluation/fixtures/**`
- `evaluation/publication_results/**`
- `evaluation/preregistration/**`
- `evaluation/results/**`
- generated fixture documents
- raw JSONL/CSV research result files
- D1-D8 paper tables or reports
- MailEx benchmark records or `scripts/mailex/**`
- `docs/d1_d8_*` or `docs/evaluation/**`
- `evaluation/wolala2026/**`, WoLaLa datasets, or WoLaLa results

The R1B `evaluation/` package is infrastructure only. It does not execute or claim completion of C0-C3 evaluation.
