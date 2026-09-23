# Creator 自定义资源：添加、序列化与反序列化故障手册

本页记录在 Creator 3.8.7 中把外部转换产物接入编辑器时最容易踩到的边界。它适用于“上传/转换文件 -> AssetDB 自定义 Asset -> Inspector 拖拽 -> Scene 保存重开 -> Web/Native 构建”的完整链路。

## 1. 先决定资源身份，不要从 `.json` 开始

`.json` 不是一种资源类型，而是多个内置 importer 共同竞争的后缀。自定义格式继续使用 `.json` 时，可能被 `json` 或其他内置 importer 抢先接管；旧 `.meta` 还会让重新导入继续使用旧 importer。推荐给转换产物使用专用后缀（例如 `.myformat`），内容仍可为 JSON。

资源身份必须在四处一致：

```text
asset-handler.extnames -> importer.name -> importer.assetType
                                      -> Library JSON.__type__
                                      -> 运行时 @ccclass 名
```

`Inspector.section.asset` 使用的是 importer 名（例如 `my-format`），不是 Asset 的 `ccclass` 名；组件的 `section.node` 才使用组件完整 `ccclass` 名。资源后缀、Importer、Asset 类型和 Inspector 贡献分别验证，不能用“能拖进组件”替代资源类型验证。

## 2. 添加自定义 Asset 的最小闭环

1. 在扩展 `package.json` 声明真实存在的 `contributions.asset-db.asset-handler`、worker 脚本和（如有）`mount`；路径错误或只写 `browser.js` 不会注册 importer。
2. Importer 读取源文件，调用 `asset.depend()` 建立文件变更依赖，同时调用 `asset.setData('depends', uuid[])` 建立构建依赖。
3. `saveToLibrary('.json', ...)` 写入 Creator 序列化格式。`.myformat` 是源文件后缀，`.json` 是 Library 产物后缀，二者不要混淆。
4. 随扩展分发的 Effect、模板和 shader 使用稳定 `.meta`；Importer 应引用其真实 UUID，而不是在 Library JSON 中写路径字符串。
5. 重载扩展后重启 AssetDB/Creator 并重导目标资源，再查询 `imported=true`、`invalid=false`、正确 `importer/type`，最后检查 Library JSON 和 Builder import JSON。

重导入要发 `reimport-asset`，**不要用 `fs` 直接改写工程的 `.meta`**。直接写会和 AssetDB 的写入竞态；启动时批量比对版本号再改写，一旦版本号来源不一致（例如硬编码在扩展主进程里、和 importer 的 `version` 各改各的），就会在每次启动静默重写整个工程的 meta。导入参数写 `meta.userData`，经由 AssetDB 落盘。

第 1 步没做到时，`.meta` 的 `importer` 会是 fallback 的 `*` 而不是自己的名字，Library 里只剩一个带 `_native` 的 `cc.Asset`——这是"importer 压根没注册"的标准现场，不是 importer 写错了。先按 [SKILL.md](../SKILL.md) 的「重载与缓存」确认 handler 工厂被调用过，再回来查导入逻辑。

## 3. Worker 占位类必须参与序列化

AssetDB worker 可能早于 Scene 加载运行时脚本。若 worker 只注册一个没有字段的 `cc.Asset`，Importer 虽然能写出 Library 文件，Builder/反序列化仍可能只保留 `_name`，丢失 manifest、Buffer、Texture 和 Effect 引用。

在 worker 中注册与运行时完全同名的最小类，并一次性声明所有将被序列化的字段：

```js
class DataAsset extends cc.Asset {}
property({ visible: false })(DataAsset.prototype, 'manifestJson');
property({ type: [cc.BufferAsset], visible: false })(DataAsset.prototype, 'buffers');
property({ type: [cc.Texture2D], visible: false })(DataAsset.prototype, 'textures');
property({ type: cc.EffectAsset, visible: false })(DataAsset.prototype, 'effectAsset');
cc._decorator.ccclass('myext.DataAsset')(DataAsset);
```

Creator 3.8.7 的内部 decorator 调用顺序必须是“先 `property(prototype, field)`，最后 `ccclass(name)(Class)`”。反过来会触发 `getSubDict(..., 'proto')` 空指针；对已经注册的 class 再补 property 也可能失败。修复后需要重启 worker，不能只点 Inspector 刷新。

## 4. Library JSON 的引用形状

字段类型决定反序列化是否能构造真实对象。Buffer、Texture 和 Effect 必须写 UUID 引用，并声明 `__expectedType__`：

```json
{
  "__type__": "myext.DataAsset",
  "manifestJson": "{...}",
  "buffers": [{"__uuid__": "...", "__expectedType__": "cc.BufferAsset"}],
  "textures": [{"__uuid__": "...", "__expectedType__": "cc.Texture2D"}],
  "effectAsset": {"__uuid__": "...", "__expectedType__": "cc.EffectAsset"}
}
```

不要把磁盘路径、`db://` 字符串或导入器内部对象直接写入 Library。图片主 Asset 也通常不是 Texture2D；应从图片 `subAssets` 或 `.meta.subMetas` 找到 texture 子资源 UUID。缺少子资源时让导入失败并提示重导，不要静默引用错误类型。

## 5. Scene 运行时的反序列化时序

运行时先加载并执行定义 `@ccclass` 的模块，再按资源 URL/UUID 调用 `assetManager.loadAny/load`，让序列化的 `__type__` 选择构造函数。类住在扩展 mount 里时不用额外处理：mount 里的脚本会被当作工程脚本收集，并挂在主包的 `prerequisite-imports` 上随包启动执行。不要在 class 尚未注册时手动把路径对象传给 `resources.load`，也不要把“资源路径对象”当作已经加载的 Asset 传入组件；这会产生：

```text
Can not parse this input: {"path":"...","__requestType__":"path",...}
```

组件字段应使用 `@property({ type: CustomAsset })` 保存强类型 Asset。setter 负责停止旧异步加载、释放旧 GPU 对象、刷新依赖字段并排队 reload；Asset Inspector 只读展示 Library 结果，导入参数写入 `meta.userData`，不要直接编辑 Library JSON（重导会覆盖）。

Scene 保存/重开要单独验证：

- 组件序列化的是 Asset UUID 和稳定的名字/索引，而不是临时节点或路径对象；
- `onRestore()`、资源 setter 和签名检查会在编辑器直接修改 dump 后触发 reload；
- 异步加载使用 generation/token 丢弃旧结果；`onDisable/onDestroy` 取消任务并释放 Mesh、Material、Texture；
- 资源切换后旧名字不存在时回退默认值，避免索引误指向另一个条目。

## 6. 调试与验收顺序

按层定位，不要用后一层掩盖前一层：

1. `query-asset-info`：后缀、UUID、importer、type、imported、invalid；
2. Library `.json`：`__type__`、字段表、`__expectedType__` 和 `depends`；
3. Scene `loadAny()`：`cc.js.getClassName`、`instanceof`、Effect/Buffer/Texture 引用；
4. 编辑器 Inspector：资源专用面板、强类型拖拽、动态枚举下拉、编辑态预览；
5. 保存重开场景：字段和 Asset UUID 仍在，旧资源不覆盖新资源；
6. Builder import JSON 与最终 Web/Native 包：字段和依赖仍在，且没有 `Missing class`、`missing or invalid` 或旧 importer 日志。

只看到 Library 文件存在，不能证明 Builder 使用了新的占位类；只看到 Inspector 能拖拽，也不能证明 Scene 反序列化和构建依赖正确。
