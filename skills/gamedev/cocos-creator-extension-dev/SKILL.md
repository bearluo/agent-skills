---
name: cocos-creator-extension-dev
description: Use when creating, modifying, or debugging a Cocos Creator 3.8.x project extension, especially package.json contributions, asset-db mounts, custom importers/assets, resource inspectors, scene-process integration, extension reloads, and live editor verification. The procedures are validated on Creator 3.8.7; verify internal APIs before applying them to another version.
---

# Cocos Creator 扩展开发

目标是交付一个在真实 Creator 编辑器中可加载、可重载、可构建的项目扩展，而不只是让 Node/TypeScript 测试通过。

## 先分清运行上下文

Creator 扩展至少会跨越这些上下文：

| 上下文 | 常见入口 | 能做什么 |
| --- | --- | --- |
| 扩展主进程 | `package.json.main`、`browser.js` | `Editor.Message`、`Editor.Package`、文件与面板协调 |
| AssetDB worker | `contributions.asset-db` | importer、资源依赖、Library 产物 |
| Scene 进程 | `contributions.scene`、项目组件 | `cc` 运行时对象、场景节点、编辑态预览 |
| 面板/Inspector | `panels`、Inspector contribution | UI、资源检查、预览控制 |

不要用一个上下文的成功替代另一个上下文的验证。主进程能 `require()` 某模块，不证明 Scene 进程能反序列化对应 Asset；Importer 生成 Library 文件，也不证明组件能创建材质或渲染节点。

## 工作流

1. 先确认 Creator 精确版本、扩展放置位置、需要的上下文和最终用户操作方式。
2. 查同版本官方扩展的 `package.json` 与 contribution 写法。涉及 Shader/挂载资源时，优先参考官方 `cocos-creator-extensions/extensions/shader-graph`，不要凭印象发明字段。
3. 保持扩展边界清楚：编辑器逻辑放 `extensions/<name>/`。**运行时代码（自定义 Asset 类、组件、Effect）优先随扩展走**——放进 `contributions.asset-db.mount` 的目录，目标工程装上扩展即可用，不必手工拷文件、也不会两边版本漂移。前提是这些文件的 `.meta` 要随扩展入库，见下节关键决策。
4. 修改后按“静态检查 → AssetDB → Scene → 构建产物”逐层验证。具体清单见 [references/validation.md](references/validation.md)。
5. 涉及 Web/Native 交付时，按 [references/build-verification.md](references/build-verification.md) 检查 Bundle 裁剪和产物内容；不要把旧产物或“构建成功”当作验收。

## `package.json` 原则

- 使用 `package_version: 2`，明确 `name`、`version`、`main` 与所需 contributions。
- 只声明真实需要的 contribution；普通主进程扩展不要顺手接管 AssetDB 或 Scene。
- 扩展自带 Effect、脚本模板或只读资源时，用 `contributions.asset-db.mount` 挂载扩展内目录。挂载 URL 是 `db://<package-name>/...`。
- 只读内部资源通常设 `readonly: true`；不希望污染资源面板时设 `visible: false`。
- 修改 package manifest 后要重启 Creator，不是重载扩展；仅保存 JS 文件不等于 Creator 已重新注册 contribution。原因见「重载与缓存」。

## 自定义资源与 Importer

| 要做的事 / 遇到的问题 | 先读 |
| --- | --- |
| 自定义后缀、聚合 Asset、隐藏依赖、构建依赖、扩展 mount | [references/asset-db-importer.md](references/asset-db-importer.md) |
| 资源不被识别、Library 字段丢失、`Can not parse this input`、Scene 保存重开或反序列化失败、worker 占位类 | [references/custom-asset-serialization.md](references/custom-asset-serialization.md) |
| 自定义 Asset Inspector、组件 Inspector、动态枚举下拉、编辑态预览 | [references/custom-inspectors.md](references/custom-inspectors.md) |
| 场景进程脚本（`execute-scene-script`）、右键 / 顶部菜单、简单面板、首次启动弹窗、拖入层级面板生成节点、多产物写盘顺序、编辑器侧 TS 打包 | [references/editor-ui-and-scene-script.md](references/editor-ui-and-scene-script.md) |

关键决策：

