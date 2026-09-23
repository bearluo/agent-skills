# Godot —— Android 驱动经验

被 `android-driver` agent / `android-playtest` skill 在**识别到目标是 Godot 引擎**时 Read 加载。通用套路(起模拟器 / adb / -gpu host / 坐标点按 / 验证纪律)见 agent 正文,这里只放 **Godot 专属**的。

## 识别 Godot

- APK 内含 `lib/**/libgodot_android.so`,资源打进 `*.pck`(或 `assets/` 下 `.pck`)。
- 主 Activity 常为 `com.godot.game.GodotAppLauncher`。
- `unzip -l <apk> | grep -iE 'libgodot|\.pck'` 命中即是。

## ⚠️ swiftshader 黑屏的**具体特征**(Godot 版)

`-gpu swiftshader_indirect` 下 Godot 报:
```
CanvasShaderGLES3 链接失败:Fragment shader active uniforms exceed GL_MAX_FRAGMENT_UNIFORM_VECTORS (261)
```
→ **画布全黑**(引擎逻辑照跑、GDScript 正常执行,只是不出画面)。SwiftShader 的 fragment uniform 上限太低撑不住 Godot 的 canvas shader。
- 解法就是通用铁律 `-gpu host`(走宿主 Intel Arc/Xe:`Using Device: Google (Intel) - Intel(R) Graphics`)→ shader 报错归零、UI 完整渲染。
- 截图全黑 + 日志见上面这行 uniform 报错 = 十有八九是 swiftshader,不是崩溃。

## 渲染器

- my-game 用 **Compatibility / GLES3 渲染器(非 Vulkan)**,所以不用操心模拟器 Vulkan。若某 Godot 项目改用 Forward+ / Mobile(Vulkan),模拟器 Vulkan 支持另说。

## 观察 = 只能截图 + 坐标

- **Godot 把整屏画在一个 SurfaceView 上,UI 完全不进 Android 无障碍树** → `uiautomator dump` 看不到任何游戏内按钮。只能:截图 → Read 看 → 估坐标 → `input tap`。这是 Godot 铁的限制,没有 JS/devtools 之类旁路。

## arm64 翻译

- arm64-only 的 Godot APK 能在 x86_64 google_apis 镜像上跑(API 30+ 自带 arm64→x86_64 翻译),`install Success`、引擎正常执行 GDScript。

## 引擎就绪 / 里程碑日志标志(logcat 过滤 `godot` 或方括号 tag)

- `godot ... CoreKit vX ready`
- `[MyGame] ready: ...`(my-game 特有)
- 项目一般会打自己的方括号 tag,优先用它做"是否响应"的可靠信号,而非整屏像素比对。

## 游戏专属锚点属 local(不放这)

本文件只放 Godot **引擎通用**经验。具体游戏的包名/主 Activity/分辨率/APK 路径/OTA 端口等属 **local**,按自成长协议(`../SELF-GROWTH.md`)落个人记忆,不写进这份共享 playbook。
- (启动后中间安卓系统"Viewing full screen / Got it"沉浸提示是系统级、点掉即可——这条 agent 正文已通用覆盖。)
