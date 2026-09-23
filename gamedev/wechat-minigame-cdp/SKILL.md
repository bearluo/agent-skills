---
name: wechat-minigame-cdp
description: Use when verifying a WeChat Mini Game (小游戏, compileType "game") running in WeChat DevTools — read its console/exceptions programmatically, evaluate JS inside the game context, or screenshot the canvas, instead of asking the human to eyeball the DevTools console. Works for any engine that compiles to WeChat minigame (Godot, Cocos, Unity, Laya…). Note miniprogram-automator and wechat-devtools-mcp CANNOT drive minigames; this skill uses the Chrome DevTools Protocol directly.
---

# 微信小游戏 CDP 观测流程

**微信开发者工具不是 VSCode 二次开发的**(常见误解——编辑器是 Monaco 而已)。实测它是 **NW.js + Chromium 91**(进程参数含 `--nwjs` / `--nwapp-path` / `package.nw`,`/json/version` 返回 `Chrome/91.0.4472.114`)。既然是 Chromium,加一个 `--remote-debugging-port` 就能挂 CDP,程序化读小游戏的一切。

**不要走 `miniprogram-automator` / `wechat-devtools-mcp`** —— 实测它们只懂小程序 RPC,对 `compileType:"game"` 的工程**所有调用无限挂起**(小程序对照组正常)。这条已经排除过,别重复踩。

## 路径锚点(环境变量,勿散落绝对路径)

- `$env:WECHAT_DEVTOOLS`(可选)= 微信开发者工具装目录;不设则脚本按常见位置探(`D:\Program Files (x86)\Tencent\微信web开发者工具` 等)。
- 已登录 profile 自动取 `%LOCALAPPDATA%\微信开发者工具\User Data\<32位hash>` 里最近改动的那个,**不写死 hash**。

## 三步

### 1. 用调试端口重启开发者工具

```powershell
powershell -File "<skill目录>\launch.ps1"
```

它**照抄当前正在跑的实例的完整 argv**,只追加 `--remote-debugging-port=9222`(没在跑就按检测结果重建)。端口起来会打印确认。
- 换端口:`-Port 9333`。恢复原样(不带调试端口):`-Off`。
- 已经开着同一端口 → 直接跳过,不重启。

### 2. 在 IDE 里点「编译 / 运行」

⚠️ **小游戏的 CDP target 只在模拟器跑着时存在**,停掉就消失。没点运行的话第 3 步会提示你去点。

### 3. 观测

```powershell
$K = "<skill目录>\cdp.js"

node $K --targets                            # 列 target(排查用)
node $K --seconds 30 --out log.txt           # 跟读控制台 30s
node $K --grep "ERROR|FAIL|CoreKit" --out log.txt   # 只留关心的行
node $K --eval "Object.keys(GODOTSDK)"       # 在【游戏上下文】求值
node $K --eval "document.title" --ctx page   # 在【页面外壳上下文】求值
node $K --shot shot.png                      # 截图
node $K --dom                                # 打印上下文/canvas/iframe 清单
```

零依赖(Node ≥ 22 有全局 `WebSocket`/`fetch`),不用 `npm i`。

## 换了代码要重跑:只能 `quit` 整个 IDE

⚠️ **`cli.bat close` 关不掉模拟器**。它报 `✔ close`,但 CDP target 还活着、游戏继续在跑;随后 `open` 对"还开着"的工程只聚焦,**不重新编译也不重启游戏**(实测:server 收不到任何新请求)。所以想让新导出的代码跑起来,唯一可靠的办法是退掉整个 IDE:

