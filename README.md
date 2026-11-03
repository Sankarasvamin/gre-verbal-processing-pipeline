# GRE Verbal Processing Pipeline

This repository contains the reproducible workflow used to inventory local GRE PDFs, extract candidate verbal questions, build review packs, merge AI-assisted answer drafts, and validate reviewed records.

## Scope

- PDF inventory and text-quality diagnostics
- candidate extraction for text completion and sentence equivalence
- section and answer-mode normalization
- human-review tables and AI-response templates
- schema, mapping, and answer-quality validation

## Data boundary

Source PDFs, archived test banks, extracted questions, answer keys, review outputs, and caches are intentionally excluded. They may contain copyrighted or locally licensed material. The public repository contains only workflow code and documentation.

## Structure

- `scripts/`: extraction, review, validation, and reporting commands
- `docs/`: workflow, schema, and review documentation
- `requirements.txt`: Python dependencies

Start with `docs/PROJECT_OVERVIEW.md`, then follow `docs/PDF_EXTRACTION_PLAN.md` and `docs/REVIEW_WORKFLOW.md`.
