# Error Analysis

Generated at: 2026-08-24T23:33:45.550941Z

Runtime/provider failures: 0 across all 144 measured records.
Safety/leakage findings: 0 across all available frozen counters.

## By Configuration
### C0 - C0_VECTOR_ONLY
- citation document miss: 6
- false answer: 3
- unsupported citation: 12
- wrong page: 3
- Known frozen citation-completeness limitations observed: S1-Q6 (3/3 reps)

### C1 - C1_VECTOR_ROUTING
- citation document miss: 9
- false answer: 3
- unsupported citation: 3
- Known frozen citation-completeness limitations observed: S1-Q6 (3/3 reps), S2-Q2 (3/3 reps)

### C2 - C2_PERMISSION_FILTERED
- citation document miss: 6
- unsupported citation: 12
- wrong page: 3
- Known frozen citation-completeness limitations observed: S1-Q6 (3/3 reps)

### C3 - C3_FULL_ROLE_AWARE
- citation document miss: 9
- unsupported citation: 3
- Known frozen citation-completeness limitations observed: S1-Q6 (3/3 reps), S2-Q2 (3/3 reps)

## Known Frozen Limitations Kept Separate
- S1-Q6: Missing second required care-guide citation.
- S2-Q2: Missing second required warranty-terms citation.
- S2-Q5: Missing second required regional-service-notice citation.

## Notes
- Routing keyword and embedding provider calls are not fully token-accounted by the frozen adapter.
- Cost is not recorded because no frozen local pricing configuration was supplied and the OpenAI adapter returns cost=None.
