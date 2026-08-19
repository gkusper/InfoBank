# A-GATE Phase A2 routing and graph scope

## Audited pre-A2 state

Before Phase A2, `POST /api/ask` asked the configured model to select up to three database keywords, narrowed document identifiers by any exact keyword match, and only then applied the policy engine. If no match existed, it fell back to the permitted corpus. The sequence did not allow denied content into generation because policy resolution still ran before retrieval, but it had two material scope problems:

1. the keyword prompt was assembled from every stored keyword, including keywords belonging only to documents the caller could not use; and
2. routing had no explicit off-mode, stable trace, deterministic ablation, or false-exclusion measurement.

The former `GET /api/ontology/*` implementation counted keyword co-occurrence over direct permission rows in database iteration order. It was a small visualization, not a semantic ontology: it had no typed relations, inference, taxonomy, ontology lifecycle, or scale evidence. Its output order and identifiers were not deterministic, and its direct permission join did not express the query-time Full/Aggregate/Metadata/Deny policy.

## Implemented routing contract

`backend_python/routing.py` defines exactly two evaluation modes:

- `ROUTING_OFF`: return the complete governance-permitted input set.
- `KEYWORD_ROUTING`: return documents with a normalized exact selected-keyword match; if no keyword is selected or no permitted match exists, fall back to the complete governance-permitted input set.

Both modes are post-policy operations. They accept `permitted_document_ids`, never raw database scope, and their candidate set is structurally limited to that input. Production `POST /api/ask` now:

1. collects only active documents reachable through a direct permission or the existing Aggregate/Metadata visibility rule;
2. resolves Full/Aggregate/Metadata/Deny decisions;
3. stops safely when there is no usable source;
4. builds the model-visible keyword vocabulary only from usable document identifiers;
5. applies `KEYWORD_ROUTING` within that usable set; and
6. resolves policy again for the selected candidates before retrieval and generation.

There is deliberately no client-controlled routing-mode parameter on `POST /api/ask`; the two-mode switch belongs to the local evaluator and cannot be used to bypass policy. The trace records mode, selected and matched keywords, candidates, excluded governed documents, fallback state and reason, governed input size, candidate size, routing configuration version, and SHA-256 configuration hash.

## Semantic Co-occurrence Graph contract

`backend_python/semantic_graph.py` exports a deterministic visualization:

- node: stable UUIDv5 ID, normalized keyword, document frequency;
- edge: stable source/target node IDs, source/target keyword, shared-document count;
- stable node and edge sorting;
- no document ID, filesystem path, source text, page text, or protected raw content.

`GET /api/semantic-cooccurrence-graph/me` and its same-user variant apply governance before export. Full and Metadata documents may contribute keywords. Aggregate-only and denied documents do not contribute, because per-document keyword relationships could reveal more than aggregate permission allows. `/api/ontology/*` remains a compatibility alias but returns the same explicitly scoped graph.

The frontend label is now “Semantic Co-occurrence Graph.” This graph is visualization-only. It is not an ontology, knowledge-representation layer, inference engine, routing authority, or drift-prevention mechanism.

## Measured A2 decision

The local privacy-safe development run contained 12 documents and 24 queries, producing 48 paired mode records at `k=3`:

| Metric | ROUTING_OFF | KEYWORD_ROUTING |
|---|---:|---:|
| Mean Recall@3 | 1.000000 | 1.000000 |
| Mean Precision@3 | 0.466667 | 0.466667 |
| Found rate | 1.000000 | 1.000000 |
| Mean target rank | 1.066667 | 1.066667 |
| Mean candidate-set size | 12.000000 | 4.000000 |
| Hard-negative candidate inclusion rate | 1.000000 | 0.233333 |
| False exclusions | 0 | 0 |

Latency is recorded per run in `artifacts/a_gate_phase2/summary.json` and `summary.csv`, but is not copied here because sub-millisecond local timing is environment-sensitive.

Decision: retain keyword routing only as measured, governance-preserving candidate narrowing with permitted-corpus fallback. The A2 evidence does not justify a production performance claim, semantic-routing claim, ontology claim, or removal of the fallback. A later representative dataset must re-evaluate this decision; any recall regression or false exclusion changes the decision to visualization-only/no retrieval narrowing.
