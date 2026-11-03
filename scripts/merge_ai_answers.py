#!/usr/bin/env python3
"""Merge AI suggested answers into normalized question JSONL."""

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


def answer_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list) and value:
        return value
    return None


def merge_row(row: dict[str, Any], ai_row: dict[str, Any] | None) -> dict[str, Any]:
    item = dict(row)
    if not ai_row:
        return item

    ai_answer = answer_list(ai_row.get("ai_suggested_answer"))
    item["ai_suggested_answer"] = ai_answer
    item["ai_answer_confidence"] = ai_row.get("ai_answer_confidence") or ("none" if not ai_answer else "medium")
    item["ai_answer_reasoning_brief"] = ai_row.get("ai_answer_reasoning_brief")
    if ai_row.get("vocab_items") is not None:
        item["vocab_items"] = ai_row.get("vocab_items")
    if ai_row.get("notes") is not None:
        item["notes"] = ai_row.get("notes")

    manual_answer = answer_list(item.get("manual_answer"))
    official_answer = answer_list(item.get("official_answer"))
    item["answer_conflict_flag"] = False

    if official_answer and ai_answer and official_answer != ai_answer:
        item["answer_conflict_flag"] = True
        existing_notes = item.get("answer_match_notes") or ""
        conflict_note = f"AI suggested answer {ai_answer} conflicts with official_answer {official_answer}."
        item["answer_match_notes"] = f"{existing_notes} {conflict_note}".strip()

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
    parser = argparse.ArgumentParser(description="Merge AI answers into question JSONL.")
    parser.add_argument("--questions", required=True)
    parser.add_argument("--ai-answers", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = read_jsonl(Path(args.questions))
    ai_rows = {row.get("question_id"): row for row in read_jsonl(Path(args.ai_answers))}
    merged = [merge_row(row, ai_rows.get(row.get("question_id"))) for row in rows]
    write_jsonl(Path(args.output), merged)
    print(f"Wrote {len(merged)} rows to {args.output}")
    print(f"Merged AI answers: {sum(1 for row in merged if row.get('ai_suggested_answer'))}")


if __name__ == "__main__":
    main()

