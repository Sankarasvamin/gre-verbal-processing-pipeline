#!/usr/bin/env python3
"""Export unanswered training candidates as AI answer requests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


INSTRUCTION = (
    "请根据 GRE verbal 题干和选项选择最可能答案；判断题型是 text completion / "
    "sentence equivalence / short verbal；对每个选项核心词汇给出 word、part_of_speech、"
    "zh_meaning、en_definition、contextual_meaning_zh、synonyms；给出简短解释；不要输出长篇推理。"
    "如果无法判断，ai_suggested_answer 设为 null，ai_answer_confidence 设为 low。"
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def needs_ai(row: dict[str, Any]) -> bool:
    return (
        bool(row.get("keep_for_training"))
        and row.get("official_answer_status") == "missing"
        and not row.get("ai_suggested_answer")
        and row.get("question_type") != "reading"
        and bool(row.get("options"))
    )


def request_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "question_id": row.get("question_id"),
        "question_type": row.get("question_type"),
        "stem_clean": row.get("stem_clean"),
        "options": row.get("options"),
        "instruction": INSTRUCTION,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export AI answer request JSONL.")
    parser.add_argument("--questions", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = [request_row(row) for row in read_jsonl(Path(args.questions)) if needs_ai(row)]
    write_jsonl(Path(args.output), rows)
    print(f"Wrote {len(rows)} AI answer requests to {args.output}")


if __name__ == "__main__":
    main()

