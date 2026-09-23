# Mermaid diagram types — 10.7-safe examples

One clean example per type. All verified to parse on **Mermaid 10.7** (GitLab CE 18.7). Each is vertical-friendly and uses only stable syntax. Copy, then adapt.

> ⚠️ Avoid on 10.7: `architecture-beta` (v11), `block-beta` (v10.9), and any `layout: elk` / `defaultRenderer: elk` directive. For an architecture diagram use **flowchart + subgraphs** (first example).

---

## 1. Layered architecture (flowchart + subgraphs) — the default for 架构图

```mermaid
%%{init: {"flowchart": {"nodeSpacing": 70, "rankSpacing": 90}}}%%
flowchart TB
    subgraph CLIENT["🖥️ 客户端层"]
        APP["桌面/Web 客户端"]
    end
    subgraph SVC["⚙️ 服务层"]
        GW["网关 · 路由/鉴权"]
        DB[("数据库")]
        GW --> DB
    end
    subgraph EXT["☁️ 外部上游"]
        API["第三方付费 API"]
    end
    APP -->|HTTPS| GW
    GW -->|转发| API

    classDef client fill:#0e7490,stroke:#22d3ee,color:#fff;
    classDef backend fill:#065f46,stroke:#34d399,color:#fff;
    classDef ext fill:#92400e,stroke:#fbbf24,color:#fff;
    classDef store fill:#1e293b,stroke:#64748b,color:#fff;
    class APP client;
    class GW backend;
    class API ext;
    class DB store;
```

## 2. Plain flowchart (decision flow)

```mermaid
flowchart TD
    A["开始"] --> B{"条件?"}
    B -->|是| C["处理 A"]
    B -->|否| D["处理 B"]
    C --> E["结束"]
    D --> E
```

## 3. Sequence diagram (时序/交互)

```mermaid
sequenceDiagram
    autonumber
    participant C as 客户端
    participant G as 网关
    participant U as 上游API
    C->>G: POST /remove-bg
    G->>U: 转发请求
    U-->>G: 200 PNG
    G-->>C: 返回结果
    Note over G: 记录用量到 SQLite
```

## 4. Class diagram (类/接口)

```mermaid
classDiagram
    class Provider {
        <<interface>>
        +RemoveBackground(image) png
    }
    class Clipdrop
    class LocalEngine
    Provider <|.. Clipdrop
    Provider <|.. LocalEngine
    Clipdrop --> Meta : returns
```

## 5. State diagram (状态机) — use stateDiagram-v2

```mermaid
stateDiagram-v2
    [*] --> HotUpdate
    HotUpdate --> LoginPackageUpdate
    LoginPackageUpdate --> Login
    Login --> LobbyPackageUpdate
    LobbyPackageUpdate --> Lobby
    Lobby --> [*]
```

## 6. ER diagram (数据模型)

```mermaid
erDiagram
    USER ||--o{ ORDER : places
    ORDER ||--|{ ORDER_ITEM : contains
    USER {
        int id PK
        string name
    }
    ORDER {
        int id PK
        int user_id FK
    }
```

## 7. Gantt (排期)

```mermaid
gantt
    title 发版计划
    dateFormat YYYY-MM-DD
    section 后端
    设计       :done,    des1, 2026-06-01, 5d
    开发       :active,  dev1, after des1, 10d
    section 客户端
    联调       :         test1, after dev1, 5d
```

## 8. Git graph (分支)

```mermaid
gitGraph
    commit
    branch feature
    checkout feature
    commit
    commit
    checkout main
    merge feature
```

## 9. Mindmap (思维导图) — v9.3+, OK on 10.7

```mermaid
mindmap
  root((系统))
    客户端
      桌面端
      Web
    服务端
      网关
      存储
    上游
      付费API
      自建引擎
```

## 10. Timeline (时间线) — v10.1+, OK on 10.7

```mermaid
timeline
    title 项目里程碑
    2026-Q1 : 立项 : 原型
    2026-Q2 : MVP 上线
    2026-Q3 : 灰度 : 正式发布
```

## 11. Pie (占比)

```mermaid
pie title 后端调用占比
    "付费API" : 45
    "自建引擎" : 40
    "免费web" : 15
```

## 12. Quadrant (四象限) — v10.3+, OK on 10.7

```mermaid
quadrantChart
    title 优先级
    x-axis 低成本 --> 高成本
    y-axis 低收益 --> 高收益
    quadrant-1 立即做
    quadrant-2 规划
    quadrant-3 不做
    quadrant-4 顺手做
    需求A: [0.3, 0.8]
    需求B: [0.7, 0.4]
```
