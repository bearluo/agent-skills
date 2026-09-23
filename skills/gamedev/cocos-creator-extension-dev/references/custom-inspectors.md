# 自定义资源与组件 Inspector

本页针对 Cocos Creator 3.8.7。Inspector、AssetDB worker 和 Scene 是不同进程；界面能显示不代表 importer、运行时 Asset 或编辑态渲染已经正常。

## 先确定属性属于哪一层

| 需求 | 数据来源 | 实现位置 |
| --- | --- | --- |
| 修改导入参数并触发重导 | `meta.userData` | Asset Inspector |
| 展示导入后的统计、依赖和兼容性 | 源文件与 Library JSON | Asset Inspector |
| 编辑场景组件的序列化字段 | component dump | Component Inspector |
| 根据资源动态生成下拉列表 | 自定义 Asset + 组件属性元数据 | Scene 运行时代码 |
| 编辑器中直接播放 | Scene 运行时组件 | `@executeInEditMode` 组件 |

不要让 Inspector 直接改 Library JSON。Library 是 importer 的输出，会被重导覆盖；可编辑的导入配置应写入 `meta.userData`，再由 importer 读取。

## 注册 Inspector contribution

资源 Inspector 的键使用 importer 名；组件 Inspector 的键使用组件 `ccclass` 名。两者都必须与真实注册值一致：

```json
{
  "contributions": {
    "inspector": {
      "section": {
        "asset": {
          "my-format": "./inspector/asset.js"
        },
        "node": {
          "myext.Player": "./inspector/component.js"
        }
      },
      "footer": {
        "asset": {
          "my-format": "./inspector/preview.js"
        }
      }
    }
  }
}
```

修改 contribution 后必须重载扩展。仅保存 Inspector JS 不会重新注册 `package.json`。

## Asset Inspector

入口接收 `assetList` 和 `metaList`：

```js
exports.update = function update(assetList, metaList) {
  this.assetList = assetList;
  this.metaList = metaList;
  if (assetList.length !== 1) return;

  const asset = assetList[0];
  const meta = metaList[0];
  const importedPath = asset.library && asset.library['.json'];
  const imported = JSON.parse(fs.readFileSync(importedPath, 'utf8'));

  this.$.scale.value = meta.userData.scale ?? 1;
  this.$.effect.value = imported.effectAsset?.__uuid__ ?? '';
};
```

处理两类字段时使用不同策略：

- 导入结果字段只读展示。依赖使用 `ui-asset`，设置 `readonly`、`droppable` 和 UUID；数组依赖动态创建多行。
- 导入参数写入 `meta.userData`。在输入的 `change`/`confirm` 事件中同步所有选中 meta，然后按 Creator 3.8.7 Inspector 约定派发 `change`，在确认点派发 `snapshot`，让 Apply、撤销和脏状态生效。
- 多选时只编辑所有 meta 都支持的字段；若实现不支持多选，应明确提示并禁用编辑，不要只修改第一项。
- importer 必须把 `meta.userData` 纳入输出逻辑；否则界面虽然保存了参数，重导结果仍不会变化。

资源详情可能来自三个位置：

1. `asset.file` 或 `asset.source`：用户工程中的源文件；
2. `asset.library['.json']`：importer 生成的自定义 Asset 序列化结果；
3. `meta.userData`：可编辑的导入配置。

读取前检查路径存在；解析失败要在面板内显示错误，并保留带扩展前缀的控制台日志。不要吞掉错误后继续显示旧值。

`.myformat` 能进入专用 Asset Inspector 的前提是 importer 已注册为 `my-format`。普通 `.json` 若仍由 `json` 等内置 importer 接管，Inspector contribution 无法把它补救成自定义 Asset。

## 强类型自定义 Asset

运行时 Asset 只公开组件真正需要的强类型引用，manifest、Effect、Buffer 与纹理等内部依赖可以隐藏：

```ts
@ccclass('myext.DataAsset')
export class MyDataAsset extends Asset {
  @property({ visible: false })
  private manifestJson = '';

  @property({ type: [BufferAsset], visible: false })
  readonly buffers: BufferAsset[] = [];

  @property({ type: EffectAsset, visible: false })
  readonly effectAsset: EffectAsset | null = null;
}
```

必须同时对齐：

- Runtime 的 `@ccclass('myext.DataAsset')`；
- importer 的 `assetType: 'myext.DataAsset'`；
- Library JSON 的 `__type__: 'myext.DataAsset'`；
- UUID 引用的 `__expectedType__`。

任一处不一致都会出现资源已导入但强类型字段拖不进去、`loadAny()` 结果不是预期类，或 `Can not parse this input`。

## Component Inspector

先用装饰器定义可序列化 API，再用 Component Inspector 控制布局。强类型资源字段不要退回字符串路径：

```ts
@property({ type: MyDataAsset, visible: false })
private dataBacking: MyDataAsset | null = null;

@property({
  type: MyDataAsset,
  displayName: 'Data',
  tooltip: '导入后的主资源',
})
get data(): MyDataAsset | null {
  return this.dataBacking;
}
set data(value: MyDataAsset | null) {
  if (this.dataBacking === value) return;
  this.stopLoadingAndDispose();
  this.dataBacking = value;
  this.refreshEntryEnum();
  this.requestReload();
}
```

