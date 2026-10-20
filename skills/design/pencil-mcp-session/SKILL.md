---
name: pencil-mcp-session
description: Use before calling any Pencil MCP tool (mcp__pencil__*), or when a .pen file must be created, opened, or saved — including errors like "failed to connect to running Pencil app" or "A file needs to be open in the editor". Covers creating an empty .pen, opening it in the Pencil desktop app, verifying the MCP connection, and saving to disk, all without asking the user to do it by hand.
---

# 自己把 Pencil MCP 接上：新建 / 打开 / 保存 .pen

`mcp__pencil__*` 只能操作 **Pencil 桌面端当前打开的那个文件**。文件没开、应用没起，工具一律报错。这些步骤全都可以自己做，**不要停下来让用户去点 Pencil**。

## 报错对照

| 报错 | 含义 | 处理 |
|---|---|---|
| `failed to connect to running Pencil app: desktop … transport not connected` | Pencil 桌面端没在运行（或 MCP server 绑的是另一个 app，如 VS Code 扩展） | 启动 Pencil 并打开文件（见下）；仍报错再查 MCP server 的 `--app` 参数 |
| `A file needs to be open in the editor to perform this action` | 应用在运行，但没有打开文件 | 新建或打开 `.pen`（见下） |

`get_guidelines` 这类看起来与文件无关的工具，没开文件时也会报第二条。

## 1. 新建（文件还不存在时）

`.pen` 是明文 JSON（MCP 文档说加密，实测不是）。建一个最小文件，目录要先存在：

```bash
mkdir -p <dir>
printf '{\n  "version": "2.17",\n  "children": []\n}\n' > <dir>/<name>.pen
```

`version` 照抄本机已有 `.pen` 文件的值更稳；应用打开后会按自己的版本保存。

## 2. 用桌面端打开

找到可执行文件后，把**绝对路径**作为参数启动；应用已在运行时也这样做，它会切到这个文件：

```powershell
# Windows：从运行中的进程找路径
(Get-Process Pencil -ErrorAction SilentlyContinue | Select-Object -First 1).Path
& "<Pencil.exe 路径>" "<绝对路径>\<name>.pen"
```

- 没在运行时，看 Agent 的 MCP 配置：pencil server 的 `command` 形如 `<安装目录>\resources\app.asar.unpacked\out\mcp-server-*.exe`，`Pencil.exe` 就在 `<安装目录>` 下。
- 后台启动，等几秒再调 MCP。
- npm 里的 `pencil` / `pen` 命令是 pen.dev 的 AI 作图 CLI（会另起一个 agent 去画），**不是**打开文件用的。
- macOS（**未验证**）：`open -a Pencil "<绝对路径>/<name>.pen"`。

## 3. 确认连上

```
mcp__pencil__get_editor_state(include_schema: true)
```

返回的 "Currently active editor" 必须是你要的那个路径。不是就回到第 2 步。

## 4. 保存到磁盘

MCP 的改动只在应用内存里，**磁盘上的文件不会自动更新**；应用只往 `~/.pencil/backup/` 写备份。提交 git、删目录、换文件之前必须保存。

Windows 上给窗口发 Ctrl+S（窗口标题是 `file:///<路径>`）：

```powershell
$p = Get-Process Pencil | Where-Object { $_.MainWindowTitle -like '*<name>.pen' } | Select-Object -First 1
$w = New-Object -ComObject WScript.Shell
$null = $w.AppActivate($p.Id); Start-Sleep -Milliseconds 600; $w.SendKeys('^s')
```

保存后核对文件大小与修改时间确实变了，再提交。

## 注意

- **应用开着时不要直接改磁盘上的 JSON**：应用下次保存会用内存里的版本覆盖。小改动也走 MCP；只有应用没打开这个文件时，才直接编辑 JSON。
- **文件在临时目录（如 git worktree）里**：删目录前先保存、合并，再用第 2 步打开正式位置的那份，否则应用里开着的是一个已经不存在的路径。
- 何时该画图、图放哪，见 skill `pen-design-first`；本 skill 只管把工具接通。
