from __future__ import annotations

import argparse
import json
from pathlib import Path
from pydantic import TypeAdapter
from .evaluator import evaluate_records
from .schemas import EvaluationReport, HumanAnnotationRecord, SystemClaimRecord


def _load_records[T](path: Path, adapter: TypeAdapter[list[T]]) -> list[T]:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    if path.suffix.lower() == ".jsonl":
        items = [json.loads(line) for line in raw.splitlines() if line.strip()]
        return adapter.validate_python(items)
    return adapter.validate_json(raw)


def _render_markdown(report: EvaluationReport) -> str:
    lines = [
        "# CFAF Evidence Evaluation Report (PR3)",
        "",
        "## Summary Counts",
        f"- Total system records: {report.total_system_records}",
        f"- Total annotations: {report.total_annotations}",
        f"- Evaluated records: {report.evaluated_records}",
        f"- Missing annotations: {report.missing_annotations}",
        f"- Unapproved annotations: {report.unapproved_annotations}",
        f"- Unmatched annotations: {report.unmatched_annotations}",
        f"- Runtime errors: {report.runtime_errors}",
        "",
        "## Metrics",
        "| Dimension | Evaluated | Correct | Accuracy |",
        "| :--- | :---: | :---: | :---: |",
    ]
    for name, metric in report.metrics.items():
        acc_str = f"{metric.accuracy:.4f}" if metric.accuracy is not None else "N/A"
        lines.append(
            f"| `{name}` | {metric.evaluated_count} | {metric.correct_count} | {acc_str} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline deterministic evaluator for CFAF evidence validation (PR3)."
    )
    parser.add_argument(
        "--inputs",
        type=Path,
        required=True,
        help="Path to system output JSON or JSONL file.",
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        required=True,
        help="Path to human annotations JSON or JSONL file.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Path to output JSON report.",
    )
    parser.add_argument(
        "--md-out",
        type=Path,
        required=False,
        default=None,
        help="Optional path to output Markdown report.",
    )
    args = parser.parse_args()

    sys_adapter = TypeAdapter(list[SystemClaimRecord])
    ann_adapter = TypeAdapter(list[HumanAnnotationRecord])

    system_records = _load_records(args.inputs, sys_adapter)
    annotations = _load_records(args.annotations, ann_adapter)

    report = evaluate_records(system_records, annotations)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report.model_dump(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if args.md_out is not None:
        args.md_out.parent.mkdir(parents=True, exist_ok=True)
        args.md_out.write_text(_render_markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()