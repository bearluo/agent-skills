// Globalping 全球对比多个域名：node gp-compare.js <path> <host1> [host2 ...]
// 环境变量：LOC="US:8,GB:3,DE:2,IN:3,SG:2,JP:2,BR:2,AU:2"  ROUNDS=3  GLOBALPING_TOKEN=（可选，提高额度）
const [path, ...hosts] = process.argv.slice(2);
if (!path || !hosts.length) { console.error('usage: node gp-compare.js <path> <host...>'); process.exit(1); }
const LOC = (process.env.LOC || 'US:8,GB:3,DE:2,IN:3,SG:2,JP:2,BR:2,AU:2').split(',').map(s => { const [country, n] = s.split(':'); return { country, limit: +n }; });
const ROUNDS = +(process.env.ROUNDS || 3);
const H = { 'content-type': 'application/json', ...(process.env.GLOBALPING_TOKEN ? { authorization: 'Bearer ' + process.env.GLOBALPING_TOKEN } : {}) };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const med = a => { a = a.filter(x => x != null).sort((x, y) => x - y); return a.length ? a[Math.floor((a.length - 1) / 2)] : '-'; };
const post = t => fetch('https://api.globalping.io/v1/measurements', { method: 'POST', headers: H, body: JSON.stringify({ type: 'http', target: t, locations: LOC, measurementOptions: { protocol: 'HTTPS', request: { method: 'GET', path } } }) }).then(r => r.json());
const get = async id => { for (;;) { const j = await (await fetch('https://api.globalping.io/v1/measurements/' + id, { headers: H })).json(); if (j.status !== 'in-progress') return j; await sleep(1000); } };
(async () => {
  const R = {};
  for (let round = 0; round < ROUNDS; round++) {
    const ms = await Promise.all(hosts.map(post));
    for (let i = 0; i < hosts.length; i++) {
      if (!ms[i].id) { console.error('round', round + 1, hosts[i], JSON.stringify(ms[i].error || ms[i])); continue; }
      for (const r of (await get(ms[i].id)).results) {
        const x = r.result, t = x.timings || {}, h = x.headers || {};
        if (!x.statusCode || x.statusCode >= 500) continue;
        ((R[r.probe.country] ??= {})[hosts[i]] ??= []).push({ ip: x.resolvedAddress, pop: h['x-amz-cf-pop'], tcp: t.tcp, tls: t.tls, w: t.firstByte, tot: t.total });
      }
    }
    await sleep(3000);
  }
  // firstByte = TLS 完成到首字节 = 「服务端等待」（含 1×客户端RTT + 回源 + 源站处理）
  console.log('国家 | 域名 | 样本 | IP@POP | tcp | tls | 服务端等待 | total');
  for (const k of Object.keys(R)) for (const h of hosts) {
    const a = R[k][h] || []; if (!a.length) continue;
    const ips = [...new Set(a.map(x => x.pop ? x.ip + '@' + x.pop : x.ip))].slice(0, 4).join(',');
    console.log(k, '|', h, '|', a.length, '|', ips, '|', med(a.map(x => x.tcp)), '|', med(a.map(x => x.tls)), '|', med(a.map(x => x.w)), '|', med(a.map(x => x.tot)));
  }
})();
