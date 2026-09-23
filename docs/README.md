> 状态：活文档
> 摘要：agent-skills 仓库的文档地图，按任务路由到对应文档。
> 何时读：不知道该打开哪个文档时。
> 依赖：无

# agent-skills 文档地图

这里只放**仓库本身**的文档；每个 skill 的内容都在 `skills/<分类>/<name>/` 里。

## 要做什么 → 读哪个

| 你的任务 | 打开 |
|---|---|
| 新增 / 修改 skill，遵守仓库约定 | `../CLAUDE.md` |
| 安装、挂载 skill | `../README.md` |
| 了解目录为什么是 `skills/<分类>/<name>/`、为什么用 junction 而不是 plugin | `adr/0001-skills-directory-layout.md` |

分层、头部规范、命名规则见全局 skill `project-layout`（`~/.claude/skills/project-layout/SKILL.md`），不在此重复。
