# PDF 抽取计划

## 第一阶段策略

第一阶段只做文本层抽取，不做全量 OCR。

处理顺序：

1. 扫描题库目录下的 PDF。
2. 记录文件大小、页数、文本层存在性。
3. 抽样保存前几页和后几页文本。
4. 对单个 PDF 做样本结构分析。
5. 尝试识别 section 边界、verbal section、answer key 区域。
6. 抽取 verbal 非阅读选择题候选。
7. 写入 review JSONL，等待人工复核。

## Inventory 输出

`scripts/inventory_pdfs.py` 输出到：

```text
data/processed/pdf_inventory.jsonl
```

每行包含：

- `path`
- `relpath`
- `file_size_bytes`
- `page_count`
- `likely_has_text_layer`
- `first_pages_sample`
- `last_pages_sample`
- `error`

## 样本抽取输出

`scripts/extract_sample.py` 输出到：

```text
data/review/questions_candidates_sample.jsonl
data/review/sample_extraction_summary.md
```

## Section 识别思路

候选规则不作为最终判断：

- 出现 `Verbal Reasoning`、`Text Completion`、`Sentence Equivalence`、大量填空和 A-F 选项时，倾向 verbal。
- 出现 `Quantitative Reasoning`、计算符号、图表、单位和数字密集时，倾向 quant。
- 出现 `Analyze an Issue`、`Argument`、作文 instruction 时，倾向 writing。
- 出现 `Answer Key`、`答案`、题号到字母映射密集时，倾向 answer key。

## 非阅读 verbal 过滤规则

保留倾向：

- 题干较短。
- 有明确选项。
- 选项通常是单词、短语或短句。
- 没有长篇 passage。
- 题型可能是填空、双空、三空或 sentence equivalence。

排除倾向：

- 题目前或附近有明显长篇 passage。
- 题干引用 passage 内容。
- 大段文本后跟多道题。
- 数学符号、图表、数量计算明显较多。
- 作文 instruction。
- quant section。
- reading comprehension。

## OCR 后续方案

只有当 inventory 显示 PDF 无文本层或文本层质量不足时，才考虑 OCR。后续 OCR 应单 PDF、小批量、可恢复地执行：

1. 使用 PyMuPDF 渲染指定页为图片。
2. 保存到 `data/ocr_images/`，该目录不进入 git。
3. 调用 OCR 工具生成页级文本。
4. 把 OCR 文本和来源页码写入 `data/cache/`。
5. 继续走同一套候选抽取与人工复核流程。

第一阶段不直接引入全量 OCR，避免产生大量图片和不可控缓存。

