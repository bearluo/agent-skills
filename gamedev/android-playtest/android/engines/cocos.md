# Cocos —— Android 驱动经验(脚手架 · 待实机验证)

被 `android-driver` agent / `android-playtest` skill 在**识别到目标是 Cocos 引擎**时 Read 加载。通用套路见 agent 正文,这里只放 **Cocos 专属**。

> 状态:**尚无本机实机 adb 驱动的踩坑记录**。以下是从 Cocos 引擎常识推出的起点 + 待验证项。第一次真机跑通后,把实测结论替掉对应 TODO(尤其黑屏特征、渲染器、日志 tag)。

## 识别 Cocos

- APK 内 native so:`libcocos.so` / `libcocos2djs.so` / `libgame.so`(视版本/构建而定)。
- Cocos Creator(JS)项目资源:`assets/main.js`、`assets/project.json`、`assets/jsb-adapter/`、`assets/src/`。
- `unzip -l <apk> | grep -iE 'libcocos|libgame|assets/main\.js|project\.json|jsb-adapter'` 命中即是。
- 主 Activity 常见 `org.cocos2dx.javascript.AppActivity` 或 `com.cocos.game.AppActivity`(以实际包为准,用 `cmd package resolve-activity` 查)。

## 渲染器 / -gpu host

- Cocos2d-x 底层 GLES2/GLES3(部分版本可选 Vulkan/Metal)。通用铁律照旧:**先 `-gpu host`**。
- **TODO(黑屏特征)**:Cocos 在 swiftshader 下是否也黑屏、报什么错,尚未实测。真遇到黑屏 + 日志正常,同样先切 `-gpu host`,并把它这边的具体报错记到这里。

## 观察

- Cocos Creator/2d-x 同样把整屏渲到一个 **GLSurfaceView**,UI 不进 Android 无障碍树 → 默认仍是**截图 + 坐标点按**,`uiautomator dump` 看不到游戏内按钮。
- **可能的旁路(Godot 没有)**:Cocos 是 JS 运行时,若该构建开了远程调试(debug 包 / `remote-debugging` / v8 inspector),理论上能连 devtools 注入 JS 观察状态。**TODO**:本机是否用得上、怎么开,待验证;没开就老老实实截图+坐标。
- **funplay_cocos MCP** 是**编辑器内**驱动(改场景/prefab/跑 preview),不是驱动模拟器里已装的 APK;两者别混——真机 APK 验证仍走 adb 这套。

## 日志标志

- logcat 过滤 `cocos` / `Cocos` / `jsb` / `JS:` / `V8`。**TODO**:补该项目"引擎就绪 / 里程碑"的实际打点行,用作可靠验证信号。

## 常识锚点

- **TODO**:填具体游戏的包名 / 主 Activity / 分辨率朝向 / APK 产物路径(每个 Cocos 项目不同,首次跑通后补)。
