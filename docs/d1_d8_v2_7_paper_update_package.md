# D1-D8 v2.7 Paper Update Package

## Abstract Result Paragraph

We evaluated InfoBank on a frozen D1-D8 benchmark with 400 D1-D5 document-RAG cases and 340 D6-D8 EvidenceUnit cases, producing 9020 measured records in the recorded run. D1-D5 compared standard RAG, governance-only RAG, and role-aware RAG under shared retrieval; D6-D8 evaluated the production action-reconstruction path on a held-out MailEx-derived benchmark. The run status is `READY WITH LISTED EDITORIAL LIMITATIONS`; numerical claims should be inserted from `paper_numbers.json` after confirming the final real-API run.

## Evaluation Section Replacement

The final evaluation used a preregistered, frozen benchmark protocol. The document-RAG benchmark contains 400 synthetic cases arranged as matched D1/D2/D4 triplets, D3 aggregate pairs, and D5 mixed/contextual pairs. Each case was evaluated under four RAG configurations with five repetitions, using shared top-4 retrieval candidates across modes. The EvidenceUnit benchmark contains 340 held-out MailEx-derived or controlled synthetic cases covering open actions, browser-only counterfactuals, closures, and non-closing controls, evaluated across three clean database runs.

## Metrics Subsection Replacement

Permitted-answer accuracy is the proportion of correct answers among answer-permitted cases only. Prohibited-disclosure, safe-withholding, and generator-exposure rates are computed only over restricted cases. Exact behavioral conformance measures the exact expected output class and is reported separately from safe withholding. Source-role conformance compares expected and observed evidence roles. Repetitions are not treated as independent samples; inferential tests aggregate at the case level.

## Results Subsection Replacement

Insert the final numerical results from `evaluation/publication_results/d1_d8_large_scale_v1/paper_numbers.json` and the LaTeX tables in the adjacent `tables/` directory.

## Threats-to-Validity Replacement

The evaluation remains limited by synthetic D1-D5 construction, synthetic browser-only D7 cases, a synthetic subset of D8 closures where unambiguous natural closures were not available, one provider/model configuration, and a MailEx/Enron-derived e-mail domain. The benchmark is frozen after development but was not externally administered.
As noted during peer review, the benchmark size (50 threads, 195 messages) remains modest and serves primarily as an action-oriented proof-of-concept; future evaluations must expand scale across broader corporate corpora.

## Conclusion Update

The large-scale evaluation provides a frozen, reproducible estimate of InfoBank's role-aware behavior under the D1-D8 taxonomy, while preserving clear limits on generalization and deployment claims.

## MailEx Citation

Use the bibliographic entry already present in the manuscript or the official MailEx publication metadata. Do not fabricate missing fields.

## Replacement for Development-Pilot Sentence

An earlier 53-record development pilot was used only for implementation diagnostics; the reported results are from a subsequent frozen large-scale D1-D8 evaluation.

## Machine-Readable Numbers

