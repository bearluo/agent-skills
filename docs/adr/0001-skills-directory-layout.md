> 状态：已接受
> 日期：2026-09-23
> 摘要：skill 统一放在 `skills/<分类>/<name>/` 下，用 `scripts/link.ps1` 以 junction 挂到 `~/.claude/skills/<name>`，不做成 plugin。
> 依赖：无

# ADR-0001：skill 收进 skills/<分类>/<name>/，用 junction 挂载

## 背景

仓库最初把分类目录（`git/`、`devops/`、`docs/`、`design/`、`gamedev/`、`ai-tooling/`）直接平铺在根目录，这样有几个问题：

- 仓库自己的 `docs/`、`scripts/` 会和 skill 分类混在同一层，而且分类 `docs/` 已经和 project-layout 约定里的 `docs/` 撞名。
- 根目录一眼看不出哪些是 skill、哪些是仓库自身的东西。
- 挂载靠手敲 `New-Item -ItemType Junction`，每新增一个 skill 就要敲一次，移动目录后旧 junction 会悬空。

agent 只认 `~/.claude/skills/<name>/SKILL.md` 这一层，分类只对浏览仓库的人有意义。

## 备选方案

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| **A. `skills/<分类>/<name>/` + `scripts/link.ps1` 建 junction** | 根目录干净；保留分类；改仓库立即生效；skill 名不变 | 新机器要跑一次脚本 | ✅ 采纳 |
| B. 保持分类平铺在根目录 | 不用动 | 撞名，根目录混杂 | ❌ 否决 |
| C. 做成 Claude Code plugin（`.claude-plugin/` + `skills/<name>/`） | `/plugin install` 一键安装，别人装起来方便 | 调用名会带命名空间（`agent-skills:rebase-merge`），全局 CLAUDE.md 和记忆里写的 `/rebase-merge` 都得改；plugin 要求 `skills/<name>/` 平铺，分类会丢；改动要走 plugin 更新，不能改完即生效 | ❌ 否决 |
| D. `skills/<name>/` 平铺，不分类 | 结构最简单，与 plugin 布局兼容 | 13 个以上的 skill 平铺，不好浏览 | ❌ 否决 |

## 决策

skill 一律放在 `skills/<分类>/<name>/`，深度固定两层；`<name>` 全仓唯一，并且等于 frontmatter 的 `name`。`scripts/link.ps1` 扫描这一层的 `SKILL.md`，幂等地在 `~/.claude/skills/<name>` 重建 junction；遇到同名实体目录（第三方或公司内网 skill）时跳过，不覆盖。

## 否决理由

- **B**：分类名 `docs` 和仓库文档目录冲突，不可能两者都叫 `docs/`；而且根目录会随着分类增多越来越杂。
- **C**：代价主要在命名空间。现有的全局约定、记忆、skill 之间的互相引用都用裸名（`/rebase-merge`、`/project-layout`），改成带前缀会牵动很多地方。另外 junction 的「改完即生效」对自用仓库来说比一键安装更重要。
- **D**：分类对浏览有用，而保留分类的成本只是 `link.ps1` 多扫一层目录。

## 代价

- 新机器（或 macOS / Linux）需要跑一次挂载命令；macOS / Linux 的 `ln -s` 写法见 README。
- 分类会被拍平，所以 `<name>` 必须全仓唯一，需要人自己留意。

## 什么时候该推翻

- 这个仓库需要被别人大规模安装使用，一键安装的价值超过了命名空间带来的改动成本 → 考虑方案 C。
- Claude Code 的 plugin 支持不带前缀的调用名，或者支持嵌套的 skill 目录 → 重新评估方案 C。
