# QASPER source audit

Original source: [allenai/qasper](https://huggingface.co/datasets/allenai/qasper/tree/fdc9d8214fbab5dd782958601db4d678e6934a54). Hugging Face repository revision: `fdc9d8214fbab5dd782958601db4d678e6934a54`.

The pinned official loader identifies version 0.3.0 and the original [v0.3 train/dev archive](https://qasper-dataset.s3.us-west-2.amazonaws.com/qasper-train-dev-v0.3.tgz), which is the actual data source used here. The loader was inspected as source only; its default split-generator also downloads test, so it was not executed. No test archive was downloaded or test record read. The downloaded archive contains train, dev and README; only dev and README were extracted, and no train JSON was parsed.

Archive SHA-256: `a28fdf966db827bcee3d873107d6b6669864fb7ca8fbf73a192f5e39191bdb5a`; size 10,835,856 bytes.
Dev member SHA-256: `2ae7ee62a65b1c4225791c70de80c2aad4e8998cf1fd4f09a53103db4f21af93`.

Schema observed directly: a JSON mapping from original arXiv paper IDs to `title`, `abstract`, `full_text`, `qas`, `figures_and_tables`. Full text is a list of `{section_name, paragraphs}`; figures/tables are textual caption/file objects. Each QA includes its question ID and multiple `{answer, annotation_id, worker_id}` answer wrappers. The original answer has unanswerable, extractive_spans, yes_no, free_form_answer, evidence, highlighted_evidence. The archive README contains an outdated caption-field description, so the adapter follows the actual `figures_and_tables` structure.

Observed dev counts: 281 papers, 1005 questions, 1764 answer annotations. Original paper reports 5049 questions over 1585 papers across all splits; those global counts are not the pilot dev denominator. See [Dasigi et al., NAACL 2021](https://aclanthology.org/2021.naacl-main.365/).

License: CC BY 4.0, verified in the pinned official Hugging Face dataset card. Attribution: Pradeep Dasigi, Kyle Lo, Iz Beltagy, Arman Cohan, Noah A. Smith, Matt Gardner (2021), A Dataset of Information-Seeking Questions and Answers Anchored in Research Papers. Dataset/card are kept locally; no full original papers or answer annotations are committed. The official loader source is Apache-2.0 and is not incorporated into the adapter.

One first-record answer object was viewed to audit nested representation before sampling; its ID is explicitly recorded in the exposure ledger. Selection remained the independent seeded draw. Label auditing necessarily inspected annotation fields for all dev questions; it is not claimed that the rest are label-unseen holdout data. Only the selected ten questions are model-evaluated.

Downloaded artifact hashes:

- `hf_metadata.json`: `bef0d5e452c29b426ddbd0536aa59d48f5183ce1380b3dff168a28cfd6516ccc` (1718 bytes)
- `hf_qasper.py`: `381d623d4992118738c0a17b9c8219136f493eda381125716ab32b814d0b3c0a` (5950 bytes)
- `hf_README.md`: `da348d3f8277f8a93ca397941f6a525433e282858b1c0562aed3f667d8e55b05` (9639 bytes)
- `ORIGINAL_README.md`: `199ab78533b6155efd0af39614e61fb24c1d5ef6d907a5990dede570fd629b75` (4099 bytes)
- `qasper-dev-v0.3.json`: `2ae7ee62a65b1c4225791c70de80c2aad4e8998cf1fd4f09a53103db4f21af93` (11398686 bytes)
- `qasper-train-dev-v0.3.tgz`: `a28fdf966db827bcee3d873107d6b6669864fb7ca8fbf73a192f5e39191bdb5a` (10835856 bytes)
