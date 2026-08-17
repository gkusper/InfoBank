#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from mailex_utils import (
    EVENT_DELIVER_ACTION_DATA,
    EVENT_REQUEST_ACTION,
    SPLITS,
    event_argument_spans,
    iter_split_files,
    load_json,
    resolve_data_root,
    turn_index,
    write_json,
)


def inspect(source: str | Path) -> dict:
    root = resolve_data_root(source)
    split_counts = {split: len(list((root / split).glob("*.json"))) for split in SPLITS}
    event_counts: Counter[str] = Counter()
    argument_names: dict[str, set[str]] = {}
    request_with_required_args = 0
    request_action_count = 0
    deliver_action_count = 0
    total_turns = 0
    thread_lengths: list[int] = []
    candidate_threads_with_later_action = 0

    for split, path in iter_split_files(root):
        data = load_json(path)
        turns = data.get("events", {})
        total_turns += len(turns)
        thread_lengths.append(len(turns))
        thread_has_request_later_action = False
        for turn_id, events in turns.items():
            for event_type, event_data in events.items():
                event_counts[event_type] += len(event_data.get("labels") or [1])
                spans = event_argument_spans(data, turn_id, event_type)
                argument_names.setdefault(event_type, set()).update(spans)
            if EVENT_REQUEST_ACTION in events:
                request_action_count += 1
                spans = event_argument_spans(data, turn_id, EVENT_REQUEST_ACTION)
                if spans.get("Action Description") and spans.get("Action Members") and spans.get("Action Date"):
                    request_with_required_args += 1
                later_turns = [
                    other_turn
                    for other_turn, other_events in turns.items()
                    if turn_index(other_turn) > turn_index(turn_id)
                    and (EVENT_REQUEST_ACTION in other_events or EVENT_DELIVER_ACTION_DATA in other_events)
                ]
                if later_turns:
                    thread_has_request_later_action = True
            if EVENT_DELIVER_ACTION_DATA in events:
                deliver_action_count += 1
        if thread_has_request_later_action:
            candidate_threads_with_later_action += 1

    stats = {
        "data_root": str(root),
        "split_thread_counts": split_counts,
        "total_threads": sum(split_counts.values()),
        "total_email_turns": total_turns,
        "event_counts": dict(sorted(event_counts.items())),
        "event_type_names": sorted(event_counts),
        "argument_names": {key: sorted(values) for key, values in sorted(argument_names.items())},
        "request_action_events": request_action_count,
        "deliver_action_data_events": deliver_action_count,
        "request_action_with_action_description_members_date": request_with_required_args,
        "thread_lengths": {
            "min": min(thread_lengths) if thread_lengths else 0,
            "max": max(thread_lengths) if thread_lengths else 0,
            "avg": round(sum(thread_lengths) / len(thread_lengths), 3) if thread_lengths else 0,
        },
        "candidate_threads_with_request_and_later_action_related_messages": candidate_threads_with_later_action,
    }
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect the local MailEx dataset structure and annotations.")
    parser.add_argument("--source", default="data/external/mailex/extracted/data", help="MailEx data root or parent directory.")
    parser.add_argument("--json-out", default="", help="Optional JSON output path.")
    args = parser.parse_args()
    stats = inspect(args.source)
    if args.json_out:
        write_json(Path(args.json_out), stats)
    for key, value in stats.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
