---
name: weekly-report-from-git
description: Use when the user asks to write / generate a weekly report (周报) / work summary / 本周做了什么 / 月报 / standup from git history — anything needing commits aggregated into a readable progress narrative across one or more repos.
---

# Weekly Report from Git

## Overview

Weekly reports are tedious to write by hand and people forget what they did. Every commit already records it. This skill bundles a script that scans git history, filters by week + author, parses Conventional Commit subjects (`type(scope): subject`), and emits a structured digest grouped by repo → type → scope. **The script collects; you write the prose.**

## When to Use

- "帮我写周报 / 生成周报 / 本周工作总结 / 月报 / standup"
- "我这周/上周做了什么"
- Summarizing progress across multiple repos for a report

**Not for:** raw `git log` dumps (just run git), or release changelogs for end users (different audience/format).

## Workflow

1. Run the script to get the structured digest (see Quick Reference).
2. **Turn the digest into prose** — do NOT paste raw commit lines as the report:
   - Group by outcome/feature, not by commit. Multiple commits → one bullet.
   - Lead with `feat`/`fix` impact; fold `chore`/`style`/`build`/`ci` into a brief "工程维护" line.
   - Use the `[scope]` tags to organize by module/area.
   - Use `--body` output (the "why") to explain significance, not just what changed.
   - Write in the user's language (Chinese here) and their report's usual structure.
3. **Write the report to `docs/reports/`** (relative to the repo root) as a Markdown file — name it by window, e.g. `docs/reports/2026-W22.md` (ISO week) or `docs/reports/2026-05-25_2026-05-29.md` for an explicit range. Create the folder if missing.
4. Show the draft; offer to adjust granularity or window.

## Quick Reference

```bash
python3 ~/.claude/skills/weekly-report-from-git/weekly.py [flags]
```

| Flag | Effect |
|---|---|
| (none) | Current repo, this week (Mon→today), author = repo `user.email` |
| `--repo PATH` | Repo to scan (repeatable; default cwd) |
| `--since YYYY-MM-DD [--until …]` | Explicit window (overrides "this week") |
| `--all-authors` | Everyone's commits, not just the user's |
| `--author SUBSTR` | Override author filter (name or email) |
| `--branch NAME` | One branch only (default: all branches) |
| `--stat` | Add files / +insertions / -deletions aggregate |
| `--body` | Include commit body — the "why" (use this for good reports) |

Full options: `weekly.py --help`. **Recommended default run:** `--stat --body`.

## How It Works

- Default window = Monday 00:00 of the current week → today (configurable).
- Default author = each repo's `git config user.email` (a weekly report is *your* work). `--all-authors` for team-wide.
- Scans **all branches** by default (`git log --all`) so feature-branch work counts; dedups commits by short hash.
- Excludes merge commits. Unrecognized subjects fall under an `other` group.
- Forces UTF-8 stdout so Chinese commit subjects render in Windows consoles.

## Common Mistakes

- **Pasting commit lines verbatim as the report.** The digest is raw material; synthesize it. One feature spanning 8 commits = one sentence about the feature.
- Forgetting `--all-authors` when the user wants a team report (default is the user only).
- Reporting `chore`/`build`/`ci` noise prominently — collapse it.
- Wrong window: if the user says "上周", pass explicit `--since/--until` (default is *this* week).
- Multi-repo: pass `--repo` once per repo; don't assume only the current one.
