#!/usr/bin/env bash
# 用 DoH + edns_client_subnet 模拟各地区解析：geo-dns.sh <domain> [A|AAAA] [google|aliyun]
# Cloudflare 的 DoH 不支持 ECS，不能用来测 GeoDNS。
set -u
D=$1; T=${2:-A}; P=${3:-google}
case $P in
  google) BASE="https://dns.google/resolve?name=$D&type=$T&edns_client_subnet=" ;;
  aliyun) BASE="https://dns.alidns.com/resolve?name=$D&type=$T&edns_client_subnet=" ;;
  *) echo "unknown doh: $P" >&2; exit 1 ;;
esac
# 每个国家一个有代表性的网段；要更细（同国多运营商）自己往后加
for cc in US:8.8.8.0/24 CA:24.48.0.0/16 MX:189.203.0.0/16 BR:177.0.0.0/16 \
          GB:81.2.69.0/24 DE:46.114.0.0/16 FR:90.0.0.0/16 PL:83.0.0.0/16 \
          IN:49.36.0.0/16 SG:118.200.0.0/16 JP:126.0.0.0/16 KR:211.234.0.0/16 \
          ID:36.80.0.0/16 PH:112.198.0.0/16 TH:171.96.0.0/16 VN:113.160.0.0/16 \
          AU:1.120.0.0/16 TW:1.160.0.0/16 HK:14.0.0.0/16 CN:202.96.0.0/16; do
  c=${cc%%:*}; e=${cc#*:}
  a=$(curl -s -m 10 "$BASE$e" | grep -o '"data": *"[^"]*"' | sed 's/.*"\([^"]*\)"$/\1/' | tr '\n' ' ')
  printf '%-3s %s\n' "$c" "${a:-(空)}"
done
