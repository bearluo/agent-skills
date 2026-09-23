---
name: token-usage-report
description: Use when the user asks about recent token usage / consumption / cost / "最近 token 消耗" / "用了多少 token" / "哪个会话最烧" / Claude Code historical usage across sessions — anything needing cross-session aggregation of local logs that /cost and /usage cannot show.
---

# Token 用量报告

## 概述

`/cost` 只显示当前会话，`/usage` 只显示套餐限额窗口，两者都给不出**跨会话的历史**总量。Claude Code 会把每个会话（以及每个 subagent）写进 `~/.claude/projects/**/*.jsonl`，每条消息都带 `usage`。本 skill 附带一个脚本，解析这些日志，按天 / 模型 / 会话汇总。

## 何时使用

- 「最近 N 天 token 消耗 / 用量 / 花了多少」
- 「哪个 session / 项目最烧 token」
- 对比一段时间内的模型占比（Opus / Sonnet / Haiku）
- 任何 `/cost` 和 `/usage` 回答不了的历史 token 问题

**不适用于**：当前会话的花费（用 `/cost`）、套餐限额状态（用 `/usage`）、Pro/Max 的真实账单（订阅制不按 token 计费）。

## 速查

在任意目录运行（脚本会自动定位 `~/.claude/projects`）：

```bash
python3 ~/.claude/skills/token-usage-report/report.py [flags]
```

| 参数 | 作用 |
|---|---|
| （无） | 最近 2 个自然日，按天 + 模型 |
| `--days N` | 最近 N 天（含今天） |
| `--since YYYY-MM-DD [--until YYYY-MM-DD]` | 指定时间窗 |
| `--by-session` | 追加按会话的 Top-15 明细 |
| `--by-tool` | **按工具结果灌进上下文的体积排名**——做优化时最有用的视图 |
| `--no-subagents` | 排除 `subagents/` 下的记录 |
| `--cost` | 追加按 API 价格折算的粗略美元估算 |
| `--project SUBSTR` | 只统计目录名包含 SUBSTR 的项目 |

完整参数见 `report.py --help`。

## 工作原理

- glob 项目根目录下所有 `*.jsonl`（包括 subagent 的记录）。
- 按 `(message.id, output_tokens)` 去重——同一条 assistant 消息会同时出现在父会话和 resume 出来的会话记录里。
- 按每条记录 `timestamp` 的 UTC 日期前缀分桶。
- 累加 `input_tokens`、`output_tokens`、`cache_creation_input_tokens`、`cache_read_input_tokens`。

## 解读输出（要告诉用户）

- **cache read 通常占大头**（长时间 agentic / 多 subagent 会话里常超过 90%）。总 token 高 ≠ 花费高——cache read 的价格约为 input 的 1/10。
- **今天的数字是不完整的**（只统计到运行那一刻）。
- **日期是 UTC**，不是本地时间——本地深夜的会话可能落到下一个 UTC 日。
- **`--cost` 只是按 API 标价折算的等价值。** Pro/Max 订阅是包月的，不按 token 计费。引用美元数字时一定要说明这一点。
- 结果用 markdown 表格呈现（按天 → 模型分行，最后一个 TOTAL 汇总块），不要直接贴脚本原始输出。

## `--by-tool`：把数字变成优化方案

按天 / 模型 / 会话的视图告诉你**用了多少**；`--by-tool` 告诉你**该改什么**。它通过 `tool_use_id` 把每个 `tool_use`（工具名）和对应的 `tool_result`（返回内容）关联起来，再按灌进上下文的总字符数排名。图片统一按约 1.6k token 计（图片在 token 化之前会被缩放，用 `len(base64)` 会严重高估）。

怎么读：

- **看 `~tok avg`，不是 `~tok total`。** 平均 900 × 500 次调用只是正常干活（`Read`、`Edit`）；平均 10k × 11 次调用就是**参数问题**——这个工具没有 `limit`，或者调用时没传。
- 对每个平均值高的工具，依次问：它有没有我没传的 `limit` / 过滤参数？有没有更窄的同类工具（用 `search_*` 代替 `get_recent_*`，用 `find_*` 代替 `get_hierarchy`）？能不能用 shell 命令加一个 grep 解决？
- 数字是估算（字符数 ÷ 3.5），只用于**排名**，不用于计费，别当成精确的 token 数引用。

## 常见错误

- 忘了默认会统计 subagent——用户只想看主会话的交互用量时加 `--no-subagents`。
- 对订阅用户把 `--cost` 当成真实账单报出去。它不是。
- 把巨大的 cache read 总量当成「浪费的钱」——应该解释缓存的计费方式。
