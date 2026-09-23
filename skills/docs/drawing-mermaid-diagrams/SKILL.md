---
name: drawing-mermaid-diagrams
description: Use when creating or editing Mermaid diagrams (architecture/flowchart, sequence, class, state, ER, gantt, gitGraph, mindmap, timeline, pie) — especially to embed in a self-hosted GitLab (e.g. Mermaid 10.7, no ELK) or Feishu/Lark whiteboard, or when subgraph boxes overlap or a diagram renders differently across viewers.
---

# Drawing Mermaid Diagrams

## Overview

Author Mermaid that renders correctly on **this user's real targets** — self-hosted GitLab CE 18.7 and Feishu/Lark whiteboard — not just in a local preview. The target's Mermaid **version** and **layout engine** decide what works. Pick syntax to the target, using the verified facts below; don't re-investigate them.

## Render targets (verified — do not re-investigate)

| Target | What it actually runs | Implications |
|---|---|---|
| GitLab (self-hosted) | **18.7.6 CE → bundles Mermaid 10.7.0, no elkjs** | `%%{init}%%` spacing + `classDef` coloring **work — use them**. **ELK is NOT available**: v11 `config:{layout:elk}` doesn't exist in 10.7; v10 `defaultRenderer:elk` is unsupported/unreliable. **Never use ELK.** `architecture-beta` / `block-beta` are v11/v10.9 — **not in 10.7**; build architecture from `flowchart` + subgraphs. |
| Feishu / Lark whiteboard | **`lark-whiteboard` skill CONVERTS mermaid → native shapes; Feishu does the layout** | Renderer / `%%{init}%%` / elk directives are **no-ops** (the converter ignores them). The same source works; overlap depends on Feishu's own layout. Output via the **`lark-whiteboard`** skill. |
| VS Code / Typora / Obsidian preview | each bundles **its own** Mermaid version | **NOT authoritative** — differs from GitLab 10.7. Always final-check on the real target. |

## Default conventions (this user)

- **Vertical `flowchart TB`**, and **keep the subgraph group boxes**.
- Spacing init at the very top (valid in 10.7): `%%{init: {"flowchart": {"nodeSpacing": 70, "rankSpacing": 90}}}%%`
- **Semantic coloring** via `classDef` (palette below) — works on GitLab 10.7.
- **Short** edge labels; **directed** edges only (avoid undirected `-.-` / `---`); escape `<`→`&lt;`, `>`→`&gt;`; quote labels containing `()` or `/`; line breaks `<br/>`, never `\n`.

## Fixing overlapping subgraph boxes (the #1 problem)

Root cause: **two sibling subgraphs placed side-by-side at the same rank** — dagre (the only layout in 10.7) mis-computes cluster bounds and overlaps them. Apply in order:

1. **Raise `nodeSpacing`** (the horizontal gap between side-by-side clusters) to **100+** in the init directive.
2. Still overlapping? **Stack the siblings vertically** (one below the other, e.g. an ordering edge between them) instead of side-by-side — OR **ungroup the smaller sibling subgraph**: keep its nodes + color + an emoji tag so it still reads as a group, just without a box (no box → no box overlap).
3. Do **NOT** rely on `direction LR` inside a subgraph to fix it — Mermaid 10.7 **ignores subgraph `direction` when that subgraph has edges to outside nodes**.
4. Do **NOT** reach for ELK — unavailable here.

## Diagram types

Mermaid supports many. For a clean, **10.7-safe** example of each (layered architecture, flowchart, sequence, class, statev2, ER, gantt, gitGraph, mindmap, timeline, pie, quadrant), see [diagram-types.md](diagram-types.md). Pick the type that fits the information: flow/architecture → `flowchart`+subgraphs; interactions over time → `sequenceDiagram`; data model → `erDiagram`; lifecycle → `stateDiagram-v2`; schedule → `gantt`.

## Color palette (semantic; works on GitLab 10.7)

```
classDef client  fill:#0e7490,stroke:#22d3ee,color:#fff;  %% 前端/客户端 青
classDef backend fill:#065f46,stroke:#34d399,color:#fff;  %% 后端/服务   绿
classDef engine  fill:#5b21b6,stroke:#a78bfa,color:#fff;  %% 推理/计算   紫
classDef infra   fill:#1e3a8a,stroke:#60a5fa,color:#fff;  %% 基础设施   蓝
classDef ext     fill:#92400e,stroke:#fbbf24,color:#fff;  %% 外部上游   琥珀
classDef store   fill:#1e293b,stroke:#64748b,color:#fff;  %% 存储/CDN   灰
```

## Common mistakes

| Mistake | Fix |
|---|---|
| Using ELK to "fix overlap" | Unavailable on GitLab 10.7 — raise `nodeSpacing`, or stack/ungroup siblings |
| Trusting VS Code/Typora preview | Different Mermaid version; verify on GitLab / 飞书 |
| `architecture-beta` / `block-beta` for an arch diagram | v11/v10.9 — won't render on 10.7; use `flowchart`+subgraphs |
| Long multi-line edge labels | Shorten — long labels widen clusters and trigger overlap |
| Undirected `-.-` / `---` edges | Make directed; undirected edges distort dagre ranking |
| Raw `<`/`>` in labels (e.g. `Foo<T>`) | Escape to `&lt;` / `&gt;` |
| Relying on subgraph `direction` with external edges | Ignored in 10.7 — don't depend on it |

## Verify before shipping

Render on the **actual target** — push to GitLab and open the `.md`, or convert via lark-whiteboard for 飞书. Local previews are not proof. **For Feishu output, use the `lark-whiteboard` skill.**
