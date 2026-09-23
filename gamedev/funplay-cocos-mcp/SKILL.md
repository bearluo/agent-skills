---
name: funplay-cocos-mcp
description: Use when driving Cocos Creator 3.8 through the funplay-cocos MCP — authoring scenes/prefabs/nodes, inspecting the editor scene, running/screenshotting/driving preview, or validating runtime logic. Covers the updated underscore tool namespace, which tools hit the editor scene vs the live preview runtime, screenshot & input-simulation quirks per preview mode, and the diagnostic-noise / UI_2D-layer / prefab-authoring gotchas.
---

# funplay-cocos MCP 使用手册

FunplayAI/funplay-cocos-mcp（MIT）——通过 MCP 驱动 Cocos Creator 3.8 编辑器：造场景/prefab/节点、查场景、起预览、截图、模拟输入、验运行时。装在 `<cocos-project>`，随 Creator 编辑器进程走，HTTP 在 `127.0.0.1:8765`，profile=`core`。

> 本 skill 是**用法与坑位速查**，不是工具全清单（工具名自解释，按需 ToolSearch 加载 schema）。核心价值在下面的「四条铁律」和「坑位」——它们是踩出来的，不看会白跑一堆预览、白烧一堆上下文。

---

## 两个 namespace（先认清）

- **`mcp__funplay_cocos__*`（下划线）= 更新后的当前版**，约 80 个工具，能力齐全（authoring / inspect / preview / 输入模拟 / 截图 / 运行时）。**优先用这套**。
- `mcp__funplay-cocos__*`（连字符）= 旧的兼容入口，工具少（execute_javascript / execute_editor_script / execute_scene_script / run_script_diagnostics / get_recent_logs / clear_logs / open_scene / list_scenes 等）。旧工作流里还在用的少数几个仍可用。
- 两套同名工具（如 `get_runtime_state`、`capture_*`）行为一致，认下划线那套即可。

工具大类（下划线套）：
- **authoring**：`create_node` `create_label` `create_button` `create_sprite` `create_canvas` `create_camera` `add_component` `set_component_property` `set_node_transform` `set_camera_properties` `delete_node` `remove_component`
- **prefab**：`create_prefab_from_node` `instantiate_prefab` `create_prefab_instance` `inspect_prefab` `inspect_prefab_instance` `edit_prefab_json` `apply_prefab_instance` `revert_prefab_instance` `duplicate_prefab` `list_prefabs`
- **inspect（编辑器场景）**：`find_nodes` `get_hierarchy` `inspect_node` `inspect_component` `list_components` `list_cameras` `get_editor_selection` `get_selection`
- **preview**：`run_project_preview` `set_preview_mode` `get_preview_mode` `pause_runtime` `resume_runtime` `set_time_scale` `get_runtime_state` `run_scene_asset`
- **输入模拟**：`simulate_button_click` `simulate_mouse_click` `simulate_mouse_drag` `simulate_key_press` `simulate_key_combo` `simulate_preview_input` `emit_node_event` `invoke_component_method` `bind_button_click_event`
- **截图**：`capture_game_screenshot` `capture_preview_screenshot` `capture_editor_screenshot` `capture_scene_screenshot` `capture_desktop_screenshot`
- **诊断/日志**：`run_script_diagnostics` `get_recent_logs` `clear_logs` `search_project_logs` `get_script_diagnostic_context`
- **资源/文件**：`refresh_assets` `list_assets` `list_directory` `read_file` `write_file` `delete_asset` `search_files` `get_file_snippet` `inspect_asset` `inspect_asset_dependencies` `validate_*`
- **脚本执行**：`execute_javascript`（editor 上下文）`execute_editor_script`（编辑器 API）`execute_scene_script`（场景进程上下文）

---

## 四条铁律（最重要，先记这个）

### 铁律一：节点级工具查的是「编辑器打开的场景」，不是预览运行时

`find_nodes` / `get_hierarchy` / `inspect_node` / `emit_node_event` / `invoke_component_method` / `simulate_button_click`（按节点名）——**全部作用于编辑器当前打开的场景**（`db://` 里那份），**不是**预览（play）里跑着的运行时。

- 运行时**代码建的节点**（`new Node()` + `addChild`、`addPersistRootNode`、`instantiate(prefab)`）在预览里存在，但这些工具**看不到**（`find_nodes` 返回 count:0）。它们只反映场景资源里静态摆好的节点。
- 推论：**别指望用 `emit_node_event` / `simulate_button_click`（按名）去点预览里运行时生成的按钮**——够不着。

### 铁律二：`get_runtime_state` 才是预览运行时的唯一直读窗口

