# Evaluation methodology

Status: `METHODOLOGY_DEFINED_IMPLEMENTATION_PENDING`

This document defines the required evidence boundary for Review C and Review D. It is technical methodology, not manuscript or reviewer-response prose.

## Evidence levels

1. A **deterministic contract test** checks schemas, control flow, invariants and reproducibility. It may use generated fixtures, but it is not a system-performance estimate.
2. An **actual-pipeline development evaluation** indexes a development corpus through production-equivalent processing, retrieval, routing, policy, controlled-failure, generation and citation components. Raw execution is gold-blind and scoring occurs only after raw output is sealed.
3. A **candidate-holdout evaluation** uses a disjoint, non-frozen candidate solely for readiness assessment. It must not be used to tune thresholds, rules, prompts or scorers.
4. A **frozen final evaluation** uses approved immutable dataset, scorer, configuration and code versions exactly once. This is the only level eligible for final E1 claims.

## Gold-blind execution

Runtime input and gold annotation must be separate artifacts. `QueryInput` contains identity, query, purpose, corpus/package reference, policy-fixture reference and mode-independent runtime parameters. `GoldAnnotation` contains expected output class and reason, sources/pages/messages, factual atoms, evidence roles, action status and human-validation state.

The runner may read `QueryInput`, corpus and fixture/setup data. It must not import or access expected output classes, gold reasons, gold source/page/message IDs or reference answers. Removing or corrupting gold must not change a raw run; changing query input must.

## Raw-run sealing and post-run scoring

The runner writes complete raw JSONL before any scorer receives gold. A seal records the raw-run SHA-256, query-input hash, corpus hash, config hash, exact commit, provider/model, timestamp and run ID. After sealing, a separate scorer joins records to `GoldAnnotation`, validates exact case identity/order/version and emits results that reference the sealed raw-run hash.

Measured wall-clock durations, deterministic/simulated timing fields and provider-reported latency or usage must remain distinct. Missing provider measurements are `NOT_AVAILABLE`, never inferred. Answer correctness and unsupported-answer rate require actual produced answer text and post-run gold/human scoring.

## Dataset partitions

- Development: may be used for calibration and implementation fixes.
- Candidate holdout: disjoint and non-frozen; not used for tuning.
- Frozen final: unavailable until human annotation, adjudication, licence, citation and no-health gates complete.
- Frozen D1–D8/CogInfoCom: excluded from v2 tuning.

## Provider evidence

The deterministic local provider exercises the provider interface without network access and may support repeatable development evaluation. A real-provider result requires an explicit provider/model/config, network authorization, provider usage records and a separate evidence label. Deterministic-provider results must not be represented as real-provider quality.

## Current valid evidence

- A2 routing preserved Recall@3 and reduced candidate size on its synthetic development corpus with zero routing false exclusions.
- The C scale microbenchmark repeats the same retrieval questions at 50/250/1000 documents and measures lexical/IDF routing/retrieval behavior.
- Permission, aggregate, provider and controlled-failure invariants have deterministic tests.
- B0/B1 production unreachability is a required hard invariant.

## Deprecated performance claims

The pre-hardening D-GATE B0–B3 records are deterministic contract simulations. Gold output classes, reason codes, source IDs or pages were used to construct some predictions, retrieval records or citations; some safety, timing and usage values were assigned or simulated. Their perfect B3, controlled-failure and action scores validate contracts only and are deprecated as empirical performance claims.

The C scale runner did not generate answer text. Its former `answer_correctness` is `gold_document_retrieval_completeness`; unsupported-answer rate is `NOT_EVALUATED`. Page retrieval correctness is not human citation faithfulness.

Actual gold-blind pipeline development evaluation now passes on the generated development fixture. Human citation audit, human MailEx annotation, approved network-provider evaluation, and final frozen E1 remain pending.
