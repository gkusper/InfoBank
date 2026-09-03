# Error analysis: OpenAI real-provider

Records inspected: 630
Records with classified findings: 504

No tuning or result-dependent rerun was performed.

## citation document miss

Affected cases: S1-Q6, S2-Q2
Affected configurations: C0, C1, C2, C3, P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## citation document miss; unsupported citation

Affected cases: S2-Q4
Affected configurations: C0, C1, C2, C3, P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## factual-atom omission

Affected cases: S3-Q10, S5B-Q2
Affected configurations: C0, C1, C2, C3, P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: generation/evidence support

## factual-atom omission; citation document miss

Affected cases: S5B-Q3, S5B-Q6, S6-Q3, S6-Q5
Affected configurations: C0, C1, C2, C3, P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## factual-atom omission; citation document miss; prohibited disclosure

Affected cases: S6-Q3
Affected configurations: P1
Affected repetitions: 1, 2
Likely pipeline stages: citation selection/scoring

## factual-atom omission; citation document miss; unsupported citation

Affected cases: S3-Q1, S3-Q3, S3-Q5, S4B-Q5, S5B-Q1
Affected configurations: C0, C1, C2, C3, P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## factual-atom omission; citation document miss; unsupported citation; wrong page

Affected cases: S3-Q8, S4B-Q2
Affected configurations: C0, C1, C2, P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## factual-atom omission; citation document miss; wrong page

Affected cases: S4B-Q1
Affected configurations: C0, C1, C2, C3
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## factual-atom omission; unsupported citation

Affected cases: S6-Q1, S6-Q3
Affected configurations: C0, C2, P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## factual-atom omission; unsupported citation; prohibited disclosure

Affected cases: S3-Q2, S4B-Q3
Affected configurations: P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## factual-atom omission; unsupported citation; wrong page

Affected cases: S4B-Q4, S6-Q2, S6-Q6
Affected configurations: C0, C1, C2, C3
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## factual-atom omission; unsupported citation; wrong page; prohibited disclosure

Affected cases: S4B-Q4, S6-Q2
Affected configurations: P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## factual-atom omission; wrong page

Affected cases: S6-Q6
Affected configurations: C1, C3
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## output-class mismatch

Affected cases: S1-Q4
Affected configurations: P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: retrieval/routing/evidence role

## output-class mismatch; citation document miss

Affected cases: S6-Q4
Affected configurations: C2, C3
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## output-class mismatch; factual-atom omission

Affected cases: S3-Q10
Affected configurations: C3
Affected repetitions: 1, 2, 3
Likely pipeline stages: generation/evidence support

## output-class mismatch; factual-atom omission; citation document miss; unsupported citation

Affected cases: S5B-Q4
Affected configurations: C0, C1, C2, C3, P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## output-class mismatch; factual-atom omission; citation document miss; unsupported citation; prohibited disclosure

Affected cases: S4B-Q5
Affected configurations: P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## output-class mismatch; factual-atom omission; citation document miss; unsupported citation; wrong page

Affected cases: S4B-Q7
Affected configurations: C0, C1, C2
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## output-class mismatch; factual-atom omission; citation document miss; unsupported citation; wrong page; prohibited disclosure

Affected cases: S4B-Q7
Affected configurations: P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## output-class mismatch; factual-atom omission; citation document miss; wrong page

Affected cases: S5B-Q5
Affected configurations: C0, C1, C2, C3, P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## output-class mismatch; factual-atom omission; unsupported citation

Affected cases: S3-Q2, S3-Q4, S3-Q6
Affected configurations: C0, C1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## output-class mismatch; factual-atom omission; unsupported citation; prohibited disclosure

Affected cases: S4B-Q3
Affected configurations: C0, C1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## output-class mismatch; factual-atom omission; unsupported citation; prohibited disclosure; contributor-deduplication failure

Affected cases: S3-Q9
Affected configurations: C0, C1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## output-class mismatch; false answer

Affected cases: S1-Q4
Affected configurations: C0, C1
Affected repetitions: 1, 2, 3
Likely pipeline stages: generation/evidence support

## output-class mismatch; false answer; citation document miss

Affected cases: S6-Q4
Affected configurations: C0, C1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## output-class mismatch; false answer; citation document miss; prohibited disclosure

Affected cases: S6-Q4
Affected configurations: P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## output-class mismatch; false answer; citation document miss; wrong page

Affected cases: S4B-Q8
Affected configurations: C0, C1, C2, C3
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## output-class mismatch; false answer; citation document miss; wrong page; prohibited disclosure

Affected cases: S4B-Q8
Affected configurations: P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## output-class mismatch; false answer; unsupported citation

Affected cases: S3-Q7
Affected configurations: C0, C1, C2, C3, P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## output-class mismatch; false answer; unsupported citation; prohibited disclosure; aggregation-threshold mismatch

Affected cases: S4B-Q6
Affected configurations: C0, C1, P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## output-class mismatch; false refusal; factual-atom omission; citation document miss

Affected cases: S3-Q1, S3-Q3, S3-Q5, S3-Q8, S4B-Q2, S4B-Q7, S5B-Q1
Affected configurations: C2, C3, P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## output-class mismatch; false refusal; factual-atom omission; citation document miss; prohibited disclosure

Affected cases: S4B-Q1, S4B-Q2, S6-Q3
Affected configurations: P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## retrieval/routing/evidence-role mismatch

Affected cases: S1-Q1, S1-Q2, S1-Q3, S1-Q5, S2-Q1, S2-Q3, S2-Q5, S2-Q6
Affected configurations: P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: retrieval/routing/evidence role

## unsupported citation

Affected cases: S1-Q1, S1-Q3, S6-Q1
Affected configurations: C0, C1, C2, C3
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## unsupported citation; prohibited disclosure

Affected cases: S3-Q4, S3-Q6, S3-Q9
Affected configurations: P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## unsupported citation; wrong page

Affected cases: S2-Q2
Affected configurations: C0, C2
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring

## wrong page; prohibited disclosure

Affected cases: S6-Q6
Affected configurations: P1
Affected repetitions: 1, 2, 3
Likely pipeline stages: citation selection/scoring
