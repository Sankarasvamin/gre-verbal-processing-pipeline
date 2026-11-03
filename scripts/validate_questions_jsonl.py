#!/usr/bin/env python3
"""Validate GRE question JSONL files."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {
    "question_id",
    "source_pdf_relpath",
    "source_page_start",
    "source_page_end",
    "section_id",
    "question_number",
    "question_type",
    "is_reading",
    "keep_for_training",
    "stem_clean",
    "options",
    "correct_answer",
    "parse_confidence",
    "status",
    "raw_block",
}

ANSWER_MODES = {"manual", "official", "ai_suggested", "none"}
AI_CONFIDENCES = {"high", "medium", "low", "none", None}
OFFICIAL_STATUSES = {"matched", "missing", "conflicted", "not_applicable", None}
VOCAB_FIELDS = {
    "word",
    "option_label",
    "part_of_speech",
    "zh_meaning",
    "en_definition",
    "contextual_meaning_zh",
    "synonyms",
}


def validate_row(row: dict[str, Any], line_number: int) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    missing = sorted(field for field in REQUIRED_FIELDS if field not in row)
    if missing:
        errors.append(f"line {line_number}: missing required fields: {missing}")

    options = row.get("options") or []
    option_labels = {option.get("label") for option in options if isinstance(option, dict)}
    if row.get("keep_for_training"):
        if not row.get("stem_clean"):
            errors.append(f"line {line_number}: keep_for_training=true but stem_clean is empty")
        if not options:
            errors.append(f"line {line_number}: keep_for_training=true but options is empty")

    correct_answer = row.get("correct_answer")
    if correct_answer:
        if not isinstance(correct_answer, list):
            errors.append(f"line {line_number}: correct_answer must be a list, null, or empty")
        else:
            for label in correct_answer:
                if label not in option_labels:
                    errors.append(
                        f"line {line_number}: correct_answer label {label!r} not found in option labels {sorted(option_labels)}"
                    )

    if row.get("is_reading") is True and row.get("keep_for_training") is True:
        warnings.append(f"line {line_number}: is_reading=true but keep_for_training=true")

    if (
        row.get("section_mapping_status") == "unresolved"
        and row.get("correct_answer")
        and row.get("answer_mode") != "ai_suggested"
    ):
        warnings.append(f"line {line_number}: unresolved section mapping but correct_answer is present")

    answer_mode = row.get("answer_mode")
    if answer_mode is not None:
        if answer_mode not in ANSWER_MODES:
            errors.append(f"line {line_number}: invalid answer_mode {answer_mode!r}")
        expected_answer = None
        if answer_mode == "manual":
            expected_answer = row.get("manual_answer")
            if not expected_answer:
                errors.append(f"line {line_number}: answer_mode=manual but manual_answer is empty")
        elif answer_mode == "official":
            expected_answer = row.get("official_answer")
            if not expected_answer:
                errors.append(f"line {line_number}: answer_mode=official but official_answer is empty")
        elif answer_mode == "ai_suggested":
            expected_answer = row.get("ai_suggested_answer")
            if not expected_answer:
                errors.append(f"line {line_number}: answer_mode=ai_suggested but ai_suggested_answer is empty")
        elif answer_mode == "none":
            expected_answer = None
        if expected_answer != row.get("correct_answer"):
            errors.append(
                f"line {line_number}: correct_answer {row.get('correct_answer')!r} does not match answer_mode "
                f"{answer_mode!r} expected answer {expected_answer!r}"
            )

    if row.get("official_answer_status") not in OFFICIAL_STATUSES:
        errors.append(f"line {line_number}: invalid official_answer_status {row.get('official_answer_status')!r}")
    if row.get("ai_answer_confidence") not in AI_CONFIDENCES:
        errors.append(f"line {line_number}: invalid ai_answer_confidence {row.get('ai_answer_confidence')!r}")
    if row.get("answer_conflict_flag") is True:
        warnings.append(f"line {line_number}: answer_conflict_flag=true")

    for answer_field in ("official_answer", "manual_answer", "ai_suggested_answer"):
        value = row.get(answer_field)
        if value:
            if not isinstance(value, list):
                errors.append(f"line {line_number}: {answer_field} must be a list or null")
                continue
            for label in value:
                if label not in option_labels:
                    errors.append(
                        f"line {line_number}: {answer_field} label {label!r} not found in option labels {sorted(option_labels)}"
                    )

    vocab_items = row.get("vocab_items") or []
    if not isinstance(vocab_items, list):
        errors.append(f"line {line_number}: vocab_items must be a list")
    else:
        for index, item in enumerate(vocab_items, start=1):
            if not isinstance(item, dict):
                errors.append(f"line {line_number}: vocab_items[{index}] must be an object")
                continue
            missing_vocab = sorted(field for field in VOCAB_FIELDS if field not in item)
            if missing_vocab:
                errors.append(f"line {line_number}: vocab_items[{index}] missing fields {missing_vocab}")
            if item.get("synonyms") is not None and not isinstance(item.get("synonyms"), list):
                errors.append(f"line {line_number}: vocab_items[{index}].synonyms must be a list")

    return errors, warnings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a GRE question JSONL file.")
    parser.add_argument("--path", required=True, help="JSONL path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    path = Path(args.path).expanduser()
    rows = 0
    errors: list[str] = []
    warnings: list[str] = []
    status_counts: Counter[str] = Counter()
    mapping_counts: Counter[str] = Counter()
    answer_mode_counts: Counter[str] = Counter()

    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: invalid JSON: {exc}")
                continue
            rows += 1
            row_errors, row_warnings = validate_row(row, line_number)
            errors.extend(row_errors)
            warnings.extend(row_warnings)
            status_counts[str(row.get("status"))] += 1
            mapping_counts[str(row.get("section_mapping_status"))] += 1
            answer_mode_counts[str(row.get("answer_mode"))] += 1

    print(f"Validated: {path}")
    print(f"Rows: {rows}")
    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")
    print(f"Status counts: {dict(status_counts)}")
    print(f"Section mapping counts: {dict(mapping_counts)}")
    print(f"Answer mode counts: {dict(answer_mode_counts)}")
    if errors:
        print("Error details:")
        for error in errors[:50]:
            print(f"- {error}")
    if warnings:
        print("Warning details:")
        for warning in warnings[:50]:
            print(f"- {warning}")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
