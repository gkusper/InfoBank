# Original GaRAGe source audit

Repository: https://github.com/amazon-science/GaRAGe

Resolved source commit **before** download: `2b7264f5d4e066affbe4b67b7d3b9cffeff98ede` (git ls-remote refs/heads/main). The official GitHub commit API independently returned the same SHA. Immutable data URL: https://raw.githubusercontent.com/amazon-science/GaRAGe/2b7264f5d4e066affbe4b67b7d3b9cffeff98ede/data/GaRAGe_benchmark.jsonl

Downloaded UTC 2026-10-28T22:59:48.452762+00:00; `GaRAGe_benchmark.jsonl`, 28,426,483 bytes; SHA-256 `419e3941f6e8eb4082a74ca2140c1f9337f8b467ff76656a6b8b0290ca3f3a72`. 2366 JSONL rows, 2366 unique IDs, no missing/duplicate IDs, no invalid row silently dropped. Total grounding passages 35,351; min 5, max 15, mean 14.941. Count distribution: `{'10': 2, '11': 4, '12': 7, '13': 4, '14': 11, '15': 2329, '5': 2, '6': 1, '7': 3, '8': 2, '9': 1}`. No evidence-array length mismatches.

Licence: CC-BY-NC-4.0, verified from the same pinned commit; local licence SHA-256 `41003d4a74749c0220e33dd415042164b5a1093ed401f36277234f772d22d3d0`. Publication: [Findings of ACL 2025, pages 17030–17049](https://aclanthology.org/2025.findings-acl.875/), DOI 10.18653/v1/2025.findings-acl.875. This is the original dataset, not RefusalBench-GaRAGe.

Original ordered fields: `['sample_id', 'question_date', 'grounding', 'question', 'question_valid', 'question_false_premise', 'question_seeking', 'question_sensitive', 'question_type', 'question_complexity', 'question_category', 'question_popularity', 'evidence_relevant', 'evidence_correct', 'answer_generate', 'answer_related_info', 'answer_validate', 'comments', 'evidence_cited', 'question_tag', 'topic_tag']`. All rows have these 21 fields. Actual `grounding` is a list; each selected passage has `cite_N` text and original age/date/provider metadata. Evidence relevance/correctness/citation fields are parallel ordered string lists. Original human answers, comments and tags remain locally intact. Names use the actual `question_` prefixes and `answer_related_info`.

Observed evidence relevance: `{'': 4, 'NO': 9393, 'YES': 25954}`.

Observed evidence correctness: `{'': 9402, 'ANSWER-THE-QUESTION': 11015, 'OUTDATED': 2771, 'RELATED-INFORMATION': 9337, 'UNKNOWN': 2826}`. OUTDATED and blank extend the simplified three-category expectation. Blank is not relabelled UNKNOWN. Original source labels and category spelling/whitespace were preserved.

Observed reference citation labels: `{'NO': 23371, 'YES': 11980}`. Reference validation: `{'': 427, 'YES': 1939}`. Question-valid/false-premise/seeking: `{'YES': 2366}` / `{'NO': 2366}` / `{'YES': 2366}`. Sensitivity: `{'NO': 780, 'YES': 1586}`; dynamism: `{'': 780, 'FAST-CHANGING': 413, 'SLOW-CHANGING': 1173}`; complexity: `{'Aggregation': 55, 'Comparison': 355, 'Multi-hop': 713, 'Post-processing heavy': 696, 'Set': 278, 'Simple': 54, 'Simple w. condition': 215}`; popularity: `{'Head': 422, 'Tail': 1304, 'Torso': 640}`. Full category value counts and types are in source_audit.json. Free-text fields are preserved and are not converted into new class vocabularies.

Only metadata and structure were aggregated over unselected records. No unselected question, passage, reference answer or comment was qualitatively inspected. Original full JSONL, pinned README and licence files are ignored local artifacts.
