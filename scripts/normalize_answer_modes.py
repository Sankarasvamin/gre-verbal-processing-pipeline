#!/usr/bin/env python3
"""Normalize answer-source fields while preserving legacy correct_answer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def non_empty_answer(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list) and value:
        return value
    return None


def valid_answer(answer: list[str] | None, row: dict[str, Any]) -> bool:
    if not answer:
        return False
    labels = {str(option.get("label")).upper() for option in row.get("options") or []}
    return all(str(label).upper() in labels for label in answer)


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    legacy_correct = non_empty_answer(item.get("correct_answer"))
    candidate_official = non_empty_answer(item.get("official_answer")) or legacy_correct
    official_answer = candidate_official if valid_answer(candidate_official, item) else None
    manual_answer = non_empty_answer(item.get("manual_answer"))
    ai_answer = non_empty_answer(item.get("ai_suggested_answer"))

    item["official_answer"] = official_answer
    if official_answer:
        item["official_answer_status"] = "matched"
    elif candidate_official:
        item["official_answer_status"] = "conflicted"
        existing_notes = item.get("answer_match_notes") or ""
        item["answer_match_notes"] = (
            f"{existing_notes} official answer labels {candidate_official} do not match parsed option labels."
        ).strip()
    else:
        item["official_answer_status"] = "missing"
    item["manual_answer"] = manual_answer
    item.setdefault("manual_answer_notes", None)
    item["ai_suggested_answer"] = ai_answer
    item["ai_answer_confidence"] = item.get("ai_answer_confidence") or ("none" if not ai_answer else "medium")
    item.setdefault("ai_answer_reasoning_brief", None)
    item.setdefault("answer_conflict_flag", False)

    if manual_answer:
        item["answer_mode"] = "manual"
        item["correct_answer"] = manual_answer
    elif official_answer:
        item["answer_mode"] = "official"
        item["correct_answer"] = official_answer
    elif ai_answer:
        item["answer_mode"] = "ai_suggested"
        item["correct_answer"] = ai_answer
    else:
        item["answer_mode"] = "none"
        item["correct_answer"] = None
    return item


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize answer mode fields.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = [normalize_row(row) for row in read_jsonl(Path(args.input))]
    write_jsonl(Path(args.output), rows)
    print(f"Wrote {len(rows)} normalized rows to {args.output}")


if __name__ == "__main__":
    main()