```powershell
$cli = 'D:\Program Files (x86)\Tencent\微信web开发者工具\cli.bat'
$K   = "<skill目录>\cdp.js"

echo y | & $cli quit                                    # 1. 退整个 IDE
# 轮询等 wechatdevtools 进程消失
powershell -File "<skill目录>\launch.ps1"   # 2. 带调试端口重启
Start-Process node -ArgumentList "`"$K`" --wait 300 --seconds 180 --grep `"PROBE`" --out log.txt" -NoNewWindow
echo y | & $cli open --project <工程目录>                # 3. 监听已挂上,再 open
```

⚠️ **`echo y |` 不能省**:IDE 的「服务端口」可能是关的,此时 `cli.bat` 会**交互式**问 `Enable IDE Service (y/N)`,而工具调用的 stdin 是空的 → 命令永久挂起。管道喂 `y` 一次即可持久开启(之后在 IDE 设置 → 安全设置里可见)。

⚠️ **CDP 不回放控制台历史**。游戏跑起来之后再连,只能收到连上之后的消息,启动期那几十行全拿不到 —— 所以监听必须在 `open` **之前**挂。

❌ **别用 `location.reload()` 重载游戏页**:页面回来了但引擎不启动,两个上下文的 `GODOTSDK` 全变 undefined(踩过)。

即便如此,`--wait` 抓到的 target 有时也收不到日志(IDE 会换端口重建 target,监听跟在了旧的那个上)。**日志不是唯一出路** —— 见下一节。

## 拿不到日志时:直接从 wx FS 读 Godot 的 `user://`

⚠️ **`GODOTSDK.getWxPath("user://x")` 返回的 `http://usr/user/x` 是 Godot 的 WXMEMFS 虚拟路径,不是 wx 文件系统的真实路径** —— 拿它去 `wx.getFileSystemManager().readFileSync()` 一律报 `no such file or directory`,哪怕文件确实存在。

真实数据在 **`<USER_DATA_PATH>/godot/app_userdata/<项目名>/`** 下。

⚠️ **`wx.env.USER_DATA_PATH` 的 scheme 随运行时而变,别写死**(2026-07-28 实测):

| 运行时 | `wx.env.USER_DATA_PATH` |
|---|---|
| 开发者工具模拟器 | `http://usr` |
| 微信电脑版 | `wxfile://usr` |
| 手机端 | `wxfile://usr`(iOS/Android 各自沙盒) |

所以**一律用 `wx.env.USER_DATA_PATH` 拼**,不要抄成 `http://usr/...` —— 在电脑版/真机上会一律 `no such file or directory`,和"文件不存在"长得一模一样。游戏跑着的时候可以直接把 `user://` 的落盘结果读出来,不必依赖日志:

```powershell
node $K --eval "(()=>{const fs=wx.getFileSystemManager();
  const b=wx.env.USER_DATA_PATH+'/godot/app_userdata/<项目名>';
  return {base:b, dir:fs.readdirSync(b), x:fs.readFileSync(b+'/saves/a.json','utf8')}})()"
```

这条比抓日志更可靠(不受时序影响),验存档/下载/缓存类的东西优先用它。**判读时务必先拿一个已知存在的文件做对照** —— 我就是因为少了这步,把"路径读法错"误判成"目录不存在"。

## 两个执行上下文(容易搞错的地方)

target 是 `http://127.0.0.1:<随机端口>/game/gamePage.html`,但它只是**外壳**,里面套一个 iframe 才是游戏真身:

| 上下文 | url | 有什么 |
|---|---|---|
| page(外壳) | `/game/gamePage.html` | `wx`、`<canvas>` 元素;**没有** `GODOTSDK` |
| game(真身) | `/game/gameContext?id=N` | `GODOTSDK`、引擎全局、游戏代码 |

`--eval` **默认打到 game 上下文**(要 `GODOTSDK` 就用默认);`--ctx page` 才切外壳。控制台事件两边都会冒上来,不用挑。

小游戏运行时**阉掉了大部分 DOM API**(实测 `getComputedStyle is not defined`),写 eval 表达式时别当浏览器用。

## 实测能力清单

| 能力 | 结论 |
|---|---|
| `Runtime.consoleAPICalled` 读控制台 | ✅ 一次读到 167 条,含引擎版本行与全部业务日志 |
| `Runtime.exceptionThrown` / `Log.entryAdded` | ✅ |
| `Runtime.evaluate` | ✅ 需按上面挑对 `contextId` |
| `Page.captureScreenshot` | ✅ WebGL 画布**能**合成进去 |
| 内置调试器面板 | ✅ 与外部 CDP 客户端**同时工作**,不互斥 |

