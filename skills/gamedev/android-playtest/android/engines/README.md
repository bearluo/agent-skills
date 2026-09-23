# engines/ —— 按引擎拆分的 Android 驱动经验

这里每个 `<engine>.md` 装**某一款游戏引擎**在本机模拟器上被 adb 驱动/观察时的专属经验(渲染器、swiftshader 黑屏特征、观察方式、日志 tag、常识锚点)。

**为什么拆开**:通用套路(起模拟器 / adb / `-gpu host` / 坐标点按 / 验证纪律)对所有引擎一样,写在 agent/skill 正文里常驻;而"Godot 单 SurfaceView 无无障碍树""swiftshader 下 `CanvasShaderGLES3` uniform 超限黑屏"这类**只对某引擎成立**的经验,若也塞进全局正文,驱别的引擎时就是噪音/误导。所以按引擎拆成独立文件,**由 `android-driver` agent / `android-playtest` skill 在识别到目标引擎后按需 Read 加载**(它们的第 0 步)。

## 现有

- `godot.md` —— 已实机跑通(my-game)。
- `cocos.md` —— 脚手架,待首次实机验证后补实测项。

## 新增一个引擎

1. 加 `<engine>.md`,建议含小节:**识别**(APK so/资源特征 + 主 Activity)、**渲染器 / -gpu**、**swiftshader 黑屏特征**、**观察方式**(能否只截图+坐标,有无旁路)、**日志标志**、**常识锚点**(包名/Activity/分辨率/产物路径)。
2. 在 `..\..\agents\android-driver.md` 和 `..\..\skills\android-playtest\SKILL.md` 的**第 0 步识别列表**里补一行探测特征 + 指向新文件。
3. 首次实机跑通后,把推测项(TODO)替换成实测结论。
