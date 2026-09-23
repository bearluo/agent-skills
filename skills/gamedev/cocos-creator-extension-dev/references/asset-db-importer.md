# AssetDB mount、自定义 Importer 与 Asset

本页用于 Creator 3.8.7。其他版本先检查官方扩展和 `@editor/asset-db` API，尤其不要直接沿用内部 worker 路径。

## 推荐目录

```text
extensions/my-importer/
├── package.json
├── browser.js
├── assets/                      <- mount 目录，整棵随扩展分发，.meta 必须入库
│   ├── runtime.effect
│   ├── runtime.effect.meta
│   └── runtime/
│       ├── MyAsset.ts           <- 运行时类，@ccclass('myext.MyAsset')
│       └── MyAsset.ts.meta
└── dist/
    ├── asset-db.js
    └── worker-bootstrap-<extension-version>.js
```

**运行时代码优先放进 mount 目录**，随扩展分发：目标工程装上扩展就有，不必手工拷贝、也不会两边版本漂移。Importer worker 仍要注册一个同名的最小 `cc.Asset` 占位类；最终 Scene 反序列化必须命中 mount 里那个带 `@ccclass` 的真实类。

前提是 mount 目录的 `.meta` 要随扩展入库，否则 UUID 在目标工程被重新生成。mount 里的脚本会被当作工程脚本自动收集进构建产物（实测落在主包并随包启动执行），接入方不需要额外做什么。两条都在 [SKILL.md](../SKILL.md) 的关键决策里展开。

## 扩展资源挂载

`package.json` 的核心结构：

```json
{
  "name": "my-importer",
  "package_version": 2,
  "version": "1.0.0",
  "main": "./browser.js",
  "contributions": {
    "asset-db": {
      "mount": {
        "path": "./assets",
        "readonly": true,
        "visible": false
      },
      "script": "./dist/asset-db.js",
      "asset-handler": [
        {
          "handler": "registerMyHandler",
          "name": "my-format",
          "extnames": [".myformat"]
        }
      ]
    }
  }
}
```

挂载后的资源 URL 为 `db://my-importer/runtime.effect`。随扩展分发的只读资源必须带稳定 `.meta` **并且入库**；否则目标工程会为它生成新 UUID，而 Importer 早已把旧 UUID 写进了 Library——这类失效是静默的，导入与构建都不报错。

## Importer 应建立两层依赖

Importer 生成自定义 Asset 时同时处理：

1. `asset.depend(absolutePath)`：让源文件变化触发重导入；
2. `asset.setData('depends', uuid[])`：让 AssetDB/构建系统知道 UUID 依赖。

Library JSON 中使用 Creator 的 UUID 引用结构：

```json
{
  "__type__": "MyAsset",
  "buffer": {
    "__uuid__": "...",
    "__expectedType__": "cc.BufferAsset"
  },
  "effectAsset": {
    "__uuid__": "...",
    "__expectedType__": "cc.EffectAsset"
  }
}
```

然后写入 Library：

```js
await asset.saveToLibrary('.json', `${JSON.stringify(serialized, null, 2)}\n`);
asset.setData('depends', Array.from(depends));
```

`.myformat` 是源文件后缀；`.json` 是 Library 序列化文件后缀，两者不要混淆。

## 扩展 mount 在 worker 中的坑

Creator 3.8.7 实测：主 AssetDB 能通过 `query-asset-info` 找到 `db://<package>/...`，但自定义 importer 所在 worker 的 `asset._assetDB.path2asset` 不一定包含扩展 mount。

因此不要仅凭下面这种代码判断挂载资源不存在：

```js
asset._assetDB.path2asset.get(extensionAssetAbsolutePath);
```

对扩展自带且不可变的资源，可读取随包 `.meta` 获取 UUID，并在主进程先用 `query-asset-info` 验证该 URL 已导入成功。这里读取 `.meta` 是为了跨 worker 取得扩展自己拥有的稳定身份，不是绕开 AssetDB 给任意文件伪造 UUID。

## 图片子资源

图片本体通常不是最终应引用的 `cc.Texture2D`。从图片 Asset 的 `subAssets` 中找到 importer 为 `texture` 的子资源 UUID，并把该 UUID 写入自定义 Asset。若图片尚未完成导入，明确失败并让用户重导，不要悄悄引用图片主 Asset。

## 专用后缀优先

让一个领域数据文件继续叫 `.json`，会参与 `json` 等已有 importer 的选择：

- 新复制进工程时可能落到 `cc.JsonAsset`；
- 更新 importer 后可能因为旧 `.meta` 继续走旧类型；
- 动态注册先后会改变选择结果；
- 普通 JSON 的行为容易被误伤。

除非格式就是既有生态的一部分，否则用 `.myformat`。文件内容仍可保持 JSON，兼顾可读性与稳定的 importer 路由。

## Worker bootstrap：注册不确定性的兜底

`contributions.asset-db.asset-handler` 是正确写法，但 3.8.7 上它只在扩展随 AssetDB 初始化一起 enable 时才生效；走 `enableAttach` 那条路径时 handler 工厂根本不被调用，且静默（判据与观测见 [SKILL.md](../SKILL.md) 的「重载与缓存」）。bootstrap 做的就是在 worker 里把这一步补上：

- 在 worker 注册同名 Asset class；
- 加载 handler 并补齐 importer registration；
- 更新时清理目标模块的 `require.cache`；
- 从旧后缀注册表移除同名 handler；
- bootstrap 文件名带扩展版本，避免已运行 worker 把入口本身也缓存。

该方案引用 `builtin/asset-db/dist/...` 并直接改写 worker 的注册表，属于内部 API。锁定 Creator 版本，失败时回到官方 contribution 和重启编辑器，不要把内部路径包装成跨版本公共库。

它是整个扩展里唯一一处会随 Creator 小版本碎掉的地方，所以要么锁版本留着，要么接受官方注册偶发失效——**不要因为"本机试了几次都对"就删掉**，那几次可能只是都走到了好的那条路径。

## Asset Inspector 与组件 Inspector

- `@property({ type: MyAsset })` 解决组件 Inspector 的拖拽类型。
- Importer 的 `assetType: 'MyAsset'` 解决资源被识别为什么类型。
- 资源被选中后显示哪些字段、预览窗口、播放控制，属于独立的资源 Inspector contribution。

实现带专用面板的自定义资源时，分别验收这三层，不能因为组件能拖入就宣称资源 Inspector 已完成。

