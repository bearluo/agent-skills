# 构建产物与 Bundle 裁剪验收

本页针对 Cocos Creator 3.8.7 的 Web/Native 构建，重点是避免把编辑器工具、旧产物或“构建成功”误当成扩展已交付。

## 构建方式与互斥

- 同一工程同一时刻只能有一个 Creator 在跑构建：可见编辑器、命令行 `--build` 隐藏实例、MCP 调用的 Builder 共享 `library/`、`temp/`，并发会互相踩。
- 用可见编辑器构建（例如经 MCP 在 editor 上下文调用 Builder）可以复用已完成导入的 AssetDB；用命令行 `CocosCreator --project <dir> --build configPath=<json>` 前先关闭该工程的编辑器。选哪种按项目自己的构建脚本约定。
- 平台工程（Android gradle、iOS Xcode 等）在 Builder 完成后再编。

每次构建记录 Builder 日志、产物路径、修改时间和哈希。验收用的产物必须来自本次构建输出，不能复用目录里的旧文件。

## Bundle 裁剪验收

Creator 的裁剪以场景入口和静态依赖为边界：

```text
正式场景 -> 运行时组件 -> 自定义 Asset -> 依赖资源
调试场景 -> 调试/转换工具 -> 调试 Bundle
```

调试入口静态 import 了转换器、分析工具时，它们出现在主 Bundle 是预期的依赖收集结果，不是 Creator 没裁剪。正式包应通过独立场景、独立子 Bundle 或编辑器扩展隔离工具链，然后逐个 Bundle 检查：

- `index.js`：是否包含预期运行时类，是否混入工具模块；
- `cc.config.json` 和 import JSON：自定义 Asset 的 `__type__`、Effect/Buffer/Texture2D 等 UUID 依赖；
- native 资源：自定义 Asset 依赖的二进制与纹理是否在预期 Bundle；
- 重复依赖：主包与子包是否各自复制了同一份大资源。

子 Bundle 有自己的依赖图，只有被它引用的代码和资源才会进入该 Bundle。

## 结果解释

- 主 Bundle 出现工具模块：先检查场景入口的静态 import，不要直接归因于 Creator 未裁剪。
- 包体变大：区分 JS、自定义资源、纹理和 native 库，不能只看总大小。
- 构建日志出现 `Missing class`、`missing or invalid`、`A Class already exists`：视为失败，回到 [custom-asset-serialization.md](custom-asset-serialization.md) 查类名与占位类。
- 没法在目标平台启动验证：保留构建证据，明确标记“未完成平台验证”，不要用另一个平台或旧产物补写结论。
