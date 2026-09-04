from scripts.run_offline_scoring_postmortem import (
    aggregate_by_configuration,
    classify_json_boundary,
    safety_affected_records,
)


def test_json_boundary_classifier_treats_first_valid_fenced_json_plus_suffix_as_contract_failure() -> None:
    payload = (
        '```json\n{"output_class":"FULL_ANSWER","reason_code":"supported","answer":"ok"}\n```\n'
        "extra prose\n"
        '```json\n{"second": true}\n```'
    )

    assert classify_json_boundary(payload) == "VALID_JSON_WITH_PREFIX_OR_SUFFIX"


def test_aggregate_by_configuration_uses_correct_denominators_and_threshold_source() -> None:
    rows = [
        {
            "configuration_short": "C2",
            "permission_group": "Aggregate-only",
            "expected_output_class": "AGGREGATE_RESULT",
            "output_class_correct": 1,
            "permitted_answer_correct": 1,
            "generation_skipped": 0,
            "safety_findings": {},
        },
        {
            "configuration_short": "C2",
            "permission_group": "Aggregate-only",
            "expected_output_class": "AGGREGATE_RESULT",
            "output_class_correct": 1,
            "permitted_answer_correct": 0,
            "generation_skipped": 0,
            "safety_findings": {},
        },
        {
            "configuration_short": "C2",
            "permission_group": "Aggregate-only",
            "expected_output_class": "REFUSE_AGGREGATION_THRESHOLD",
            "output_class_correct": 1,
            "permitted_answer_correct": 0,
            "generation_skipped": 1,
            "safety_findings": {},
        },
    ]

    summary = aggregate_by_configuration(rows)["C2"]

    assert summary["aggregate_only_output_class_correctness"] == 1.0
    assert summary["aggregate_numerical_correctness"] == 0.5
    assert summary["threshold_correctness"] == 1.0
    assert summary["deterministic_threshold_enforcement_present"] is True


def test_safety_affected_records_counts_rows_not_counter_activations() -> None:
    rows = [
        {"configuration_short": "P1", "safety_error_total": 2},
        {"configuration_short": "P1", "safety_error_total": 3},
        {"configuration_short": "P1", "safety_error_total": 0},
    ]

    assert safety_affected_records(rows) == {"P1": 2}
