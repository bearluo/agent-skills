# 编辑器内 UI 与场景进程

本页针对 Cocos Creator 3.8.7，除标注「未验证」「推测」的条目外都在该版本实测过。覆盖一类常见扩展形态：右键资源打开参数面板 → 在场景进程里计算 → 产物写盘并导入 → 自定义资源拖进层级面板生成节点，外加首次启动弹一次的指导面板。

## 场景进程脚本

凡是必须依赖 `cc` 的编辑期计算（例如烘焙、按 uuid 读真实资源、调引擎模块），都放进场景进程脚本，主进程和面板都不直接碰 `cc`。

```json
{
  "contributions": {
    "scene": { "script": "./scene.js" }
  }
}
```

```js
// scene.js —— 运行在场景进程，可以 require('cc')
const cc = require('cc');

exports.methods = {
  async bake(assetUuid, options) {
    const asset = await new Promise((resolve, reject) =>
      cc.assetManager.loadAny(assetUuid, (err, a) => (err ? reject(err) : resolve(a))));
    // ...创建节点、调用引擎模块、计算...
    return { ok: true /* 只返回纯数据 */ };
  },
};
```

主进程或面板调用：

```js
const result = await Editor.Message.request('scene', 'execute-scene-script', {
  name: 'my-extension',   // package.json 的 name
  method: 'bake',
  args: [assetUuid, options],
});
```

- `args` 和返回值都必须能结构化克隆：纯数据，不能传 `cc` 对象、函数或类实例。要把资源交给场景进程，传 uuid 让它自己加载。
- **场景脚本和它 `require` 进来的模块都会被缓存**，改完要重启 Creator 才生效，重载扩展不够。

### 临时节点

为计算临时创建的节点：

```js
const { CCObject, director } = cc;
const temp = new cc.Node('__my_extension_temp');
temp.hideFlags |= CCObject.Flags.DontSave | CCObject.Flags.HideInHierarchy;
director.getScene().addChild(temp);
try {
  // ...计算...
} finally {
  temp.destroy();
}
```

- `DontSave` 防止被写进场景文件，`HideInHierarchy` 防止在层级面板闪现。
- 前提是编辑器当前打开着一个场景（`director.getScene()` 非空）。没有场景时要给出明确错误，并在面板或文档里提示用户「先打开一个场景」。

## 菜单

资源右键菜单：

```json
{
  "contributions": {
    "assets": {
      "menu": { "methods": "./assets-menu.js", "assetMenu": "onAssetMenu" }
    }
  }
}
```

```js
// assets-menu.js
exports.onAssetMenu = function (assetInfo) {
  if (assetInfo.type !== 'MyAsset') return [];   // 不想显示就返回 []
  return [{
    label: '打开参数面板',
    async click() {
      await Editor.Message.request('my-extension', 'set-target', assetInfo.uuid);
      Editor.Panel.open('my-extension.bake');
    },
  }];
};
```

`click` 里先 `request` 主进程把目标资源存下来，再打开面板；面板打开后自己去主进程取（见下文「给面板传数据」）。

顶部菜单：

```json
{
  "contributions": {
    "menu": [
      { "path": "i18n:menu.extension", "label": "My Extension/Guide", "message": "open-guide" }
    ]
  }
}
```

菜单在启动时注册，新增或修改后要重启 Creator。

## 简单面板（不引框架）

```json
{
  "panels": {
    "bake": {
      "title": "My Extension",
      "type": "simple",
      "main": "./panels/bake.js",
      "size": { "width": 360, "height": 480, "min-width": 300, "min-height": 300 }
    }
  }
}
```

```js
// panels/bake.js
module.exports = Editor.Panel.define({
  template: `
    <ui-label value="Scale"></ui-label><ui-num-input id="scale" value="1"></ui-num-input>
    <ui-checkbox id="flip">Flip</ui-checkbox>
    <ui-button id="run">Bake</ui-button>`,
  style: `:host { padding: 8px; }`,
  $: { scale: '#scale', flip: '#flip', run: '#run' },
  methods: {
    setTarget(data) { this.target = data; },   // 供消息推送调用
  },
  async ready() {
    this.target = await Editor.Message.request('my-extension', 'get-target');
    this.$.scale.addEventListener('change', (e) => { this.scale = e.target.value; });
    this.$.run.addEventListener('confirm', async () => {
      this.$.run.setAttribute('disabled', '');
      try { /* request 主进程或 execute-scene-script */ }
      finally { this.$.run.removeAttribute('disabled'); }
    });
  },
  close() {},
});
```

- 打开 / 关闭：`Editor.Panel.open('<package>.<panel>')` / `Editor.Panel.close('<package>.<panel>')`。
- 原生控件：`ui-input`、`ui-num-input`、`ui-checkbox`、`ui-button`、`ui-label`。按钮监听 `confirm`；复选框和输入框监听 `change`，值在 `event.target.value`；设 `disabled` 属性置灰。
- 面板运行在渲染进程，加载不了依赖 `cc` 的模块。要用 `cc` 就经 `execute-scene-script` 转到场景进程。

### 给面板传数据

推给**已经打开**的面板：在 `contributions.messages` 里把消息指向面板方法，再 `send`。

```json
{
  "contributions": {
    "messages": {
      "target-changed": { "methods": ["bake.setTarget"] }
    }
  }
}
```

```js
Editor.Message.send('my-extension', 'target-changed', data);
```

面板刚打开时消息可能已经发过了（面板在消息之后才加载完），所以 `ready` 里要主动 `request` 主进程拿一次初始数据，不能只靠推送。

