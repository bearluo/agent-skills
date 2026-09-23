# emulator.md —— 起哪台模拟器 / 本机环境

引擎无关的那一层：**选镜像、建 AVD、Windows 下的路径规矩、原生 App 的观察通道**。引擎专属经验在 `engines/<engine>.md`，别混。

## 选镜像：能不能装 App 是硬区别

| 要做什么 | 镜像 |
|---|---|
| 绝大多数活（跑 APK、看日志、坐标点按、网络/埋点） | `google_apis` |
| 要装 **Play 上架的 App**：Facebook / Discord / Google 登录 / Google Play 内购 | `google_apis_playstore` |
| 要 `adb root`、要改 `/system` | `google_apis` —— **Play 镜像不可 root**，Google 的限制，没有绕法 |

分享到某个 App、第三方登录、内购这类需求，目标 App 必须真装在机器上，而它们只在 Play 上架 —— 起机器**之前**就得选对镜像，事后换等于重来一遍。

### `com.android.vending` 会骗人

`google_apis` 镜像里**也有** `com.android.vending` 这个包，但它只是个桩。光看 `pm list packages` 会以为有 Play 商店，白登一次 Google 账号才发现装不了东西。看 APK 路径才作数：

```bash
adb -s <设备> shell pm path com.android.vending
# Phonesky.apk       → 真 Play 商店
# LicenseChecker.apk → 桩（版本号 1.8、零个启动入口）
```

Play 商店还必须登 Google 账号，账号按设备存，换一台要重登（`dumpsys account | grep "Accounts:"` 查）。登录这一步只能人工做。

## 建 AVD：默认规格装不下大 App

```bash
"$ANDROID_SDK_ROOT/cmdline-tools/<ver>/bin/sdkmanager.bat" "system-images;android-34;google_apis_playstore;x86_64"
echo "no" | "$ANDROID_SDK_ROOT/cmdline-tools/<ver>/bin/avdmanager.bat" create avd \
  -n <名字> -k "system-images;android-34;google_apis_playstore;x86_64" -d pixel_6 --force
```

新建的 AVD 默认 **1536M 内存 / 800M 数据分区**，装两个大 App 就满。改 `~/.android/avd/<名字>.avd/config.ini`：

```ini
hw.ramSize=4096M
disk.dataPartition.size=8G
```

等开机别靠 sleep 猜：

```bash
until [ "$(adb -s <设备> shell getprop sys.boot_completed | tr -d '\r')" = "1" ]; do sleep 3; done
```

同时开多台时端口按启动顺序递增（5554、5556…），**所有命令显式带 `-s <设备>`**。

## Windows / Git Bash：三条互相打架的路径规矩

1. **设备上的路径会被改写** —— `adb shell ... /sdcard/ui.xml` 里的 `/sdcard/…` 被当成 Unix 路径转成 `C:\…`。解法 `export MSYS_NO_PATHCONV=1`。
2. **但本机文件路径反过来要 Windows 形式** —— `adb.exe` 是 Windows 程序；设了 `MSYS_NO_PATHCONV=1` 之后 `/e/work/…` 不再被自动转换，`adb install /e/…` 直接报 `failed to stat`。装 APK 一律写 `'D:\path\…'`。
3. **`python3` 也是 Windows 版** —— 传给它的路径同样要 Windows 形式，`/tmp/x.xml` 它读不到。临时文件直接放 `C:/Users/…/Temp/…`。

记混这三条会浪费很多时间，症状还都是「文件明明在却说找不到」。

## 原生 App 可以用 uiautomator

skill / agent 正文说的「整屏一个 SurfaceView、UI 不进无障碍树、只能截图+坐标」**只对游戏引擎成立**。测原生 Android App（SDK demo、设置页、Play 商店本身）时 `uiautomator dump` 完全可用，比估坐标准得多：

```bash
export MSYS_NO_PATHCONV=1
adb -s <设备> shell uiautomator dump /sdcard/ui.xml
adb -s <设备> shell cat /sdcard/ui.xml > "C:/Users/…/ui.xml"
```

解析取 `bounds` 中心点去 tap。**中文在终端是乱码**（终端按 GBK 解 UTF-8），按 `unicode_escape` 打出来再对照：

```python
import re, io
s = io.open("C:/Users/…/ui.xml", encoding="utf-8").read()
for m in re.finditer(r'(?:text|content-desc)="([^"]*)"[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', s):
    t = m.group(1)
    if t.strip():
        x1, y1, x2, y2 = map(int, m.groups()[1:])
        print("%s (%d,%d)" % (t.encode('unicode_escape').decode(), (x1+x2)//2, (y1+y2)//2))
```

找按钮别一次滑到底，写个「dump → 找到就 tap，找不到就滑一屏」的循环最省事。

## `playtest.ps1` 是为 my-game 写的

脚本里写死了 `emulator-5556` 和默认包 `com.example.mygame`。**拿它测别的 App 时只能借它起模拟器**，启动得自己来：

```bash
adb -s <设备> shell cmd package resolve-activity --brief <包名> | tail -1   # 拿入口
adb -s <设备> shell am start -n "<包名>/<入口>"
```

包名也别想当然 —— 用 `output-metadata.json` 里的 `applicationId`，它常和源码目录名对不上。
