#!/usr/bin/env python3
"""Apply a human-editable section mapping to sample candidates."""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any


def parse_scalar(value: str) -> str | None:
    value = value.strip()
    if value == "null":
        return None
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def read_simple_mapping_yaml(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {"mappings": {}, "notes": {}}
    current_section: str | None = None

    with path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.rstrip()
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if not line.startswith(" "):
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()
                if key in {"mappings", "notes"}:
                    current_section = key
                    continue
                data[key] = parse_scalar(value)
                current_section = None
                continue
            if current_section in {"mappings", "notes"}:
                stripped = line.strip()
                key, _, value = stripped.partition(":")
                map_key = parse_scalar(key.strip())
                data[current_section][str(map_key)] = parse_scalar(value)
    return data


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def infer_pdf_section_id(row: dict[str, Any]) -> str | None:
    if row.get("pdf_section_id") is not None:
        return str(row.get("pdf_section_id"))
    match = re.search(r"Section\s+(\d{1,3})\s+of\s+\d{1,3}", row.get("raw_block") or "", re.IGNORECASE)
    return match.group(1) if match else None


def source_text(answer_key: dict[str, Any], answer_key_section_id: str, question_number: str) -> str:
    raw_text = answer_key.get("raw_answer_text") or ""
    return f"configured answer key section {answer_key_section_id}, question {question_number}\n{raw_text[:1200]}"


def apply_mapping(rows: list[dict[str, Any]], answer_key: dict[str, Any], mapping: dict[str, Any]) -> list[dict[str, Any]]:
    answer_sections: dict[str, dict[str, list[str]]] = answer_key.get("sections") or {}
    mappings: dict[str, str | None] = mapping.get("mappings") or {}
    notes: dict[str, str | None] = mapping.get("notes") or {}
    output: list[dict[str, Any]] = []

    for row in rows:
        item = deepcopy(row)
        pdf_section_id = infer_pdf_section_id(item)
        question_number = str(item.get("question_number") or "")
        mapped_section = mappings.get(str(pdf_section_id)) if pdf_section_id is not None else None
        mapping_note = notes.get(str(pdf_section_id), "")

        item["pdf_section_id"] = pdf_section_id
        item["answer_key_section_id"] = mapped_section
        item["correct_answer"] = None
        item["answer_source_text"] = ""

        if mapped_section is None:
            item["section_mapping_status"] = "unresolved"
            item["answer_match_confidence"] = "none"
            item["answer_match_notes"] = (
                f"section mapping is null for pdf_section_id={pdf_section_id}. {mapping_note}".strip()
            )
        else:
            answer_map = answer_sections.get(str(mapped_section), {})
            if question_number in answer_map:
                item["correct_answer"] = answer_map[question_number]
                item["section_mapping_status"] = "exact" if str(mapped_section) == str(pdf_section_id) else "configured"
                item["answer_match_confidence"] = "high" if item["section_mapping_status"] == "exact" else "medium"
                item["answer_match_notes"] = (
                    f"answer matched via section mapping: pdf_section_id={pdf_section_id} -> "
                    f"answer_key_section_id={mapped_section}. {mapping_note}".strip()
                )
                item["answer_source_text"] = source_text(answer_key, str(mapped_section), question_number)
            else:
                item["section_mapping_status"] = "configured"
                item["answer_match_confidence"] = "low"
                item["answer_match_notes"] = (
                    f"mapping exists but question_number={question_number} was not found in "
                    f"answer_key_section_id={mapped_section}. {mapping_note}".strip()
                )
        if item.get("correct_answer") is None and item.get("keep_for_training"):
            item["parse_confidence"] = "low"
        output.append(item)
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply section mapping config to question candidates.")
    parser.add_argument("--questions", required=True)
    parser.add_argument("--answer-key", required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    questions_path = Path(args.questions)
    answer_key_path = Path(args.answer_key)
    mapping_path = Path(args.mapping)
    output_path = Path(args.output)

    rows = read_jsonl(questions_path)
    answer_key = json.loads(answer_key_path.read_text(encoding="utf-8"))
    mapping = read_simple_mapping_yaml(mapping_path)
    mapped_rows = apply_mapping(rows, answer_key, mapping)
    write_jsonl(output_path, mapped_rows)

    matched = sum(1 for row in mapped_rows if row.get("correct_answer"))
    print(f"Wrote mapped questions to {output_path}")
    print(f"Rows: {len(mapped_rows)}")
    print(f"Matched answers: {matched}")
    print(f"Unmatched answers: {len(mapped_rows) - matched}")


if __name__ == "__main__":
    main()

