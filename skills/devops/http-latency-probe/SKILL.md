---
name: http-latency-probe
description: Use when measuring or comparing the real-world latency of an HTTPS API domain across regions — "测一下这个域名的延迟", "新加的加速域名效果怎么样", "回源连接有没有复用", "CDN / 代理 / 负载均衡 keep-alive 配置对不对", GeoDNS line checks. Covers per-region DNS via DoH+ECS, TLS/header inspection, local keep-alive cases (steady / cold / concurrent / idle window) against a pinned IP, Globalping global comparison and edge-to-origin idle-window tests, plus how to read the numbers and what to tell ops.
---

# HTTPS 接口延迟与回源复用测试

回答三类问题：某个域名在各地解析到哪；各地请求慢在哪一段；入口（代理 / CDN / 负载均衡）到源站的连接有没有复用、空闲多久会断。

脚本都在 `scripts/`，依赖 `curl`、`node`（≥18，自带 `fetch`）、`bash`（Windows 用 Git Bash）。

## 一、先搞清时间分段

一次 HTTPS 请求在客户端看到的是：`dns → tcp → tls → 服务端等待(ttfb) → 下载`。

- **tcp / tls 是和最近的入口节点握手**，不是和源站握手，所以通常很快。
- **服务端等待** = TLS 完成到首字节，包含：1 次客户端 RTT + 入口回源 + 源站处理。慢基本都慢在这里。
- 入口回源时，连接如果是**复用**的，只要 1 次入口↔源站 RTT；如果要**新建**，明文 HTTP 多 1 次 RTT（TCP），HTTPS 多 2~3 次（TCP + TLS）。所以「新建 / 复用」的差值除以入口↔源站 RTT，能反推回源走的是 HTTP 还是 HTTPS。

估算公式（入口↔源站 RTT 记为 r，源站处理记为 s）：

| 回源状态 | 服务端等待 ≈ |
|---|---|
| 复用 | 客户端RTT + r + s |
| 新建，明文 HTTP | 客户端RTT + 2r + s |
| 新建，HTTPS | 客户端RTT + 3~4r + s |

## 二、流程

### 1. 解析线路

```bash
scripts/geo-dns.sh <domain>            # A 记录，20 个地区
scripts/geo-dns.sh <domain> AAAA       # 看有没有 IPv6
scripts/geo-dns.sh <domain> A aliyun   # 用阿里 DoH 交叉验证
```

- 靠 `edns_client_subnet` 模拟地区，Google / 阿里 DoH 支持，**Cloudflare 不支持**。
- 记下每条线路的入口：自建代理 IP、CDN 的 CNAME、直连源站。后续按线路分组测。
- 网段是代表值，GeoDNS 偶尔会把某些网段判错地区，单个异常点别过度解读。

### 2. 证书、协议、响应头

对每个入口 IP 各跑一次（`--resolve` 固定 IP）：

```bash
curl -s --resolve <host>:443:<ip> -D - -o /dev/null https://<host><path>
echo | openssl s_client -connect <ip>:443 -servername <host> -alpn h2,http/1.1 2>/dev/null | grep -E "subject=|issuer=|ALPN"
echo | openssl s_client -connect <ip>:443 -servername <host> 2>/dev/null | openssl x509 -noout -dates -ext subjectAltName
```

看：证书到期时间（CDN 托管证书要确认会自动续期）、是否 h2、各入口回来的响应头是否一致（判断是不是同一个后端）、CDN 的 `X-Cache`（动态接口应为 Miss，出现 Hit 要警惕把带用户态的响应缓存了）、`X-Amz-Cf-Pop` 之类的边缘节点标识。

### 3. 本机测某个入口的回源复用

```bash
scripts/keepalive.sh <host> <入口ip> <path>                 # A B C D 全跑
IDLES="5 30 55 65" scripts/keepalive.sh <host> <ip> <path> D # 只测空闲窗口
```

| 用例 | 做法 | 看什么 |
|---|---|---|
| A 连续 | 一条客户端连接上连发 20 个 | 稳态回源耗时 |
| B 新连接 | 每次新开客户端连接，发 10 次 | 客户端换连接后，入口是否还复用回源池 |
| C 并发 | 10 并发 × 3 轮 | 并发时复用比例（明显低于新建水平的算复用） |
| D 空闲窗口 | 先预热，再空闲 N 秒，连发 3 个 | 空闲多久后第一个请求变回新建水平 → 实际生效的空闲超时 |

