# P001-P010 Adjudicated Annotation-Quality Robustness Subset

This directory contains the adjudicated P001-P010 robustness benchmark, annotation agreement report, and two fixed-generator RAG runs.

The benchmark is rebuilt from `Finalized_Annotation` in the external workbook. It is not a filtered copy of the original 271-question benchmark, and raw MailEx email bodies are not committed here.

Key commands:

```powershell
python experiments\iscmi2026\experiment\validate_no_leakage.py --benchmark-dir experiments\iscmi2026\robustness\p001_p010_adjudicated\benchmark --packet-dir C:\path\outside\repo\mailex_pilot_external_packet --generator-model gpt-4o-mini-2024-07-18
python experiments\iscmi2026\experiment\validate_no_leakage.py --benchmark-dir experiments\iscmi2026\robustness\p001_p010_adjudicated\benchmark --packet-dir C:\path\outside\repo\mailex_pilot_external_packet --generator-model gpt-4.1-2025-04-14
```

Questions: 57. Final tasks: 44. Classification: ROBUST TO ADJUDICATED ANNOTATION.

**This experiment tests annotation-quality robustness of the oracle task-state representation on the adjudicated P001–P010 subset. It does not evaluate automatic task-state extraction.**