`get_runtime_state` 返回 `{sceneName, paused, timeScale, totalFrames}`，**读的是 play 中的预览**（帧数在涨、能看到 `loadScene` 后的 sceneName）。要确认「预览是否在跑、当前哪个场景、有没有暂停」用它。逻辑内部状态它给不了——那要靠日志（见下）。

### 铁律三：逻辑流验证靠「自驱 + `[TAG]` 日志」，输入/视觉验证才用 `simulate_*` + 截图

因为铁律一/二，**验证一条业务链路（点 A→加载 B→状态 C）最可靠的做法仍是**：在代码里临时写一段自驱序列（`await` 串起各步 + `console.log('[XXX-TEST] ... → PASS/FAIL')`），起预览，用 `search_project_logs({query:'\\[XXX-TEST\\]', regex:true, limit:20})` 收断言，**验毕删除自驱代码**。预览无法靠节点工具程序化点击，这条到今天仍成立。

`simulate_*`（Electron 级输入）+ 截图 用于**真输入管线 / 真渲染像素**的验证，且**在 browser / simulator 预览模式下才稳**（见预览小节）。

### 铁律四：默认参数会烧上下文，每次调用都要限流

一轮"改代码→起预览→验"的上下文开销里，**截图不是大头，日志和层级 dump 才是**：

| 调用 | 实测开销 | 正确姿势 |
|---|---|---|
| `run_script_diagnostics()` | **~10.6k token / 次**（实测均值，本工具**无任何 limit / 过滤参数**，88 条引擎噪声每次全量回灌） | 改在终端跑 `npx tsc --noEmit -p <tsconfig>` 再筛 `assets[\\/]`，只剩自己的错，**省 99%**；只有要看错误上下文时才用 `get_script_diagnostic_context({limit:5})` |
| `get_recent_logs()` | **3–6k token / 次**（实测均值；`includeProjectLogs` 默认拉全部项目日志 tail） | 有明确标记就别用它——用 `search_project_logs({query, limit:20})`；非用不可时 `{includeProjectLogs:false, limit:30}` |
| `get_hierarchy()` | 2–8k token（全量 JSON，节点一多就爆） | 知道找什么就用 `find_nodes({name})`；只在真要看整棵树时才 dump |
| `inspect_prefab` / `inspect_asset_dependencies` | 1–5k token | 同上，先想清楚要哪个字段 |
| `capture_*_screenshot` | ~1–1.6k token / 张 | 只在验**渲染像素 / 黑屏 / 布局**时截；逻辑验证一律走铁律三的 `[TAG]` 日志 |
| `get_tool_catalog()` | **>10 万 token** | 永不直接调，见坑位 8 |

另外两条：

- **别盲等预览启动**。轮询 `get_runtime_state` 看 `totalFrames` 在涨即可（前台 `sleep` 在本环境被禁；要等就 `run_in_background`）。
- **验完就清**。截图和日志的价值在拿到 PASS/FAIL 那一刻归零，别背着它继续开发——该 `/clear` 就 `/clear`。同理，交互式调试**不要派 subagent**（独立 agentic loop 请求翻倍 + 看不到你刚改了什么）；只有"跑一串场景冒烟、返回一行结论"这种一次性批量回归才值得派。

---

## 预览（preview）

三种模式，`run_project_preview({mode})` 起 / `set_preview_mode({mode})` 切：

| mode | 载体 | 截图 | 输入模拟 |
|---|---|---|---|
| `gameView`（内嵌，默认） | 编辑器内 Game 面板（webview 画布） | ⚠️ **抓不到画布**——`capture_game_screenshot` 只拿到面板工具条（FPS/分辨率条）；桌面截屏够不到 webview 内容 | 坐标点击面板可行但换算麻烦、不可靠 |
| `browser` | 独立浏览器窗口 | ✅ `capture_preview_screenshot` 能抓真渲染 | ✅ `simulate_preview_input` / `simulate_mouse_click`（windowKind: preview）可靠 |
| `simulator` | 独立模拟器窗口 | ✅ 同上 | ✅ 同上 |

- **要真截图 / 真点击 → 切 `browser` 或 `simulator`**，别在内嵌 gameView 上硬抓。
- 旧法起内嵌预览：`execute_editor_script` 调 `Editor.Message.request('scene','editor-preview-set-play', true/false)`——等价于 gameView 模式的起/停，够用且轻。
- `capture_preview_screenshot` 在内嵌 gameView 下报 `Could not locate a visible 'game' panel`——因为没有独立预览窗，符合预期。
- 预览起来时会**重建脚本**（packer-driver 增量构建）；改完 `.ts` 存盘后编辑器自动重编，起预览即拿最新。保险起见先 `refresh_assets` 再起。
- 预览进程日志前缀 `[PreviewInEditor]`，落在 `<cocos-project>/temp/logs/project.log`；**优先 `search_project_logs` 按标记取**，`get_recent_logs` 只在"不知道要找什么、需要扫一眼"时用且必须限流（铁律四）。

