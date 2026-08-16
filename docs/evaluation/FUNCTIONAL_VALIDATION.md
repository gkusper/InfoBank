# Functional Validation

This document records the sanitized functional smoke tests completed during pre-pilot preparation. It preserves the scientific result without storing local runtime artifacts, database identifiers, tokens, or credentials.

## Tested State

Tested Git state: pre-pilot evaluation history up to `evaluation-pilot`, latest pre-publication commit `9b7326b9d53741c3455cbdc61186a2f6412f5864`.

Python: 3.12 evaluation environment with pinned dependencies.

Database: MariaDB local runtime.

OpenAI models:

- chat generation: `gpt-4o-mini`
- embeddings: `text-embedding-3-small`

## Synthetic Fixture Text

The smoke tests used synthetic document content with the protected marker:

```text
BLUE ORCHID
```

The tests asked the same factual question against different access conditions.

## Expected Fact

Expected fact marker:

```text
BLUE ORCHID
```

## Full-Access Outcome

Condition: owner/full access to the synthetic document.

Observed behavior:

- the answer returned the expected synthetic fact;
- output mode was `full_answer`;
- the source role was `primary`;
- the pipeline exercised retrieval, governance resolution, source-role classification, evidence checking, and generation.

Protected-content leakage result: disclosure was permitted under full access, so returning `BLUE ORCHID` was expected.

## Metadata-Only Outcome

Condition: cross-user Metadata access to the same synthetic document and question.

Observed behavior:

- the protected marker was not disclosed;
- output mode was `metadata_only_answer`;
- the source role was `contextual`;
- governance and controlled-failure restriction behavior were observed.

Protected-content leakage result: the protected marker was withheld in the metadata-only condition.

## Pipeline Stages Exercised

The smoke tests exercised:

- MariaDB-backed user/document state;
- document permissions;
- OpenAI-backed embedding and generation calls;
- Chroma-backed retrieval;
- policy/governance resolution;
- source-role classification;
- evidence-sufficiency logic;
- controlled-failure/output-mode selection;
- final answer generation.

## Conclusion

The smoke tests support the current pre-pilot claim that full access can return a governed synthetic fact, while Metadata access withholds the protected marker and returns a restricted safe answer.

Production scientific behavior was not modified during the functional validation.
