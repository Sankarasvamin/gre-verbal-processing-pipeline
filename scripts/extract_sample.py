#!/usr/bin/env python3
"""Extract review-only GRE verbal non-reading candidates from one PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: PyMuPDF. Install with `python3 -m pip install -r requirements.txt`."
    ) from exc

fitz.TOOLS.mupdf_display_errors(False)
fitz.TOOLS.mupdf_display_warnings(False)


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "his",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "may",
    "might",
    "more",
    "most",
    "must",
    "no",
    "not",
    "of",
    "on",
    "one",
    "or",
    "our",
    "she",
    "should",
    "so",
    "such",
    "than",
    "that",
    "the",
    "their",
    "there",
    "these",
    "they",
    "this",
    "those",
    "to",
    "was",
    "were",
    "which",
    "who",
    "will",
    "with",
    "would",
    "you",
    "your",
}

QUESTION_START_RE = re.compile(r"(?m)^\s*(\d{1,3})[\.\)、)]\s+")
SCREEN_QUESTION_RE = re.compile(r"Question\s+(\d{1,3})\s+of\s+\d{1,3}", re.IGNORECASE)
SCREEN_SECTION_RE = re.compile(r"Section\s+(\d{1,3})\s+of\s+\d{1,3}", re.IGNORECASE)
OPTION_RE = re.compile(r"(?m)^\s*(?:\(([A-H])\)|([A-H])[\.\)、)]|([A-H])\s{2,})(?:\s*)(.+?)\s*$")
ANSWER_RE = re.compile(r"(?<!\d)(\d{1,3})\s*[\.\)、):：]\s*([A-H](?:\s*[,/，]\s*[A-H])*)")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")


@dataclass
class PageText:
    page: int
    text: str


def clean_text(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def resolve_pdf(root: Path, pdf_arg: str | None) -> Path:
    if pdf_arg:
        path = Path(pdf_arg).expanduser()
        return path if path.is_absolute() else root / path

    for folder_name in ("testbank", "test_bank"):
        folder = root / folder_name
        if folder.exists():
            pdfs = sorted(path for path in folder.rglob("*.pdf") if path.is_file())
            if pdfs:
                return pdfs[0]
    raise SystemExit("No PDF specified and no PDF found under testbank/ or test_bank/.")


def load_pages(pdf_path: Path) -> list[PageText]:
    pages: list[PageText] = []
    with fitz.open(pdf_path) as doc:
        for index in range(doc.page_count):
            text = clean_text(doc.load_page(index).get_text("text"))
            pages.append(PageText(page=index + 1, text=text))
    return pages


def classify_page(text: str, pdf_name: str = "") -> str:
    lower = f"{pdf_name}\n{text}".lower()
    if any(key in lower for key in ("answer key", "answers", "答案", "正确答案", "参考答案")):
        if len(ANSWER_RE.findall(text)) >= 3 or "答案" in lower:
            return "answer_key"
    if any(key in lower for key in ("analyze an issue", "analyze an argument", "issue task", "argument task", "作文")):
        return "writing"
    if any(key in lower for key in ("quantitative reasoning", "quant", "data interpretation")):
        return "quant"
    quant_symbols = len(re.findall(r"[=<>±×÷√]|(?:\d+\s*[%+\-*/]\s*\d+)", text))
    if quant_symbols >= 8:
        return "quant"
    if any(key in lower for key in ("verbal reasoning", "text completion", "sentence equivalence")):
        return "verbal"
    if re.search(r"\bblank\b|_{3,}|sentence equivalence|text completion", lower):
        return "verbal"
    return "unknown"


def detect_sections(pages: list[PageText], pdf_name: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current_type: str | None = None
    current_start: int | None = None
    section_index = 0

    for page in pages:
        page_type = classify_page(page.text, pdf_name)
        normalized = page_type if page_type != "unknown" else current_type or "unknown"
        if current_type is None:
            current_type = normalized
            current_start = page.page
            section_index += 1
            continue
        if normalized != current_type:
            sections.append(
                {
                    "section_id": f"section_{section_index}",
                    "section_type": current_type,
                    "page_start": current_start,
                    "page_end": page.page - 1,
                }
            )
            section_index += 1
            current_type = normalized
            current_start = page.page

    if current_type is not None and current_start is not None:
        sections.append(
            {
                "section_id": f"section_{section_index}",
                "section_type": current_type,
                "page_start": current_start,
                "page_end": pages[-1].page if pages else None,
            }
        )
    return sections


def section_for_page(sections: list[dict[str, Any]], page: int) -> dict[str, Any] | None:
    for section in sections:
        if section["page_start"] <= page <= section["page_end"]:
            return section
    return None


def find_answer_key_pages(pages: list[PageText], pdf_name: str) -> list[PageText]:
    explicit = [page for page in pages if classify_page(page.text, pdf_name) == "answer_key"]
    if explicit:
        return explicit
    tail = pages[-5:]
    scored = []
    for page in tail:
        scored.append((len(ANSWER_RE.findall(page.text)), page))
    table_pages = [page for page in tail if looks_like_answer_table(page.text)]
    return [page for score, page in scored if score >= 3] + table_pages


def looks_like_answer_table(text: str) -> bool:
    section_count = len(re.findall(r"(?im)^\s*section\s+\d{1,3}\.?\s*$", text))
    answer_token_count = len(re.findall(r"\b[A-H]{1,3}\b", text))
    return section_count >= 1 and answer_token_count >= 8


def parse_answers(answer_pages: list[PageText]) -> tuple[dict[str, list[str]], dict[str, str]]:
    answers: dict[str, list[str]] = {}
    sources: dict[str, str] = {}
    for page in answer_pages:
        for match in ANSWER_RE.finditer(page.text):
            number = match.group(1)
            labels = [part.strip().upper() for part in re.split(r"[,/，]", match.group(2)) if part.strip()]
            if labels:
                answers[number] = labels
                start = max(0, match.start() - 80)
                end = min(len(page.text), match.end() + 80)
                sources[number] = f"page {page.page}: {page.text[start:end]}"
    return answers, sources


def parse_answer_tables(answer_pages: list[PageText]) -> tuple[dict[str, dict[str, list[str]]], dict[str, dict[str, str]]]:
    answers: dict[str, dict[str, list[str]]] = {}
    sources: dict[str, dict[str, str]] = {}

    for page in answer_pages:
        text = page.text
        section_matches = list(re.finditer(r"(?im)^\s*section\s+(\d{1,3})\.?\s*$", text))
        for index, match in enumerate(section_matches):
            section_number = match.group(1)
            start = match.end()
            end = section_matches[index + 1].start() if index + 1 < len(section_matches) else len(text)
            block = text[start:end]
            answer_tokens = re.findall(r"\b[A-H]{1,3}\b", block)
            answer_tokens = [token for token in answer_tokens if token not in {"I"}]
            if not answer_tokens:
                continue
            section_answers = answers.setdefault(section_number, {})
            section_sources = sources.setdefault(section_number, {})
            for offset, token in enumerate(answer_tokens, start=1):
                number = str(offset)
                section_answers[number] = list(token)
                section_sources[number] = f"page {page.page}, section {section_number}: {block[:500]}"

    return answers, sources


def split_question_blocks(pages: list[PageText], answer_pages: list[PageText]) -> list[dict[str, Any]]:
    answer_page_numbers = {page.page for page in answer_pages}
    blocks: list[dict[str, Any]] = []
    for page in pages:
        if page.page in answer_page_numbers:
            continue
        matches = list(QUESTION_START_RE.finditer(page.text))
        if matches:
            for index, match in enumerate(matches):
                start = match.start()
                end = matches[index + 1].start() if index + 1 < len(matches) else len(page.text)
                block = page.text[start:end].strip()
                if block:
                    blocks.append({"page_start": page.page, "page_end": page.page, "raw_block": block})
        elif SCREEN_QUESTION_RE.search(page.text):
            blocks.append({"page_start": page.page, "page_end": page.page, "raw_block": page.text.strip()})
    return blocks


def parse_options(raw_block: str) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for match in OPTION_RE.finditer(raw_block):
        label = next(group for group in match.groups()[:3] if group)
        text = match.group(4).strip()
        if text:
            options.append({"label": label.upper(), "text_raw": text, "text_clean": text})
    if options:
        return options

    checkbox_options: list[str] = []
    for line in raw_block.splitlines():
        stripped = line.strip()
        match = re.match(r"^[D0]\s+(.+)$", stripped)
        if match:
            checkbox_options.append(match.group(1).strip())
    if checkbox_options:
        return [
            {"label": chr(ord("A") + index), "text_raw": text, "text_clean": text}
            for index, text in enumerate(checkbox_options)
        ]

    lines = [line.strip() for line in raw_block.splitlines() if line.strip()]
    option_texts: list[str] = []
    has_blank_columns = any(re.match(r"(?i)^Blank\b", line) for line in lines)
    if has_blank_columns:
        after_blank = False
        for line in lines:
            if re.match(r"(?i)^Blank\b", line):
                after_blank = True
                continue
            if not after_blank:
                continue
            if is_non_option_line(line) or line == ".":
                continue
            if is_short_option_line(line):
                option_texts.append(line)
    else:
        for line in reversed(lines):
            if is_non_option_line(line) or line == ".":
                continue
            if option_texts and looks_like_sentence_tail(line):
                break
            if is_short_option_line(line):
                option_texts.append(line)
                continue
            if option_texts:
                break
        option_texts.reverse()

    return [
        {"label": chr(ord("A") + index), "text_raw": text, "text_clean": text}
        for index, text in enumerate(option_texts)
    ]
    return options


def is_non_option_line(line: str) -> bool:
    lower = line.lower()
    prefixes = (
        "section ",
        "question ",
        "select ",
        "fill ",
        "for each blank",
        "00:",
    )
    if lower.startswith(prefixes):
        return True
    if "hide time" in lower or "best completes the text" in lower:
        return True
    if "when used to complete the sentence" in lower or "sentence as a whole" in lower:
        return True
    if "produce completed sentences" in lower or "alike in meaning" in lower:
        return True
    return False


def looks_like_sentence_tail(line: str) -> bool:
    stripped = line.strip()
    return stripped.endswith((".", ".)", '."', '."')) or "___" in stripped


def is_short_option_line(line: str) -> bool:
    if len(line) > 80:
        return False
    words = WORD_RE.findall(line)
    if not words:
        return False
    if len(words) > 6:
        return False
    if line.endswith((".", ":", ";", "?")) and len(words) > 2:
        return False
    return True


def strip_question_number(raw_block: str) -> tuple[str, str]:
    match = QUESTION_START_RE.search(raw_block)
    if not match:
        screen_match = SCREEN_QUESTION_RE.search(raw_block)
        if screen_match:
            return screen_match.group(1), raw_block
        return "", raw_block
    return match.group(1), raw_block[match.end() :].strip()


def stem_without_options(block_without_number: str, options: list[dict[str, str]]) -> str:
    option_match = OPTION_RE.search(block_without_number)
    if option_match:
        return block_without_number[: option_match.start()].strip()

    option_values = {option["text_raw"] for option in options}
    stem_lines: list[str] = []
    for line in block_without_number.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in option_values:
            continue
        if re.match(r"^[D0]\s+", stripped):
            continue
        if stripped == ".":
            continue
        if re.match(r"(?i)^Blank\b", stripped):
            continue
        if is_non_option_line(stripped):
            continue
        stem_lines.append(stripped)

    return "\n".join(stem_lines).strip()


def screen_section_number(raw_block: str) -> str | None:
    match = SCREEN_SECTION_RE.search(raw_block)
    return match.group(1) if match else None


def is_reading_like(raw_block: str, stem: str) -> tuple[bool, str | None]:
    lower = raw_block.lower()
    passage_terms = (
        "according to the passage",
        "the passage suggests",
        "the highlighted sentence",
        "in line ",
        "primary purpose",
        "the passage is primarily",
        "reading comprehension",
        "based on this",
        "basrd on",
        "bd,ed on",
        "baspd on",
    )
    if any(term in lower for term in passage_terms):
        return True, "疑似阅读题：出现 passage/author/line 等阅读题信号"

    paragraphs = [part for part in stem.split("\n") if len(part.split()) >= 18]
    word_count = len(WORD_RE.findall(stem))
    if len(paragraphs) >= 3 or word_count >= 180:
        return True, "疑似阅读题：题干或前置文本过长"
    return False, None


def classify_question_type(stem: str, options: list[dict[str, str]], is_reading: bool, raw_block: str) -> str:
    if is_reading:
        return "reading"
    blank_count = stem.count("_____") + stem.count("____") + stem.count("___")
    lower = f"{stem}\n{raw_block}".lower()
    if "sentence equivalence" in lower or "select the two answer choices" in lower or "alike in meaning" in lower:
        return "sentence_equivalence"
    if blank_count >= 1 or "blank" in lower:
        return "text_completion"
    if options:
        return "short_verbal"
    return "unknown"


def looks_quant(raw_block: str) -> bool:
    symbols = len(re.findall(r"[=<>±×÷√]|(?:\d+\s*[%+\-*/]\s*\d+)", raw_block))
    numbers = len(re.findall(r"\b\d+(?:\.\d+)?\b", raw_block))
    return symbols >= 5 or numbers >= 18


def extract_vocab_items(options: list[dict[str, str]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    items: list[dict[str, Any]] = []
    for option in options:
        for match in WORD_RE.finditer(option["text_clean"]):
            word = match.group(0)
            lemma = word.lower().strip("'")
            if len(lemma) <= 2 or lemma in STOPWORDS:
                continue
            key = (option["label"], lemma)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "word": word,
                    "lemma": lemma,
                    "option_label": option["label"],
                    "part_of_speech": None,
                    "zh_meaning": None,
                    "en_definition": None,
                    "contextual_meaning_zh": None,
                    "synonyms": [],
                }
            )
    return items


def stable_question_id(relpath: str, question_number: str, raw_block: str) -> str:
    digest = hashlib.sha1(f"{relpath}\n{question_number}\n{raw_block}".encode("utf-8")).hexdigest()[:12]
    safe_number = question_number or "unknown"
    return f"gre_{safe_number}_{digest}"


def build_candidate(
    block: dict[str, Any],
    root: Path,
    pdf_path: Path,
    sections: list[dict[str, Any]],
    answers: dict[str, list[str]],
    answer_sources: dict[str, str],
    table_answers: dict[str, dict[str, list[str]]],
    table_answer_sources: dict[str, dict[str, str]],
) -> dict[str, Any] | None:
    raw_block = block["raw_block"]
    question_number, without_number = strip_question_number(raw_block)
    options = parse_options(raw_block)
    stem_raw = stem_without_options(without_number, options)
    is_reading, reading_reason = is_reading_like(raw_block, stem_raw)
    section = section_for_page(sections, block["page_start"])
    section_type = section["section_type"] if section else "unknown"
    pdf_section_number = screen_section_number(raw_block)

    if len(options) < 3:
        return None

    correct_answer = answers.get(question_number, [])
    answer_source_text = answer_sources.get(question_number, "")
    if pdf_section_number and pdf_section_number in table_answers:
        correct_answer = table_answers[pdf_section_number].get(question_number, correct_answer)
        answer_source_text = table_answer_sources[pdf_section_number].get(question_number, answer_source_text)

    reject_reasons: list[str] = []
    if reading_reason:
        reject_reasons.append(reading_reason)
    if section_type in {"quant", "writing", "answer_key"}:
        reject_reasons.append(f"section_type={section_type}")
    if looks_quant(raw_block):
        reject_reasons.append("疑似数学题：数字或数学符号密集")

    question_type = classify_question_type(stem_raw, options, is_reading, raw_block)
    keep_for_training = not reject_reasons and question_type in {
        "text_completion",
        "sentence_equivalence",
        "short_verbal",
    }

    confidence = "medium"
    if keep_for_training and len(options) in {5, 6} and question_number in answers:
        confidence = "high"
    elif reject_reasons or len(options) < 3:
        confidence = "low"

    relpath = str(pdf_path.relative_to(root)) if pdf_path.is_relative_to(root) else str(pdf_path)
    return {
        "question_id": stable_question_id(relpath, question_number, raw_block),
        "source_pdf": pdf_path.name,
        "source_pdf_relpath": relpath,
        "source_page_start": block["page_start"],
        "source_page_end": block["page_end"],
        "section_id": section["section_id"] if section else None,
        "section_type": section_type,
        "question_number": question_number,
        "question_type": question_type,
        "is_reading": is_reading,
        "keep_for_training": keep_for_training,
        "stem_raw": stem_raw,
        "stem_clean": stem_raw,
        "options": options,
        "correct_answer": correct_answer,
        "answer_source_text": answer_source_text,
        "parse_confidence": confidence,
        "status": "pending_review",
        "reject_reason": "; ".join(reject_reasons) if reject_reasons else None,
        "vocab_items": extract_vocab_items(options),
        "raw_block": raw_block,
        "notes": None,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_summary(
    path: Path,
    pdf_path: Path,
    root: Path,
    pages: list[PageText],
    sections: list[dict[str, Any]],
    answer_pages: list[PageText],
    table_answers: dict[str, dict[str, list[str]]],
    candidates: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    relpath = str(pdf_path.relative_to(root)) if pdf_path.is_relative_to(root) else str(pdf_path)
    section_lines = [
        f"- {item['section_id']}: {item['section_type']}, pages {item['page_start']}-{item['page_end']}"
        for item in sections
    ]
    type_counts = Counter(item["question_type"] for item in candidates)
    confidence_counts = Counter(item["parse_confidence"] for item in candidates)
    kept = sum(1 for item in candidates if item["keep_for_training"])
    reading = sum(1 for item in candidates if item["is_reading"])
    answer_matched = sum(1 for item in candidates if item["correct_answer"])
    answer_table_sections = ", ".join(sorted(table_answers)) if table_answers else "未识别"
    unmatched_kept = sum(1 for item in candidates if item["keep_for_training"] and not item["correct_answer"])

    content = f"""# 样本抽取 Summary