getter/setter 适合在属性变化时释放旧资源、刷新依赖字段并排队 reload。backing field 必须隐藏，避免 Inspector 同时展示两份状态。

自定义组件面板应复用 Creator 的 dump 渲染，不要重新实现资产拖拽、撤销和多选协议：

```js
const PROPERTY_NAMES = [
  'data',
  'initialEntryIndex',
  'loop',
  'timeScale',
  'previewInEditor',
];

exports.update = function update(dump) {
  for (const name of PROPERTY_NAMES) {
    const propertyDump = dump.value && dump.value[name];
    if (!propertyDump || !propertyDump.visible) continue;
    const element = document.createElement('ui-prop');
    element.setAttribute('type', 'dump');
    element.render(propertyDump);
    this.$.properties.appendChild(element);
  }
};
```

实际实现应缓存 `ui-prop`，在后续 `update()` 中复用并移除已隐藏字段，避免频繁选择节点后堆积重复 DOM。

## 动态枚举下拉

下拉选项随所选资源变化时（例如资源里的条目列表），让自定义 Asset 提供 `Enum` 形状的数据（与官方 `sp.SkeletonData.getAnimsEnum()` 同形）：

```ts
getAnimsEnum(): Record<string, string | number> {
  const definition: Record<string, number> = { '<Default>': 0 };
  this.entries.forEach((entry, index) => {
    definition[entry.name] = index + 1;
  });
  return Enum(definition) as Record<string, string | number>;
}
```

组件保留稳定的条目名用于序列化，用数值属性给 Inspector 展示枚举：

```ts
private refreshEntryEnum(): void {
  const entries = this.dataBacking?.getAnimsEnum() ?? DEFAULT_ENTRIES;
  setPropertyEnumType(this, 'initialEntryIndex', entries);
}
```

在 `onLoad()`、`onRestore()` 和资源 setter 中刷新枚举。资源变化后还要校验旧条目名是否仍存在；不存在时回退 `<Default>`，避免索引指向另一个条目。

## 编辑态预览与资源生命周期

编辑态预览组件通常需要：

```ts
@executeInEditMode
@playOnFocus
export class MyPlayer extends Component {}
```

配合以下约束：

- 用 `EDITOR_NOT_IN_PREVIEW` 区分场景编辑态和真正运行态。
- 提供 `previewInEditor`，关闭时立即取消异步加载并释放临时渲染资源。
- setter 不要同步反复创建 GPU 对象；用 `scheduleOnce(..., 0)` 合并同一轮属性变化。
- 用 generation/token 丢弃过期的异步加载结果，防止快速换资源后旧请求覆盖新状态。
- 以资源 UUID 和影响输出的序列化字段生成签名；编辑器直接修改序列化字段而未触发 setter 时，由 `update()` 检测签名变化后 reload。
- `onDisable()` 与 `onDestroy()` 都取消排队任务、使异步请求失效并释放临时创建的 Mesh、Material、Texture 等引用。

预览成功的证据是 Scene 进程中真实创建渲染资源并有画面，不能只看 Inspector 没报错。

## 组件职责

- 组件若继承某个 Renderer（`MeshRenderer`、`UIRenderer` 等），它本身就是节点上的渲染器；不要在同一节点再叠加另一个正式渲染器，必要时在 Inspector 提示冲突。
- 正式组件只负责当前节点这一个实例，变换来自 `this.node`。批量生成、排布等测试参数属于测试驱动，不要塞进正式组件的序列化字段。

## 常见失败定位

| 现象 | 优先检查 |
| --- | --- |
| `Can not parse this input: {"path": ...}` | 是否把资源路径对象误传给 `resources.load`；组件应持有强类型 Asset，不应再解析手填路径 |
| `.myformat` 仍是普通文件或 JsonAsset | `asset-handler`、扩展重载、`.meta.importer` 与 importer version |
| 资源 Inspector 不出现 | `section.asset` 的键是否等于 importer 名，而不是 Asset `ccclass` |
| 组件 Inspector 不出现 | `section.node` 的键是否等于组件完整 `ccclass` |
| 强类型字段不能拖入 | Runtime `ccclass`、`assetType`、Library `__type__`、`__expectedType__` 是否一致 |
| 下拉列表还是旧资源的内容 | 资源 setter、`onRestore()` 是否调用 `setPropertyEnumType`，旧条目名是否清理 |
| 编辑态不刷新或重复创建资源 | 是否启用 `@executeInEditMode`、属性签名检测、延迟 reload 与 generation 取消 |
| CLI Build 报场景脚本 missing/invalid | QuickPack 是否在 AssetDB 发现脚本变化前就开始反序列化场景；等待编译迭代完成并要求构建脚本把此日志视为失败 |

## 验证顺序

1. 查询 AssetDB：确认 `importer`、`type`、`imported`、`invalid`。
2. 选择源资源：验证自定义 Asset Inspector、只读依赖和可编辑 `meta.userData`。
3. 给节点添加组件：只显示期望字段，强类型资源可拖入，枚举下拉随资源更新。
4. 编辑态开启/关闭预览：确认画面、reload 合并与资源释放。
5. 保存并重开场景：确认各序列化字段正确反序列化。
6. 构建 Web/Native：日志不得含 `Missing class`、`missing or invalid`；最终包必须包含运行时代码、Effect 和依赖资源。
