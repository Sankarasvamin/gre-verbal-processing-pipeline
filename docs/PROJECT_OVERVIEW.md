# GRE Verbal 快速刷题项目概览

## 项目目标

本项目用于把本地 GRE PDF 题库逐步整理成可复核、可训练的轻量题库。第一阶段不做完整平台，也不做全量 OCR，只建立稳定的数据结构、抽取流程和样本验证脚本。

核心使用场景：

1. 在空档时间快速练习 GRE verbal 非阅读选择题。
2. 展示题干和选项。
3. 用户作答后判断对错。
4. 展示正确答案。
5. 展示选项核心词汇解释。

## 当前阶段范围

只处理 GRE verbal 部分的非阅读选择题候选，包括：

- text completion
- sentence equivalence
- 单句或短段落填空类 verbal 题

明确排除：

- 作文题
- 数学题
- 阅读题及其 passage 题组
- 图表题、计算题、quant section

## 原始数据边界

原始 PDF 位于项目根目录下的题库目录。需求文档写作 `testbank/`，当前本地实际目录为 `test_bank/`。脚本会同时兼容两个目录名，并优先使用实际存在的目录。

原始 PDF、OCR 图片、中间缓存文件不进入 git。结构化后的轻量 JSONL 可以进入版本管理，例如：

- `data/processed/questions_sample.jsonl`
- `data/processed/questions_pending.jsonl`
- `data/processed/vocab_items.jsonl`
- `data/processed/synonym_groups.jsonl`
- `data/review/questions_candidates_sample.jsonl`

## 第一阶段交付物

- 项目文档
- 数据 schema 初版
- PDF inventory 脚本
- 单 PDF 样本抽取脚本
- 样本候选题 JSONL
- 样本抽取 summary markdown

## 重要原则

所有自动解析结果默认只是候选数据，`status` 必须为 `pending_review`。只有人工复核后，题目才能进入 `accepted` 状态。OCR 或文本层抽取结果不能直接视为正式题库。

