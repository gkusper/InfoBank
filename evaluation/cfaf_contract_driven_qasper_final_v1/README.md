# QASPER final replacement artifacts

Read REPORT.md for the complete study and fourteen research answers; REVISED_THREE_DATASET_SUMMARY.md places it beside exact imported Dataset1/2 development results. Dataset3-v1 GaRAGe remains archived in the unchanged original study.

The 80-case test run is complete. Do not rerun the API runner or resample these exposed cases. Public per-case results, request hashes, frozen manifests and audits are committed here. Original test papers, human answers and full raw outputs are ignored under datasets/ and local/. The complete local case-by-case report is local/CASE_REPORT.md.

RESULTS_FOR_PAPER_QASPER.tex is a compiled replacement section for the verified CF2AF_v5.9.tex source; PAPER_REPLACEMENT_NOTES.md gives precise integration anchors. The manuscript itself is unchanged.

The isolated branch is experiment/cfaf-final-qasper-replacement-v1, starting from frozen bfd80bbfe2ccbb251da46bdc22b791dad5b9341f. It deliberately does not include later one-call/component algorithm changes. Frozen mappings, inference sources and sample must remain unchanged. Scoring/review/packaging helpers do not alter inference.

checksums.sha256 covers public files except itself. COMPLETION_AUDIT.json describes precommit checks; the adjacent output completion receipt supplies the resulting commit and postcommit checks. Only a local commit is performed. To publish manually, use git push -u origin experiment/cfaf-final-qasper-replacement-v1 from this isolated worktree; do not force-push another branch.
