#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""飞书/Lark 妙记 文字记录导出。

用法:
    python export_minutes.py <minutes_url> [outdir]
    python export_minutes.py selftest        # 纯函数自检

做什么:
    连接本机 127.0.0.1:9222 的调试 Edge（持久化配置目录，已登录飞书），
    走妙记 web 接口 (paragraph-ids / subtitles_v2 / speakers) 抓全量文字记录，
    组装成带时间戳+说话人的 .md 和 .txt，写到 outdir。

退出码:
    0  成功
    2  未登录 —— 调试 Edge 已把登录页显示出来，让用户在那个可见窗口扫码后重跑
    其它非 0  出错
"""
import json, sys, os, time, re, urllib.request, subprocess

PORT = 9222
USER_DATA = os.environ.get("EDGE_AUTOMATION_DIR", os.path.join(os.path.expanduser("~"), "edge-automation"))
EDGE_CANDIDATES = [
    os.environ.get("EDGE_BIN", ""),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

# ---------- 纯函数（可自检） ----------

def paragraph_text(paragraph):
    """一段 = 多个 sentence，每个 sentence = 多个 content 片段，拼接成整段文本。"""
    return "".join(
        "".join(c.get("content", "") for c in (s.get("contents") or []))
        for s in (paragraph.get("sentences") or [])
    )

def name_for(pid, maps):
    """pid -> 说话人名。优先 speaker_info_map，回落 device_owner_map，再回落占位名。"""
    p2s, info, dev, p2d = maps
    sid = p2s.get(pid)
    if sid and info.get(sid, {}).get("user_name"):
        return info[sid]["user_name"]
    did = p2d.get(pid)
    if did and dev.get(did, {}).get("user_name"):
        return dev[did]["user_name"]
    if sid and dev.get(sid, {}).get("user_name"):
        return dev[sid]["user_name"]
    return ("说话人" + sid) if sid else "未知"

def mmss(ms):
    s = int(ms) // 1000
    return f"{s // 60:02d}:{s % 60:02d}"

def safe_name(title):
    t = re.sub(r"\s*[-–—]\s*(飞书妙记|飞书|Feishu|Lark).*$", "", (title or "").strip())
    t = re.sub(r'[\\/:*?"<>|\r\n]+', "_", t).strip() or "飞书妙记文字记录"
    return t

# ---------- CDP ----------

def http_json(path, timeout=5):
    return json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=timeout))

def ensure_edge(url):
    try:
        http_json("/json/version"); return
    except Exception:
        pass
    exe = next((p for p in EDGE_CANDIDATES if p and os.path.exists(p)), None)
    if not exe:
        sys.exit("找不到 msedge.exe，设 EDGE_BIN 环境变量指向它")
    subprocess.Popen(
        [exe, f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
         f"--user-data-dir={USER_DATA}", "--no-first-run", "--no-default-browser-check",
         "--new-window", url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        time.sleep(1)
        try:
            http_json("/json/version"); return
        except Exception:
            pass
    sys.exit("调试 Edge 起不来")

class CDP:
    def __init__(self):
        import websocket  # websocket-client
        tabs = [t for t in http_json("/json/list") if t.get("type") == "page"]
        tab = next((t for t in tabs if "/minutes/" in t.get("url", "")), None) or (tabs[0] if tabs else http_json("/json/new"))
        self.ws = websocket.create_connection(tab["webSocketDebuggerUrl"], max_size=None, suppress_origin=True)
        self._id = 0
        self.cmd("Page.enable"); self.cmd("Runtime.enable")

    def cmd(self, method, params=None, timeout=120):
        self._id += 1; mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        self.ws.settimeout(timeout)
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == mid:
                return m

    def eval(self, expr, timeout=180):
        r = self.cmd("Runtime.evaluate", {"expression": expr, "awaitPromise": True, "returnByValue": True}, timeout=timeout)
        res = r.get("result", {})
        if res.get("exceptionDetails"):
            raise RuntimeError(json.dumps(res["exceptionDetails"], ensure_ascii=False)[:1000])
        return res.get("result", {}).get("value")

    def navigate(self, url):
        self.cmd("Page.navigate", {"url": url})
        for _ in range(30):
            time.sleep(1)
            loc = self.eval("JSON.stringify({host: location.hostname, path: location.pathname})")
            loc = json.loads(loc)
            if "accounts." in loc["host"] or "/login" in loc["path"]:
                return "login"
            if "/minutes/" in loc["path"]:
                time.sleep(2)  # 让 SPA 起来
                return "ok"
        return "timeout"

# 在页面里跑：拉全量段落 + 说话人，返回 rows
FETCH_JS = r"""
(async () => {
  const token = location.pathname.split('/').pop();
  const base = location.origin + '/minutes/api';
  const j = async (u) => (await fetch(u, {credentials:'include'})).json();
  const pidResp = await j(`${base}/subtitles/paragraph-ids?page_size=10000&page_num=0&object_token=${token}&language=zh_cn`);
  if (!pidResp || pidResp.code !== 0) return JSON.stringify({error:'no_access', raw: JSON.stringify(pidResp).slice(0,300)});
  const pidList = pidResp.data.list.map(x=>x.pid);
  const order = new Map(pidList.map((p,i)=>[p,i]));
  const total = pidList.length;
  const sp = await j(`${base}/speakers?size=10000&translate_lang=default&object_token=${token}&language=zh_cn`);
  const maps = {
    p2s: sp.data.paragraph_to_speaker || {},
    info: sp.data.speaker_info_map || {},
    dev: sp.data.device_owner_map || {},
    p2d: sp.data.paragraph_to_device_owner || {},
  };
  const paraText = new Map();
  let idx = 0, guard = 0;
  while (paraText.size < total && guard < total + 50) {
    guard++;
    const r = await j(`${base}/subtitles_v2?paragraph_id=${pidList[idx]}&size=100&translate_lang=default&is_fluent=false&filter_speaker=true&object_token=${token}&language=zh_cn`);
    const paras = (r.data && r.data.paragraphs) || [];
    if (!paras.length) { idx++; if (idx>=total) break; continue; }
    let maxIdx = idx;
    for (const p of paras) {
      paraText.set(p.pid, {t: p.start_time, para: p});
      if (order.has(p.pid)) maxIdx = Math.max(maxIdx, order.get(p.pid));
    }
    idx = maxIdx + 1;
    if (idx >= total) break;
  }
  const rows = pidList.map(pid => {
    const e = paraText.get(pid);
    return {pid, t: e ? Number(e.t) : 0, para: e ? e.para : {sentences:[]}};
  });
  return JSON.stringify({total, got: paraText.size, title: document.title, url: location.href, maps, rows});
})()
"""

def build_files(payload, outdir):
    maps = (payload["maps"]["p2s"], payload["maps"]["info"], payload["maps"]["dev"], payload["maps"]["p2d"])
    rows = []
    for r in payload["rows"]:
        txt = paragraph_text(r["para"]).strip()
        if not txt:
            continue
        rows.append((int(r["t"]), name_for(r["pid"], maps), txt))
    if not rows:
        sys.exit("没有取到任何文字记录（可能这条妙记没有转写文本）")
    title = safe_name(payload["title"])
    speakers = sorted({s for _, s, _ in rows})
    span = f"{mmss(min(t for t, _, _ in rows))} – {mmss(max(t for t, _, _ in rows))}"
    header = [
        f"# {title}  文字记录", "",
        "- 发言人：" + "、".join(speakers),
        f"- 时间跨度：{span}",
        "- 来源：" + payload["url"],
        f"- 共 {len(rows)} 段", "", "---", "",
    ]
    lines = [f"[{mmss(t)}] {sp}：{tx}" for t, sp, tx in rows]
    os.makedirs(outdir, exist_ok=True)
    md = os.path.join(outdir, f"{title}-文字记录.md")
    tx = os.path.join(outdir, f"{title}-文字记录.txt")
    open(md, "w", encoding="utf-8").write("\n".join(header + lines) + "\n")
    open(tx, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return md, tx, len(rows), speakers, span

# ---------- 自检 ----------

def selftest():
    para = {"sentences": [
        {"contents": [{"content": "喂，"}, {"content": "你好。"}]},
        {"contents": [{"content": "在吗？"}]},
    ]}
    assert paragraph_text(para) == "喂，你好。在吗？", paragraph_text(para)
    maps = ({"p1": "s1", "p2": "d1", "p3": "9"},
            {"s1": {"user_name": "张三"}},
            {"d1": {"user_name": "李四"}},
            {"p2": "d1"})
    assert name_for("p1", maps) == "张三"
    assert name_for("p2", maps) == "李四"          # 回落 device_owner
    assert name_for("p3", maps) == "说话人9"       # 无名 -> 占位
    assert name_for("pX", maps) == "未知"
    assert mmss(172645) == "02:52" and mmss(7135) == "00:07"
    assert safe_name("线上面试-刘浩 - 飞书妙记") == "线上面试-刘浩"
    print("selftest ok")

# ---------- main ----------

def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "selftest":
        selftest(); return
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    url = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    ensure_edge(url)
    cdp = CDP()
    state = cdp.navigate(url)
    if state == "login":
        print("LOGIN_REQUIRED")
        sys.exit(2)
    if state != "ok":
        sys.exit("导航到妙记页超时")
    payload = json.loads(cdp.eval(FETCH_JS))
    if payload.get("error"):
        if payload["error"] == "no_access":
            print("LOGIN_REQUIRED")  # 登录了但没这条妙记的访问权，也当作需人工处理
            sys.exit(2)
        sys.exit("抓取失败：" + json.dumps(payload, ensure_ascii=False)[:300])
    md, tx, n, speakers, span = build_files(payload, outdir)
    print(json.dumps({"ok": True, "md": md, "txt": tx, "paragraphs": n,
                      "speakers": speakers, "span": span, "title": payload["title"]},
                     ensure_ascii=False))

if __name__ == "__main__":
    main()
