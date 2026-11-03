#!/usr/bin/env python3
"""Compare predicted candidates against accepted gold sample rows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def accepted(row: dict[str, Any]) -> bool:
    return row.get("manual_status") == "accepted" or row.get("status") == "accepted"


def gold_value(row: dict[str, Any], manual_field: str, normal_field: str) -> Any:
    value = row.get(manual_field)
    if value is not None and value != "":
        if normal_field == "correct_answer" and isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value
    return row.get(normal_field)


def normalize_answer(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return list(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test predictions against accepted gold sample rows.")
    parser.add_argument("--pred", required=True)
    parser.add_argument("--gold", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pred_rows = read_jsonl(Path(args.pred))
    gold_rows = [row for row in read_jsonl(Path(args.gold)) if accepted(row)]
    if not gold_rows:
        print("No accepted gold rows yet.")
        print("total_gold: 0")
        return

    pred_by_id = {row.get("question_id"): row for row in pred_rows}
    mismatches: list[str] = []
    missing: list[str] = []
    matched = 0

    for gold in gold_rows:
        question_id = gold.get("question_id")
        pred = pred_by_id.get(question_id)
        if not pred:
            missing.append(str(question_id))
            continue
        row_mismatches: list[str] = []
        comparisons = [
            ("keep_for_training", gold_value(gold, "manual_keep_for_training", "keep_for_training"), pred.get("keep_for_training")),
            ("question_type", gold_value(gold, "manual_question_type", "question_type"), pred.get("question_type")),
            ("is_reading", gold.get("is_reading"), pred.get("is_reading")),
        ]
        for field, expected, actual in comparisons:
            if expected != actual:
                row_mismatches.append(f"{field}: expected {expected!r}, got {actual!r}")
        expected_answer = normalize_answer(gold_value(gold, "manual_correct_answer", "correct_answer"))
        actual_answer = normalize_answer(pred.get("correct_answer"))
        if expected_answer != actual_answer:
            row_mismatches.append(f"correct_answer: expected {expected_answer!r}, got {actual_answer!r}")
        if row_mismatches:
            mismatches.append(f"{question_id}: " + "; ".join(row_mismatches))
        else:
            matched += 1

    print(f"total_gold: {len(gold_rows)}")
    print(f"matched: {matched}")
    print(f"mismatched: {len(mismatches)}")
    print(f"missing: {len(missing)}")
    if mismatches:
        print("mismatch details:")
        for item in mismatches:
            print(f"- {item}")
    if missing:
        print("missing details:")
        for item in missing:
            print(f"- {item}")
    if mismatches or missing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

