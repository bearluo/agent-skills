---
name: weekly-report-from-git
description: Use when the user asks to write / generate a weekly report (周报) / work summary / 本周做了什么 / 月报 / standup from git history — anything needing commits aggregated into a readable progress narrative across one or more repos.
---

# 从 git 生成周报

## 概述

手写周报很烦，而且人会忘记自己做过什么，但每个 commit 都已经记下来了。本 skill 附带一个脚本：扫描 git 历史，按周 + 作者过滤，解析 Conventional Commit 标题（`type(scope): subject`），输出按 仓库 → type → scope 分组的结构化摘要。**脚本负责收集，你负责写成文字。**

## 何时使用

- 「帮我写周报 / 生成周报 / 本周工作总结 / 月报 / standup」
- 「我这周/上周做了什么」
- 为汇报汇总多个仓库的进展

**不适用于**：直接看 `git log` 原始输出（直接跑 git 就行），或面向最终用户的发布 changelog（受众和格式都不同）。

## 流程

1. 运行脚本拿到结构化摘要（见「速查」）。
2. **把摘要写成文字**——不要把 commit 原文当周报贴出来：
   - 按成果 / 功能分组，不按 commit 分。多个 commit → 一条要点。
   - 先写 `feat` / `fix` 的影响；`chore` / `style` / `build` / `ci` 收成一句简短的「工程维护」。
   - 用 `[scope]` 标签按模块 / 领域组织。
   - 用 `--body` 输出（commit 的「为什么」）说明意义，而不只是改了什么。
   - 用用户的语言、按用户周报惯用的结构写。
3. **把周报写到 `docs/reports/`**（相对仓库根目录），Markdown 文件，按时间窗命名，例如 `docs/reports/2026-W22.md`（ISO 周）或 `docs/reports/2026-05-25_2026-05-29.md`（指定日期范围）。目录不存在就建。
4. 展示草稿，询问是否要调整粒度或时间窗。

## 速查

```bash
python3 ~/.claude/skills/weekly-report-from-git/weekly.py [flags]
```

| 参数 | 作用 |
|---|---|
| （无） | 当前仓库，本周（周一 → 今天），作者 = 仓库的 `user.email` |
| `--repo PATH` | 要扫描的仓库（可重复；默认当前目录） |
| `--since YYYY-MM-DD [--until …]` | 指定时间窗（覆盖「本周」） |
| `--all-authors` | 所有人的 commit，不只是用户自己的 |
| `--author SUBSTR` | 覆盖作者过滤（名字或邮箱） |
| `--branch NAME` | 只看一个分支（默认所有分支） |
| `--stat` | 追加文件数 / +新增行 / -删除行汇总 |
| `--body` | 包含 commit 正文——「为什么」（写好周报要用这个） |

完整参数见 `weekly.py --help`。**推荐默认跑法：** `--stat --body`。

## 工作原理

- 默认时间窗 = 本周一 00:00 → 今天（可配置）。
- 默认作者 = 每个仓库的 `git config user.email`（周报写的是**你自己的**工作）。团队周报用 `--all-authors`。
- 默认扫描**所有分支**（`git log --all`），功能分支上的工作也算；按短哈希去重。
- 排除 merge commit。识别不了的标题归到 `other` 组。
- 强制 stdout 用 UTF-8，保证中文 commit 标题在 Windows 控制台正常显示。

## 常见错误

- **把 commit 原文当周报贴出来。** 摘要是原材料，要提炼。一个功能跨了 8 个 commit = 一句话讲这个功能。
- 用户要团队周报时忘了加 `--all-authors`（默认只统计用户自己）。
- 把 `chore` / `build` / `ci` 这类杂项写得很显眼——应该收起来。
- 时间窗错了：用户说「上周」时要显式传 `--since/--until`（默认是**本周**）。
- 多仓库：每个仓库传一次 `--repo`，别以为只有当前仓库。