> 截图判读:整屏纯 `#4D4D4D` = Godot 默认清屏色 `Color(0.3,0.3,0.3)`,说明**渲染正常但场景没画东西**,不是截图失败。别把它当"截不到"。判断"截图有没有用"要量像素值,不要凭肉眼看灰。

## 坑(都实际踩过)

1. ⚠️ **`--custom-devtools-frontend` 一个都不能省**。漏了它:IDE 照跑、CDP 照读,但**内置调试器面板看不到日志**。迷惑点——带不带这个 flag,`/json` 里调试器 target 的 URL 都是 `devtools://devtools/bundled/devtools_app.html?remoteBase=...`,**不能靠 target URL 判断面板正不正常**。`launch.ps1` 抄整串 argv 就是为了根治这个。
2. ⚠️ **`--user-data-dir` 不能省**,否则只开出 NW.js 空白应用(`nw_blank.html`),profile 落到 `AppData\Local\nwjs\User`,没登录也没工程。
3. ⚠️ **PS 5.1 的 `Start-Process -ArgumentList` 传数组不会自动加引号**,含空格路径在空格处被切断(症状:弹框「加载 D:\Program」)。必须拼成**单个字符串**、每个参数自己加 `"`。
4. ⚠️ **输出经 PowerShell 控制台会按 GBK 转码,中文日志变乱码**。用 `--out <文件>`(Node 直接写 UTF-8),或先 `[Console]::OutputEncoding=[Text.Encoding]::UTF8`。
5. 心跳类日志(如每 30 帧一条)会把有用信息刷没 —— 默认加 `--grep`。
6. ⚠️ **`cli.bat` 的任何子命令都可能卡在 `Enable IDE Service (y/N)`** —— 一律 `echo y | cli.bat …`。
7. ⚠️ **`cli.bat close` 是假的**(报成功、游戏照跑),`open` 对已开工程只聚焦。换代码必须 `quit` + `launch.ps1`,见上文。
8. ⚠️ **`project.private.config.json` 覆盖 `project.config.json`** —— 改 `urlCheck`(不校验合法域名)之类的开关,只改公共那份**不生效**,IDE 界面上的勾选也是写进私有那份。症状:明明 `project.config.json` 里 `"urlCheck": false`,控制台照样刷 `xxx 不在以下 request 合法域名列表中`,而 Godot 侧只看到 `HTTPRequest` 的 `result=4 code=0`(= `RESULT_CANT_CONNECT`,对人类毫无信息量)。**两份都要看**:
   ```powershell
   grep -o '"urlCheck": *[a-z]*' project.private.config.json project.config.json
   ```
   私有那份是本地文件(通常进 `.gitignore`),所以别人机器上的行为可能和你不一样。域名校验关掉的确认信号是控制台出现 `配置中关闭合法域名、web-view(业务域名)、TLS 版本以及 HTTPS 证书检查`。
9. ⚠️ **`preview` / `auto-preview` 的二维码没法转成 URL 用**。二维码里是只有**手机微信扫一扫**能解析的临时凭据;想在**微信电脑版**上跑开发版小游戏,通道是 `auto-preview`(推送到已登录的电脑版微信),不存在"复制链接打开"。另外 `preview` 会把整包传到微信服务器(8 MB 级包要一两分钟),前台跑容易超时,用 `run_in_background`。

## 何时用这个 vs 别的

| | 本 skill | `android-playtest` / `android-driver` |
|---|---|---|
| 平台 | 微信开发者工具模拟器 | Android 模拟器 |
| 看画面 | 截图可用,但真机表现不等价 | 真设备行为 |
| 适合 | 日志/异常/JS 状态、微信 API 行为、分包与存储 | 手感、触摸、性能、真机兼容 |

微信侧仍然**验不了**的:真机触摸、退后台音频恢复、CDN 合法域名白名单+ICP 备案 —— 那些得上真机。

## 自成长

这轮若冒出新经验,按 `<skill目录>\android\SELF-GROWTH.md` 同一套路:标 public/local → 批量一次问用户 → public 落本 SKILL.md 并 git commit,local 落个人 auto-memory。
