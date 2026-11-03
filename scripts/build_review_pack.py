#!/usr/bin/env python3
"""Build human review files and v2 sample candidates from the stage-1 sample."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any


PDF_SECTION_RE = re.compile(r"Section\s+(\d{1,3})\s+of\s+\d{1,3}", re.IGNORECASE)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def detect_pdf_section_id(row: dict[str, Any]) -> str | None:
    raw_block = row.get("raw_block") or ""
    match = PDF_SECTION_RE.search(raw_block)
    return match.group(1) if match else None


def answer_source(answer_key: dict[str, Any], answer_key_section_id: str, question_number: str) -> str:
    raw_text = answer_key.get("raw_answer_text") or ""
    return f"answer key section {answer_key_section_id}, question {question_number}\n{raw_text[:1200]}"


def infer_section_mapping(rows: list[dict[str, Any]], answer_sections: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    notes: list[str] = []
    answer_section_ids = set(answer_sections)
    by_pdf_section: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        pdf_section_id = detect_pdf_section_id(row)
        if pdf_section_id and row.get("keep_for_training"):
            by_pdf_section[pdf_section_id].append(row)

    mapping: dict[str, str] = {}
    for pdf_section_id, section_rows in by_pdf_section.items():
        question_numbers = {str(row.get("question_number")) for row in section_rows}
        if pdf_section_id in answer_section_ids:
            mapping[pdf_section_id] = pdf_section_id
            notes.append(f"exact: PDF section {pdf_section_id} exists in answer key.")
            continue

        candidates: list[tuple[int, str]] = []
        for answer_section_id, answer_map in answer_sections.items():
            answer_numbers = set(answer_map)
            overlap = len(question_numbers & answer_numbers)
            candidates.append((overlap, answer_section_id))
        candidates.sort(reverse=True)
        if not candidates:
            notes.append(f"unresolved: PDF section {pdf_section_id} has no answer section candidates.")
            continue
        best_overlap, best_section = candidates[0]
        second_overlap = candidates[1][0] if len(candidates) > 1 else -1
        if best_overlap >= 5 and best_overlap >= second_overlap + 3:
            mapping[pdf_section_id] = best_section
            notes.append(
                f"hypothesis: PDF section {pdf_section_id} -> answer key section {best_section} "
                f"(question-number overlap {best_overlap}, second best {second_overlap})."
            )
        else:
            notes.append(
                f"unresolved: PDF section {pdf_section_id} best answer section {best_section} "
                f"has overlap {best_overlap}, second best {second_overlap}."
            )
    return mapping, notes


def build_v2_rows(rows: list[dict[str, Any]], answer_key: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    answer_sections: dict[str, dict[str, list[str]]] = answer_key.get("sections") or {}
    mapping, mapping_notes = infer_section_mapping(rows, answer_sections)
    v2_rows: list[dict[str, Any]] = []

    for row in rows:
        item = deepcopy(row)
        pdf_section_id = detect_pdf_section_id(item)
        question_number = str(item.get("question_number") or "")
        answer_key_section_id = None
        section_mapping_status = "unresolved"
        answer_match_confidence = "none"
        answer_match_notes = "未找到可确认的答案 section 映射。"
        correct_answer = None
        source_text = ""

        if pdf_section_id and pdf_section_id in answer_sections:
            answer_key_section_id = pdf_section_id
            section_mapping_status = "exact"
            answer_map = answer_sections[answer_key_section_id]
            if question_number in answer_map:
                correct_answer = answer_map[question_number]
                answer_match_confidence = "high"
                answer_match_notes = "PDF 页眉 section 与答案表 section 编号一致。"
                source_text = answer_source(answer_key, answer_key_section_id, question_number)
            else:
                answer_match_notes = "section 编号一致，但答案表中没有该题号。"
        elif pdf_section_id and pdf_section_id in mapping:
            answer_key_section_id = mapping[pdf_section_id]
            section_mapping_status = "inferred"
            answer_map = answer_sections.get(answer_key_section_id, {})
            if question_number in answer_map:
                correct_answer = answer_map[question_number]
                answer_match_confidence = "medium"
                answer_match_notes = (
                    f"hypothesis: PDF section {pdf_section_id} inferred to answer key section "
                    f"{answer_key_section_id}; requires manual confirmation."
                )
                source_text = answer_source(answer_key, answer_key_section_id, question_number)
            else:
                answer_match_notes = (
                    f"hypothesis: PDF section {pdf_section_id} inferred to answer key section "
                    f"{answer_key_section_id}, but question {question_number} is absent."
                )

        item["pdf_section_id"] = pdf_section_id
        item["answer_key_section_id"] = answer_key_section_id
        item["section_mapping_status"] = section_mapping_status
        item["answer_match_confidence"] = answer_match_confidence
        item["answer_match_notes"] = answer_match_notes
        item["correct_answer"] = correct_answer
        item["answer_source_text"] = source_text
        if correct_answer is None and item.get("keep_for_training"):
            item["parse_confidence"] = "low" if item.get("parse_confidence") == "medium" else item.get("parse_confidence", "low")
        v2_rows.append(item)

    return v2_rows, mapping_notes


def format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def write_review_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = ["# Questions Candidates Sample Review", ""]
    for index, row in enumerate(rows, start=1):
        lines.extend(
            [
                f"## Candidate {index}",
                "",
                f"* question_id: {format_value(row.get('question_id'))}",
                f"* source_pdf_relpath: {format_value(row.get('source_pdf_relpath'))}",
                f"* source_page_start: {format_value(row.get('source_page_start'))}",
                f"* source_page_end: {format_value(row.get('source_page_end'))}",
                f"* section_id: {format_value(row.get('section_id'))}",
                f"* question_number: {format_value(row.get('question_number'))}",
                f"* question_type: {format_value(row.get('question_type'))}",
                f"* is_reading: {format_value(row.get('is_reading'))}",
                f"* keep_for_training: {format_value(row.get('keep_for_training'))}",
                f"* correct_answer: {format_value(row.get('correct_answer'))}",
                f"* parse_confidence: {format_value(row.get('parse_confidence'))}",
                f"* status: {format_value(row.get('status'))}",
                f"* reject_reason: {format_value(row.get('reject_reason'))}",
                f"* answer_source_text: {format_value(row.get('answer_source_text'))}",
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
                "### Raw block",
                "",
                "```text",
                row.get("raw_block") or "",
                "```",
                "",
                "### Review fields",
                "",
                "manual_keep_for_training:",
                "manual_question_type:",
                "manual_correct_answer:",
                "manual_notes:",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_gold_template(path: Path, rows: list[dict[str, Any]], limit: int) -> None:
    clear_rows = [
        row for row in rows
        if row.get("keep_for_training")
        and not row.get("is_reading")
        and row.get("stem_clean")
        and len(row.get("options") or []) >= 5
    ]
    selected = clear_rows[:limit]
    template_rows: list[dict[str, Any]] = []
    for row in selected:
        item = deepcopy(row)
        item["status"] = "pending_review"
        item["manual_status"] = None
        item["manual_keep_for_training"] = None
        item["manual_question_type"] = None
        item["manual_correct_answer"] = None
        item["manual_reject_reason"] = None
        item["manual_notes"] = None
        template_rows.append(item)
    write_jsonl(path, template_rows)


def write_mapping_notes(path: Path, v2_rows: list[dict[str, Any]], mapping_notes: list[str]) -> None:
    status_counts = Counter(row.get("section_mapping_status") for row in v2_rows)
    matched = sum(1 for row in v2_rows if row.get("correct_answer"))
    unmatched = len(v2_rows) - matched
    lines = [
        "# Sample V2 Build Notes",
        "",
        f"- rows: {len(v2_rows)}",
        f"- matched_answers: {matched}",
        f"- unmatched_answers: {unmatched}",
        f"- section_mapping_status: {dict(status_counts)}",
        "",
        "## Mapping Notes",
        "",
    ]
    lines.extend(f"- {note}" for note in mapping_notes)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build review markdown, v2 candidates, and a gold sample template.")
    parser.add_argument("--root", default=".", help="Project root.")
    parser.add_argument("--input", default="data/review/questions_candidates_sample.jsonl")
    parser.add_argument("--answer-key", default="data/review/answer_key_extracted_sample.json")
    parser.add_argument("--review-output", default="data/review/questions_candidates_sample_review.md")
    parser.add_argument("--v2-output", default="data/review/questions_candidates_sample_v2.jsonl")
    parser.add_argument("--gold-output", default="data/review/gold_sample_template.jsonl")
    parser.add_argument("--notes-output", default="data/review/questions_candidates_sample_v2_notes.md")
    parser.add_argument("--gold-limit", type=int, default=12)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    input_path = root / args.input
    answer_key_path = root / args.answer_key
    rows = read_jsonl(input_path)
    answer_key = json.loads(answer_key_path.read_text(encoding="utf-8"))
    v2_rows, mapping_notes = build_v2_rows(rows, answer_key)

    write_review_markdown(root / args.review_output, rows)
    write_jsonl(root / args.v2_output, v2_rows)
    write_gold_template(root / args.gold_output, v2_rows, args.gold_limit)
    write_mapping_notes(root / args.notes_output, v2_rows, mapping_notes)

    print(f"Wrote review markdown to {root / args.review_output}")
    print(f"Wrote v2 candidates to {root / args.v2_output}")
    print(f"Wrote gold template to {root / args.gold_output}")
    print(f"Rows: {len(v2_rows)}")
    print(f"Matched answers: {sum(1 for row in v2_rows if row.get('correct_answer'))}")
    print(f"Mapping status: {dict(Counter(row.get('section_mapping_status') for row in v2_rows))}")


if __name__ == "__main__":
    main()
