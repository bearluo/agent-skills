---
name: android-playtest
description: Use when the user wants a windowed, player-assisted (human-in-the-loop) Android playtest on the local emulator — a visible emulator window where the human plays by hand while you assist live: screenshot on demand, watch logcat for errors, automate repetitive taps, and record a playtest report. Works for any engine (Godot, Cocos, …): loads the matching engine playbook on demand. This is an interactive main-session flow; do NOT delegate it to the android-driver subagent (that one is for headless autonomous runs).
---

# 有界面·玩家辅助 playtest 流程

**人在环**的手动测试:弹出真模拟器窗口,**用户亲手玩**,你(主会话)在旁**实时辅助**。与 `android-driver` 子agent(无界面、自主跑完只回结论)互补——**这套必须在主会话里做**,因为要和用户来回交互、共享同一个窗口画面。

本 skill 只放**引擎无关的通用套路**。引擎专属提醒(黑屏特征/观察方式/常识锚点)见第 0 步按需加载的 playbook。

## 路径锚点(环境变量,勿散落绝对路径)

- `$env:ANDROID_SDK_ROOT` = 独立 SDK 根;adb / emulator 从它取。
- 均 User 级已设。脚本内 kit-local 文件走 `$PSScriptRoot`(脚本目录)。

## 起机器之前:确认镜像选对了

要装 Play 上架的 App(Facebook / Discord / Google 登录 / 内购)必须用 `google_apis_playstore` 镜像;要 `adb root` 则只能 `google_apis`(Play 镜像不可 root)。**起之前**就得选对,事后换等于重来。这层(选镜像 / 建 AVD / Windows 路径规矩 / 原生 App 用 uiautomator)见 `<skill目录>\android\emulator.md`,与引擎无关,按需 Read。

## 第 0 步:识别引擎 → 加载对应经验

先弄清这次玩的是哪个引擎的包(调用方通常已点明,或 `unzip -l <apk> | grep -iE 'libgodot|libcocos|libunity|\.pck|assets/main\.js'` 探),然后 Read 对应经验并入辅助判断:
- `<skill目录>\android\engines\godot.md`
- `<skill目录>\android\engines\cocos.md`
- 缺则照通用套路走,并跟用户说明"该引擎经验暂缺"。新增引擎见 `<skill目录>\android\engines\README.md`。

## 何时用这个 vs 子agent

| | android-playtest(本 skill) | android-driver 子agent |
|---|---|---|
| 界面 | **有窗口**,人能看能操作 | 无窗口(headless) |
| 谁操作 | **用户亲手玩**,你辅助 | 子agent 自主驱动 |
| 交互 | 主会话来回 | 跑完只回一个结论 |
| 适合 | 手感/视觉/探索/复杂交互的人工测 | 无人值守自动化、回归 |

## 开场(一条命令)

让用户跑(或你替他跑):
```
powershell -File "<skill目录>\playtest.ps1" -Apk <路径>
```
它 windowed 起模拟器(`-gpu host` 有画面)→ 等 boot → 装/更新 APK → 启动游戏 → 后台把 logcat 持续写到**脚本同目录的 `playtest-logcat.txt`**(脚本启动时会打印其绝对路径,tail 那个)。
- 参数(都可用环境变量代替):`-Apk`(`PLAYTEST_APK`)、`-Package`(`PLAYTEST_PACKAGE`,不给就从 APK 读)、`-Avd`(`PLAYTEST_AVD`,默认 `playtest_avd`)、`-Port`(`PLAYTEST_PORT`,默认 5556)。续上次进度加 `-KeepState`;已装在设备上加 `-NoInstall`。
- 设备序列号 `<serial>` = `emulator-<Port>`,脚本开场会打印,下文命令都用它。
- 若同端口已有 headless 模拟器在跑,先 `& "$env:ANDROID_SDK_ROOT\platform-tools\adb.exe" -s <serial> emu kill` 再开窗口版,或换 `-Port`。

## 你的辅助工具箱(用户玩,你按需搭手)

Git Bash 里 `ADB="$ANDROID_SDK_ROOT/platform-tools/adb.exe"`,设备恒 `-s <serial>`(别碰同时开着的其他模拟器)。

- **「看一下现在」** → `"$ADB" -s <serial> exec-out screencap -p > <scratch>/now.png`,再 Read 那张图,用中文描述当前画面/状态。
- **「盯日志,有报错叫我」** → `tail`/Read 脚本目录的 `playtest-logcat.txt`(路径见脚本开场打印),过滤 `godot|cocos|FATAL|AndroidRuntime|ERROR|assert|shader`(引擎专属 tag 见其 playbook);发现异常主动打断提示用户。
- **「帮我刷 X」/重复操作** → 循环 `"$ADB" -s <serial> shell input tap <x> <y>`(坐标从截图估,注意缩放倍率换算回原图);刷完截图确认。
- **验证一次点按是否生效**:`input tap` 后**先 `sleep 0.4` 再截图**(游戏 UI 数值/浮字有一帧延迟,截太快会误判"没变"),并优先读**数值标签/logcat 标志**而非整屏像素比对;确实没反应先诊断(坐标偏?按钮置灰?)再重试,**别靠狂点凑数**。
- **状态/存档核对** → 需要时用 `adb shell run-as` 或游戏日志里的里程碑行佐证,而非只凭画面。
- **「记一下这轮」** → 汇总一份简报:玩了什么、发现的问题(带截图路径)、logcat 里的报错、复现步骤、建议。

## 通用引擎提醒

- 多数游戏引擎整屏是一个 SurfaceView/GLSurfaceView,**UI 不进 Android 无障碍树** → 你只能靠**截图+坐标**观察和辅助点按,`uiautomator dump` 看不到游戏内按钮。个别引擎有旁路(如 Cocos 的 JS/devtools),见其 playbook。
- 画面**全黑但引擎日志正常** = 十有八九用了 swiftshader;本流程脚本已固定 `-gpu host`,若手动起过别忘了。各引擎黑屏的**具体报错**见其 playbook。

## 收尾

- 用户说结束 → 出 playtest 报告 → 询问是否 `emu kill` 关窗口(默认保留让他接着玩)。
- 截图放会话 scratchpad,别塞进用户仓库。
- **自成长**:这轮若冒出新经验,按 `<skill目录>\android\SELF-GROWTH.md` 收集候选 → 分类(**引擎通用 = public**,落 `engines\<engine>.md` 并 git commit;**游戏/个人专属 = local**,落个人 auto-memory)→ **批量一次问用户**是否落库、去重后写入。
