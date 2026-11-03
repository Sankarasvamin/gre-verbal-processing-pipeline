#!/usr/bin/env python3
"""Report quality signals for AI-suggested answers."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def answer_text(answer: Any) -> str:
    if answer is None:
        return "null"
    if isinstance(answer, list):
        return ",".join(str(item) for item in answer)
    return str(answer)


def needs_priority_review(row: dict[str, Any]) -> bool:
    if row.get("ai_answer_confidence") == "low":
        return True
    if not row.get("vocab_items"):
        return True
    if row.get("question_type") == "sentence_equivalence" and len(row.get("ai_suggested_answer") or []) != 2:
        return True
    if row.get("notes"):
        return True
    return False


def write_report(path: Path, rows: list[dict[str, Any]]) -> None:
    ai_rows = [row for row in rows if row.get("answer_mode") == "ai_suggested"]
    confidence_counts = Counter(row.get("ai_answer_confidence") for row in ai_rows)
    type_counts = Counter(row.get("question_type") for row in ai_rows)
    low_rows = [row for row in ai_rows if row.get("ai_answer_confidence") == "low"]
    notes_rows = [row for row in ai_rows if row.get("notes")]
    priority_rows = [row for row in ai_rows if needs_priority_review(row)]

    lines = [
        "# AI Answer Quality Report",
        "",
        f"- ai_suggested total: {len(ai_rows)}",
        f"- confidence distribution: {dict(confidence_counts)}",
        f"- question_type distribution: {dict(type_counts)}",
        "",
        "## Per Question",
        "",
    ]
    for row in ai_rows:
        lines.extend(
            [
                f"- question_id: {row.get('question_id')}",
                f"  question_type: {row.get('question_type')}",
                f"  ai_suggested_answer: {answer_text(row.get('ai_suggested_answer'))}",
                f"  ai_answer_confidence: {row.get('ai_answer_confidence')}",
                f"  ai_answer_reasoning_brief: {row.get('ai_answer_reasoning_brief')}",
                f"  vocab_items_count: {len(row.get('vocab_items') or [])}",
                "",
            ]
        )

    lines.extend(["## Low Confidence", ""])
    lines.extend(f"- {row.get('question_id')}" for row in low_rows) if low_rows else lines.append("- none")
    lines.extend(["", "## Notes Non-Empty", ""])
    lines.extend(f"- {row.get('question_id')}: {row.get('notes')}" for row in notes_rows) if notes_rows else lines.append("- none")
    lines.extend(["", "## Priority Manual Review", ""])
    if priority_rows:
        for row in priority_rows:
            reasons: list[str] = []
            if row.get("ai_answer_confidence") == "low":
                reasons.append("confidence=low")
            if not row.get("vocab_items"):
                reasons.append("vocab_items empty")
            if row.get("question_type") == "sentence_equivalence" and len(row.get("ai_suggested_answer") or []) != 2:
                reasons.append("sentence_equivalence answer count != 2")
            if row.get("notes"):
                reasons.append("notes non-empty")
            lines.append(f"- {row.get('question_id')}: {', '.join(reasons)}")
    else:
        lines.append("- none")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report AI answer quality signals.")
    parser.add_argument("--questions", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = read_jsonl(Path(args.questions))
    write_report(Path(args.output), rows)
    print(f"Wrote AI answer quality report to {args.output}")


if __name__ == "__main__":
    main()