## 首次启动只弹一次

```json
{
  "profile": {
    "editor": { "guideShown": { "default": false } }
  }
}
```

```js
// 主进程 load
async load() {
  const shown = await Editor.Profile.getConfig('my-extension', 'guideShown', 'global');
  if (!shown) {
    Editor.Panel.open('my-extension.guide');
    await Editor.Profile.setConfig('my-extension', 'guideShown', true, 'global');
  }
}
```

`global` 是按机器记的，不是按工程记：同一台机器开第二个工程不会再弹。想按工程记就换别的作用域，并先确认它在当前版本的行为。

## 把自定义资源拖进层级面板 / 场景视图生成节点

层级面板允许拖入的资源类型（creatable asset types）是编辑器写死的，自定义资源拖进去默认没反应。扩展要自己声明 drop contribution：

```json
{
  "contributions": {
    "hierarchy": { "drop": [{ "type": "MyAsset", "message": "drop-my-asset" }] },
    "scene":     { "drop": [{ "type": "MyAsset", "message": "drop-my-asset" }] },
    "messages":  { "drop-my-asset": { "methods": ["onDropMyAsset"] } }
  }
}
```

`type` 是资源类型，也就是 importer 的 `assetType`，不是后缀也不是 importer 名。

主进程方法里用场景消息拼出节点：

```js
async onDropMyAsset(dropInfo) {
  const request = (m, ...a) => Editor.Message.request('scene', m, ...a);

  let parent = dropInfo.parent;   // 以实际收到的字段为准，先打日志看一次结构
  if (!parent) {
    // 拖进场景视图时显式挂到场景根，否则会挂到当前选中节点下
    const tree = await request('query-node-tree');
    parent = tree.uuid;
  }

  const node = await request('create-node', { parent, name: 'MyAsset' });
  await request('create-component', { uuid: node, component: 'cc.UITransform' });   // 2D 节点
  await request('create-component', { uuid: node, component: 'MyComponent' });

  const dump = await request('query-node', node);
  const i = dump.__comps__.findIndex((c) => c.type === 'MyComponent');

  await request('set-property', {
    uuid: node,
    path: `__comps__.${i}.myAsset`,
    dump: { type: 'MyAsset', value: { uuid: dropInfo.uuid } },
  });
  await request('set-property', {
    uuid: node,
    path: `__comps__.${i}.mode`,
    dump: { type: 'Enum', value: 1 },   // 枚举属性写 type: 'Enum'
  });
  await request('set-property', {
    uuid: node,
    path: 'layer',
    dump: { type: 'Number', value: 1 << 25 },   // UI_2D
  });
}
```

- 组件下标 `<i>` 从 `query-node` 返回的 `__comps__` 里按类型找，不要写死。
- 2D 节点除了补 `cc.UITransform`，还要把 `layer` 设为 `UI_2D`（`1 << 25`），否则 2D 相机看不到。

## 一次写出多个产物的写盘顺序

产物是「若干子文件（贴图、二进制）+ 一个引用它们的聚合清单」时：

1. 先写全部子文件，然后对输出目录 `Editor.Message.request('asset-db', 'refresh-asset', dirUrl)`，等它返回；
2. **最后**才写聚合清单，并单独对它 `refresh-asset`。

同时写的话，清单的 importer 执行时贴图还没导入完（`Texture2D` 子资源还不存在），导入失败，要手动再刷新一次才会好。

## 编辑器侧 TS 源码打包

场景脚本和主进程只能 `require` JS。TS 源码用 esbuild 打包：

```js
await esbuild.build({
  entryPoints: ['src/scene/index.ts'],
  bundle: true,
  platform: 'node',
  format: 'cjs',
  external: ['cc'],          // cc 由场景进程提供
  outfile: 'dist/scene-core.js',
});
```

- 场景脚本 `require('./dist/scene-core.js')` 使用产物。
- **产物要入库**，接入方不需要构建。仓库 `.gitignore` 若有 `dist/`，用 `git add -f` 或给这个目录加例外。
- 构建脚本配一个 `--check` 参数：构建到临时位置，与已入库产物比对，不同就非零退出，给 CI 用。
- **产物里的路径注释会随运行目录变化**，固定在同一个目录（例如仓库根）运行，否则 `--check` 会误报不同步。
- esbuild 默认把非 ASCII 字符转义成 `\uXXXX`，不影响运行。

## 已知现象

- **改完扩展没重启时，Inspector 里组件的资源字段显示「未知类型」**，重启 Creator 即恢复。原因**推测**（未验证）是自定义 Asset 类在 asset-db worker 和场景进程里各注册了一份，热重载只更新了其中一边。处理：改扩展后重启 Creator。
- **资源图标（未验证）**：asset-handler 返回对象里写 `iconInfo: { default: { type: 'image', value: 'packages://<package>/static/icon.svg' } }`，在 3.8.7 上是否生效未验证，使用前先实测。

## 交付验收

扩展交付给别人时，除主文档的验收口径外再走两步：

1. 把扩展目录原样拷进一个**空的新工程**，重启 Creator；
2. 走一遍完整用户路径：右键 → 面板 → 产物导入 → 拖入生成节点。

新工程默认的引擎模块配置（例如某个第三方运行时的版本）可能和开发用的工程不一样。场景进程依赖某个引擎模块时，在入口处检测模块是否启用 / 版本是否匹配并给出明确提示，不要让它在深层崩溃。
