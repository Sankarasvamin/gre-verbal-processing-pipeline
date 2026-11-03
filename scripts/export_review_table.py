#!/usr/bin/env python3
"""Export a compact TSV table for manual review."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


FIELDS = [
    "question_id",
    "source_page_start",
    "pdf_section_id",
    "answer_key_section_id",
    "question_number",
    "question_type",
    "is_reading",
    "keep_for_training",
    "correct_answer",
    "official_answer",
    "official_answer_status",
    "ai_suggested_answer",
    "ai_answer_confidence",
    "answer_mode",
    "manual_answer",
    "answer_conflict_flag",
    "ai_answer_reasoning_brief",
    "section_mapping_status",
    "answer_match_confidence",
    "stem_clean_short",
    "options_short",
    "manual_keep_for_training",
    "manual_correct_answer",
    "manual_question_type",
    "manual_status",
    "manual_notes",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def shorten(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def options_short(options: list[dict[str, Any]]) -> str:
    parts = [f"{option.get('label')}. {option.get('text_clean')}" for option in options or []]
    return shorten(" | ".join(parts), 300)


def row_for_export(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "question_id": row.get("question_id"),
        "source_page_start": row.get("source_page_start"),
        "pdf_section_id": row.get("pdf_section_id"),
        "answer_key_section_id": row.get("answer_key_section_id"),
        "question_number": row.get("question_number"),
        "question_type": row.get("question_type"),
        "is_reading": row.get("is_reading"),
        "keep_for_training": row.get("keep_for_training"),
        "correct_answer": ",".join(row.get("correct_answer") or []),
        "official_answer": ",".join(row.get("official_answer") or []),
        "official_answer_status": row.get("official_answer_status"),
        "ai_suggested_answer": ",".join(row.get("ai_suggested_answer") or []),
        "ai_answer_confidence": row.get("ai_answer_confidence"),
        "answer_mode": row.get("answer_mode"),
        "manual_answer": ",".join(row.get("manual_answer") or []),
        "answer_conflict_flag": row.get("answer_conflict_flag"),
        "ai_answer_reasoning_brief": shorten(row.get("ai_answer_reasoning_brief") or "", 180),
        "section_mapping_status": row.get("section_mapping_status"),
        "answer_match_confidence": row.get("answer_match_confidence"),
        "stem_clean_short": shorten(row.get("stem_clean") or "", 150),
        "options_short": options_short(row.get("options") or []),
        "manual_keep_for_training": "",
        "manual_correct_answer": "",
        "manual_question_type": "",
        "manual_status": "",
        "manual_notes": "",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export review TSV from question JSONL.")
    parser.add_argument("--questions", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = read_jsonl(Path(args.questions))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row_for_export(row))
    print(f"Wrote {len(rows)} rows to {output}")


if __name__ == "__main__":
    main()
