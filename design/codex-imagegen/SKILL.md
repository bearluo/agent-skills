---
name: codex-imagegen
description: Use when the user wants an AI-generated raster image asset — a game sprite, character art, item/UI icon, texture, illustration, product/UI mockup, logo concept, or transparent-background PNG cutout — and expects Claude to actually produce the image file. Claude Code has no built-in image generator, so it delegates the generation to a Codex worker through Orca orchestration. Also use to reproduce, hand off, or troubleshoot that dispatch-to-Codex image pipeline. Background removal / transparency is NOT automatic — the user removes backgrounds themselves with their own (non-unified) tools; this skill only generates the raw image and never auto-keys or auto-cuts.
---

# Codex 出图（经 Orca orchestration）

## 概述
Claude Code 自己**没有**文生图工具；Codex CLI 有内置 `image_gen`（真·文生图，**无需 `OPENAI_API_KEY`**）。所以「让 Claude 出图」= 把出图任务经 **Orca orchestration** 派给一个 Codex worker，等它回 `worker_done`，再取回 PNG。这是 supervised 编排流程（不是甩手交接）。

> ⚠️ **本 skill 只负责「出图」。去背景/透明化不由 Claude 自动做**——用户有自己一套（不统一的）去背景工具，自己手动抠。**除非用户明确要求，否则绝不擅自跑抠图/绿键**（`remove_chroma_key.py`、`grid_slice.py --transparent` 等），也不要默认强制绿幕底、不要在 prompt 里默认要求透明背景。默认交付**原图**，背景处理交回用户。

## 前置
- `orca status --json` 的 `runtime.state == "ready"`，且 `orca` 在 PATH（不是 `orch`）。
- 自己的 coordinator handle = 环境变量 `ORCA_TERMINAL_HANDLE`（PowerShell: `$env:ORCA_TERMINAL_HANDLE`）。worker 的 `worker_done` 会回到这个 handle。

## Quick Reference（出图流程 7 步）

| 步 | 命令 |
|----|------|
| 1 备 worker | `orca terminal create --worktree active --title bunny-asset --command "codex" --json` → 记 `handle` |
| 2 等就绪 | `orca terminal wait --terminal <h> --for tui-idle --timeout-ms 60000 --json` |
| 3 建任务 | `orca orchestration task-create --spec "<结构化 prompt + 要求>" --json` → 记 `taskId` |
| 4 派发注入 | `orca orchestration dispatch --task <taskId> --to <h> --from $env:ORCA_TERMINAL_HANDLE --inject --json` |
| 5 确认已提交 | `orca terminal read --terminal <h> --json --limit 8`（见「常见坑」paste 未提交） |
| 6 等回执 | `orca orchestration check --wait --types worker_done,escalation,decision_gate --timeout-ms 570000 --json` |
| 7 验收 | 从 `payload.filesModified` 取路径 → `Test-Path` + 尺寸 → `Read` 看图（**不代去背景**，交回用户） |

**别开新 worktree**（用户偏好）：`--worktree active` 在当前工作树里开 fresh Codex 会话即可，`fresh worker` 指新 agent 会话，不是新 git worktree。

## 步骤要点

- **步 2 若 `blockedReason: codex-update-prompt`**：Codex 弹了升级提示挡住 idle。`orca terminal read` 看到 `1. Update now / 2. Skip / 3. Skip until next version`，发 `orca terminal send --terminal <h> --text "2" --enter --json` 选 Skip，再 `wait` 一次。**不要**直接回车（默认高亮在 Update now）。
- **步 5 关键坑（几乎每次都要做）**：`--inject` 返回 `injected:true` 只代表内容**粘进了输入框**。实测当前 Codex 版本**几乎总是只粘贴、不自动回车**（不限于 MCP 启动期，idle 状态也复现）。所以把「读一眼 → 补回车」当**标准步骤**：`terminal read --limit 8` 尾部若是 `… [Pasted Content NNNN chars]` 停在 `›` 提示符，就补 `orca terminal send --terminal <h> --text "" --enter --json`，再 read 确认它进入 `Working…`。
- **步 6**：出图约几分钟。`check --wait` 会周期吐 `{_keepalive:true}` 心跳，正常。超时或 `count:0` 是**检查点不是失败**，继续再 wait。PowerShell 工具超时要 ≥ orca 的 `--timeout-ms`（如 orca 570000 / 工具 600000）。
- **步 7**：`worker_done` 带匹配的 `taskId`+`dispatchId` 时，Orca **自动**把 task/dispatch 标记完成——**别**再 `task-update --status completed`。验收只做 `Test-Path` + 尺寸 + `Read` 看图；**背景/透明交回用户自己处理，别自动抠图**。

