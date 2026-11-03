#!/usr/bin/env python3
"""Diagnose question section ids against answer-key section ids."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PDF_SECTION_RE = re.compile(r"Section\s+(\d{1,3})\s+of\s+\d{1,3}", re.IGNORECASE)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def pdf_section_id(row: dict[str, Any]) -> str | None:
    match = PDF_SECTION_RE.search(row.get("raw_block") or "")
    return match.group(1) if match else None


def compact_counter(counter: Counter[Any]) -> str:
    return ", ".join(f"{key}: {value}" for key, value in sorted(counter.items(), key=lambda item: str(item[0])))


def infer_hypotheses(rows: list[dict[str, Any]], answer_sections: dict[str, Any]) -> list[str]:
    hypotheses: list[str] = []
    by_pdf_section: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        section = pdf_section_id(row)
        if section and row.get("keep_for_training"):
            by_pdf_section[section].append(row)

    for section, section_rows in sorted(by_pdf_section.items()):
        question_numbers = {str(row.get("question_number")) for row in section_rows}
        if section in answer_sections:
            hypotheses.append(f"- hypothesis: PDF section {section} may correspond to answer key section {section} by exact section number.")
            continue
        overlaps = []
        for answer_section, answer_map in answer_sections.items():
            overlaps.append((len(question_numbers & set(answer_map)), answer_section))
        overlaps.sort(reverse=True)
        if overlaps:
            best_overlap, best_section = overlaps[0]
            second = overlaps[1][0] if len(overlaps) > 1 else 0
            confidence = "weak" if best_overlap < second + 3 else "possible"
            hypotheses.append(
                f"- hypothesis ({confidence}): PDF section {section} may correspond to answer key section {best_section} "
                f"by question-number overlap {best_overlap}; second best overlap {second}."
            )
        else:
            hypotheses.append(f"- hypothesis: PDF section {section} has no answer key section candidate.")
    return hypotheses


def write_report(path: Path, rows: list[dict[str, Any]], answer_key: dict[str, Any]) -> None:
    answer_sections: dict[str, dict[str, list[str]]] = answer_key.get("sections") or {}
    by_section: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_section[str(row.get("section_id"))].append(row)

    keep_by_section = Counter(str(row.get("section_id")) for row in rows if row.get("keep_for_training"))
    pdf_section_counts = Counter(pdf_section_id(row) or "unknown" for row in rows)
    matched_patterns = []
    failed_patterns = []
    needs_manual = []

    for row in rows:
        section = pdf_section_id(row)
        question_number = str(row.get("question_number") or "")
        exact_possible = bool(section and section in answer_sections and question_number in answer_sections[section])
        current_matched = bool(row.get("correct_answer"))
        pattern = (
            f"page {row.get('source_page_start')}, section_id={row.get('section_id')}, "
            f"pdf_section_id={section}, q={question_number}, type={row.get('question_type')}, "
            f"keep={row.get('keep_for_training')}"
        )
        if current_matched or exact_possible:
            matched_patterns.append(f"- {pattern}")
        else:
            failed_patterns.append(f"- {pattern}")
            if row.get("keep_for_training"):
                needs_manual.append(f"- {row.get('question_id')} page {row.get('source_page_start')} q{question_number}")

    lines = [
        "# Section Alignment Diagnosis",
        "",
        "## Candidate Section IDs",
        "",
        f"- section_id counts: {compact_counter(Counter(str(row.get('section_id')) for row in rows))}",
        f"- detected pdf_section_id counts: {compact_counter(pdf_section_counts)}",
        "",
        "## Per section_id Details",
        "",
    ]
    for section_id, section_rows in sorted(by_section.items()):
        question_numbers = [str(row.get("question_number")) for row in section_rows]
        type_counts = Counter(row.get("question_type") for row in section_rows)
        lines.extend(
            [
                f"### {section_id}",
                "",
                f"- candidate_count: {len(section_rows)}",
                f"- keep_for_training_count: {keep_by_section.get(section_id, 0)}",
                f"- question_numbers: {question_numbers}",
                f"- question_type_counts: {dict(type_counts)}",
                "",
            ]
        )

    lines.extend(
        [
            "## Answer Key Sections",
            "",
            f"- sections: {sorted(answer_sections)}",
        ]
    )
    for section, answer_map in sorted(answer_sections.items()):
        lines.append(f"- section {section}: {len(answer_map)} answers, question_numbers={list(answer_map)}")

    lines.extend(
        [
            "",
            "## Current Matching Patterns",
            "",
            "### Matched or exactly matchable",
            "",
            *(matched_patterns or ["- none"]),
            "",
            "### Failed or unresolved",
            "",
            *(failed_patterns or ["- none"]),
            "",
            "## Mapping Hypotheses",
            "",
            *infer_hypotheses(rows, answer_sections),
            "",
            "These are hypotheses only. They are not accepted facts until manually reviewed.",
            "",
            "## Needs Manual Answer Confirmation",
            "",
            *(needs_manual or ["- none"]),
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose section alignment for sample candidates.")
    parser.add_argument("--root", default=".", help="Project root.")
    parser.add_argument("--candidates", default="data/review/questions_candidates_sample.jsonl")
    parser.add_argument("--answer-key", default="data/review/answer_key_extracted_sample.json")
    parser.add_argument("--output", default="data/review/section_alignment_diagnosis_sample.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    rows = read_jsonl(root / args.candidates)
    answer_key = json.loads((root / args.answer_key).read_text(encoding="utf-8"))
    output = root / args.output
    write_report(output, rows, answer_key)
    print(f"Wrote section alignment diagnosis to {output}")


if __name__ == "__main__":
    main()