- 同时测一个**对照域名**（走同一入口、配置不同的那个），差值才说明问题。
- 本机离入口越远，单次波动越大；看 p50，不看单个值。
- D 里每轮第一个请求跳高、后两个恢复，就是「空闲期间回源连接被关掉，第一个请求重建」。实际生效的超时 = 链路上**各层空闲超时的最小值**（入口代理的 upstream keepalive、负载均衡的空闲超时、源站 web server 的 keepalive_timeout）。

### 4. 全球对比

```bash
node scripts/gp-compare.js <path> <新域名> <对照域名>
LOC="US:8,GB:3,IN:3,BR:2,AU:2" ROUNDS=2 node scripts/gp-compare.js <path> <host1> <host2>
```

输出按国家分组：样本数、解析到的 IP（CDN 带 POP）、tcp、tls、服务端等待、total 的中位数。

- 匿名 Globalping 每小时额度有限（按探测点计数），超了返回 `rate_limit_exceeded`。探测点 × 域名 × 轮数先算好；需要更多就设 `GLOBALPING_TOKEN`（免费注册）。
- Globalping 每次测量都是新连接、单个请求，测出来的是**冷客户端**的数字；边缘回源是冷是热取决于该节点当时有没有别的流量。

### 5. 边缘 → 源站的空闲窗口（CDN 场景）

```bash
node scripts/gp-idle.js <host> <path>
GAPS="0,0,5,15,60" node scripts/gp-idle.js <host> <path>
```

用同一批探测点（第二发起 `locations` 传首发的 measurement id）按间隔连发。间隔短时 firstByte 降到「复用」水平、间隔拉长后跳回「首发」水平，跳变点就是边缘节点的回源空闲超时。离源站远的地区（RTT 大）最明显。

## 三、常见结论与给运维的建议

| 现象 | 原因 | 建议 |
|---|---|---|
| 自建代理线路服务端等待 ≈ 新建水平，D 用例几秒就断 | 代理 upstream keepalive 或负载均衡空闲超时太短 | 代理 `keepalive_timeout` 设得比负载均衡空闲超时**小**几秒，避免复用到对端已关的连接（502）；两边都往上调 |
| 负载均衡空闲超时调不上去 | 产品上限。阿里云 CLB 七层监听 1–60s；四层（TCP）可到 900s；ALB 默认 600s、提配额到 3600s | 先用满七层上限；仍不够再评估四层监听或换产品 |
| 新建回源只多 2×RTT | 回源是明文 HTTP | 路径经过公网且 URL / 头里有 token、签名时，改 HTTPS 回源并开 TLS 会话复用（nginx `proxy_ssl_session_reuse on`） |
| 新 CDN 分发远地区特别慢，本机测却很快 | 新分发没流量，边缘回源连接是冷的；CloudFront 回源 keep-alive 默认只有 5s（可调 1–60s，提配额到 180s） | 调大回源 keep-alive；开 Origin Shield（选离源站最近的区域）让回源集中到一层；或复用已有流量的旧分发 |
| 某地区新线路比旧线路慢 | GeoDNS 把该地区从更近的自建节点改到了 CDN | 先保留旧线路，等新线路优化后复测再切 |
| 负载均衡健康检查没开 | — | 开，否则后端挂了还会转发 |

本机测入口离源站很近（同城 POP）时，新建和复用几乎没差别，**不能用来判断复用**，要从离源站远的地区测。

## 四、汇报模板

1. 一句话结论：哪条线路赚了多少 ms，哪条线路亏了，主因是什么。
2. 解析线路表：地区 → 入口。
3. 延迟对比表：地区 / 线路 / 新域名 / 对照域名 / 差值（服务端等待中位数）。
4. 回源复用：A/B/C/D 结果和推出的空闲超时。
5. 原因分析（标明哪些是推断、哪些已实测）。
6. 给运维的建议，按收益排序；改完后用同一套脚本复测。

## 五、坑

- `curl` 一次带多个 URL 时，`-o /dev/null` 只作用于紧跟的那个 URL，必须每个 URL 前都写一次，否则响应体混进 `-w` 输出，算出负数。
- 复用的连接 `time_connect` / `time_appconnect` 都是 0，计算回源时要区分新建和复用。
- Windows 上 `python` 可能是应用商店占位，统计用 `node` / `awk`。
- 测试脚本放临时目录，结论和实测数字写进项目自己的文档，不写回本 skill。
