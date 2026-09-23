---
name: drawing-mermaid-diagrams
description: Use when creating or editing Mermaid diagrams (architecture/flowchart, sequence, class, state, ER, gantt, gitGraph, mindmap, timeline, pie) — especially to embed in a self-hosted GitLab (e.g. Mermaid 10.7, no ELK) or Feishu/Lark whiteboard, or when subgraph boxes overlap or a diagram renders differently across viewers.
---

# 画 Mermaid 图

## 概述

写出来的 Mermaid 要在**真实的渲染目标**上正确显示——自建 GitLab CE 18.7 和飞书 / Lark 画板——而不只是本地预览里好看。能用什么语法，取决于目标平台的 Mermaid **版本**和**布局引擎**。按目标平台选语法，直接用下面已验证的结论，不要重新调查。

## 渲染目标（已验证，不要重新调查）

| 目标 | 实际运行的是什么 | 影响 |
|---|---|---|
| GitLab（自建） | **18.7.6 CE → 内置 Mermaid 10.7.0，没有 elkjs** | `%%{init}%%` 间距设置和 `classDef` 着色**都能用，要用**。**ELK 不可用**：v11 的 `config:{layout:elk}` 在 10.7 里不存在；v10 的 `defaultRenderer:elk` 不支持 / 不可靠。**永远不要用 ELK。** `architecture-beta` / `block-beta` 分别是 v11 / v10.9 的特性，**10.7 没有**；架构图用 `flowchart` + subgraph 画。 |
| 飞书 / Lark 画板 | **`lark-whiteboard` skill 把 mermaid 转换成原生图形，由飞书自己布局** | 渲染器 / `%%{init}%%` / elk 指令都是**空操作**（转换器会忽略）。同一份源码可以直接用，会不会重叠取决于飞书自己的布局。通过 **`lark-whiteboard`** skill 输出。 |
| VS Code / Typora / Obsidian 预览 | 各自内置**自己的** Mermaid 版本 | **不作数**——和 GitLab 10.7 不一样。最终一定要在真实目标上检查。 |

## 默认约定

- **纵向 `flowchart TB`**，并**保留 subgraph 分组框**。
- 间距 init 放在最顶部（10.7 有效）：`%%{init: {"flowchart": {"nodeSpacing": 70, "rankSpacing": 90}}}%%`
- 用 `classDef` 做**语义着色**（配色见下）——GitLab 10.7 支持。
- 连线标签要**短**；只用**有向**连线（避免无向的 `-.-` / `---`）；`<` 转义成 `&lt;`、`>` 转义成 `&gt;`；标签里有 `()` 或 `/` 要加引号；换行用 `<br/>`，不要用 `\n`。

## 修复 subgraph 框重叠（头号问题）

根因：**两个同级 subgraph 在同一 rank 上左右并排**——dagre（10.7 唯一的布局引擎）算错了分组框边界，导致它们重叠。按顺序尝试：

1. **调大 `nodeSpacing`**（并排分组框之间的水平间距），在 init 指令里设到 **100 以上**。
2. 还重叠？**把同级 subgraph 改成上下堆叠**（比如在它们之间加一条表示先后的连线），不要左右并排——或者**拆掉较小那个 subgraph 的框**：保留它的节点、颜色，再加一个 emoji 标记，看起来仍是一组，只是没有框（没有框就不会框重叠）。
3. **不要**指望在 subgraph 里写 `direction LR` 来解决——**当 subgraph 有连到外部节点的边时，Mermaid 10.7 会忽略它的 `direction`**。
4. **不要**求助 ELK——这里用不了。

## 图表类型

Mermaid 支持很多类型。每种类型的干净、**10.7 安全**示例（分层架构、流程图、时序图、类图、stateDiagram-v2、ER、甘特图、gitGraph、思维导图、时间线、饼图、四象限）见 [diagram-types.md](diagram-types.md)。按信息选类型：流程 / 架构 → `flowchart` + subgraph；随时间的交互 → `sequenceDiagram`；数据模型 → `erDiagram`；生命周期 → `stateDiagram-v2`；排期 → `gantt`。

## 配色（语义化；GitLab 10.7 可用）

```
classDef client  fill:#0e7490,stroke:#22d3ee,color:#fff;  %% 前端/客户端 青
classDef backend fill:#065f46,stroke:#34d399,color:#fff;  %% 后端/服务   绿
classDef engine  fill:#5b21b6,stroke:#a78bfa,color:#fff;  %% 推理/计算   紫
classDef infra   fill:#1e3a8a,stroke:#60a5fa,color:#fff;  %% 基础设施   蓝
classDef ext     fill:#92400e,stroke:#fbbf24,color:#fff;  %% 外部上游   琥珀
classDef store   fill:#1e293b,stroke:#64748b,color:#fff;  %% 存储/CDN   灰
```

## 常见错误

| 错误 | 改法 |
|---|---|
| 用 ELK「修复重叠」 | GitLab 10.7 上不可用——调大 `nodeSpacing`，或把同级 subgraph 堆叠 / 拆框 |
| 相信 VS Code / Typora 预览 | Mermaid 版本不同；到 GitLab / 飞书上验证 |
| 架构图用 `architecture-beta` / `block-beta` | v11 / v10.9 特性——10.7 渲染不出来；用 `flowchart` + subgraph |
| 连线标签又长又多行 | 缩短——长标签会撑宽分组框，引发重叠 |
| 无向连线 `-.-` / `---` | 改成有向；无向连线会打乱 dagre 的分层 |
| 标签里有裸 `<` / `>`（比如 `Foo<T>`） | 转义成 `&lt;` / `&gt;` |
| 依赖带外部连线的 subgraph 的 `direction` | 10.7 会忽略——别依赖它 |

## 交付前验证

在**真实目标**上渲染——推到 GitLab 打开那个 `.md`，或者通过 lark-whiteboard 转到飞书。本地预览不算数。**输出到飞书时，用 `lark-whiteboard` skill。**
