#!/usr/bin/env python3
"""Build an empty AI answer response JSONL template."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build AI answer response template JSONL.")
    parser.add_argument("--requests", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    requests = read_jsonl(Path(args.requests))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for request in requests:
        rows.append(
            {
                "question_id": request.get("question_id"),
                "ai_suggested_answer": None,
                "ai_answer_confidence": "none",
                "ai_answer_reasoning_brief": None,
                "vocab_items": [],
                "notes": None,
            }
        )
    output.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} response templates to {output}")


if __name__ == "__main__":
    main()

