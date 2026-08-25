# Configuration Identifier Migration: B0-B3 to C0-C3

Date: 2026-08-25

Branch: `infocom2026`

Starting commit: `8eb5c3d46d88f162cd85583bb3b065a0426aad53`

## Purpose

This document records the terminology-only migration from the old B0-B3 architectural labels to the C0-C3 architectural configuration labels used by the current implementation and canonical evaluation artifacts.

The labels C0-C3 identify the four architectural configurations compared in the ablation study, with C0 serving as the reference configuration. C means configuration.

## Canonical Mapping

Short labels:

- B0 -> C0
- B1 -> C1
- B2 -> C2
- B3 -> C3

Full mode names:

- `B0_VECTOR_ONLY` -> `C0_VECTOR_ONLY`
- `B1_VECTOR_ROUTING` -> `C1_VECTOR_ROUTING`
- `B2_PERMISSION_FILTERED` -> `C2_PERMISSION_FILTERED`
- `B3_FULL_ROLE_AWARE` -> `C3_FULL_ROLE_AWARE`

Current terminology:

- C0: vector-only reference configuration
- C1: vector retrieval with keyword routing
- C2: permission-filtered configuration
- C3: complete role-aware configuration

## Scope

This migration changed identifiers, labels, paths, summary filenames, and derived hashes. It did not change configuration semantics, retrieval behavior, routing behavior, permission behavior, evidence-role behavior, controlled-failure behavior, prompts, thresholds, model identifiers, questions, scenarios, author-validated reference annotations, measured answers, citations, or numerical results.

New evaluation output is expected to emit only:

- `C0_VECTOR_ONLY`
- `C1_VECTOR_ROUTING`
- `C2_PERMISSION_FILTERED`
- `C3_FULL_ROLE_AWARE`

The C-labeled canonical artifacts were derived from the existing measured records. No OpenAI provider call was repeated.

## Provenance

The original locked OpenAI preregistration remains unchanged at:

`artifacts/s1s2_publication_ablation_openai/REAL_PROVIDER_PREREGISTRATION.json`

Its SHA-256 remains:

`254dd996d8bdd7322061cfbffc8cb6cad4998e449ae4081b62570b13420a5c7c`

The historical fact that the completed provider execution used the old labels is preserved by Git history and by the migration manifest. The manifest records source paths, source hashes, resulting paths, resulting hashes, and the exact identifier mapping.

Machine-readable migration manifest:

`artifacts/configuration_identifier_migration_b_to_c.json`

Machine-readable validation artifact:

`artifacts/configuration_identifier_migration_b_to_c_validation.json`

The manifest records 215 artifact path/hash pairs: 189 renamed pairs and 26 updated-in-place pairs.

Package-level pair hashes:

- deterministic source pair hash: `6ff77b91c6d927846b13436ed9a02312e4dc8c3eef8a71a96681cd1265ee57a2`
- deterministic resulting pair hash: `fc7478343c8a2eb96e6584542bea1df087dd575b7569597e485b43e207e60823`
- OpenAI source pair hash: `bf09e582d3d4f374454335671fa8c4edc15968ec0155af3ce8d5cc09b508a9bc`
- OpenAI resulting pair hash: `c654cd30dad6d9bd77921944a15c159c27d7fe4bc32c0f9ba1cc4e301d8a63c7`

## Numeric Equivalence

The validation compared the canonical deterministic and OpenAI outputs before and after the label migration, ignoring only expected identifier, path, run-id label, and derived-hash changes.

Validation result:

- status: `PASS`
- OpenAI measured records compared: 144
- deterministic records compared: 48
- total records compared including deterministic records: 192
- semantic difference count: 0
- numerical difference count: 0
- missing record count: 0
- extra record count: 0
- OpenAI provider calls performed: 0

For the real-provider experiment, repetitions remain 3, configurations remain 4, and cases per configuration per repetition remain 12.

## Frozen S1/S2 Package

The existing frozen S1/S2 v2 package remains unchanged:

`artifacts/s1s2_freeze/S1_S2_JOURNAL_BENCHMARK_V2`

It is historical evaluation evidence. The migration did not silently edit that package in place, and no successor package was created because the canonical publication artifacts already provide the C-labeled presentation package needed for this terminology migration.

## S3-S6 Handling

Tracked S3-S6 scenario definitions are present in source/test files, but no S3-S6 scenario file used the C0-C3 ablation vocabulary in a way requiring mechanical replacement. No S3-S6 scenario ID, question, source document, annotation, expected output class, metric, or status was changed.

## Required Statements

- no provider call was repeated
- no answer was changed
- no score was changed
- no record was added or removed
- only configuration identifiers, paths, labels, and derived hashes changed
