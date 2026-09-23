---
name: feishu-minutes-export
description: Use when the user wants to export / download a Feishu or Lark Minutes (妙记) transcript / 文字记录 to a local file. Triggers include "导出飞书妙记", "妙记文字记录", "飞书会议文字记录导出", "把这个妙记导出", or any feishu.cn / larksuite.com "/minutes/" URL. Pulls the full timestamped transcript with speaker names via the Minutes web API using a logged-in browser session (no manual scroll-scraping, no cookie extraction).
---

# 飞书妙记文字记录导出

用页面自身的登录态调飞书妙记内部接口，一次性把整份文字记录（带时间戳 + 说话人）拉成 `.md` / `.txt`。
**不靠**滚动截屏、**不靠**读/解密浏览器 cookie（那条路被本机安全策略拦，且脆）。

## 核心脚本

`scripts/export_minutes.py <妙记URL> [输出目录]`

它会：
1. 确保本机 `127.0.0.1:9222` 上有一个调试 Edge（持久化配置目录 `~/edge-automation`，登录态长期保存）。没起就自动拉起一个**可见窗口**并打开该 URL。
2. 通过 CDP 把标签导航到妙记页。
3. 页内 fetch `subtitles/paragraph-ids` → `subtitles_v2` → `speakers`，组装全文。
4. 写 `<标题>-文字记录.md` 和 `.txt` 到输出目录，stdout 打印 JSON（含路径、段数、发言人、时间跨度）。

退出码：`0` 成功；`2` = `LOGIN_REQUIRED`（未登录或无此妙记访问权，调试 Edge 已把登录页显示在可见窗口）；其它非 0 出错。

## 用法（主会话直接跑，别派 subagent）

```bash
python3 "~/.claude/skills/feishu-minutes-export/scripts/export_minutes.py" \
  "<妙记URL>" "<scratchpad或指定目录>"
```

- **首次**（或登录过期）会打印 `LOGIN_REQUIRED`：此时可见的 Edge 窗口停在飞书登录页，让用户在**那个窗口**用手机飞书扫码，扫完**原样重跑**同一条命令即可。登录态持久化，之后同一账号能访问的妙记都免扫码（换飞书租户子域名也没关系，同账号即可）。
- 成功后，把 `.md`（可读）和 `.txt`（纯文本）用 `SendUserFile` 发给用户。要「打开目录」就 `explorer.exe "<目录>"`。
- 输出目录默认给本会话 scratchpad；用户指定了就用用户的。

## 会话里怎么串（推荐）

1. 跑脚本。stdout 是 JSON → 直接拿 `md`/`txt` 路径。
2. `LOGIN_REQUIRED` → 一句话让用户扫可见窗口里的码 → 收到「扫好了/授权了」再重跑。
3. `SendUserFile` 发两份文件，附一行摘要（段数、时间跨度、发言人）。

## 坑位（都已在脚本里处理，改脚本时别踩回去）

- **不能静默复用主 Edge 登录**：读取/克隆 Edge 的 cookie 库被 Claude Code 安全分类器拦截（属凭据外泄类操作）。所以用**独立持久化调试 profile**，而不是去解密主 Edge 的 cookie。
- **CDP WebSocket 403**：Edge 152+ 会因 Origin 校验拒连，报 `--remote-allow-origins` 提示。脚本两头都堵：启动带 `--remote-allow-origins=*`，连接带 `suppress_origin=True`。
- **终端 GBK 乱码**：本机终端按 GBK 解码，中文别往 stdout 直接打大段正文——脚本把正文只写 UTF-8 文件，stdout 只回 ASCII-safe 的 JSON。
- **subtitles_v2 分页语义**：`?paragraph_id=X&size=N` 返回的是**从 X 起的 N 段**（不是单段内分页）。脚本按 `paragraph-ids` 的顺序表游标推进，去重装配，直到覆盖全部 `total` 段。
- **说话人映射**：`/speakers` 的 `speaker_info_map`（id→姓名）配 `paragraph_to_speaker`（pid→id），回落 `device_owner_map` / `paragraph_to_device_owner`。没绑定到人的音轨会显示「说话人 N」——原始数据如此，不臆造人名（用户要求时才按上下文归并）。
- **只导「文字记录」**，不含「智能纪要」。要 AI 纪要另说（对应接口不同）。

## 自检

`python3 scripts/export_minutes.py selftest` —— 验证段落拼接、说话人回落、时间格式、文件名清洗四个纯函数。
