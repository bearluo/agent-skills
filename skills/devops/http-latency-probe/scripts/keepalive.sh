#!/usr/bin/env bash
# 本机测「入口代理 → 源站」回源连接是否复用：keepalive.sh <host> <ip> <path> [用例]
#   用例：A 连续 / B 新连接 / C 并发 / D 空闲窗口，默认 ABCD
#   D 的空闲秒数：IDLES="5 15 30 50 70" 覆盖
# 指标「回源」= ttfb − TLS 完成时刻 − 1×客户端RTT ≈ 请求在入口代理后面花的时间（含源站处理）
set -u
H=$1; IP=$2; P=$3; CASES=${4:-ABCD}; IDLES=${IDLES:-5 15 30 50 70}
U="https://$H$P"
# 一个 curl 进程里多个 URL 会复用同一条连接；-o 必须每个 URL 各写一次，否则响应体会混进计时输出
req(){ curl -s -m 60 --resolve "$H:443:$IP" -w "%{time_connect} %{time_appconnect} %{time_starttransfer}\n" $(for i in $(seq "$1"); do echo "-o /dev/null $U"; done); }
pct(){ sort -n | awk -v t="$1" -v v="${2:-}" '{a[NR]=$1;s=s" "$1}END{n=int(NR*.9);if(n<1)n=1;printf "%s n=%d p10=%s p50=%s p90=%s\n",t,NR,a[int(NR*.1)+1],a[int(NR/2)+1],a[n];if(v)print "  全部:"s}'; }
cold(){ awk '{print int(($3-$2-$1)*1000)}'; }   # 新连接：减掉本次 TLS 完成时刻和 1×RTT（time_connect≈RTT）
RTT=$(curl -s -o /dev/null -m 20 --resolve "$H:443:$IP" -w "%{time_connect}" "$U")
echo "host=$H ip=$IP RTT=${RTT}s"
# 复用的连接 time_connect / time_appconnect 都是 0，所以 A 用 ttfb − RTT；丢掉前两个（含建连）
case $CASES in *A*) req 20 | awk -v r="$RTT" 'NR>=3{print int(($3-$2-r)*1000)}' | pct "A 连续(同一条客户端连接)";; esac
case $CASES in *B*) for i in $(seq 10); do req 1; done | cold | pct "B 每次新客户端连接" v;; esac
case $CASES in *C*) for r in 1 2 3; do for i in $(seq 10); do req 1 & done; wait; done | cold | pct "C 并发10×3" v;; esac
case $CASES in *D*) for idle in $IDLES; do
  req 8 >/dev/null; sleep "$idle"
  echo "D 空闲${idle}s 后连发3个: $(for i in 1 2 3; do req 1; done | cold | tr '\n' ' ')"
done;; esac
