from __future__ import annotations

import unittest

from evaluate_results import score_result
from experiment_core import ANSWER_TYPES, load_benchmark, parse_model_output


ATTRIBUTE_TYPES = {
    "ACTOR_RESPONSIBILITY": "TASK_ATTRIBUTE_MAP",
    "REQUESTER": "TASK_ATTRIBUTE_MAP",
    "DEADLINE": "TASK_ATTRIBUTE_MAP",
    "WAITING_FOR": "TASK_ATTRIBUTE_MAP",
    "BLOCKED_BY": "TASK_ATTRIBUTE_MAP",
}


def perfect_prediction(question: dict, task_evidence: dict[tuple[str, str], set[str]]) -> dict:
    gold = question["gold_structured"]
    family = question["question_family"]
    tasks = []
    for gold_task in gold.get("tasks", []):
        task = dict(gold_task)
        if "events" in task:
            task["events"] = [dict(event) for event in task["events"]]
        task["evidence_message_ids"] = sorted(
            task_evidence.get((question["pilot_id"], task.get("task_id")), set())
        )
        tasks.append(task)
    if family in {"OPEN_TASKS", "CLOSED_TASKS"}:
        answer_type = "TASK_SET"
    elif family == "TASK_HISTORY":
        answer_type = "TASK_HISTORY"
    elif family == "NO_TASK_CONTROL":
        answer_type = "NO_TASK"
    else:
        answer_type = ATTRIBUTE_TYPES[family]
    return {
        "answer_type": answer_type,
        "tasks": tasks,
        "none": bool(gold.get("none", False)),
        "evidence_message_ids": list(question["evidence_message_ids"]),
        "controlled_failure": False,
        "failure_reason": None,
    }


class ExperimentEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.benchmark = load_benchmark()
        cls.task_evidence = {
            (row["pilot_id"], row["task_id"]): set(row["evidence_message_ids"])
            for row in cls.benchmark["histories"]
        }
        cls.message_ids = {row["message_id"] for row in cls.benchmark["evidence"]}

    def test_perfect_structured_predictions_score_exactly(self) -> None:
        failures = []
        for question in self.benchmark["questions"]:
            inference = {
                "question_id": question["question_id"],
                "question_family": question["question_family"],
                "condition": "ORACLE_TASK_STATE_RAG",
                "parsed_output": perfect_prediction(question, self.task_evidence),
                "retrieved_message_ids": sorted(self.message_ids),
                "error": None,
            }
            scored = score_result(
                inference, question, self.task_evidence, self.message_ids
            )
            if not scored["exact_correct"] or scored["structured_score"] != 1.0:
                failures.append(question["question_id"])
        self.assertEqual([], failures)

    def test_parser_recognizes_every_answer_type(self) -> None:
        for answer_type in ANSWER_TYPES:
            parsed, error = parse_model_output(
                '{"answer_type":"%s","tasks":[],"evidence_message_ids":[]}' % answer_type
            )
            self.assertIsNone(error)
            self.assertEqual(answer_type, parsed["answer_type"])

    def test_empty_history_prediction_scores_zero(self) -> None:
        question = next(
            row for row in self.benchmark["questions"] if row["question_family"] == "TASK_HISTORY"
        )
        inference = {
            "question_id": question["question_id"],
            "question_family": question["question_family"],
            "condition": "STANDARD_RAG",
            "parsed_output": {
                "answer_type": "INSUFFICIENT_EVIDENCE",
                "tasks": [],
                "evidence_message_ids": [],
                "controlled_failure": True,
            },
            "retrieved_message_ids": [],
            "error": None,
        }
        scored = score_result(inference, question, self.task_evidence, self.message_ids)
        self.assertFalse(scored["exact_correct"])
        self.assertEqual(0.0, scored["structured_score"])

    def test_truncated_json_recovers_only_complete_values(self) -> None:
        raw = (
            '{"answer_type":"TASK_SET","tasks":['
            '{"task_id":"T1","events":[],"evidence_message_ids":["m::turn_0"]},'
            '{"task_id":"unfinished'
        )
        parsed, error = parse_model_output(raw)
        self.assertIsNone(error)
        self.assertEqual("T1", parsed["tasks"][0]["task_id"])
        self.assertEqual(1, len(parsed["tasks"]))
        self.assertEqual("closed_at_last_complete_json_boundary", parsed["_parser_recovery"])

    def test_no_task_on_positive_question_is_not_a_correct_abstention(self) -> None:
        question = next(
            row
            for row in self.benchmark["questions"]
            if row["question_family"] == "OPEN_TASKS" and not row["negative_control"]
        )
        inference = {
            "question_id": question["question_id"],
            "question_family": question["question_family"],
            "condition": "STANDARD_RAG",
            "parsed_output": {
                "answer_type": "NO_TASK",
                "tasks": [],
                "none": True,
                "evidence_message_ids": [],
                "controlled_failure": False,
            },
            "retrieved_message_ids": [],
            "error": None,
        }
        scored = score_result(inference, question, self.task_evidence, self.message_ids)
        self.assertFalse(scored["controlled_failure_correct"])


if __name__ == "__main__":
    unittest.main()
