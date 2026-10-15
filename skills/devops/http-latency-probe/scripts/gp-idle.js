// 同一批 Globalping 探测点按不同间隔连发，看「边缘节点 → 源站」回源连接的空闲窗口
// node gp-idle.js <host> <path>
// 环境变量：LOC="BR:2,AU:2,GB:2,JP:2,DE:2"  GAPS="0,0,3,10,30,90"（每发之前等几秒）  GLOBALPING_TOKEN=
// 读法：某个间隔之后 firstByte 跳回首发水平 → 回源连接在这个间隔内被关掉了
const [host, path] = process.argv.slice(2);
if (!host || !path) { console.error('usage: node gp-idle.js <host> <path>'); process.exit(1); }
const LOC = (process.env.LOC || 'BR:2,AU:2,GB:2,JP:2,DE:2').split(',').map(s => { const [country, n] = s.split(':'); return { country, limit: +n }; });
const GAPS = (process.env.GAPS || '0,0,3,10,30,90').split(',').map(Number);
const H = { 'content-type': 'application/json', ...(process.env.GLOBALPING_TOKEN ? { authorization: 'Bearer ' + process.env.GLOBALPING_TOKEN } : {}) };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const post = loc => fetch('https://api.globalping.io/v1/measurements', { method: 'POST', headers: H, body: JSON.stringify({ type: 'http', target: host, locations: loc, measurementOptions: { protocol: 'HTTPS', request: { method: 'GET', path } } }) }).then(r => r.json());
const get = async id => { for (;;) { const j = await (await fetch('https://api.globalping.io/v1/measurements/' + id, { headers: H })).json(); if (j.status !== 'in-progress') return j; await sleep(500); } };
(async () => {
  let first; const rows = {};
  for (const [i, gap] of GAPS.entries()) {
    await sleep(gap * 1000);
    const m = await post(first || LOC);   // locations 传上一次的 measurement id = 复用同一批探测点
    if (!m.id) { console.error(`第${i + 1}发(+${gap}s)`, JSON.stringify(m.error || m)); break; }
    first ??= m.id;
    for (const r of (await get(m.id)).results) {
      const x = r.result, t = x.timings || {}, h = x.headers || {};
      (rows[r.probe.country + '-' + r.probe.city] ??= []).push(`${i ? '+' + gap + 's' : '首发'}:${t.firstByte}${h['x-amz-cf-pop'] ? '@' + h['x-amz-cf-pop'] : ''}${/hit/i.test(h['x-cache'] || '') ? '(HIT)' : ''}`);
    }
  }
  for (const k in rows) console.log(k, '|', rows[k].join('  '));
})();