---

## 坑位（踩过的，逐条）

1. **`run_script_diagnostics` 恒有约 88 条 `cc.d.ts` / `jsb.d.ts` 报错**（`GPU*` / `TypedArray` / `pal/*` / const-enum / `____private` 等）——**是 Cocos 引擎自带声明的环境噪声，不是你的错**。判断自己代码干不干净：只看 `file` 指向 `assets/**` 的条目；没有就是过。
   **但别用这个工具查**——它没有过滤参数，88 条噪声每次全量回灌（实测 ~10.6k token/次，是本 MCP 最烧的单个调用）。等价且几乎零开销的做法：
   ```powershell
   npx tsc --noEmit -p <cocos-project>/tsconfig.json 2>&1 | Select-String 'assets[\\/]'
   ```
   没有输出 = 过。要看错误上下文再补 `get_script_diagnostic_context({limit:5})`。

2. **代码建 UI 节点必须置 `Layers.Enum.UI_2D`**，否则 UI 相机 `visibility` 不含 `DEFAULT` → **黑屏**。Canvas / Camera / 每个 UI 子节点都要设。相机配方：`projection=ORTHO`、`clearFlags=Camera.ClearFlag.SOLID_COLOR`（不是 `ClearFlagBit`）、`visibility=Layers.Enum.UI_2D`、Canvas 的 `cameraComponent` 指向它。

3. **造 prefab 用 `create_prefab_from_node`**（编辑器原生），产出的 PrefabInfo 合法（编辑器打开不崩）。**别**用 `cce.Utils.serialize` 手搓裸 Node——缺 PrefabInfo，运行时能 `instantiate` 但编辑器打开崩 `reading 'instance'`。配方：`create_node`/`add_component` 搭结构 → cc-API 设属性 → `create_prefab_from_node`。

4. **`execute_scene_script` 里 `scene` 是全局变量**，别自己 `const scene=...`（报 `Identifier 'scene' already declared`）。用带前缀的变量名（`_root`/`_find` 等）；按 uuid 找节点从 `cc.director.getScene()` 递归。

5. **改核心/引擎包（monorepo）后预览不更新**：demo 经 `node_modules` symlink 吃 `@cck/core`、`@cck/engine` 的 `dist`，改了包源码要先 `pnpm build` 再起预览，否则跑的是旧 dist。demo 自己 `assets/**` 的 `.ts` 则编辑器直接重编，不用 build。

6. **i18n 启动告警**：boot 时 `setLocale('zh')` 而该 locale 表还没加载 → warn「无翻译表，仍切换」。良性，但要消：先 `getI18n().addTable('zh', {})` 预埋空表再 `setLocale`。

7. **HMR 会重跑模块顶层副作用**：预览期间反复存盘触发重编 + 模块重载，模块级 `let` 守卫会被重置 → 自测/自驱代码可能被重跑出「幽灵」序列。验完**务必删掉自驱代码**再提交，别把自动循环留进仓库。

8. **`get_tool_catalog` 输出巨大**（>10 万 token）会被转存文件——别直接调；要查工具用 `ToolSearch("select:名字")` 精确加载 schema。

---

## 典型流程

**造场景 / prefab**：`open_scene` 或 `create_scene` → `create_node`/`create_canvas`/`create_camera`/`add_component`/`set_component_property` 搭 → （prefab）`create_prefab_from_node` → `save_current_scene` → `refresh_assets`。

**验一条运行时逻辑链**：写自驱 + `[TAG]` 日志（铁律三）→ `refresh_assets` → `clear_logs` → 起预览 → 轮 `get_runtime_state` 等 `totalFrames` 涨 → `search_project_logs({query:'\\[TAG\\]', regex:true, limit:20})` 读 PASS/FAIL → 停预览 → **删自驱代码** → 结论落定后清上下文。

**验真输入 / 真渲染**：`run_project_preview({mode:'browser'})` → `capture_preview_screenshot` 看渲染 → `simulate_preview_input`/`simulate_mouse_click`（windowKind:preview）点 → 再截图/读状态比对。**只截关键那一两张**，中间态用日志确认。

**查自己代码编不编得过**：`run_script_diagnostics([...ts])` → 只看 `assets/**` 的条目（坑位 1）。
