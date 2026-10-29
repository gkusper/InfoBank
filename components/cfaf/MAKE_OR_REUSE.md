# Make or reuse: implemented decisions

The existing `evaluation/cfaf_contract_driven_2h_v1/MAKE_OR_REUSE.md` at base `bfd80bbfe2ccbb251da46bdc22b791dad5b9341f` was audited first. Its historical two-call design is preserved; this package implements a separate small one-call configuration. No broad framework search or wholesale experiment-module copy was performed.

| Responsibility | Actual component | Reuse decision and cost |
|---|---|---|
| Four typed contracts/internal proposal | Pydantic 2.12.3, Python enums | MIT dependency; no custom schema engine. SDK strict schema is generated from Pydantic types. |
| Generative transport | Official OpenAI Python SDK 1.59.9; httpx 0.28.1 | Apache-2.0 / BSD-3-Clause metadata. One strict Chat Completions request, retries 0, timeout 45 s. No custom HTTP provider framework. |
| Query-only preparation | Small LocalProfiler | Explicit AND offsets, known simple value hints and pronoun dependency; OR unresolved. No general parser/NER or regex NLP framework. The title-conjunction false split in the pilot is reported. |
| Supplied benchmark context | ProvidedContextRetriever | No redundant search or embedding call. |
| Document search | SQLite FTS5/BM25 adapter | Standard-library sqlite3, SQLite public-domain code. Authorized in-memory index only, deterministic rank/tie handling. No own search/database engine. |
| Policy projection | Existing pure policy_projection.py plus authenticated resolver/current callbacks | Repository CC-BY-NC-4.0 reuse; no legacy FastAPI/SQLAlchemy/Pydantic-V1 import. Reused source and adapter costs are counted. Production must authenticate callbacks and supply durable authorization/revocation. |
| Dependency validation | Python graphlib | PSF-licensed stdlib; no NetworkX. DAG/membership/equality do not prove semantic dependency correctness. |
| Aggregation | Existing vendored pure aggregate_core.py | Reuses threshold, policy filtering and contributor deduplication. Current-repository provenance/license recorded; the earlier upstream-main license was not separately reverified. No DuckDB or replacement aggregate engine. |
| Selector | Small extracted first-failing-assessment principle | Relevant fields match the historical selector on 300 nonempty states. New request/execution preconditions are explicit, not hidden equivalence claims. |
| Publication | DeterministicRenderer plus legacy-contract compatibility renderer | No second LLM call; explicit claim IDs and reference labels. No template framework needed. |
| Testing | pytest 9.0.2, Hypothesis 6.147.0, official SDK over httpx.MockTransport | MIT / MPL-2.0 metadata. Mock results remain separate from live API results. |
| Optional NLI/spaCy/vector/workflow services | NOT_IMPLEMENTED_OPTIONAL | No model downloads, missing-package fallback or phantom benchmark. Core runs without these dependencies. |

Exact resolved distribution versions and metadata licenses are in component_manifest.json; requirements.lock fixes all 26 distributions in the isolated component environment, including build/test tools. Python is 3.12.14. Runtime, copied runtime and adapter line counts are separate in code_size_report.json. A separate legacy-only environment adds pyarrow 26.0.0 for existing metadata-filter tests; it does not change the component environment or frozen inference dependencies.

The inspected legacy requirements pin Pydantic 1.10.24, FastAPI 0.103.2 and ChromaDB 0.4.24. They remain unchanged. A JSON/dict boundary is used instead of nesting V1/V2 models. This package imports no Chroma, LangChain, LangGraph, LlamaIndex, Haystack, Casbin, DuckDB, spaCy, torch or sentence_transformers at startup. No package/model is installed or fetched by runtime code.

The default generative model is exactly gpt-4o-mini; the observed live deployment is gpt-4o-mini-2024-07-18. No stronger generative model, external judge or NLI model was used. NLI cold/warm time, memory, label mapping, truncation and revision therefore remain NOT_RUN, not fabricated zero-valued measurements.

Implementation documentation checked: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [Pydantic migration boundary](https://docs.pydantic.dev/latest/migration/), [SQLite FTS5/BM25](https://www.sqlite.org/fts5.html). The provider uses required fields, explicit null unions and additionalProperties=false; refusals and incomplete outputs are handled separately. The installed official SDK and actual live calls establish compatibility for the pinned environment. These documentation facts are not performance evidence.
