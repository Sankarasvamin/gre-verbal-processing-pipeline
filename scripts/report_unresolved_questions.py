#!/usr/bin/env python3
"""Report questions that still block accepted training data."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def compact(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def suspected_section(notes: str | None) -> str:
    if not notes:
        return ""
    match = re.search(r"suspected to map to answer section\s+(\w+)", notes, re.IGNORECASE)
    return match.group(1) if match else ""


def needs_review(row: dict[str, Any]) -> bool:
    if row.get("keep_for_training") and not row.get("correct_answer"):
        return True
    if row.get("section_mapping_status") == "unresolved":
        return True
    if row.get("answer_match_confidence") in {"none", "low"}:
        return True
    return False


def write_report(path: Path, rows: list[dict[str, Any]]) -> int:
    unresolved = [row for row in rows if needs_review(row)]
    priority = [row for row in unresolved if row.get("keep_for_training") and not row.get("correct_answer")]
    lines = [
        "# Unresolved Questions Report",
        "",
        f"- unresolved_or_low_confidence_count: {len(unresolved)}",
        f"- priority_keep_without_answer_count: {len(priority)}",
        "",
    ]
    for index, row in enumerate(unresolved, start=1):
        lines.extend(
            [
                f"## {index}. {row.get('question_id')}",
                "",
                f"- page: {row.get('source_page_start')}",
                f"- pdf_section_id: {row.get('pdf_section_id')}",
                f"- question_number: {row.get('question_number')}",
                f"- suspected answer section: {suspected_section(row.get('answer_match_notes'))}",
                f"- keep_for_training: {row.get('keep_for_training')}",
                f"- section_mapping_status: {row.get('section_mapping_status')}",
                f"- answer_match_confidence: {row.get('answer_match_confidence')}",
                f"- answer_match_notes: {row.get('answer_match_notes')}",
                "",
                "### Stem",
                "",
                row.get("stem_clean") or "",
                "",
                "### Options",
                "",
            ]
        )
        for option in row.get("options") or []:
            lines.append(f"{option.get('label')}. {option.get('text_clean')}")
        lines.extend(
            [
                "",
                "### Raw block short",
                "",
                "```text",
                compact(row.get("raw_block") or "", 800),
                "```",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return len(priority)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report unresolved question candidates.")
    parser.add_argument("--questions", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = read_jsonl(Path(args.questions))
    priority_count = write_report(Path(args.output), rows)
    print(f"Wrote unresolved report to {args.output}")
    print(f"Priority keep_for_training without answer: {priority_count}")


if __name__ == "__main__":
    main()

