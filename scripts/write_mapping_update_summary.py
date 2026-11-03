#!/usr/bin/env python3
"""Write a summary after applying section mapping."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_section_mapping import read_simple_mapping_yaml  # noqa: E402


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write mapping update summary markdown.")
    parser.add_argument("--questions", required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--previous-matched", type=int, default=14)
    parser.add_argument("--previous-keep-unmatched", type=int, default=15)
    return parser.parse_args()


def section_effectiveness(rows: list[dict[str, Any]], mappings: dict[str, str | None], pdf_sec: str, answer_sec: str) -> str:
    configured = mappings.get(pdf_sec)
    section_rows = [row for row in rows if str(row.get("pdf_section_id")) == pdf_sec]
    section_keep = sum(bool(row.get("keep_for_training")) for row in section_rows)
    section_matched = sum(bool(row.get("correct_answer")) for row in section_rows)
    if configured == answer_sec:
        verdict = "configured and effective" if section_matched else "configured but no answers matched"
    elif configured is None:
        verdict = "not configured; mapping remains unresolved"
    else:
        verdict = f"configured to {configured}, not expected {answer_sec}"
    return (
        f"- pdf_section_id `{pdf_sec}` -> answer_key_section_id `{answer_sec}`: "
        f"{verdict}; rows={len(section_rows)}, keep={section_keep}, matched={section_matched}"
    )


def main() -> None:
    args = parse_args()
    rows = read_jsonl(Path(args.questions))
    mapping = read_simple_mapping_yaml(Path(args.mapping))
    mappings: dict[str, str | None] = mapping.get("mappings") or {}
    notes: dict[str, str | None] = mapping.get("notes") or {}

    total = len(rows)
    keep = sum(bool(row.get("keep_for_training")) for row in rows)
    matched = sum(bool(row.get("correct_answer")) for row in rows)
    unmatched = total - matched
    keep_matched = sum(bool(row.get("keep_for_training")) and bool(row.get("correct_answer")) for row in rows)
    keep_unmatched = sum(bool(row.get("keep_for_training")) and not bool(row.get("correct_answer")) for row in rows)
    status_counts = Counter(row.get("section_mapping_status") for row in rows)
    confidence_counts = Counter(row.get("answer_match_confidence") for row in rows)
    unresolved = [
        row for row in rows
        if row.get("section_mapping_status") == "unresolved" or row.get("answer_match_confidence") in {"none", "low"}
    ]
    configured_missing = [
        row for row in rows
        if row.get("section_mapping_status") == "configured" and not row.get("correct_answer")
    ]

    lines = [
        "# Mapping Update Summary",
        "",
        "## Current Mappings",
        "",
        f"- source_pdf_relpath: `{mapping.get('source_pdf_relpath')}`",
    ]
    for key in sorted(mappings, key=str):
        lines.append(f"- pdf_section_id `{key}` -> answer_key_section_id `{mappings[key]}`; note: {notes.get(key, '')}")

    lines.extend(
        [
            "",
            "## Match Statistics",
            "",
            f"- mapped JSONL total rows: {total}",
            f"- keep_for_training=true total: {keep}",
            f"- matched answers: {matched}",
            f"- unmatched answers: {unmatched}",
            f"- keep_for_training=true and matched answers: {keep_matched}",
            f"- keep_for_training=true but unmatched answers: {keep_unmatched}",
            f"- section_mapping_status distribution: {dict(status_counts)}",
            f"- answer_match_confidence distribution: {dict(confidence_counts)}",
            f"- previous matched answers before this rerun: {args.previous_matched}",
            f"- matched answer delta: {matched - args.previous_matched}",
            f"- previous keep_for_training=true but unmatched answers: {args.previous_keep_unmatched}",
            f"- keep unmatched delta: {keep_unmatched - args.previous_keep_unmatched}",
            "",
            "## Configured Mapping Missing Question Numbers",
            "",
        ]
    )
    if configured_missing:
        for row in configured_missing:
            lines.append(
                f"- {row.get('question_id')} page {row.get('source_page_start')} "
                f"pdf_section_id={row.get('pdf_section_id')} "
                f"answer_key_section_id={row.get('answer_key_section_id')} "
                f"question_number={row.get('question_number')} notes={row.get('answer_match_notes')}"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Section 3->2 and 5->4 Effectiveness", ""])
    lines.append(section_effectiveness(rows, mappings, "3", "2"))
    lines.append(section_effectiveness(rows, mappings, "5", "4"))

    lines.extend(["", "## Still Unresolved Rows", ""])
    if unresolved:
        for row in unresolved:
            lines.append(
                f"- {row.get('question_id')} page={row.get('source_page_start')} "
                f"pdf_section_id={row.get('pdf_section_id')} q={row.get('question_number')} "
                f"keep={row.get('keep_for_training')} status={row.get('section_mapping_status')} "
                f"confidence={row.get('answer_match_confidence')}"
            )
    else:
        lines.append("- none")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote mapping update summary to {output}")
    print(f"matched={matched} keep_unmatched={keep_unmatched} unresolved={len(unresolved)} configured_missing={len(configured_missing)}")


if __name__ == "__main__":
    main()