## 样本 PDF

- 文件：`{relpath}`
- 页数：{len(pages)}
- 文本层：{'可能存在' if sum(len(page.text) for page in pages) >= 80 else '未可靠识别'}

## Section 初步识别

{chr(10).join(section_lines) if section_lines else '- 未识别到稳定 section'}

## Answer Key

- 疑似答案页：{', '.join(str(page.page) for page in answer_pages) if answer_pages else '未识别'}
- 疑似答案表 section：{answer_table_sections}
- 候选题中匹配到答案：{answer_matched}
- 建议保留但暂未匹配答案：{unmatched_kept}

## 候选题结果

- 候选题总数：{len(candidates)}
- 建议保留训练：{kept}
- 疑似阅读题：{reading}
- 题型分布：{dict(type_counts)}
- 置信度分布：{dict(confidence_counts)}

## 主要风险

- PDF 文本层的换行、分栏和选项顺序可能被打乱。
- 当前 section 识别只基于关键词、题型和页面文本特征，不能替代人工判断。
- 答案区格式差异较大，自动提取可能漏题或错配。
- 本样本中 PDF 页眉 section 编号和答案表 section 编号可能不完全一致，未匹配答案的题目必须人工核对。
- 阅读题的 passage 有时会被拆散到多个文本块，单页规则可能误判。
- 选项词汇抽取目前只做候选英文词过滤，未接入词典、词性和中文释义。

