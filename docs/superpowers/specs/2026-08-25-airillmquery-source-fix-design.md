# airillmquery 来源统计修复设计

## 问题

2026-08-24 最终对话生成从普通文本调用切换为结构化 `generate_dialogue()`。该函数复用 `call_structured()`，而后者把成功调用固定记录为“对话机制”，导致 Airi 的实际对话回复被错误归入“对话机制”，“对话”来源不再正常增长。

情绪分析、知识提取、记忆整理等内部结构化调用仍应归入“对话机制”。现有统计文件只保存日期、来源、模型和聚合次数，不包含逐次调用明细，因此无法可靠拆分已经产生的历史错分数据。

## 修复范围

- 让结构化调用方显式指定统计来源。
- `generate_dialogue()` 指定来源为“对话”。
- 其余现有结构化调用继续默认归入“对话机制”。
- 不修改查询参数、展示格式、日期聚合、持久化结构和已有数据。

## 接口设计

`utils.llm.call_structured()` 增加可选的 `usage_source` 参数，默认值为 `SOURCE_MECHANISM`。该参数沿调用链传入实际执行单次模型请求的结构化创建函数，由后者在 API 成功返回后调用 `record_success(usage_source, model)`。

`plugins.airi_llm.llm_client.generate_dialogue()` 调用结构化接口时显式传入 `SOURCE_CHAT`。通用 `call_llm_json()` 不传参数，继续使用默认的 `SOURCE_MECHANISM`。

这样最终对话虽然使用 JSON 协议，统计语义仍按业务来源归为“对话”；内部分析继续归为“对话机制”。

## 数据流

最终对话：

`generate_dialogue()` → `call_structured(..., usage_source=SOURCE_CHAT)` → 模型 API 成功 → `record_success(SOURCE_CHAT, model)`

内部机制：

`call_llm_json()` → `call_structured()` → 模型 API 成功 → `record_success(SOURCE_MECHANISM, model)`

请求抛出异常时不计数。空内容、JSON 解析失败或业务校验失败仍沿用现有口径，在 API 已成功返回时计数。备用模型按每次实际请求使用的模型名称分别计数。

## 测试

- 先增加失败回归测试，证明当前 `generate_dialogue()` 会被记录为“对话机制”。
- 修复后验证 `generate_dialogue()` 记录为“对话”。
- 验证普通 `call_llm_json()` 仍记录为“对话机制”。
- 验证请求失败不计数，备用模型成功时记录对应模型。
- 执行相关插件加载、Python 编译和 `git diff --check`。

## 历史数据

不自动迁移既有统计。聚合文件无法区分同一天、同一模型下哪些“对话机制”次数来自最终对话，推算迁移会破坏统计可信度。修复从部署新代码后的调用开始生效。
