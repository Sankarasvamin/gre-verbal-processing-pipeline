#!/usr/bin/env python3
"""Diagnose whether a PDF text layer is usable for the GRE verbal text pipeline."""

from __future__ import annotations

import argparse
import re
import statistics
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


SIGNAL_RE = re.compile(r"\b(GRE|verbal|section|question|answer|select|blank|sentence equivalence)\b", re.I)
QUESTION_RE = re.compile(r"\bQuestion\s+\d+\b|\b\d{1,2}\.\s*[A-I]{1,3}\b", re.I)
WATERMARK_TERMS = ("逐鹿留学", "我佛留学", "卧佛", "留学")


def clean_text(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def resolve_pdf(root: Path, pdf_arg: str) -> Path:
    path = Path(pdf_arg).expanduser()
    return path if path.is_absolute() else root / path


def sample_indexes(page_count: int, sample_pages: int) -> list[int]:
    if page_count <= sample_pages * 3:
        return list(range(page_count))
    first = list(range(min(sample_pages, page_count)))
    mid_center = page_count // 2
    mid_start = max(0, mid_center - sample_pages // 2)
    middle = list(range(mid_start, min(page_count, mid_start + sample_pages)))
    last = list(range(max(0, page_count - sample_pages), page_count))
    return sorted(set(first + middle + last))


def diagnose_page_texts(page_texts: list[str], page_count: int) -> dict[str, Any]:
    lengths = [len(text.strip()) for text in page_texts]
    pages_with_text = sum(length > 20 for length in lengths)
    low_text_pages = sum(length < 120 for length in lengths)
    joined = "\n".join(page_texts)
    signal_hits = len(SIGNAL_RE.findall(joined))
    question_hits = len(QUESTION_RE.findall(joined))
    watermark_hits = sum(joined.count(term) for term in WATERMARK_TERMS)
    avg_chars = int(sum(lengths) / len(lengths)) if lengths else 0
    median_chars = int(statistics.median(lengths)) if lengths else 0

    if pages_with_text == 0:
        quality = "poor"
    elif question_hits >= 5 and signal_hits >= 8 and avg_chars >= 300:
        quality = "good"
    elif question_hits >= 1 or signal_hits >= 5:
        quality = "partial"
    elif watermark_hits >= 10 and signal_hits < 5:
        quality = "poor"
    elif avg_chars < 120:
        quality = "poor"
    else:
        quality = "unknown"

    if quality == "good":
        ocr = "no_ocr_needed"
    elif quality == "partial":
        ocr = "maybe_ocr"
    elif quality == "poor":
        ocr = "ocr_likely_needed"
    else:
        ocr = "maybe_ocr"

    return {
        "page_count": page_count,
        "sampled_pages": len(page_texts),
        "pages_with_text": pages_with_text,
        "average_text_chars_per_page": avg_chars,
        "median_text_chars_per_page": median_chars,
        "pages_with_low_text": low_text_pages,
        "watermark_hits": watermark_hits,
        "gre_signal_hits": signal_hits,
        "question_pattern_hits": question_hits,
        "pdf_text_quality": quality,
        "ocr_recommendation": ocr,
    }


def write_report(path: Path, pdf_path: Path, root: Path, metrics: dict[str, Any], samples: list[tuple[int, str]]) -> None:
    relpath = str(pdf_path.relative_to(root)) if pdf_path.is_relative_to(root) else str(pdf_path)
    lines = [
        "# PDF Text Quality Diagnosis",
        "",
        f"- source_pdf_relpath: `{relpath}`",
    ]
    for key, value in metrics.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Text Samples", ""])
    for page_number, text in samples:
        preview = text[:1200]
        lines.extend([f"### Page {page_number}", "", "```text", preview, "```", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose PDF text-layer quality.")
    parser.add_argument("--root", default=".", help="Project root.")
    parser.add_argument("--pdf", required=True, help="PDF path relative to root or absolute.")
    parser.add_argument("--output", required=True, help="Markdown output path.")
    parser.add_argument("--sample-pages", type=int, default=3, help="Pages to sample from first/middle/last.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    pdf_path = resolve_pdf(root, args.pdf).resolve()
    output = Path(args.output).expanduser()
    output = output if output.is_absolute() else root / output

    samples: list[tuple[int, str]] = []
    with fitz.open(pdf_path) as doc:
        indexes = sample_indexes(doc.page_count, args.sample_pages)
        for index in indexes:
            samples.append((index + 1, clean_text(doc.load_page(index).get_text("text"))))
        metrics = diagnose_page_texts([text for _, text in samples], doc.page_count)
    write_report(output, pdf_path, root, metrics, samples)
    print(f"Wrote PDF text quality diagnosis to {output}")
    print(f"pdf_text_quality: {metrics['pdf_text_quality']}")
    print(f"ocr_recommendation: {metrics['ocr_recommendation']}")


if __name__ == "__main__":
    main()

