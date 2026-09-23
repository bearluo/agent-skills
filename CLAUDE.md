# agent-skills

个人整理的通用 Agent Skill 合集（`SKILL.md` 格式）。**公开仓库**（github.com/bearluo/agent-skills），每次提交都等于公开发布。

## 目录结构

```
skills/<分类>/<name>/   一个 skill 一个目录，SKILL.md 在这一层；附带脚本、模板、经验文档都放在该目录内
scripts/               仓库自身的工具（link.ps1：把全部 skill 以 junction 挂到 ~/.claude/skills/）
docs/                  本仓库自己的文档（不是 skill），先看 docs/README.md
```

规则：

- **skill 只能放在 `skills/<分类>/<name>/`，深度固定两层。** `link.ps1` 按这个深度找 `SKILL.md`，放深了不会被挂载。
- `<name>` 必须和 frontmatter 的 `name` 一致，并且在所有分类中唯一，因为挂载后分类这一层会被拍平。
- 新增或移动 skill 后，跑一遍 `powershell -File scripts/link.ps1`（幂等），然后在 `README.md` 的表格里补一行。
- 分类只是给人浏览用的，agent 看不到。没有合适的分类就新建一个，不要往 `skills/` 根目录直接放 skill。
- 实施计划、排查记录写到 `.scratch/`（已加入 gitignore），不要写进 `docs/`。

## 文档规则

目录与文档的通用约定见全局 skill `project-layout`：往 `docs/` 写任何文件前先读 `~/.claude/skills/project-layout/SKILL.md` 的「零、规则速查」。本项目与通用约定不同的地方写在下面，**以这里为准**；加一条要用户拍板：

- `skills/` 下的文件不受 docs 规则约束（不要求头部、不限文件名），它们按 skill 自己的格式写。

先看 `docs/README.md` 文档地图。

## 写 skill 的约定

- frontmatter 的 `description` 用英文，沿用 “Use when …” 的写法；正文用中文；`name` 用 kebab-case。
- 只收通用 skill：正文里不出现具体项目名、业务名词、实测数字，示例一律用占位写法（`my-game`、`<project>`、`<serial>`）。
- 机器私有的数据（端口登记表、坐标、包名、设备号）放在仓库外（`~/.claude/` 或个人记忆），仓库里只放模板。
- `.ps1` 如果含非 ASCII 字符，必须存成 UTF-8 **带 BOM**，否则 Windows PowerShell 5.1 会按 GBK 读，中文注释会把下一行代码吞掉。不想加 BOM 就把注释全写成 ASCII。

## 业务红线

1. **提交前 grep 敏感信息**，命中就改成占位写法。要查的包括：公司域名、内网 IP、本机绝对路径、具体项目名、账号、token。具体关键词放在仓库外的 `~/.claude/agent-skills-sensitive.txt`（每行一个正则），**不要写进仓库**：
   `git diff --cached | grep '^+' | grep -niEf ~/.claude/agent-skills-sensitive.txt`
2. **换行符只能是 LF**（已在 `.gitattributes` 固定）。`SKILL.md` 或 agent 文件一旦变成 CRLF，frontmatter 解析会失败：skill 的描述会变样，agent 会直接消失。

## 不要做的事

- 不要收录第三方 skill，也不要收录跟公司内网绑定的 skill，这些留在 `~/.claude/skills/` 的实体目录里。
- 不要改成 Claude Code plugin 的形式分发，理由见 `docs/adr/0001-skills-directory-layout.md`。
