# 人工复核流程

## 输入文件

样本候选题默认写入：

```text
data/review/questions_candidates_sample.jsonl
```

每条记录都是 `pending_review`，不能直接进入正式训练题库。

## 复核重点

逐题检查：

1. 是否确实属于 verbal。
2. 是否不是阅读题。
3. 题干是否完整。
4. 选项是否完整且标签正确。
5. 答案是否和 PDF 末尾答案区一致。
6. `source_page_start`、`source_page_end` 是否便于回查。
7. `raw_block` 是否保留了足够原始上下文。
8. `vocab_items` 是否包含核心选项词。

## 状态更新

通过复核：

```json
{
  "status": "accepted",
  "reject_reason": null
}
```

不通过复核：

```json
{
  "status": "rejected",
  "reject_reason": "阅读题 / 数学题 / 题干缺失 / 选项缺失 / 答案无法核对"
}
```

需要保留但暂不确定：

```json
{
  "status": "pending_review",
  "notes": "需要回到 PDF 第 N 页人工确认"
}
```

## 正式题库建议

人工确认后的题目再合并到：

```text
data/processed/questions_pending.jsonl
```

其中：

- `accepted` 可进入训练候选池。
- `rejected` 不进入训练。
- `pending_review` 保留在 review 流程内，不参与正式练习。

## 第三阶段 section mapping 复核流程

样本 PDF 的答案页 section 编号和 PDF 页眉 section 编号需要通过人工配置确认，不要在 parser 中硬编码。

建议流程：

1. 先看 `data/review/unresolved_questions_report.md`，优先处理 `keep_for_training=true` 但没有答案的题。
2. 再打开 `data/review/questions_review_table.tsv`，用表格软件快速查看题号、页码、section、题干和选项。
3. 人工确认 `pdf_section_id=3` 是否对应答案页 `answer_key_section_id=2`。
4. 人工确认 `pdf_section_id=5` 是否对应答案页 `answer_key_section_id=4`。
5. 如果确认，修改 `data/review/section_mapping_sample.yaml`，例如把对应 mapping 从 `null` 改为 `"2"` 或 `"4"`。
6. 重新运行 `scripts/apply_section_mapping.py` 生成 `data/review/questions_candidates_sample_mapped.jsonl`。
7. 再运行 `scripts/validate_questions_jsonl.py` 检查 JSONL 结构和答案标签。
8. 从已人工确认的题中抽取一小批，写入 `data/review/gold_sample_template.jsonl`，并把人工字段设置为确认值。
9. 运行 `scripts/test_against_gold_sample.py`，把当前 parser 输出和 gold sample 对比。

当前 `section_mapping_sample.yaml` 中的 `null` 表示尚未人工确认。脚本不会把未确认的 section 映射自动当作事实。