## 下一步建议

1. 人工抽查 `data/review/questions_candidates_sample.jsonl` 中的 `raw_block`、页码和答案。
2. 总结该 PDF 的选项格式和答案格式，再收紧解析规则。
3. 选 2-3 个版式不同的 PDF 重复样本验证。
4. 只有文本层质量不足时，再设计单 PDF OCR，不做全量 OCR。
"""
    path.write_text(content, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract review candidates from one GRE PDF.")
    parser.add_argument("--root", default=".", help="Project root. Default: current directory.")
    parser.add_argument("--pdf", default=None, help="PDF path relative to root or absolute path.")
    parser.add_argument(
        "--output",
        default="data/review/questions_candidates_sample.jsonl",
        help="Output JSONL path relative to root.",
    )
    parser.add_argument(
        "--summary",
        default="data/review/sample_extraction_summary.md",
        help="Output summary markdown path relative to root.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    pdf_path = resolve_pdf(root, args.pdf).resolve()
    output = Path(args.output).expanduser()
    output = output if output.is_absolute() else root / output
    summary = Path(args.summary).expanduser()
    summary = summary if summary.is_absolute() else root / summary

    pages = load_pages(pdf_path)
    sections = detect_sections(pages, pdf_path.name)
    answer_pages = find_answer_key_pages(pages, pdf_path.name)
    answers, answer_sources = parse_answers(answer_pages)
    table_answers, table_answer_sources = parse_answer_tables(answer_pages)
    blocks = split_question_blocks(pages, answer_pages)

    candidates: list[dict[str, Any]] = []
    for block in blocks:
        candidate = build_candidate(
            block,
            root,
            pdf_path,
            sections,
            answers,
            answer_sources,
            table_answers,
            table_answer_sources,
        )
        if candidate:
            candidates.append(candidate)

    write_jsonl(output, candidates)
    write_summary(summary, pdf_path, root, pages, sections, answer_pages, table_answers, candidates)
    print(f"Wrote {len(candidates)} candidates to {output}")
    print(f"Wrote summary to {summary}")


if __name__ == "__main__":
    main()
