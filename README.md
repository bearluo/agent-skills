# agent-skills

个人整理的通用 Agent Skill 合集（`SKILL.md` 格式，Claude Code / Codex 等支持 skills 的 agent 均可用），放在 `skills/<分类>/<name>/`。

| 分类（`skills/` 下） | Skill | 用途 |
|---|---|---|
| `git/` | `rebase-merge` | rebase 后 fast-forward 合并，保持线性历史 |
| | `weekly-report-from-git` | 从 git 提交生成周报 / 月报 |
| `devops/` | `ci-cd-design` | CI/CD 流水线设计、提速与排障 |
| | `local-service-ports` | 本机服务端口登记表，避免多会话抢端口 |
| | `ssh-remote-hosts` | 用原生 ssh + `~/.ssh/config` 管理远程主机 |
| `docs/` | `drawing-mermaid-diagrams` | Mermaid 画图（兼容旧版渲染器、防子图重叠） |
| | `project-layout` | 新仓库目录结构与 `docs/` 体系约定 |
| | `feishu-minutes-export` | 导出飞书妙记文字记录 |
| `design/` | `pen-design-first` | 改 UI 前先出 .pen 设计稿确认 |
| | `codex-imagegen` | 委派 Codex 生成图片素材 |
| `gamedev/` | `android-playtest` | Android 模拟器人机协同试玩 |
| | `wechat-minigame-cdp` | 用 CDP 验证微信小游戏 |
| | `funplay-cocos-mcp` | 通过 MCP 驱动 Cocos Creator 3.8 |
| `ai-tooling/` | `token-usage-report` | 汇总 Claude Code 历史 token 用量 |

## 安装

Agent 只认 `~/.claude/skills/<name>/SKILL.md` 这一层，分类会被拍平。把 skill 目录链接进去即可，改仓库立即生效：

```powershell
# Windows：一次挂上全部 skill（目录 junction，不需要管理员权限，可以重复跑）
powershell -File scripts/link.ps1
```

```bash
# macOS / Linux
for d in skills/*/*/; do ln -sfn "$PWD/$d" ~/.claude/skills/"$(basename "$d")"; done
```

## 约定

- `description` 用英文（触发匹配用），正文用中文。
- 只收**通用** skill：不写具体项目名、内网地址、个人路径；示例用 `my-game`、`<project>` 等占位。
- 新增 skill 放在 `skills/<分类>/<name>/`，没有合适的分类就新建一个；然后重跑挂载命令，并更新上表。
- 仓库约定的详细说明见 `CLAUDE.md`，目录设计的理由见 `docs/adr/0001-skills-directory-layout.md`。
