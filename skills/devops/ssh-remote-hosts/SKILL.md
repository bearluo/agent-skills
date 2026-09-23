---
name: ssh-remote-hosts
description: Use when running commands on, copying files to/from, port-forwarding to, or adding/renaming a remote server over SSH — or whenever you need to know which remote hosts exist and what they are for. Covers the ~/.ssh/config-as-single-source-of-truth convention (comments carry purpose and a [生产]/production marker), non-interactive ssh flags, pushing keys on Windows (no ssh-copy-id), and why not to use an ssh MCP server.
---

# 远程主机（原生 ssh + `~/.ssh/config`）

## 核心

**主机清单只有一处：`~/.ssh/config`。** 每个 `Host` 块上方写一行注释说明用途；生产机在注释里标 `[生产]`。不要在 CLAUDE.md、记忆、文档里另抄一张主机表——两处必然不同步。

```
# 本地测试机，Ubuntu 24.04
Host devbox
    HostName 10.0.0.20
    User ubuntu
    IdentityFile ~/.ssh/id_ed25519

# [生产] 生产机，改动前先确认
Host prod-app
    HostName 203.0.113.10
    User root
    IdentityFile ~/.ssh/id_ed25519
```

## 用之前先看清单

```bash
cat ~/.ssh/config              # 别名、用途、[生产] 标记一次看全
ssh -G <别名> | grep -E '^(hostname|user|identityfile) '   # 解析后的实际参数
```

目标主机注释里有 **`[生产]`** → 只读命令（查日志、看状态）可以直接跑；**任何写操作**（改文件、重启服务、装包、docker 操作、删东西）先把要跑的命令给用户看，得到确认再执行。

## 常用操作

| 要做 | 命令 |
|---|---|
| 跑命令 | `ssh -o BatchMode=yes <别名> "命令"` |
| 提权 | `ssh <别名> "sudo -n <命令>"`（`-n`：要密码就直接失败，不卡住） |
| 传文件 | `scp <本地> <别名>:<远程>`；目录用 `rsync -az`（远端没装 rsync 就用 scp -r） |
| 端口转发 | `ssh -N -L <本地端口>:localhost:<远程端口> <别名>`（放后台跑） |
| 连通性检查 | `ssh -o BatchMode=yes -o ConnectTimeout=5 <别名> true` |

- 非交互场景一律加 `-o BatchMode=yes`：公钥没配好时立刻报错，而不是卡在密码提示上等一个永远不会来的输入。
- 从 PowerShell 调用时，远程命令里有 `$` 变量要用**单引号**包，否则会被本地 PowerShell 先展开；Git Bash 里同理用单引号。

## 加一台机器

1. 往 `~/.ssh/config` 追加一个 `Host` 块，**上方写注释**（用途；生产机加 `[生产]`）。
2. 推公钥。Windows 自带 OpenSSH **没有 `ssh-copy-id`**，用：
   ```powershell
   type $HOME\.ssh\id_ed25519.pub | ssh <别名> "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
   ```
   （这一步要输一次密码，让用户自己在终端跑：`! <上面的命令>`）
3. 验证：`ssh -o BatchMode=yes <别名> true` 无报错即可。立即生效，不用重启会话。

## 改 IP / 改名

- **别名按角色命名**（`devbox`、`prod-app`），不要按 IP 命名（`dev20`）——IP 一变名字就骗人。
- 只改 IP：改 `HostName` 一行即可。
- 要改名：把旧名留作第二个别名 `Host newname oldname`，已有脚本和记忆里的旧名继续能用。

## 不要做的事

- **不要用 ssh 类 MCP server。** 它是常驻进程、工具定义长期占上下文、密码常常明文写在 MCP 配置里、加机器要重启会话；原生 ssh 全都没有这些问题。
- 不要把密码写进任何文件；只用公钥。
- 不要在 `~/.ssh/config` 以外维护主机表。
