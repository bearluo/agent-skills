---
name: cocos-render-perf
description: Use when analyzing or optimizing Cocos Creator 3.8 rendering performance on Android devices — draw calls / batching breaks, CPU cost (simpleperf cycles, hotspots), GPU cost without root, per-frame buffer uploads, A/B comparing two render paths, or verifying visual correctness of an optimization with screenshot pixel diffs. Covers release builds, profileable APKs, simpleperf stat/record, stress sweeps, and the pitfalls that make numbers lie.
---

# Cocos 渲染性能分析（Android 真机）

目标：拿到**可信、可复现**的数字来回答「慢在哪 / 这个优化值不值」，而不是看一眼 FPS 就下结论。
流程在 Creator 3.8.7 上验证过；引擎内部路径（`Batcher2d`、`MeshBuffer`、`UIMeshBuffer`）换版本前先对照源码。

---

## 0. 铁律

1. **只用 Release 包的数据**。Debug 包 native 不开优化、JS 带断言与调试检查，CPU 数字偏高且偏得不均匀（会放大某些路径），拿来比 A/B 会得出错的结论。
2. **CPU 看周期数，不看 `top` 的 CPU%**。CPU% 受调频影响：负载轻 → 降频 → 百分比反而高。用 `simpleperf stat -e cpu-cycles` 数绝对周期。
3. **60fps 封顶会藏住差异**。两条路都 60fps ≠ 一样快。加压（实例数扫描）找掉帧拐点，或量 CPU 周期。
4. **每个优化都要配一道画面闸**。截图逐像素比对（或遮挡探针），性能涨了但画错了 = 没做。
5. **一次只改一个变量**。A/B 两边最好在同一个包、同一次启动里轮换阶段（排除温度 / 调频 / 后台差异）。

---

## 1. 准备：可采样的 Release 包

| 项 | 做法 | 坑 |
|---|---|---|
| Release 构建 | Creator 构建配置 `debug=false` + gradle `assembleRelease` | 同一工程**不能并发两个 Creator 构建**；命令行构建前关掉该工程的编辑器 |
| profileable | `AndroidManifest.xml` 的 `<application>` 里加 `<profileable android:shell="true"/>` | 没它 simpleperf `--app` 连不上 release 进程 |
| 放开采样 | `adb shell setprop security.perf_harden 0` | **重启手机后复位**，每次开测前确认 `getprop` 为 0 |
| 包名 | 以构建配置里的 `packageName` 为准 | 包名错 → `am start` 报 Activity 不存在 |
| 签名 | release 与 debug 签名不同，覆盖装会失败 | 先 `adb uninstall <包名>` 再装 |
| 多设备 | 连着模拟器 + 真机时 adb 必须 `-s <serial>` | 否则 `more than one device` |

---

## 2. 看什么、用什么

### 2.1 帧率 / DC / 三角形 / 显存（引擎内自报）

在测试驱动脚本里每 N 秒打一行带固定前缀的日志：

- `director.root.device.numDrawCalls` / `numTris` —— 本帧 DC、三角形
- `director.root.device.memoryStatus.textureSize / bufferSize` —— GPU 显存
- 帧时间：在 `update(dt)` 里攒，算 fps / p50 / p95 / 超 25ms 的比例（卡顿比平均 fps 更有用）

DC 高先查**断批原因**：native `Batcher2d::handleComponentDraw` 只在 dataHash（buffer / layer / texture）、材质、stencil 变化时断批。常见元凶：
- 同一批内容用了多个材质交替（例如 normal / additive 各一个材质）→ 能否合成一个 technique（如预乘混合下 additive 在 FS 里把 a 置 0）；
- 同一组件的 chunk 分进不同 MeshBuffer（`StaticVBAccessor` 首次适配），每跳一次 buffer 断一次；
- 顶点 buffer 容量太小（`macro.BATCHER2D_MEM_INCREMENT`，单 buffer 顶点数上限 65535）导致频繁换 buffer。

### 2.2 CPU：simpleperf

**总量（A/B 首选）**——10 秒周期数：

```bash
adb -s $S shell "simpleperf stat --app $PKG -e cpu-cycles --duration 10 2>&1 | cat"
```

> ⚠️ 设备端命令**末尾要接一个管道**（`| cat`）。不接的话有的机型 `simpleperf stat --app` 输出直接丢了、退出码还是 0，脚本拿到空值。

**热点（找该优化哪）**——record + 符号化 + report（脚本在 NDK `simpleperf/` 目录，Windows 用 `py` 调）：

```bash
adb shell "run-as $PKG simpleperf record -p $PID --duration 10 -f 2000 -g -o /data/data/$PKG/perf.data"
adb exec-out run-as $PKG cat /data/data/$PKG/perf.data > perf.data
py $NDK/simpleperf/binary_cache_builder.py -i perf.data -lib <未 strip 的 obj/arm64-v8a 目录>
py $NDK/simpleperf/report.py -i perf.data --sort dso,symbol --symfs binary_cache
py $NDK/simpleperf/report.py -i perf.data --children --sort symbol --symfs binary_cache --comms <线程名>
```

- 未 strip 的 so 在 `build/<target>/proj/build/<app>/intermediates/cxx/RelWithDebInfo/<hash>/obj/arm64-v8a`。
- 先 `--sort comm` 看哪个线程（Cocos 的 JS + 渲染主线程通常叫 `Thread-N`，GL 驱动线程另算），再下钻。

### 2.3 GPU：没 root 怎么办

