#!/usr/bin/env python3
"""Aggregate Claude Code local token usage from session JSONL logs.

Reads ~/.claude/projects/**/*.jsonl (every project + subagent transcript),
dedups by (message.id, output_tokens), and aggregates by day / model /
optionally per session. Cost is a ROUGH API-equivalent estimate only —
Pro/Max subscriptions are NOT billed per token.

Usage:
  python report.py                 # last 2 days, by day+model
  python report.py --days 7        # last 7 days
  python report.py --since 2026-05-18 --until 2026-05-19
  python report.py --by-session    # add per-session breakdown (top 15)
  python report.py --by-tool       # rank tools by result payload size (what to optimize)
  python report.py --no-subagents  # exclude subagents/ transcripts
  python report.py --cost          # add rough API-equivalent $ estimate
  python report.py --project foo   # only project dirs whose name contains 'foo'
"""
import os, json, glob, argparse
from collections import defaultdict
from datetime import date, timedelta

# Rough public API prices, USD per 1M tokens. Subscription users: ignore $.
PRICES = {  # (input, output, cache_write_5m, cache_read)
    "opus":   (15.0, 75.0, 18.75, 1.50),
    "sonnet": ( 3.0, 15.0,  3.75, 0.30),
    "haiku":  ( 1.0,  5.0,  1.25, 0.10),
}
def price_for(model):
    m = model.lower()
    for k in PRICES:
        if k in m: return PRICES[k]
    return None

def parse_args():
    p = argparse.ArgumentParser(description="Claude Code token usage report")
    p.add_argument("--days", type=int, default=2, help="last N calendar days incl. today (default 2)")
    p.add_argument("--since", help="start date YYYY-MM-DD (overrides --days)")
    p.add_argument("--until", help="end date YYYY-MM-DD inclusive (default today)")
    p.add_argument("--by-session", action="store_true", help="add per-session breakdown")
    p.add_argument("--by-tool", action="store_true",
                   help="rank tools by the size of what they return into context")
    p.add_argument("--no-subagents", action="store_true", help="exclude subagents/ transcripts")
    p.add_argument("--cost", action="store_true", help="add rough API-equivalent cost estimate")
    p.add_argument("--project", help="only project dirs whose name contains this substring")
    p.add_argument("--root", default=os.path.expanduser("~/.claude/projects"),
                   help="projects log root (default ~/.claude/projects)")
    return p.parse_args()

def date_window(a):
    until = a.until or date.today().isoformat()
    if a.since:
        since = a.since
    else:
        since = (date.fromisoformat(until) - timedelta(days=a.days - 1)).isoformat()
    return since, until

def fmt(n): return f"{n:,}"

# Images are resized server-side before tokenizing, so a multi-MB base64 blob
# still costs ~1.6k tokens. Charge a flat equivalent instead of len(base64).
IMAGE_CHARS = 5600
CHARS_PER_TOKEN = 3.5  # rough, CJK-heavy text runs denser than English

def result_chars(block):
    """Approx. size a tool_result block contributes to context, in characters."""
    c = block.get("content")
    if isinstance(c, str):
        return len(c)
    if isinstance(c, list):
        n = 0
        for x in c:
            if not isinstance(x, dict):
                continue
            n += IMAGE_CHARS if x.get("type") == "image" else len(x.get("text") or "")
        return n
    return 0

