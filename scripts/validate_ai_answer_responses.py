#!/usr/bin/env python3
"""Validate AI answer response JSONL against request JSONL."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


VALID_CONFIDENCES = {"high", "medium", "low", "none"}
VOCAB_REQUIRED = {"word", "option_label", "zh_meaning", "en_definition"}


def read_jsonl_lenient(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: invalid JSON: {exc}")
                continue
            if not isinstance(value, dict):
                errors.append(f"line {line_number}: response must be a JSON object")
                continue
            rows.append(value)
    return rows, errors


def request_index(requests: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(request.get("question_id")): request for request in requests}


def option_labels(request: dict[str, Any]) -> set[str]:
    return {str(option.get("label")) for option in request.get("options") or [] if option.get("label") is not None}


def validate_response(row: dict[str, Any], requests_by_id: dict[str, dict[str, Any]], seen: set[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    question_id = row.get("question_id")
    if not question_id:
        errors.append("missing question_id")
        return errors, warnings
    question_id = str(question_id)
    if question_id in seen:
        errors.append(f"{question_id}: duplicate question_id")
    seen.add(question_id)
    request = requests_by_id.get(question_id)
    if not request:
        errors.append(f"{question_id}: question_id not found in requests")
        return errors, warnings

    confidence = row.get("ai_answer_confidence")
    if confidence not in VALID_CONFIDENCES:
        errors.append(f"{question_id}: invalid ai_answer_confidence {confidence!r}")

    answer = row.get("ai_suggested_answer")
    labels = option_labels(request)
    if answer is not None:
        if not isinstance(answer, list):
            errors.append(f"{question_id}: ai_suggested_answer must be a list or null")
        else:
            for label in answer:
                if label not in labels:
                    errors.append(f"{question_id}: answer label {label!r} not in options {sorted(labels)}")
            if request.get("question_type") == "sentence_equivalence" and len(answer) != 2:
                warnings.append(f"{question_id}: sentence_equivalence answer count is {len(answer)}, expected 2")

    vocab_items = row.get("vocab_items")
    if not isinstance(vocab_items, list):
        errors.append(f"{question_id}: vocab_items must be a list")
    else:
        for index, item in enumerate(vocab_items, start=1):
            if not isinstance(item, dict):
                errors.append(f"{question_id}: vocab_items[{index}] must be an object")
                continue
            missing = sorted(field for field in VOCAB_REQUIRED if field not in item)
            if missing:
                errors.append(f"{question_id}: vocab_items[{index}] missing {missing}")
            option_label = item.get("option_label")
            if option_label is not None and option_label not in labels:
                errors.append(f"{question_id}: vocab_items[{index}].option_label {option_label!r} not in options {sorted(labels)}")
    return errors, warnings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate AI answer response JSONL.")
    parser.add_argument("--responses", required=True)
    parser.add_argument("--requests", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    requests, request_errors = read_jsonl_lenient(Path(args.requests))
    responses, response_errors = read_jsonl_lenient(Path(args.responses))
    errors = request_errors + response_errors
    warnings: list[str] = []
    requests_by_id = request_index(requests)
    seen: set[str] = set()
    confidence_counts: Counter[str] = Counter()

    for row in responses:
        row_errors, row_warnings = validate_response(row, requests_by_id, seen)
        errors.extend(row_errors)
        warnings.extend(row_warnings)
        confidence_counts[str(row.get("ai_answer_confidence"))] += 1

    missing_ids = sorted(set(requests_by_id) - seen)
    duplicate_count = sum(count - 1 for count in Counter(str(row.get("question_id")) for row in responses).values() if count > 1)
    print(f"request_count: {len(requests)}")
    print(f"response_count: {len(responses)}")
    print(f"missing_response_count: {len(missing_ids)}")
    print(f"duplicate_count: {duplicate_count}")
    print(f"errors: {len(errors)}")
    print(f"warnings: {len(warnings)}")
    print(f"confidence distribution: {dict(confidence_counts)}")
    if missing_ids:
        print("missing response ids:")
        for question_id in missing_ids[:50]:
            print(f"- {question_id}")
    if errors:
        print("error details:")
        for error in errors[:50]:
            print(f"- {error}")
    if warnings:
        print("warning details:")
        for warning in warnings[:50]:
            print(f"- {warning}")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

