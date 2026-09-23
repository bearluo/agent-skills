# Creator 扩展验证清单

## 1. 静态检查

按项目实际脚本执行，至少包括：

```powershell
node --check extensions/my-extension/browser.js
node --check extensions/my-extension/dist/asset-db.js
pnpm exec tsc -p tsconfig.json --noEmit
pnpm exec vitest run
```

同时解析 `package.json`，检查 contribution 的路径和打包清单。静态检查无法证明 Creator 已加载新代码。

## 2. 重载扩展

优先通过扩展管理器重载。可用编辑器上下文执行：

```js
const extensionPath = '<project>/extensions/my-extension';
await Editor.Package.disable(extensionPath, true);
await Editor.Package.enable(extensionPath, true);
```

不要未经用户同意关闭可见 Creator。需要命令行构建时可以启动隐藏实例，但它与可见实例共享 `library/`、`temp/` 和日志；构建期间避免同时改资源。

## 3. 检查 AssetDB

查询目标资源，记录：

```text
url
uuid
importer
type
imported
invalid
library
readonly / visible（扩展 mount）
```

合格条件通常是：

```text
importer = 预期 importer
type = 预期自定义 Asset
imported = true
invalid = false
library['.json'] 存在
```

再打开 Library JSON，确认：

- 顶层 `__type__` 正确；
- 每个依赖都有正确 UUID 和 `__expectedType__`；
- `depends` 同时包含挂载 Effect、Buffer、Texture2D 子资源；
- 普通 JSON 等邻近类型未被自定义 importer 接管。

## 4. Scene 进程验证

使用真实 Scene 上下文，而不是编辑器 Node 上下文：

```js
const asset = await new Promise((resolve, reject) => {
  cc.assetManager.loadAny(uuid, (error, value) => {
    if (error || !value) reject(error || new Error('loadAny failed'));
    else resolve(value);
  });
});
```

检查：

- `cc.js.getClassName(asset)`；
- `asset instanceof 自定义类`；
- `asset.effectAsset instanceof cc.EffectAsset` 等关键强类型引用；
- 组件赋值后调用真实 `reload/start`；
- 临时节点、材质、mesh 和纹理确实创建；
- 禁用/销毁组件后临时对象被释放。

若组件内部捕获异常而不向外抛，不能仅凭 MCP 调用返回成功。必须同时检查组件状态和日志。

## 5. 日志判定

修改后只看新时间段，避免把旧调用栈误判为当前失败。重点搜索：

```text
自定义扩展日志前缀
Can not parse this input
asset can't be load
imported=false
invalid=true
旧 bootstrap / 旧 importer 文件名
```

脚本堆栈仍指向旧 chunk 或旧 importer 时，先处理 Scene/worker 缓存，不要继续改业务逻辑碰运气。

## 6. 最终产物

对下载包、构建目录或发布 ZIP 做结构检查：

- `assets/` 中包含运行时代码；
- `extensions/` 中包含完整扩展；
- 扩展 mount 的资源与 `.meta` 同时存在；
- 不再交付的旧路径不存在；
- `package.json` 中后缀和版本与源代码一致；
- HTTP 下载入口实际返回 200；
- Web/Native 若均在范围内，分别启动验证，不能用 Web 结果代替 Native。

### 构建裁剪与 Bundle 依赖

Creator 3.8.7 会按场景入口和静态 import 图做裁剪。验证正式包时：

- 逐个检查 `data/assets/<bundle>/index.js`，确认调试 / 转换工具没有因调试入口静态引用而进入主包；
- 检查 `cc.config.json`、import JSON 和 native 资源，确认自定义 Asset、Effect、Buffer、Texture2D 的依赖落在预期 Bundle；
- 不把“模块在源码目录中存在”误判为“模块进入产物”，也不把“平台工程编译成功”误判为“代码已裁剪”；
- 若工具放入子 Bundle，验证主包和子包各自的入口、加载时机、重复依赖和卸载行为。

若构建日志出现 `Missing class`、`missing or invalid`、`A Class already exists`，先视为失败；自定义 Asset 在 AssetDB worker 中注册的最小占位类与运行时真实类必须同名，Library 顶层 `__type__` 也必须一致。

### Creator 3.8.7 手动注册自定义 Asset

如果 AssetDB worker 不能直接加载带 TypeScript 装饰器的运行时模块，需要用 JS 占位类提前注册自定义 Asset。Creator 3.8.7 的内部 decorator 实现要求手动调用顺序与 TypeScript legacy decorator 的执行顺序一致：先对 `prototype` 调用 `property(...)`，最后调用 `ccclass(...)`。反过来调用会触发 `getSubDict(..., 'proto')` 空指针；只在运行时模块中重复给已经存在的 class 补 property 也可能触发同一错误。

占位类必须一次性声明所有会被 importer 序列化的字段（包括隐藏的 `BufferAsset[]`、`Texture2D[]`、`EffectAsset` 和 manifest 字符串），再注册 class 名。改完后要重启 AssetDB/Creator，并检查构建 import JSON 的字段表；只看到 Library JSON 有字段，不代表 Builder worker 已经使用了新元数据。

## Funplay Cocos MCP

项目安装该扩展时，优先使用它的 `execute_javascript`：

- `context="editor"`：`Editor.Message`、AssetDB 查询、扩展重载；
- `context="scene"`：`cc.assetManager.loadAny`、组件实例、渲染对象检查。

`inspect_asset` 适合拿结构化 AssetDB 信息。若工具未在当前客户端注册，可按扩展配置连接本地 MCP HTTP endpoint；不要把“HTTP 服务可访问”当作 Creator 功能已经验证。