- 为新格式使用专用后缀，例如 `.myformat`；不要抢占 `.json`、`.png` 等已有 importer，除非兼容性和选择优先级已经被完整验证。
- “导入为自定义 Asset”和“给它做专用资源 Inspector”是两件事。Importer 解决类型与依赖；Inspector contribution 才负责依赖面板、枚举下拉框和预览这类资源面板体验。
- 组件字段要使用强类型装饰器，例如 `@property({ type: MyDataAsset })`。把内部 Effect、二进制数据、纹理留在 Asset 的隐藏属性里，不把实现细节暴露成一组手填数组。
- 自定义 Asset 的 `ccclass` 名、Importer 写入的 `__type__` 和 worker 中注册的类名必须完全一致；worker 占位类要一次性声明全部序列化字段，否则构建时可能只保留 `_name`。
- 运行时先让定义 `@ccclass` 的模块执行，再按 URL/UUID `assetManager.loadAny/load`，让序列化的 `__type__` 选择构造函数。
- **随扩展分发的资源与脚本，其 `.meta` 必须入库。** Importer 把它们写成 UUID 引用，而那个 UUID 只存在于 `.meta` 里。`.meta` 没被一起带到目标工程时 Creator 会重新生成新的，已导入的资源就指向一个不存在的对象——**导入照样成功、构建照样通过，只在运行时炸**。工程 `.gitignore` 若有 `*.meta` 一类的一刀切规则，要为扩展目录开例外。
- **mount 目录里的脚本会被当作工程脚本收集进构建产物**，即使没有任何静态 `import` 指向它——实测它落在主包并挂上 `prerequisite-imports`，随包启动即执行，所以 `@ccclass` 在反序列化之前就已注册，不需要接入方补一句 `System.import`。代价是这些类跟主包同寿命、卸不掉，所以 mount 里只放类型定义，别放大块运行时逻辑。
- **用 `fs` 绕过 AssetDB 改写工程 `.meta` 是兜底，不是手段。** 它会和 AssetDB 自己的写入竞态、在版本号比对失误时静默重写整个工程的 meta、并产生无意义的 git 改动。要重导入就发 `reimport-asset`，要改导入参数就写 `meta.userData`。已有扩展里的这段代码通常是在兜下一节那个注册不确定性的底（资源已经被写成 fallback importer，只能把 `.meta` 掰回去再重导）——那说明该修的是注册，不是 meta。

## 重载与缓存

先用官方扩展重载方式：

```js
const extensionPath = '<project>/extensions/my-extension';
await Editor.Package.disable(extensionPath, true);
await Editor.Package.enable(extensionPath, true);
```

注意：扩展重载不保证 AssetDB worker 重启，Node `require` 缓存也可能继续持有旧 importer。

已知现象：改完扩展没重启时，Inspector 里组件的自定义资源字段可能显示「未知类型」，重启 Creator 即恢复（原因推测是 Asset 类在 worker 和场景进程各注册一份、重载只更新了一边，未验证）。场景进程脚本和菜单同样要重启才生效，见 [references/editor-ui-and-scene-script.md](references/editor-ui-and-scene-script.md)。

**`contributions.asset-db.asset-handler` 是正确的注册方式，但它在 3.8.7 上不是每次都生效，而且失败时完全静默。** asset-db worker 里扩展有两条 enable 路径，同一份配置多次全新启动会随机落到其中一条：

| worker 内的 enable 路径 | 结果 |
| --- | --- |
| `AssetDBManager.init → PluginManager.init` | handler 工厂被调用，importer 注册成功 |
| `enableAttach → PluginManager.addTask → step` | 只 `require` 一次 `contributions.asset-db.script`，**handler 工厂根本不被调用** |

走到第二条时没有任何报错：自定义后缀落到 fallback importer `*`，Library 写成一个只有 `_name` 的 `cc.Asset`，导入和构建全绿，直到运行时才炸。**排查时先确认 handler 工厂被调用过**——在工厂里打一行日志（worker 的 `console.log` 可能被日志等级吞掉，用 `console.error` 或直接写文件），比查 `.meta` 更早定位。判据是 `.meta` 的 `importer` 字段：不是自己的名字就是没注册，跟文件内容无关。

### 装上新扩展后的正确流程

