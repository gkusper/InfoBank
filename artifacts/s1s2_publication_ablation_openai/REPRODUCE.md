# Reproduce Frozen OpenAI C0-C3 Evaluation

Generated at: 2026-08-24T23:33:45.552962Z

Prerequisite: MariaDB must be reachable on 127.0.0.1:3307 using the repository docker-compose environment. Do not print credentials.

1. Verify frozen state and Phase A validators as recorded in REAL_PROVIDER_PREREGISTRATION.json.
2. Ensure OPENAI_API_KEY is present in the environment.
3. Run the locked measured execution script without changing model, prompts, scorer, gold, or benchmark:

```powershell
& 'backend_python\.venv_r1a\Scripts\python.exe' artifacts\s1s2_publication_ablation_openai\openai_c0_c3_runner.py
```

The run order is R1 C0-C1-C2-C3, R2 C0-C1-C2-C3, R3 C0-C1-C2-C3. Each run group uses an isolated infobank_eval_* MariaDB database, Chroma directory, source-storage directory, raw output directory, and score output directory.

Confidence intervals: CONFIDENCE_INTERVALS_NOT_GENERATED_BY_FROZEN_EVALUATOR.
