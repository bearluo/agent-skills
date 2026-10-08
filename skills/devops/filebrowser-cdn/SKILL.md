---
name: filebrowser-cdn
description: "Use when a local build artifact needs a stable unauthenticated HTTP URL through an existing File Browser service, such as APK/IPA downloads, OTA or hot-update content, or files shared with another device. Also routes browser-executable web builds to a separate static host when File Browser share responses force download or restrictive CSP. Not for provisioning File Browser or designing a production CDN."
---

# 用 File Browser 分享本地产物

把已经运行的 File Browser 当作开发环境中的公开文件入口：每个项目使用独立目录，每种用途使用独立子目录，并为用途目录创建一个可复用的公开分享。服务地址、凭据、宿主目录和登记表都是机器私有配置，不写进本 skill。

## 使用前检查

需要已有可访问的 File Browser 服务。先确认这些环境变量：

| 变量 | 必需 | 用途 |
|---|---|---|
| `FILEBROWSER_URL` | 是 | File Browser 根地址，例如 `http://<host>:<port>` |
| `FILEBROWSER_USER` | 是 | API 登录用户名 |
| `FILEBROWSER_PASSWORD` | 是 | API 登录密码；不得写入仓库或输出 |
| `FILEBROWSER_HOST_ROOT` | 上传文件时 | File Browser 虚拟根对应的宿主目录 |
| `FILEBROWSER_REGISTRY` | 推荐 | 仓库外的分享登记表路径 |
| `FILEBROWSER_STATIC_BASE_URL` | Web 构建时 | 能直接执行 HTML/JS/WASM 的静态站点根地址 |

缺少服务或变量时，报告缺项；不要擅自部署容器、修改防火墙或创建公网入口。

## 目录与分享规则

```text
<hosting-root>/
  <project>/
    <purpose>/
```

- `<project>` 使用稳定的中性 slug；`<purpose>` 可用 `apk`、`cdn`、`docs`、`web` 等用途名。
- 不在托管根放散文件，也不对托管根创建公开分享。
- 分享建在用途目录；同一路径已有分享时复用，不重复创建。
- 新分享和删除操作同步记录到 `FILEBROWSER_REGISTRY`。登记表必须留在仓库外，不能随 skill 发布。
- 构建产物必须留在项目仓库时，可由用户配置 bind mount 或同步步骤；未经授权不要修改容器编排。

## 管理分享

Claude Code：

```powershell
$fb = "$HOME\.claude\skills\filebrowser-cdn\scripts\fbshare.ps1"
```

Codex：

```powershell
$fb = "$HOME\.agents\skills\filebrowser-cdn\scripts\fbshare.ps1"
```

常用操作：

```powershell
& $fb -List
& $fb -Project my-app -Sub apk
& $fb -Project my-app -Sub cdn
& $fb -Remove <share-hash>
```

脚本只管理 File Browser 虚拟目录和分享，不负责构建或复制产物。创建或复用分享后，把文件放到：

```text
$env:FILEBROWSER_HOST_ROOT/<project>/<purpose>/
```

## 选择正确的 URL

| URL 形态 | 用途 |
|---|---|
| `/api/public/dl/<hash>/<file>` | 设备、脚本、更新器直接下载；免登录 |
| `/share/<hash>` | 给人浏览和点击下载的页面 |
| `/api/raw/<path>` | 需要认证的 API，不是公开下载链接 |

机器下载的 base URL 是：

```text
<FILEBROWSER_URL>/api/public/dl/<hash>/
```

验证文件时使用 `GET` 并检查状态码、内容长度或哈希；不要假设 `HEAD` 一定受支持。不要把 `/share/<hash>` 当作二进制下载 URL，它返回的是 HTML 页面。

## Web/H5 构建

File Browser 的公开下载响应可能附带 `Content-Disposition: attachment`、`application/octet-stream` 或限制脚本执行的 CSP。需要浏览器直接运行 HTML、JavaScript 或 WASM 时：

1. 不使用 `/share/<hash>` 或 `/api/public/dl/...` 作为站点入口。
2. 使用管理员已经配置好的静态站点，并从 `FILEBROWSER_STATIC_BASE_URL` 取得根地址。
3. 将构建目录映射为 `<static-base>/<project>/<purpose>/index.html`。
4. 用真实浏览器验证入口页、脚本、WASM、资源路径和 MIME 类型。

没有静态站点配置时，说明限制并请求用户选择；不要自行把下载服务改造成可执行网页服务。

## 安全边界

- 公开分享意味着拿到 URL 的人无需登录即可访问该目录；只分享最小用途目录。
- 不在分享目录放凭据、数据库、源码缓存或其他项目的产物。
- 不输出密码或登录 token；日志中只保留路径、分享 hash 和公开 URL。
- 临时分享用完后显式删除；长期分享保持 hash 稳定，更新文件时复用原分享。
- 本方案用于开发和受控测试。生产分发、合法域名、HTTPS、访问控制和备案要求应使用正式基础设施。