def main():
    a = parse_args()
    since, until = date_window(a)
    files = glob.glob(os.path.join(a.root, "**", "*.jsonl"), recursive=True)

    agg = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0, 0]))   # [date][model]
    sess = defaultdict(lambda: [0, 0, 0, 0, 0])                       # [session]
    tool_name = {}   # tool_use_id -> tool name
    tool_size = {}   # tool_use_id -> result chars
    seen = set()
    cost = 0.0

    for f in files:
        norm = f.replace("\\", "/")
        if a.no_subagents and "/subagents/" in norm:
            continue
        if a.project:
            rel = norm[len(a.root.replace("\\", "/")):].lstrip("/")
            if a.project not in rel.split("/", 1)[0]:
                continue
        try:
            with open(f, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        o = json.loads(line)
                    except Exception:
                        continue
                    ts = o.get("timestamp", "")
                    if len(ts) < 10:
                        continue
                    d = ts[:10]
                    if d < since or d > until:
                        continue
                    msg = o.get("message") or {}
                    # Tool attribution must run before the usage gate: tool_result
                    # rows live on user messages, which carry no usage block.
                    if a.by_tool:
                        blocks = msg.get("content")
                        if isinstance(blocks, list):
                            for b in blocks:
                                if not isinstance(b, dict):
                                    continue
                                if b.get("type") == "tool_use" and b.get("id"):
                                    tool_name[b["id"]] = b.get("name", "?")
                                elif b.get("type") == "tool_result" and b.get("tool_use_id"):
                                    # id is unique; dedups parent/resumed duplicates
                                    tool_size.setdefault(b["tool_use_id"], result_chars(b))
                    u = msg.get("usage")
                    if not u:
                        continue
                    mid = msg.get("id")
                    key = (mid, u.get("output_tokens"))
                    if mid and key in seen:
                        continue
                    if mid:
                        seen.add(key)
                    model = msg.get("model", "?")
                    vals = (u.get("input_tokens", 0), u.get("output_tokens", 0),
                            u.get("cache_creation_input_tokens", 0),
                            u.get("cache_read_input_tokens", 0))
                    cell = agg[d][model]
                    for i in range(4):
                        cell[i] += vals[i]
                    cell[4] += 1
                    if a.by_session:
                        sid = o.get("sessionId") or os.path.basename(f)
                        sc = sess[sid]
                        for i in range(4):
                            sc[i] += vals[i]
                        sc[4] += 1
                    if a.cost:
                        pr = price_for(model)
                        if pr:
                            cost += sum(vals[i] * pr[i] for i in range(4)) / 1_000_000
        except Exception:
            continue

    # ASCII-only labels: Windows legacy consoles mojibake non-ASCII output.
    print(f"window: {since} ~ {until}  | root: {a.root}"
          f"{'  (subagents excluded)' if a.no_subagents else ''}")
    grand = [0, 0, 0, 0, 0]
    for d in sorted(agg):
        print(f"\n=== {d} ===")
        dt = [0, 0, 0, 0, 0]
        for model in sorted(agg[d]):
            c = agg[d][model]
            for i in range(5):
                dt[i] += c[i]; grand[i] += c[i]
            tot = c[0] + c[1] + c[2] + c[3]
            print(f"  {model:30s} msgs={c[4]:5d} in={fmt(c[0]):>11s} "
                  f"out={fmt(c[1]):>10s} cache_w={fmt(c[2]):>12s} "
                  f"cache_r={fmt(c[3]):>14s} total={fmt(tot):>14s}")
        tot = dt[0] + dt[1] + dt[2] + dt[3]
        print(f"  {'[day subtotal]':30s} msgs={dt[4]:5d} in={fmt(dt[0]):>11s} "
              f"out={fmt(dt[1]):>10s} cache_w={fmt(dt[2]):>12s} "
              f"cache_r={fmt(dt[3]):>14s} total={fmt(tot):>14s}")

    if a.by_session and sess:
        print("\n=== by session (Top 15 by total tokens) ===")
        ranked = sorted(sess.items(), key=lambda kv: -sum(kv[1][:4]))[:15]
        for sid, c in ranked:
            tot = c[0] + c[1] + c[2] + c[3]
            print(f"  {str(sid)[:40]:40s} msgs={c[4]:5d} total={fmt(tot):>14s}")

    if a.by_tool and tool_size:
        per = defaultdict(lambda: [0, 0, 0])   # name -> [calls, total_chars, max_chars]
        for tid, chars in tool_size.items():
            c = per[tool_name.get(tid, "(unknown)")]
            c[0] += 1
            c[1] += chars
            c[2] = max(c[2], chars)
        all_chars = sum(c[1] for c in per.values()) or 1
        print("\n=== by tool (result payload pulled into context, Top 20) ===")
        print("  tokens are approx: chars / %.1f; images charged flat ~%d tok"
              % (CHARS_PER_TOKEN, int(IMAGE_CHARS / CHARS_PER_TOKEN)))
        print(f"  {'tool':38s} {'calls':>6s} {'~tok total':>12s} {'~tok avg':>10s} "
              f"{'~tok max':>10s} {'share':>7s}")
        for name, c in sorted(per.items(), key=lambda kv: -kv[1][1])[:20]:
            tot_t = c[1] / CHARS_PER_TOKEN
            print(f"  {name[:38]:38s} {c[0]:6d} {fmt(int(tot_t)):>12s} "
                  f"{fmt(int(tot_t / c[0])):>10s} {fmt(int(c[2] / CHARS_PER_TOKEN)):>10s} "
                  f"{100 * c[1] / all_chars:6.1f}%")
        print(f"  {'[all tools]':38s} {sum(c[0] for c in per.values()):6d} "
              f"{fmt(int(all_chars / CHARS_PER_TOKEN)):>12s}")

    gt = grand[0] + grand[1] + grand[2] + grand[3]
    print(f"\n=== TOTAL ({since} ~ {until}) ===")
    print(f"  input (uncached): {fmt(grand[0])}")
    print(f"  output:           {fmt(grand[1])}")
    print(f"  cache write:      {fmt(grand[2])}")
    print(f"  cache read:       {fmt(grand[3])}")
    print(f"  messages:         {fmt(grand[4])}")
    print(f"  TOTAL tokens:     {fmt(gt)}")
    if a.cost:
        print(f"  API-equiv est.:   ${cost:,.2f}  (subscription is NOT billed this way; rough reference only)")

if __name__ == "__main__":
    main()
