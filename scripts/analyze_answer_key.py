#!/usr/bin/env python3
"""Analyze answer key pages for one GRE PDF without mapping them to questions."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from extract_sample import PageText, clean_text, load_pages, resolve_pdf


SECTION_HEADER_RE = re.compile(r"(?im)^\s*section\s+(\d{1,3})\.?\s*$")
ANSWER_TOKEN_RE = re.compile(r"\b[A-I]{1,3}\b")


def relpath(path: Path, root: Path) -> str:
    return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)


def looks_like_answer_key_page(text: str) -> bool:
    section_headers = len(SECTION_HEADER_RE.findall(text))
    answer_tokens = len(ANSWER_TOKEN_RE.findall(text))
    explicit_terms = any(term in text.lower() for term in ("answer key", "answers", "答案", "正确答案"))
    return explicit_terms or (section_headers >= 1 and answer_tokens >= 8)


def find_answer_pages(pages: list[PageText], tail_pages: int) -> list[PageText]:
    tail = pages[-tail_pages:] if tail_pages > 0 else pages
    candidates = [page for page in tail if looks_like_answer_key_page(page.text)]
    return candidates


def parse_section_answer_tables(raw_text: str) -> tuple[dict[str, dict[str, list[str]]], list[str]]:
    notes: list[str] = []
    sections: dict[str, dict[str, list[str]]] = {}
    matches = list(SECTION_HEADER_RE.finditer(raw_text))
    if not matches:
        notes.append("未识别到独立行形式的 section header。")
        return sections, notes

    for index, match in enumerate(matches):
        section_id = match.group(1)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw_text)
        block = raw_text[start:end]
        tokens = ANSWER_TOKEN_RE.findall(block)
        if not tokens:
            notes.append(f"section {section_id} 未解析到答案 token。")
            continue
        question_numbers = [int(value) for value in re.findall(r"\b\d{1,3}\b", block)]
        expected_count = max(question_numbers) if question_numbers else len(tokens)
        if expected_count < len(tokens):
            tokens = tokens[-expected_count:]
        sections[section_id] = {
            str(question_number): list(token)
            for question_number, token in enumerate(tokens, start=1)
        }
        notes.append(f"section {section_id} 解析到 {len(tokens)} 个答案。")

    return sections, notes


def write_markdown(
    path: Path,
    source_pdf_relpath: str,
    answer_pages: list[PageText],
    sections: dict[str, dict[str, list[str]]],
    parse_notes: list[str],
) -> None:
    raw_text = "\n\n".join(f"--- page {page.page} ---\n{page.text}" for page in answer_pages)
    lines = [
        "# Answer Key Analysis",
        "",
        f"- source_pdf_relpath: `{source_pdf_relpath}`",
        f"- answer_pages: {[page.page for page in answer_pages]}",
        f"- sections: {sorted(sections)}",
        "",
        "## Parsed Sections",
        "",
    ]
    for section_id, answer_map in sections.items():
        compact = ", ".join(f"{number}: {''.join(labels)}" for number, labels in answer_map.items())
        lines.append(f"### section {section_id}")
        lines.append("")
        lines.append(compact)
        lines.append("")

    lines.extend(["## Parse Notes", ""])
    lines.extend(f"- {note}" for note in parse_notes)
    lines.extend(["", "## Raw Answer Text", "", "```text", raw_text, "```", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze answer key pages for one PDF.")
    parser.add_argument("--root", default=".", help="Project root.")
    parser.add_argument("--pdf", required=True, help="PDF path relative to root or absolute path.")
    parser.add_argument("--tail-pages", type=int, default=8, help="How many final pages to inspect.")
    parser.add_argument(
        "--json-output",
        default="data/review/answer_key_extracted_sample.json",
        help="JSON output path relative to root.",
    )
    parser.add_argument(
        "--markdown-output",
        default="data/review/answer_key_analysis_sample.md",
        help="Markdown output path relative to root.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    pdf_path = resolve_pdf(root, args.pdf).resolve()
    json_output = Path(args.json_output).expanduser()
    json_output = json_output if json_output.is_absolute() else root / json_output
    markdown_output = Path(args.markdown_output).expanduser()
    markdown_output = markdown_output if markdown_output.is_absolute() else root / markdown_output

    pages = load_pages(pdf_path)
    answer_pages = find_answer_pages(pages, args.tail_pages)
    raw_answer_text = "\n\n".join(page.text for page in answer_pages)
    sections, parse_notes = parse_section_answer_tables(raw_answer_text)
    if not answer_pages:
        parse_notes.append(f"后 {args.tail_pages} 页未识别到答案页。")

    payload: dict[str, Any] = {
        "source_pdf_relpath": relpath(pdf_path, root),
        "answer_pages": [page.page for page in answer_pages],
        "sections": sections,
        "raw_answer_text": raw_answer_text,
        "parse_notes": parse_notes,
    }
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(markdown_output, payload["source_pdf_relpath"], answer_pages, sections, parse_notes)

    print(f"Wrote answer key JSON to {json_output}")
    print(f"Wrote answer key analysis to {markdown_output}")
    print(f"Answer pages: {payload['answer_pages']}")
    print(f"Sections: {', '.join(sorted(sections)) if sections else 'none'}")


if __name__ == "__main__":
    main()
