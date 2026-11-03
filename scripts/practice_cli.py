#!/usr/bin/env python3
"""Minimal GRE verbal practice CLI for reviewed sample questions."""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any


VALID_MODES = {"all", "official", "ai"}
ANSWER_LABEL_RE = re.compile(r"[A-Z]")


def load_questions(path: Path) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                questions.append(json.loads(line))
    return questions


def filter_questions(questions: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for question in questions:
        answer_mode = question.get("answer_mode")
        if not question.get("keep_for_training"):
            continue
        if answer_mode not in {"official", "ai_suggested"}:
            continue
        if mode == "official" and answer_mode != "official":
            continue
        if mode == "ai" and answer_mode != "ai_suggested":
            continue
        if not question.get("correct_answer"):
            continue
        if question.get("question_type") == "reading":
            continue
        if not question.get("options"):
            continue
        filtered.append(question)
    return filtered


def normalize_answer_input(raw_input: str, valid_labels: set[str]) -> list[str] | str | None:
    value = raw_input.strip().upper()
    if value == "Q":
        return "q"
    if value == "SKIP":
        return "skip"
    labels = ANSWER_LABEL_RE.findall(value)
    if not labels:
        return None
    unique = sorted(set(labels))
    if any(label not in valid_labels for label in unique):
        return None
    return unique


def normalize_answer(answer: Any) -> list[str]:
    if not answer:
        return []
    return sorted(str(label).upper() for label in answer)


def answer_source_label(question: dict[str, Any]) -> str:
    return "AI suggested" if question.get("answer_mode") == "ai_suggested" else "official"


def print_vocab(question: dict[str, Any]) -> None:
    vocab_items = question.get("vocab_items") or []
    print("\nVocabulary:\n")
    if not vocab_items:
        print("No vocabulary explanation available.")
        return
    for item in vocab_items:
        label = item.get("option_label") or "?"
        word = item.get("word") or ""
        print(f"[{label}] {word}")
        print(f"* 词性: {item.get('part_of_speech') or ''}")
        print(f"* 中文: {item.get('zh_meaning') or ''}")
        print(f"* English: {item.get('en_definition') or ''}")
        print(f"* 本题语境: {item.get('contextual_meaning_zh') or ''}")
        synonyms = item.get("synonyms") or []
        print(f"* synonyms: {', '.join(synonyms) if synonyms else ''}")
        print()


def print_explanation(question: dict[str, Any]) -> None:
    explanation = question.get("ai_answer_reasoning_brief")
    if explanation:
        if question.get("answer_mode") == "official":
            print(f"\nAI 解释参考: {explanation}")
        else:
            print(f"\nExplanation: {explanation}")
    else:
        print("\nNo explanation available.")


def ask_question(question: dict[str, Any], index: int, total: int) -> str:
    valid_labels = {str(option.get("label")).upper() for option in question.get("options") or []}
    correct_answer = normalize_answer(question.get("correct_answer"))
    print("\n" + "=" * 60)
    print(f"Question {index} / {total}")
    print(f"question_id: {question.get('question_id')}")
    print(f"type: {question.get('question_type')}")
    print(f"answer_source: {answer_source_label(question)}")
    if question.get("answer_mode") == "ai_suggested":
        print(f"confidence: {question.get('ai_answer_confidence') or 'none'}")
    else:
        print("confidence: official")
    print("\n题干:\n")
    print(question.get("stem_clean") or "")
    print("\n选项:\n")
    for option in question.get("options") or []:
        print(f"{option.get('label')}. {option.get('text_clean')}")

    while True:
        raw = input("\nYour answer: ")
        parsed = normalize_answer_input(raw, valid_labels)
        if parsed is None:
            print("Invalid input. Please enter option labels like A, A C, B,E, skip, or q.")
            continue
        if parsed == "q":
            return "quit"
        if parsed == "skip":
            print("Skipped.")
            return "skipped"

        user_answer = parsed
        is_correct = user_answer == correct_answer
        print("\nCorrect" if is_correct else "\nIncorrect")
        print(f"Your answer: {', '.join(user_answer)}")
        print(f"Correct answer: {', '.join(correct_answer)}")
        if question.get("answer_mode") == "ai_suggested":
            print("\n注意：本题答案来源为 AI suggested，不是 official answer。")
        print_explanation(question)
        print_vocab(question)
        return "correct" if is_correct else "incorrect"


def dry_run_report(all_questions: list[dict[str, Any]], eligible: list[dict[str, Any]], mode: str) -> None:
    official_count = sum(question.get("answer_mode") == "official" for question in eligible)
    ai_count = sum(question.get("answer_mode") == "ai_suggested" for question in eligible)
    print(f"loaded questions: {len(all_questions)}")
    print(f"eligible questions: {len(eligible)}")
    print(f"mode: {mode}")
    print(f"official count: {official_count}")
    print(f"ai_suggested count: {ai_count}")
    first_ids = [question.get("question_id") for question in eligible[:3]]
    print(f"first 3 question_id: {first_ids}")


def print_summary(stats: dict[str, int]) -> None:
    attempted = stats["correct"] + stats["incorrect"]
    accuracy = (stats["correct"] / attempted * 100) if attempted else 0.0
    official_attempted = stats["official_correct"] + stats["official_incorrect"]
    ai_attempted = stats["ai_correct"] + stats["ai_incorrect"]
    print("\nPractice summary\n")
    print(f"* attempted: {attempted}")
    print(f"* correct: {stats['correct']}")
    print(f"* incorrect: {stats['incorrect']}")
    print(f"* skipped: {stats['skipped']}")
    print(f"* accuracy: {accuracy:.1f}%")
    print(f"* official attempted: {official_attempted}")
    print(f"* official correct: {stats['official_correct']}")
    print(f"* ai_suggested attempted: {ai_attempted}")
    print(f"* ai_suggested correct: {stats['ai_correct']}")
    print("\n注意：AI suggested 的正确率只是参考，不应与 official 混为一谈。")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Practice GRE verbal sample questions in the terminal.")
    parser.add_argument("--questions", required=True, help="Question JSONL path.")
    parser.add_argument("--mode", choices=sorted(VALID_MODES), default="all", help="Question source mode.")
    parser.add_argument("--shuffle", action="store_true", help="Shuffle questions before practice.")
    parser.add_argument("--limit", type=int, default=None, help="Only practice the first N eligible questions.")
    parser.add_argument("--dry-run", action="store_true", help="Print question counts without interactive practice.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    all_questions = load_questions(Path(args.questions))
    eligible = filter_questions(all_questions, args.mode)
    if args.shuffle:
        random.shuffle(eligible)
    if args.limit is not None:
        eligible = eligible[: max(0, args.limit)]

    if args.dry_run:
        dry_run_report(all_questions, eligible, args.mode)
        return
    if not eligible:
        print("No eligible questions found for the selected mode.")
        return

    stats = {
        "correct": 0,
        "incorrect": 0,
        "skipped": 0,
        "official_correct": 0,
        "official_incorrect": 0,
        "ai_correct": 0,
        "ai_incorrect": 0,
    }
    for index, question in enumerate(eligible, start=1):
        result = ask_question(question, index, len(eligible))
        if result == "quit":
            break
        if result == "skipped":
            stats["skipped"] += 1
            continue
        if result == "correct":
            stats["correct"] += 1
            if question.get("answer_mode") == "official":
                stats["official_correct"] += 1
            else:
                stats["ai_correct"] += 1
        elif result == "incorrect":
            stats["incorrect"] += 1
            if question.get("answer_mode") == "official":
                stats["official_incorrect"] += 1
            else:
                stats["ai_incorrect"] += 1
    print_summary(stats)


if __name__ == "__main__":
    main()