## task-create 的 spec 怎么写

spec 是要**注入给 Codex** 的整段文字。写清 4 块：
1. 目标一句话（出什么图、什么用途）。
2. 结构化 prompt（借 Codex imagegen 的骨架）：`Use case:`（如 `stylized-concept` / `product-mockup` / `logo-brand`）、`Asset type:`、`Primary request:`、`Style/medium:`、`Composition:`、`Constraints:`、`Avoid:`。
3. 输出规格 + **绝对路径**（如 `<project>/assets/bunny.png`，让它建目录）。
4. 要求它在 `worker_done` 的 body 里如实回报「出图流程」（用了什么工具/命令、前置依赖、最终 prompt、输出路径、可复现性），并只新增文件、不动仓库其它文件。

**背景/透明由用户自理（默认不碰）**：不要默认强制绿幕，更不要在 spec 里默认要求透明背景，也不要代抠图。**仅当用户明确要「出成便于自己去背景的纯色底图」时**，才在 prompt 里要求主体画在一整块纯色底上（颜色按用户指定，无阴影/渐变/纹理/地面/文字/水印，主体不得含该底色）——但仍**只生成、不代抠**，去背景是用户用自己的工具做。

## 出图内部配方（供理解 / 直接复现）

Codex 侧默认路径（无需 key）：
- 生成源默认落在 `%APPDATA%\orca\codex-runtime-home\home\generated_images\<uuid>\ig_*.png`（即 `$CODEX_HOME/generated_images/...`）。
- 去背景工具（**Claude 不自动跑；仅在用户要求时把命令给用户参考**，用户有自己一套工具）：Codex 自带一个 `remove_chroma_key.py`（`$CODEX_HOME/skills/.system/imagegen/scripts/`），能把纯色 chroma-key 底转 alpha：
  ```powershell
  python "%USERPROFILE%\.codex\skills\.system\imagegen\scripts\remove_chroma_key.py" `
    --input <src.png> --out <final.png> `
    --auto-key border --soft-matte --transparent-threshold 12 --opaque-threshold 220 --despill
  ```
  残留绿边加 `--edge-contract 1`。**别擅自执行。**
- 需要固定尺寸再用 Pillow resize（如 1024x1024 RGBA）。
- 依赖：Codex 内置 `image_gen` + Python/Pillow + 该 helper。**无** `OPENAI_API_KEY` / 本地模型。
- **真·原生透明**（毛发/玻璃/反光/烟雾等 chroma-key 抠不净时）才需 CLI fallback `gpt-image-1.5 --background transparent`，要 `OPENAI_API_KEY`——**先问用户**再走，别自动降级。

## 常见坑

| 现象 | 处理 |
|------|------|
| `wait` 返回 `blockedReason: codex-update-prompt` | `send --text "2" --enter` 选 Skip，别直接回车 |
| `injected:true` 后 read 见 `[Pasted Content N chars]` 停在 `›`（几乎每次） | 补 `send --text "" --enter` 提交，当作标准步骤 |
| `terminal read/dispatch` 报 `terminal_handle_stale` | `orca terminal list --worktree active --json` 重新解析，只用新 handle |
| `⚠ MCP client for github failed to start` | 无害（缺 `GITHUB_PAT_TOKEN`），忽略 |
| 想省事全甩手、不必盯回执 | 改用 `orca worktree create --agent codex --prompt "<出图任务>"` 或 `terminal send`（不挂 lifecycle，**没有** worker_done） |

## 完整示例（一次成功出图的实际序列）

