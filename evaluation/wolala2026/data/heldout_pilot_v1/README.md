# heldout_pilot_v1

This is the frozen WoLaLa 2026 held-out pilot dataset.

- Cases: 40
- Pairs: 20
- Families: P1, P2, P3, P4, P5
- Origin: deterministic synthetic data only
- Personal information: none
- Medical or health data: none

Gold fields are included in `gold.jsonl` and duplicated as expected labels in
`cases.jsonl` for deterministic validation. They are not passed to adapter
generator contexts.

The held-out dataset must not be executed during Phase 2 preparation.
