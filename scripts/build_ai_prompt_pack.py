#!/usr/bin/env python3
"""Build a human-readable prompt pack from AI answer requests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


HEADER = """# GRE Verbal AI Answer Pack

请根据下面每道 GRE verbal 非阅读题，输出严格 JSONL。每一行对应一道题。不要输出 Markdown，不要输出解释性段落。

Response schema:

{
  "question_id": "...",
  "ai_suggested_answer": ["A"],
  "ai_answer_confidence": "high | medium | low",
  "ai_answer_reasoning_brief": "简短中文解释，不要长篇推理",
  "vocab_items": [
    {
      "word": "...",
      "option_label": "A",
      "part_of_speech": "...",
      "zh_meaning": "...",
      "en_definition": "...",
      "contextual_meaning_zh": "...",
      "synonyms": []
    }
  ],
  "notes": null
}

要求：

1. 只输出 JSONL。
2. 每题一行 JSON。
3. 不要 markdown code block。
4. ai_suggested_answer 必须是选项 label 数组，例如 ["A"] 或 ["B", "E"]。
5. 如果是 sentence equivalence，通常应选两个答案；如果无法确认，confidence 设为 low。
6. 如果题目或选项不完整，ai_suggested_answer 设为 null，confidence 设为 low，并在 notes 说明。
7. vocab_items 需要覆盖所有选项中的核心 GRE 词汇，不需要解释 the/a/of 等功能词。
8. 每个 vocab item 必须包含 option_label，方便回连选项。
9. 不要写长篇 chain-of-thought，只写面向用户的简短解释。
"""


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def format_options(options: list[dict[str, Any]]) -> str:
    return "\n".join(f"{option.get('label')}. {option.get('text_clean')}" for option in options)


def build_prompt(requests: list[dict[str, Any]]) -> str:
    lines = [HEADER.rstrip(), ""]
    for index, request in enumerate(requests, start=1):
        lines.extend(
            [
                f"## Request {index}",
                "",
                f"question_id: {request.get('question_id')}",
                f"question_type: {request.get('question_type')}",
                "stem:",
                request.get("stem_clean") or "",
                "",
                "options:",
                format_options(request.get("options") or []),
                "",
                "请输出这一题对应的一行 JSON。",
                "",
            ]
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Markdown prompt pack for AI answer generation.")
    parser.add_argument("--requests", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    requests = read_jsonl(Path(args.requests))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_prompt(requests), encoding="utf-8")
    print(f"Wrote prompt pack for {len(requests)} requests to {output}")


if __name__ == "__main__":
    main()

