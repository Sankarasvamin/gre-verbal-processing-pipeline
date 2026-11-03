# 数据 Schema 初版

## 题目 JSONL

每行是一道题。自动抽取结果必须保留原始信息，默认进入 `pending_review`。

```json
{
  "question_id": "string, stable id",
  "source_pdf": "string",
  "source_pdf_relpath": "string",
  "source_page_start": "integer or null",
  "source_page_end": "integer or null",
  "section_id": "string or null",
  "pdf_section_id": "string or null",
  "answer_key_section_id": "string or null",
  "section_mapping_status": "exact | configured | inferred | unresolved",
  "answer_match_confidence": "high | medium | low | none",
  "answer_match_notes": "string or null",
  "official_answer": ["A"],
  "official_answer_status": "matched | missing | conflicted | not_applicable",
  "ai_suggested_answer": ["A"],
  "ai_answer_confidence": "high | medium | low | none",
  "ai_answer_reasoning_brief": "string or null",
  "answer_mode": "manual | official | ai_suggested | none",
  "manual_answer": ["A"],
  "manual_answer_notes": "string or null",
  "section_type": "verbal | quant | writing | unknown",
  "question_number": "integer or string",
  "question_type": "text_completion | sentence_equivalence | short_verbal | reading | unknown",
  "is_reading": false,
  "keep_for_training": true,
  "stem_raw": "string",
  "stem_clean": "string",
  "options": [
    {
      "label": "A",
      "text_raw": "string",
      "text_clean": "string"
    }
  ],
  "correct_answer": ["A"],
  "answer_source_text": "string",
  "parse_confidence": "high | medium | low",
  "status": "pending_review | accepted | rejected",
  "reject_reason": "string or null",
  "vocab_items": [
    {
      "word": "string",
      "lemma": "string",
      "option_label": "A",
      "part_of_speech": "string or null",
      "zh_meaning": "string or null",
      "en_definition": "string or null",
      "contextual_meaning_zh": "string or null",
      "synonyms": []
    }
  ],
  "raw_block": "string",
  "notes": "string or null"
}
```

## 字段说明

- `question_id`：稳定 ID。当前建议由 PDF 相对路径、题号、题目原始块 hash 生成。
- `source_pdf`：PDF 文件名。
- `source_pdf_relpath`：相对项目根目录路径，便于跨机器复现。
- `source_page_start` / `source_page_end`：题目候选原文所在页码，使用 PDF 中的 1-based 页码。
- `section_id`：自动识别的 section 标识，例如 `section_1`；无法识别时为 `null`。
- `pdf_section_id`：从 PDF 页眉或题块原文中识别出的原始 section 编号，例如屏幕版 `Section 4 of 5` 中的 `4`。它比 `section_id` 更接近 PDF 自身结构，但仍需人工复核。
- `answer_key_section_id`：答案页表格中的 section 编号，例如答案页 `section 4`。该字段不能默认等同于 `section_id` 或 `pdf_section_id`。
- `section_mapping_status`：题目 section 和答案表 section 的匹配状态。`exact` 表示两者编号明确一致，`configured` 表示来自人工维护的 section mapping 配置，`inferred` 表示按样本结构高置信推断，`unresolved` 表示不能确认。
- `answer_match_confidence`：答案匹配可信度。`none` 表示未匹配答案，不能把 `correct_answer` 当成空答案。
- `answer_match_notes`：记录答案匹配依据或失败原因，便于人工复核。
- `official_answer`：从 PDF answer key 中解析并匹配到的官方答案。无法稳定匹配时为 `null`。
- `official_answer_status`：官方答案状态。`matched` 表示已匹配，`missing` 表示当前未能从答案页匹配，`conflicted` 表示官方答案与其它来源存在冲突，`not_applicable` 表示该题不需要官方答案。
- `ai_suggested_answer`：由 AI/LLM 根据题干和选项推断出的参考答案。它不是官方答案。
- `ai_answer_confidence`：AI 参考答案可信度，取值 `high | medium | low | none`。
- `ai_answer_reasoning_brief`：面向用户的简短解释，不存长篇推理。
- `answer_mode`：当前练习/判题优先使用的答案来源，取值 `manual | official | ai_suggested | none`。
- `manual_answer`：人工确认答案，优先级最高。
- `manual_answer_notes`：人工答案备注。
- `section_type`：自动判断的 section 类型，不能直接作为最终结论。
- `question_type`：候选题型。阅读题应标为 `reading`，不明确则为 `unknown`。
- `is_reading`：是否疑似阅读题。
- `keep_for_training`：是否建议进入快速训练候选池。人工确认前只代表自动建议。
- `correct_answer`：当前有效答案的兼容字段，由 `answer_mode` 决定生成，不再直接等同于 official answer。答案优先级固定为 `manual_answer > official_answer > ai_suggested_answer > none`。
- `answer_source_text`：答案区原始片段，便于人工核对。
- `parse_confidence`：解析可信度，不代表题目正确性。
- `status`：自动生成一律为 `pending_review`。
- `vocab_items`：从选项中抽取的词汇候选。第一阶段只填候选词，释义字段可为空。
- `raw_block`：原始题目文本块，人工复核时优先看这里。

## 状态流转

```text
pending_review -> accepted
pending_review -> rejected
rejected -> pending_review
```

`accepted` 必须由人工确认后设置。自动脚本不得直接写入 `accepted`。

## 轻量词汇数据

后续可把题目中的 `vocab_items` 汇总到 `data/processed/vocab_items.jsonl`：

```json
{
  "word": "string",
  "lemma": "string",
  "source_question_id": "string",
  "option_label": "A",
  "part_of_speech": null,
  "zh_meaning": null,
  "en_definition": null,
  "contextual_meaning_zh": null,
  "synonyms": [],
  "status": "pending_review"
}
```