- Adreno：`/sys/class/kgsl/kgsl-3d0/gpu_busy_percentage` 通常可读。
- Mali / 联发科 GED：`/sys/kernel/ged/hal/gpu_utilization` 等**无 root 读不到**（Permission denied）。
- 读不到就**加压扫描**：同一项开 / 关，负载（实例数、顶点数）逐级加倍，看谁先掉帧。都不掉 = 在这台机上差异不可测——这本身就是结论，写清测到多大负载（顶点 / 帧）。
- 需要深挖时：Android GPU Inspector、Arm Streamline（Mali 计数器）——都要额外装，先用加压判断值不值得。
- 帧呈现时间：`dumpsys SurfaceFlinger --latency '<layer>'`（Android 16 的 layer 名套在 `RequestedLayerState{...}` 里，要取里面那段）。`dumpsys gfxinfo` 统计的是 hwui，对 GL SurfaceView 的游戏帧没意义。

### 2.4 每帧 buffer 上传（UI / 2D 路径特有）

- web：`MeshBuffer.uploadBuffers` 只要 `dirty` 就把 `vData[0..byteOffset]` + `iData[0..indexOffset]` 全传；批次一生成就 `setDirty()`，等于**每帧全传**。
- native：`UIMeshBuffer::uploadBuffers` 更狠，`update(_vData)` 不带长度 = **传整个容量**；`frameMove` 里没有 JS 能插手的窗口。
- **量 web 上传量**：别 hook 全局 `bufferSubData`（Profiler、HUD、Label 都算进去，数字没法归因）。在页面里拿到目标组件的 `renderData.chunk.meshBuffer`，包它 `_iaPool[0].vertexBuffers[0]` / `indexBuffer` 的 `update(data, size)` 累加字节，除以 `director.getTotalFrames()` 差值。对照原版：`delete meshBuffer.uploadBuffers`（去掉实例上的覆盖，回落到原型）→ 同页 A/B。
- 对策思路：数据确实不变的 MeshBuffer（前提是顶点格式独占、只有自己写），web 覆盖该实例的 `uploadBuffers` 只传变了的；native 只能改引擎 `UIMeshBuffer.cpp`——引擎随工程从源码编译，可在 `native/engine/common/CMakeLists.txt` 里对 `cocos_engine` 目标替换源文件，做成默认关的可选项。

### 2.5 画面闸

- **截图逐像素比对**：同屏左右放「优化版 / 参照版」同一帧，`adb exec-out screencap -p > x.png`，按日志打出的屏幕矩形裁剪，算平均差和「最大通道差 >16 / >48 的像素占比」，另存 左|右|差×4 拼图。**一定要看拼图**：统计数字小的地方也可能有裂纹、噪点。
- **遮挡 / 穿插探针**：在已知位置放纯色方块，按渲染顺序判断方块区域应被盖住还是应盖住对方，数像素。
- 参照组要**定格在同一时刻**：用参照组件自己的时间轴 seek（写入播放时间后把时间缩放置 0），别依赖「暂停」——很多组件暂停后不再刷新渲染数据，画面停在旧帧上。
- 截图时机：按日志里「翻页」的行触发、延迟 ~2s 再截；**最后一页后面紧跟着别的阶段时最容易截错**，结果里整行 0 差 = 两边都空 = 截错了。

---

## 3. A/B 的标准做法

1. 驱动脚本里做**阶段表**：`{模式, 负载, 开关…}` 每 N 秒轮换，每阶段开头打一行 `phase=N mode=… count=…`，性能行带上模式名。
2. 阶段切换后**丢掉第一条性能行**（重建 / 首帧编译 shader 的抖动），取后面稳定的。
3. 主机侧脚本按 `phase=` 日志触发采样（simpleperf stat / 截图），结果追加进一个结果文件。
4. 需要两个包对比（例如引擎补丁开 / 关）时：同一台机、同一温度区间、同一阶段表，**背靠背各跑一遍**；每个包存一份 APK 副本（后一次构建会覆盖输出目录）。
5. 报告只写新包的数据，写清：设备 / GPU、包类型（Release）、阶段、指标、样本数。

---

## 4. 常见坑

- `adb logcat -d` 只有环形缓冲区那么多，长跑会丢前面的行 → 开测前 `adb logcat -G 16M`，结束时存一份全量。
- Cocos 的 JS 日志在 logcat 里 tag 是 `Cocos`（级别 D）。
- Windows 上后台跑 `python` 可能落到 Microsoft Store 的占位程序 → 用 `py`。
- PowerShell 5 读无 BOM 的 UTF-8 脚本会乱码 → 构建脚本只写 ASCII 注释。
- `simpleperf stat` 在设备端不接管道就没输出（见 2.2）。
- CMake 里 `option()` 会写进 `.cxx` 缓存，关掉后旧值还粘着 → 可选项用普通变量 + `if(NOT DEFINED …)`，本机开关放 `localCfg.cmake`（Creator 默认 gitignore）。
- 引擎补丁（替换引擎 cpp）**升级引擎要重新 diff**；在补丁文件头注释写明原文件路径和改了哪几个函数。
- 新顶点格式别和引擎内置格式同 stride：`StaticVBAccessor` 按格式共用，MeshBuffer 就混进了别人的数据，「只有我自己写」的假设不再成立。
- 用 Docker 里的浏览器测 web 构建：`host.docker.internal:<端口>` 会落到本机 **127.0.0.1** 上同端口的旧服务，拿到的是旧包——先 `netstat -ano | grep :<端口>` 确认端口干净，或换新端口。页面里 `scene.name` 是场景**根节点名**，复制场景后可能还是旧名，确认版本看组件属性。容器里的截图用 `docker cp` 取出来看。

---

## 5. 结论怎么写

一张表：`指标 × 方案 × 负载`，每格给数值；下面三行以内写结论 + 适用范围（「在某 GPU 上到 N 顶点 / 帧两者都稳 60fps，差异不可测」比「没影响」可信得多）。
画面闸的结果和性能结果放一起——没过画面闸的方案不进结论。