1. **改完 `package.json` 或 contribution 就重启 Creator，别用重载。** `Editor.Package.disable/enable` 触发的正是上表第二条路径（`enableAttach`），所以“重载扩展”能刷新代码，但**永远补不上 handler 注册**——这一条由调用栈推断，没有单独实测。上面那段重载代码只适合改 importer 内部实现后刷新代码。
2. **先验注册，再看资源。** `Editor.Message.request('asset-db', 'query-all-importer')`，确认自己的 importer 名在列表里。查不到就是这次启动落到了第二条路径，此时去调导入逻辑是白费功夫。没有编辑器界面时用离线判据：目标资源 `.meta` 的 `importer` 字段不是自己的名字（通常是 `*`）。
3. **查不到就重启 Creator。** 这是一场启动赛跑，重启等于重掷一次骰子，不是“再试一次同样的操作”。
4. **注册到位后再补救已经导错的资源。** `.meta` 里已经写死 fallback importer 的不会自己回头，要重导：删掉它的 `.meta` 或改回正确的 `importer`/`ver`，再发 `reimport-asset`。
5. **不接受“重启碰运气”就上 bootstrap。** 交付给别人的扩展基本都属于这一类：接入方不会知道要去查 `query-all-importer`。

因此 worker bootstrap **不是历史遗留，是这条不确定性的兜底**（见 [references/asset-db-importer.md](references/asset-db-importer.md)）。要不要写，看这个扩展能不能接受“偶发导错、且不报错”。代价是它依赖 Creator 内部路径，必须锁版本。与 `mount`、`mount.visible`、handler 导出在 `browser.js` 还是 db 脚本都无关——都试过，不改变结论。

### 更新已有扩展的固定流程

改 importer 代码后，已有资源**默认不会重导**，编辑器读到的还是旧 Library 产物。实测的四种情形：

| 动作 | 已有资源是否重导 |
| --- | --- |
| 只改 importer 代码，`importer.version` 不变 | 否——Library 保持旧产物，改了等于没改 |
| 同时 bump `importer.version` | 是，且 `.meta.ver` 跟着变成新版本号 |
| 源文件 mtime 变了（切分支、拷贝工程、编辑器里存一下） | 是，而且顺带用上了新代码 |
| 什么都没动 | 否 |

第三行就是“有时候莫名其妙就是新的了”的来源，**不要依赖它**：它在你机器上碰巧成立，换台机器（源文件没动过）就复现不出来，而且会掩盖你忘了 bump version 这件事。

所以每次改扩展走同一套：

1. **改了导入行为就 bump `importer.version`。** 这是唯一故意的重导开关。顺手把扩展 `version` 也带上，两者别各改各的——`.meta.ver` 存的是 importer 的那个。
2. **改了 `package.json` / contribution 就重启 Creator**，别用重载（理由见上一节）。只改 importer 内部实现时重载够用。
3. **重启后先验注册**（上一节第 2 步），没注册就再重启，此时看任何导入结果都没有意义。
4. **再验新代码确实跑过**：目标资源 `.meta` 的 `ver` 已经等于新的 importer version。这一条比去看渲染结果或 Inspector 早得多，也是区分“没重导”和“重导了但逻辑不对”的唯一判据。
5. **以上都对还不对，才清 `library/`。** 它等于绕过全部闸门强制全量重导，慢，而且会把真正的原因（version 没 bump、注册没成功）一起盖掉——排查时它是最后一步，不是第一步。

用了 worker bootstrap 时额外一条：保证 worker 能加载一个未被 `require` 缓存住的新入口（例如入口文件名带扩展版本号），否则改了代码仍在跑 worker 缓存里的旧函数。

## 验收口径

至少拿到以下证据后，才能说扩展功能完成：

- 扩展脚本语法与项目 TypeScript 检查通过；
- AssetDB 返回预期 `importer`、`type`、`imported=true`、`invalid=false`；
- Library JSON 中的 `__type__` 和 UUID 依赖正确；
- Scene 进程 `loadAny()` 得到真实自定义 Asset，关键引用通过 `instanceof`；
- 组件或场景入口实际执行成功，错误日志中没有旧调用栈；
- Web/Native 等最终产物包含扩展、挂载资源和运行时代码；
- 普通资源类型未被误接管，例如普通 JSON 仍由 `json` 导入、Spine JSON 仍由 `spine-data` 导入。

不要把“单测通过”“资源能拖入”或“Library 文件存在”单独描述为编辑器预览或构建已验证。

## 边界

本 skill 只管扩展本身能否被编辑器加载、导入、序列化、构建。运行时渲染效果、合批、性能与真机指标不在范围内，另行验证。