```powershell
# 0. 自己的 handle 在 $env:ORCA_TERMINAL_HANDLE
# 1. 当前 worktree 内开 fresh Codex（不开新 worktree）
orca terminal create --worktree active --title bunny-asset --command "codex" --json   # -> term_XXXX
# 2. 等就绪；若 update 提示挡住：send --text "2" --enter 再 wait
orca terminal wait --terminal term_XXXX --for tui-idle --timeout-ms 60000 --json
# 3. 建任务（spec 含结构化 prompt + 输出绝对路径 + 回报流程；背景按用户要求，默认不强制绿幕/不要透明）
orca orchestration task-create --spec "<...>" --json                                  # -> task_YYYY
# 4. 派发注入
orca orchestration dispatch --task task_YYYY --to term_XXXX --from $env:ORCA_TERMINAL_HANDLE --inject --json
# 5. 确认提交（若 [Pasted Content] 停在 › 就补回车）
orca terminal read --terminal term_XXXX --json --limit 8
# 6. 等 worker_done（滚动等待，别轮询）
orca orchestration check --wait --types worker_done,escalation,decision_gate --timeout-ms 570000 --json
# 7. 验收：Test-Path + 尺寸 + Read 看图（不代去背景，交回用户）
```

产物示例：`examples/my-game/assets/bunny.png`，1024x1024（背景/透明由用户自己后处理）。

## 图集/网格模式（多图一次出，省 1024² 浪费）

image_gen 每次固定吐 **1024x1024**，单张只画一个小图标很浪费。把 N 个小资源打包进**一张**网格图，一次生成、事后切片。脚本在本 skill 的 `scripts/` 下（`grid_layout.py` / `grid_slice.py`，本机需 Python + Pillow）。

三步：

1. **出模板 + 布局**（本机跑）：
   ```powershell
   python <skill>\scripts\grid_layout.py --labels "carrot,clover,coin,star" `
     --canvas 1024 --gutter 28 --margin 28 --bg "#00ff00" `
     --out-template <dir>\template.png --out-layout <dir>\layout.json
   ```
   `--labels` 决定格数并自动近似正方形网格（也可 `--cols/--rows` 指定）。产出的 `template.png` 就是喂给 Codex 的**「样例图片」**：绿幕 + 每格编号 + 标签；`layout.json` 记每格像素坐标供切片。

2. **让 Codex 填格**（走上面的 orchestration 出图流程，spec 里写清）：
   - 附 `template.png` **绝对路径**，要求它**先 `view_image` 打开模板**当排版参考。
   - 明确「第 N 格 = 什么」、每个居中留白、**不得越格/画进邻格**。
   - **输出不要画网格线/编号/标签**；整张一块纯 `#00ff00` 绿幕；主体任何部位不得含 key 色。
   - 输出 1024x1024 存到 `<dir>\filled.png`。

3. **切片**（本机跑，**默认保留原背景、不去背景**）：
   ```powershell
   python <skill>\scripts\grid_slice.py --input <dir>\filled.png --layout <dir>\layout.json `
     --out-dir <dir>\tiles --inset 10 [--resize 256]
   ```
   `--inset` 每格四边内缩，防切到网格线/邻格。切出的单张**保留生成时的背景**，去背景交给用户用自己的工具。
   （`grid_slice.py` 有个 `--transparent --key <hex>` 的简易绿键选项，但**仅在用户明确要时**才加，一般不加。）

**可靠性与坑：**
- **排版不像素级精确**：模型只是近似照模板摆位。→ 靠 gutter（格间距）+ 切片 inset 兜底；主体只要不越格就能干净切出。
- **若用户选了纯色底方便自己去背景**：提醒用户底色别撞主体色——绿色主体（四叶草/树叶/菜叶）配 `#00ff00` 绿底，用户去背景时容易把主体的绿也吃掉。建议底色避开主体色（绿色主体用品红 `#ff00ff`、蓝色主体避开 `#0000ff`）。这只是选底色的提示；**抠图本身由用户做，Claude 不代跑**。
- **格子别太多 / 高密度下模板控制失效**（实测 32×32=1024 格、每格 30px）：单个 ~30px 图标其实**能画得清晰可辨**（质量意外地好）。但高密度下两件事会崩——① image_gen **无法一次对齐到密集网格**：编号模板在 32×32 密度下不起作用，Codex 得靠后处理（检测抠出图标 + 重新平铺）才拼成整齐网格；② 一张 1024² 里模型实际只产出**约几百个不同**图标（实测约 379），其余是重复，想要上千个各不相同不现实。→ 需要**精确「第 N 格 = 什么」的模板控制**时，用**低密度**（≤ 4×4，每格 ≥ ~120px）；只是要「一堆小图标随便摆、事后按图标检测切」则可用高密度。「画大再缩小」对 30px 很友好。
