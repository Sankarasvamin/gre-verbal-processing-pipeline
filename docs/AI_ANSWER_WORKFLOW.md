# AI Answer Workflow

## 使用边界

AI suggested answer 只作为轻量训练参考，不视为官方答案。官方答案解析逻辑仍保留；当官方答案缺失时，题目可以进入 AI suggested answer 模式。

答案优先级固定为：

```text
manual_answer > official_answer > ai_suggested_answer > none
```

## Request JSONL

`scripts/export_ai_answer_requests.py` 输出每行一个请求对象：

```json
{
  "question_id": "string",
  "question_type": "text_completion | sentence_equivalence | short_verbal",
  "stem_clean": "string",
  "options": [
    {"label": "A", "text_clean": "string"}
  ],
  "instruction": "中文任务说明"
}
```

## Response JSONL

AI answer response 每行结构：

```json
{
  "question_id": "string",
  "ai_suggested_answer": ["A"],
  "ai_answer_confidence": "high | medium | low",
  "ai_answer_reasoning_brief": "简短解释",
  "vocab_items": [
    {
      "word": "string",
      "option_label": "A",
      "part_of_speech": "string",
      "zh_meaning": "string",
      "en_definition": "string",
      "contextual_meaning_zh": "string",
      "synonyms": []
    }
  ],
  "notes": null
}
```

如果 AI 无法判断，`ai_suggested_answer` 设为 `null`，`ai_answer_confidence` 设为 `low`。

