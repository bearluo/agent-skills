---
name: local-service-ports
description: Use when about to start, launch or run any long-running local service that binds a TCP port (frontend/backend dev server, API, database, mock, debug proxy), when picking a port for localhost, or when hitting "port already in use"/EADDRINUSE — so services started in different Claude Code windows/sessions never grab the same port.
---

# 本机服务端口分配（跨会话）

## 核心
本机所有会 bind 端口的长驻服务，端口统一登记在一张**跨所有 Claude Code 窗口/会话共享**的表里。起服务前先查表，避免不同会话起服务时抢占同一个端口。

**端口表位置：`~/.claude/local-service-ports.md`**（每台机器一份，不进 skill 仓库；不存在就把本 skill 目录下的 `ports.md` 模板拷过去）

## 起服务前必做
1. **先读端口表** `~/.claude/local-service-ports.md`。
2. 表里该服务/项目**已分配过端口** → 直接复用，不要另起新端口。
3. 没有 → 选一个「表里未占用、且本机当前也没在监听」的端口，确认空闲后**在表里追加一行**登记（端口 / 服务·项目 / 协议 / 状态=`使用中` / 启动命令 / 登记时间 / 备注），再起服务。

## 查端口是否空闲
```powershell
Get-NetTCPConnection -LocalPort <端口> -ErrorAction SilentlyContinue   # 有输出 = 已被占用
```
或 `netstat -ano | findstr :<端口>`。

## 服务下线
永久停掉某服务时，把它那一行状态改成 **已释放**（或删行），把端口让出来。

## 端口段轻约定（够用即可，非硬性）
| 段 | 用途 |
|----|------|
| `3000-3999` | 前端 dev / 静态 |
| `8000-8999` | 后端 HTTP API |
| `5000-5999` | 数据库 / 中间件 |
| `9000-9999` | 调试 / 杂项 |
