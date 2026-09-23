---
name: pen-design-first
description: Use when about to build or change any UI — a new page or screen, a rearranged layout, a form/panel/modal, or a changed interaction flow. Draw it in a .pen file with pen.dev, show it, and get explicit confirmation BEFORE writing any component code. Also use when the user says the interface is messy, keeps rejecting UI changes, or asks to redesign an existing screen.
---

# 先出 pen，确认了再动工

**做界面之前先画出来给需求方看，他点头了才写代码。** 这条 skill 的存在是因为反过来的顺序试过很多次：直接改代码 → 截图 → 「不是这个意思」→ 再改 → 再截图。每一轮都是一次完整的开发 + 部署，而分歧其实在第一分钟就能看出来。

## 什么时候必须先出图

- 新页面、新面板、新弹窗；
- 现有页面**换形状**：字段搬家、区块合并拆分、内联表单改弹窗、按钮增删改位置；
- **交互流程变了**：几步走完、哪一步提交、点了之后跳哪儿；
- 需求方说「乱」「难看」「奇怪」「不是这个意思」—— 这三个词出现就停手，别再在代码里试。

## 什么时候不用

- 改文案、改颜色、改一个 label；
- 修 bug（界面形状不变）；
- 需求方明确说「你直接改，不用给我看图」。

**判据是「形状变没变」，不是「改动大不大」。** 一行代码把内联表单换成弹窗，形状就变了。

## 流程

1. **先读代码，把现状画准。** 画的是「现在长什么样」+「改成什么样」两版，只画后者的话需求方没法比对，而他脑子里的「现在」经常跟实际不一样。
2. **画在 .pen 里**（见下）。
3. **导出 PNG 贴给需求方**（`--export`），不要只给一个文件路径 —— 他不一定装了 Pencil。
4. **等他明确点头**。含糊的「嗯」「行吧」不算，要他说清楚哪一版、有没有要改的。
5. **确认之后才写代码**，写完对着图逐条核对。
6. **代码改了图要跟着改**，不然三周后那份图比没有更糟 —— 看图的人得先判断哪块还算数。**图跟代码同一个 commit 走。**

## pen.dev 怎么用

CLI：`@pen.dev/cli`（`pen` 命令）。MCP：`mcp__pencil__*`。

**MCP 要求编辑器里先打开一个文件，CLI 不要求** —— 这是选路的唯一依据：

- **CLI `pen`（默认走这条）**：`pen --out x.pen --prompt "…"` 从零起稿，`--in a.pen --out b.pen` 改稿，`--export x.png --export-scale 2` 导图。
  它会**再起一个 claude 去画**（贵、细节不完全受控），所以**只用来整块重画**；改一两个节点直接编辑 JSON。
  不需要任何人操作，也不需要登录。
- **MCP `mcp__pencil__*`**：要用户先在 Pencil 应用（或 VS Code 扩展）里打开那个 `.pen`，否则一律报
  `Failed to access file . A file needs to be open in the editor`。而且**这个会话连的是哪个 app 由 MCP server 的启动参数定死**
  （`--app desktop` 还是 `--app visual_studio_code`），连错了报 `transport not connected to app: …`，
  会话中途改不了。**别为此卡住，转 CLI。**

**.pen 是明文 JSON**（`{version, children:[…]}`，节点有 `id`/`name`/`type`/`content`，隐藏用 `enabled:false`）。
所以**改一两个节点直接 node 读写就行**，不用为此再起一个 agent —— 只有整块重画才值得走 CLI。
（pencil MCP 的文档说它是加密的，实测不是。）

**CLI 不需要登录**：`pen status` 显示 Expired 照样能用，鉴权只管云端 workspace。

**改 JSON 时按块限定搜索范围**：几个 artboard 里常有同名节点（`会议室行` 在三块里各有一个），
全文档 `find(name)` 会命中第一个 —— 踩过一次，把一个链接插进了「现状」那一栏。

## 文件放哪

**跟它画的那个组件同目录、同名，当兄弟文件放** —— `Review.tsx` 旁边就是 `Review.pen`，跟
`report.ts` / `report.test.ts` 一个路子。**别单开一个 `docs/design/ui/`**：图跟代码隔着几层
目录，改代码的人根本不会想起还有一份图，而这条 skill 的全部目的就是让他想起来。组件删了 /
改名了，孤儿 `.pen` 当场露出来。

跟代码同一个 commit 走。放在仓库外面的图，下一个人找不到，也不会跟着改。

**一屏一个文件。** 但它有两种状态，别混：

- **提案期**：「现状」和「新方案」两版并排 —— 只画新的，需求方脑子里的「现在」经常跟实际不一样，没得比就吵不清。
- **落地后**：**把现状那一版删掉**，新方案各块改名成真实状态名（`屏-等面评` / `弹窗-安排面试`），
  从此这个文件只描述现状。不清理的话，下一个人打开看见两版，不知道哪版是线上跑着的。

提案期那张并排图**导出 PNG 存进 `docs/design/assets/YYYY-MM-DD-*.png`**，跟那次的决策文档放一起。
**快照里放 PNG 不放 `.pen`** —— `.pen` 会一直变，而快照的全部价值是「当时拍板的就是这个样子」，
指向一个会变的文件等于这份快照三个月后在撒谎。

## 别做的事

- 别把图当验收标准的全部 —— 密集信息的界面（表格、队列、带状态的面板）在图上看着宽松，实际数据一进去就挤。图定的是**形状和流程**，间距要在真环境里再看一眼。
- 别为一次小改动画一份新图，改原来那份。一屏一个文件，版本靠 git。
- 别画全站。只画正在动的那几屏 —— 画了不维护的部分等于给下一个人埋雷。
