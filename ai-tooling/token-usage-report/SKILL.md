---
name: token-usage-report
description: Use when the user asks about recent token usage / consumption / cost / "最近 token 消耗" / "用了多少 token" / "哪个会话最烧" / Claude Code historical usage across sessions — anything needing cross-session aggregation of local logs that /cost and /usage cannot show.
---

# Token Usage Report

## Overview

`/cost` shows only the current session; `/usage` shows only plan-limit windows. Neither gives **historical, cross-session** totals. Claude Code writes every session (and every subagent) to `~/.claude/projects/**/*.jsonl` with per-message `usage`. This skill bundles a script that parses those logs and aggregates by day / model / session.

## When to Use

- "最近 N 天 token 消耗 / 用量 / 花了多少"
- "哪个 session / 项目最烧 token"
- Comparing model split (Opus vs Sonnet vs Haiku) over time
- Any historical token question that `/cost` and `/usage` can't answer

**Not for:** current-session cost (`/cost`), plan-limit status (`/usage`), real Pro/Max billing (subscription is not per-token).

## Quick Reference

Run from anywhere (script auto-resolves `~/.claude/projects`):

```bash
python3 ~/.claude/skills/token-usage-report/report.py [flags]
```

| Flag | Effect |
|---|---|
| (none) | Last 2 calendar days, by day + model |
| `--days N` | Last N days incl. today |
| `--since YYYY-MM-DD [--until YYYY-MM-DD]` | Explicit window |
| `--by-session` | Add per-session Top-15 breakdown |
| `--by-tool` | **Rank tools by result payload pulled into context** — the actionable view for optimization |
| `--no-subagents` | Exclude `subagents/` transcripts |
| `--cost` | Add rough API-equivalent $ estimate |
| `--project SUBSTR` | Only project dirs whose name contains SUBSTR |

Full options: `report.py --help`.

## How It Works

- Globs all `*.jsonl` under the projects root (includes subagent transcripts).
- Dedups by `(message.id, output_tokens)` — the same assistant message is logged in both the parent and resumed transcripts.
- Buckets by the UTC date prefix of each record's `timestamp`.
- Sums `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`.

## Interpreting Output (tell the user)

- **Cache read usually dominates** (often >90% of total) in long agentic / multi-subagent sessions. High total tokens ≠ high spend — cache reads are ~1/10th input price.
- **Today's number is partial** (only up to the moment you run it).
- **Dates are UTC**, not local — a late-night local session may land on the next UTC day.
- **`--cost` is API-list-price equivalent only.** Pro/Max subscriptions are flat-rate, not per-token. Always state this caveat when quoting the dollar figure.
- Present results as a markdown table (day → model rows, then a TOTAL block), not raw script output.

## `--by-tool`: turning numbers into an optimization plan

The day/model/session views tell you *how much*; `--by-tool` tells you *what to fix*. It joins each
`tool_use` (name) to its `tool_result` (payload) via `tool_use_id`, then ranks by total characters
pulled into context. Images are charged a flat ~1.6k tokens (they are resized before tokenizing, so
`len(base64)` would wildly overstate them).

Reading it:

- **`~tok avg` is the lever, not `~tok total`.** A tool at 900 avg × 500 calls is just normal work
  (`Read`, `Edit`). A tool at 10k avg × 11 calls is a *parameter problem* — it has no `limit`, or it
  is being called without one.
- For each high-avg tool ask, in order: does it take a `limit` / filter param I'm not passing? is
  there a narrower sibling tool (`search_*` instead of `get_recent_*`, `find_*` instead of
  `get_hierarchy`)? can a shell command do it with a grep on the end?
- Numbers are approximations (chars ÷ 3.5), meant for *ranking*, not for billing. Don't quote them
  as exact token counts.

## Common Mistakes

- Forgetting subagents are counted by default — use `--no-subagents` if the user wants only main-session interactive usage.
- Quoting `--cost` as actual billing for a subscription user. It is not.
- Treating the huge cache-read total as "wasted money" — explain the cache economics instead.
