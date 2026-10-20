# agent-skills

个人整理的通用 Agent Skill 合集（`SKILL.md` 格式，Claude Code / Codex 等支持 skills 的 agent 均可用），放在 `skills/<分类>/<name>/`。

| 分类（`skills/` 下） | Skill | 用途 |
|---|---|---|
| `git/` | `rebase-merge` | rebase 后 fast-forward 合并，保持线性历史 |
| | `weekly-report-from-git` | 从 git 提交生成周报 / 月报 |
| `devops/` | `ci-cd-design` | CI/CD 流水线设计、提速与排障 |
| | `local-service-ports` | 本机服务端口登记表，避免多会话抢端口 |
| | `ssh-remote-hosts` | 用原生 ssh + `~/.ssh/config` 管理远程主机 |
| | `filebrowser-cdn` | 用已有 File Browser 为本地产物创建稳定公开下载链接 |
| | `http-latency-probe` | HTTPS 接口分地区延迟、GeoDNS 线路、回源 keep-alive 复用测试 |
| `docs/` | `drawing-mermaid-diagrams` | Mermaid 画图（兼容旧版渲染器、防子图重叠） |
| | `project-layout` | 新仓库目录结构与 `docs/` 体系约定 |
| | `feishu-minutes-export` | 导出飞书妙记文字记录 |
| `design/` | `pen-design-first` | 改 UI 前先出 .pen 设计稿确认 |
| | `pencil-mcp-session` | 自己新建 / 打开 / 保存 .pen，接通 Pencil MCP |
| | `codex-imagegen` | 委派 Codex 生成图片素材 |
| `gamedev/` | `android-playtest` | Android 模拟器人机协同试玩 |
| | `wechat-minigame-cdp` | 用 CDP 验证微信小游戏 |
| | `funplay-cocos-mcp` | 通过 MCP 驱动 Cocos Creator 3.8 |
| | `cocos-creator-extension-dev` | Cocos Creator 3.8 扩展开发（importer、mount、Inspector、重载与验收） |
| | `cocos-render-perf` | Cocos 在 Android 真机上的渲染性能分析与 A/B |
| `ai-tooling/` | `token-usage-report` | 汇总 Claude Code 历史 token 用量 |

## 安装

Claude Code 从 `~/.claude/skills/<name>/SKILL.md` 加载用户 Skill，Codex 从 `~/.agents/skills/<name>/SKILL.md` 加载；两边的分类都会被拍平。把仓库里的 skill 目录分别链接进去，修改仓库即可同时生效：

```powershell
# Windows：同时维护 Claude/Codex 两套入口（目录 junction，不需要管理员权限，可以重复跑）
powershell -File scripts/link.ps1
```

```bash
# macOS / Linux
mkdir -p ~/.claude/skills ~/.agents/skills
for d in skills/*/*/; do
  name="$(basename "$d")"
  ln -sfn "$PWD/$d" ~/.claude/skills/"$name"
  case "$name" in
    codex-imagegen|funplay-cocos-mcp) ;;
    *) ln -sfn "$PWD/$d" ~/.agents/skills/"$name" ;;
  esac
done
```

`codex-imagegen` 是 Claude 调度 Codex 出图的适配层；`funplay-cocos-mcp` 依赖当前只在 Claude 配置的 MCP，因此暂不挂入 Codex。其他 Skill 即使读取 `~/.claude` 下的共享状态，也以 Claude 环境为主源并同时提供给 Codex。

## 约定

- `description` 用英文（触发匹配用），正文用中文。
- 只收**通用** skill：不写具体项目名、内网地址、个人路径；示例用 `my-game`、`<project>` 等占位。
- 新增 skill 放在 `skills/<分类>/<name>/`，没有合适的分类就新建一个；然后重跑挂载命令，并更新上表。
- 仓库约定的详细说明见 `CLAUDE.md`，目录设计的理由见 `docs/adr/0001-skills-directory-layout.md`。