```json
{
  "document_by_mode": {
    "governance_only_rag": {
      "behavioral_conformance_rate": {
        "denominator": 2000,
        "numerator": 575,
        "rate": 0.2875
      },
      "controlled_failure_correctness": {
        "denominator": 2000,
        "numerator": 1600,
        "rate": 0.8
      },
      "exact_output_class_conformance": {
        "denominator": 2000,
        "numerator": 600,
        "rate": 0.3
      },
      "generation_calls": 1200,
      "generation_skipped_count": 800,
      "generator_exposure_rate": {
        "denominator": 1200,
        "numerator": 200,
        "rate": 0.166667
      },
      "permitted_answer_accuracy": {
        "denominator": 800,
        "numerator": 775,
        "rate": 0.96875
      },
      "permitted_answer_correct_rate": 0.96875,
      "prohibited_disclosure_rate": {
        "denominator": 1200,
        "numerator": 131,
        "rate": 0.109167
      },
      "protected_marker_disclosure_rate": 0.109167,
      "record_count": 2000,
      "retrieval_target_recall_at_4": {
        "denominator": 1800,
        "numerator": 1800,
        "rate": 1.0
      },
      "safe_withholding_rate": {
        "denominator": 1200,
        "numerator": 1069,
        "rate": 0.890833
      },
      "source_role_conformance": {
        "denominator": 2000,
        "numerator": 0,
        "rate": 0.0
      }
    },
    "role_aware_rag": {
      "behavioral_conformance_rate": {
        "denominator": 2000,
        "numerator": 1682,
        "rate": 0.841
      },
      "controlled_failure_correctness": {
        "denominator": 2000,
        "numerator": 2000,
        "rate": 1.0
      },
      "exact_output_class_conformance": {
        "denominator": 2000,
        "numerator": 1690,
        "rate": 0.845
      },
      "generation_calls": 490,
      "generation_skipped_count": 1510,
      "generator_exposure_rate": {
        "denominator": 1200,
        "numerator": 0,
        "rate": 0.0
      },
      "permitted_answer_accuracy": {
        "denominator": 800,
        "numerator": 482,
        "rate": 0.6025
      },
      "permitted_answer_correct_rate": 0.6025,
      "prohibited_disclosure_rate": {
        "denominator": 1200,
        "numerator": 0,
        "rate": 0.0
      },
      "protected_marker_disclosure_rate": 0.0,
      "record_count": 2000,
      "retrieval_target_recall_at_4": {
        "denominator": 1800,
        "numerator": 1800,
        "rate": 1.0
      },
      "safe_withholding_rate": {
        "denominator": 1200,
        "numerator": 1200,
        "rate": 1.0
      },
      "source_role_conformance": {
        "denominator": 2000,
        "numerator": 1920,
        "rate": 0.96
      }
    },
    "standard_rag": {
      "behavioral_conformance_rate": {
        "denominator": 2000,
        "numerator": 584,
        "rate": 0.292
      },
      "controlled_failure_correctness": {
        "denominator": 2000,
        "numerator": 800,
        "rate": 0.4
      },
      "exact_output_class_conformance": {
        "denominator": 2000,
        "numerator": 600,
        "rate": 0.3
      },
      "generation_calls": 2000,
      "generation_skipped_count": 0,
      "generator_exposure_rate": {
        "denominator": 1200,
        "numerator": 1200,
        "rate": 1.0
      },
      "permitted_answer_accuracy": {
        "denominator": 800,
        "numerator": 757,
        "rate": 0.94625
      },
      "permitted_answer_correct_rate": 0.94625,
      "prohibited_disclosure_rate": {
        "denominator": 1200,
        "numerator": 1107,
        "rate": 0.9225
      },
      "protected_marker_disclosure_rate": 0.9225,
      "record_count": 2000,
      "retrieval_target_recall_at_4": {
        "denominator": 1800,
        "numerator": 1800,
        "rate": 1.0
      },
      "safe_withholding_rate": {
        "denominator": 1200,
        "numerator": 93,
        "rate": 0.0775
      },
      "source_role_conformance": {
        "denominator": 2000,
        "numerator": 0,
        "rate": 0.0
      }
    },
    "token_budget_ablated_rag": {
      "behavioral_conformance_rate": {
        "denominator": 2000,
        "numerator": 561,
        "rate": 0.2805
      },
      "controlled_failure_correctness": {
        "denominator": 2000,
        "numerator": 800,
        "rate": 0.4
      },
      "exact_output_class_conformance": {
        "denominator": 2000,
        "numerator": 600,
        "rate": 0.3
      },
      "generation_calls": 2000,
      "generation_skipped_count": 0,
      "generator_exposure_rate": {
        "denominator": 1200,
        "numerator": 200,
        "rate": 0.166667
      },
      "permitted_answer_accuracy": {
        "denominator": 800,
        "numerator": 761,
        "rate": 0.95125
      },
      "permitted_answer_correct_rate": 0.95125,
      "prohibited_disclosure_rate": {
        "denominator": 1200,
        "numerator": 17,
        "rate": 0.014167
      },
      "protected_marker_disclosure_rate": 0.014167,
      "record_count": 2000,
      "retrieval_target_recall_at_4": {
        "denominator": 1800,
        "numerator": 1800,
        "rate": 1.0
      },
      "safe_withholding_rate": {
        "denominator": 1200,
        "numerator": 1183,
        "rate": 0.985833
      },
      "source_role_conformance": {
        "denominator": 2000,
        "numerator": 0,
        "rate": 0.0
      }
    }
  },
  "evidence_primary": {
    "D6_open_action_accuracy": 0.89,
    "D7_browser_only_false_action_rate": 0.0,
    "D8_NONCLOSING_open_status_accuracy": 0.8,
    "D8_closure_status_accuracy": 0.58,
    "EvidenceUnit_role_accuracy": 0.895588,
    "clean_run_determinism": {
      "case_pass_consistent": {
        "denominator": 340,
        "numerator": 340,
        "rate": 1.0,
        "wilson_95": {
          "high": 1.0,
          "low": 0.988828
        }
      },
      "denominator": 340,
      "numerator": 340,
      "rate": 1.0,
      "status_consistent": {
        "denominator": 340,
        "numerator": 340,
        "rate": 1.0,
        "wilson_95": {
          "high": 1.0,
          "low": 0.988828
        }
      },
      "wilson_95": {
        "high": 1.0,
        "low": 0.988828
      }
    },
    "triplet_consistency": {
      "denominator": 100,
      "numerator": 58,
      "rate": 0.58,
      "wilson_95": {
        "high": 0.672016,
        "low": 0.482065
      }
    }
  },
  "record_counts": {
    "document_records": 8000,
    "evidence_records": 1020,
    "total_records": 9020
  },
  "source": "evaluation/results large-scale combined_metrics.json"
}
```
