#!/usr/bin/env python3
"""Build a lightweight inventory for GRE PDF files."""

from __future__ import annotations

import argparse
import json
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


def resolve_testbank(root: Path, explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_absolute() else root / path

    candidates = [root / "testbank", root / "test_bank"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def clean_sample(text: str, limit: int) -> str:
    lines = [" ".join(line.split()) for line in text.splitlines()]
    compact = "\n".join(line for line in lines if line)
    return compact[:limit]


def page_text(doc: fitz.Document, page_index: int, limit: int) -> str:
    try:
        return clean_sample(doc.load_page(page_index).get_text("text"), limit)
    except Exception as exc:  # noqa: BLE001
        return f"[page_text_error] {exc}"


def inventory_pdf(pdf_path: Path, root: Path, sample_pages: int, max_sample_chars: int) -> dict[str, Any]:
    item: dict[str, Any] = {
        "path": str(pdf_path),
        "relpath": str(pdf_path.relative_to(root)) if pdf_path.is_relative_to(root) else str(pdf_path),
        "file_size_bytes": None,
        "page_count": None,
        "likely_has_text_layer": False,
        "first_pages_sample": [],
        "last_pages_sample": [],
        "error": None,
    }

    try:
        item["file_size_bytes"] = pdf_path.stat().st_size
        with fitz.open(pdf_path) as doc:
            page_count = doc.page_count
            item["page_count"] = page_count

            first_indexes = list(range(min(sample_pages, page_count)))
            last_start = max(0, page_count - sample_pages)
            last_indexes = list(range(last_start, page_count))

            first_samples = [
                {"page": index + 1, "text": page_text(doc, index, max_sample_chars)}
                for index in first_indexes
            ]
            last_samples = [
                {"page": index + 1, "text": page_text(doc, index, max_sample_chars)}
                for index in last_indexes
            ]
            item["first_pages_sample"] = first_samples
            item["last_pages_sample"] = last_samples

            sampled_text = "\n".join(sample["text"] for sample in first_samples + last_samples)
            item["likely_has_text_layer"] = len(sampled_text.strip()) >= 80
    except Exception as exc:  # noqa: BLE001
        item["error"] = str(exc)

    return item


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan GRE PDF files and write a JSONL inventory.")
    parser.add_argument("--root", default=".", help="Project root. Default: current directory.")
    parser.add_argument("--testbank", default=None, help="PDF folder relative to root or absolute path.")
    parser.add_argument(
        "--output",
        default="data/processed/pdf_inventory.jsonl",
        help="Output JSONL path relative to root.",
    )
    parser.add_argument("--sample-pages", type=int, default=3, help="Number of first/last pages to sample.")
    parser.add_argument("--max-sample-chars", type=int, default=1200, help="Max characters per sampled page.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    testbank = resolve_testbank(root, args.testbank)
    output = Path(args.output).expanduser()
    output = output if output.is_absolute() else root / output

    rows: list[dict[str, Any]] = []
    if not testbank.exists():
        rows.append(
            {
                "path": str(testbank),
                "relpath": str(testbank.relative_to(root)) if testbank.is_relative_to(root) else str(testbank),
                "file_size_bytes": None,
                "page_count": None,
                "likely_has_text_layer": False,
                "first_pages_sample": [],
                "last_pages_sample": [],
                "error": "testbank directory does not exist",
            }
        )
    else:
        pdf_paths = sorted(path for path in testbank.rglob("*.pdf") if path.is_file())
        for pdf_path in pdf_paths:
            rows.append(inventory_pdf(pdf_path, root, args.sample_pages, args.max_sample_chars))

    write_jsonl(output, rows)
    print(f"Wrote {len(rows)} inventory rows to {output}")


if __name__ == "__main__":
    main()
