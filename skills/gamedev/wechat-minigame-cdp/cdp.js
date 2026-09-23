#!/usr/bin/env node
// 通过 CDP 观测微信开发者工具里跑着的小游戏。零依赖(Node >= 22 有全局 WebSocket / fetch)。
//
//   node cdp.js --targets                 列出所有 CDP target(排查用)
//   node cdp.js                           跟读控制台 15s
//   node cdp.js --seconds 60 --out log.txt
//   node cdp.js --grep "ERROR|CoreKit"    只留匹配行(心跳类日志很吵,建议常用)
//   node cdp.js --eval "typeof GODOTSDK"  在【游戏上下文】求值(GODOTSDK 在这)
//   node cdp.js --eval "document.title" --ctx page   改在【页面上下文】求值
//   node cdp.js --dom                     打印执行上下文 / canvas / iframe 清单
//   node cdp.js --shot out.png            截图
//   --port 9222  --target gamePage        可覆盖默认值
//
// ⚠️ 输出走 PowerShell 控制台会被按 GBK 转码成乱码 —— 中文日志请加 --out <文件>(Node 直接写 UTF-8),
//    或先 [Console]::OutputEncoding=[Text.Encoding]::UTF8。

const fs = require('fs')

const argv = process.argv.slice(2)
const flag = (n, d) => {
  const i = argv.indexOf('--' + n)
  if (i < 0) return d
  return argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : true
}
const has = (n) => argv.includes('--' + n)

const PORT = Number(flag('port', 9222))
const MATCH = String(flag('target', 'gamePage'))
const SECONDS = Number(flag('seconds', 15))
const GREP = flag('grep', null)
const EVAL = flag('eval', null)
const SHOT = flag('shot', null)
const CTX = String(flag('ctx', 'game'))       // game | page
const OUT = flag('out', null)

// --out 时同时落 UTF-8 文件,绕开 PowerShell 控制台转码
const sink = OUT ? fs.createWriteStream(String(OUT), { encoding: 'utf8' }) : null
const say = (s) => { if (sink) sink.write(s + '\n'); else console.log(s) }

const die = (m) => { console.error(m); process.exit(1) }

const WAIT = flag('wait', null)   // 轮询等 target 出现(秒);抓启动日志必须先挂上再启动

const fetchTargets = async () => {
  try { return await (await fetch(`http://127.0.0.1:${PORT}/json`)).json() }
  catch (e) { die(`连不上 CDP :${PORT} —— 先跑 launch.ps1 用调试端口重启开发者工具。(${e.message})`) }
}

;(async () => {
  let list = await fetchTargets()

  if (has('targets')) {
    console.log(`targets = ${list.length}`)
    for (const t of list) console.log(` [${t.type}] ${t.url.slice(0, 120)}`)
    return
  }

  let t = list.find((x) => x.url.includes(MATCH))

  // --wait:小游戏 target 只在模拟器跑着时存在,重启工程时会换端口。
  // 200ms 一轮抢在引擎 wasm 加载完之前接上,否则收不到启动日志(CDP 不回放历史)。
  if (!t && WAIT) {
    const deadline = Date.now() + Number(WAIT) * 1000
    process.stderr.write(`等 "${MATCH}" target 出现(最多 ${WAIT}s)...\n`)
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 200))
      list = await fetchTargets()
      t = list.find((x) => x.url.includes(MATCH))
      if (t) break
    }
  }

  if (!t) {
    console.log(`没找到含 "${MATCH}" 的 target。小游戏 target 只在【模拟器跑着】时存在 —— 去 IDE 点一下编译/运行,或加 --wait <秒> 边等边接。`)
    for (const x of list) console.log(` [${x.type}] ${x.url.slice(0, 110)}`)
    process.exit(2)
  }
  say(`target: ${t.url}`)

  const ws = new WebSocket(t.webSocketDebuggerUrl)
  let id = 0
  let tailing = false                          // 只有跟读模式才打印控制台事件
  const pending = new Map()
  const ctxs = []
  const send = (method, params = {}, ms = 20000) => new Promise((res, rej) => {
    const i = ++id
    pending.set(i, { res, rej })
    ws.send(JSON.stringify({ id: i, method, params }))
    setTimeout(() => { if (pending.delete(i)) rej(new Error('TIMEOUT ' + method)) }, ms)
  })

  const val = (a) => (a.value !== undefined ? a.value : (a.description || a.unserializableValue || a.type))
  const emit = (line) => { if (tailing && (!GREP || new RegExp(GREP, 'i').test(line))) say(line) }

  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data)
    if (m.id && pending.has(m.id)) {
      const p = pending.get(m.id); pending.delete(m.id)
      return m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result)
    }
    if (m.method === 'Runtime.executionContextCreated') ctxs.push(m.params.context)
    if (m.method === 'Runtime.consoleAPICalled') emit(`  ${m.params.type}: ${m.params.args.map(val).join(' ')}`)
    if (m.method === 'Runtime.exceptionThrown') {
      const d = m.params.exceptionDetails
      emit(`  !! ${d.text} ${d.exception ? d.exception.description : ''}`)
    }
    if (m.method === 'Log.entryAdded') emit(`  [${m.params.entry.level}] ${m.params.entry.text}`)
  }

  const MODE = has('dom') ? 'dom' : (EVAL ? 'eval' : (SHOT ? 'shot' : 'tail'))

  await new Promise((r) => { ws.onopen = r })
  await send('Runtime.enable')
  await send('Log.enable')
  // 跟读模式立刻开收:CDP 不回放历史,晚一秒就少一秒启动日志
  if (MODE === 'tail') {
    tailing = true
    say(`--- 跟读控制台 ${SECONDS}s${GREP ? ` (grep: ${GREP})` : ''} ---`)
    await new Promise((r) => setTimeout(r, SECONDS * 1000))
    say('--- 结束 ---')
    if (sink) { sink.end(); console.log(`日志写到 ${OUT}`) }
    setTimeout(() => process.exit(0), 200)
    return
  }
  await new Promise((r) => setTimeout(r, 1200))   // 等 executionContextCreated 到齐

  // 游戏真身在 gameContext 那个上下文(GODOTSDK 在这);gamePage.html 是外壳
  const pick = (kind) => {
    const c = ctxs.find((x) => kind === 'game' ? /gameContext/.test(x.origin + x.name) : /gamePage/.test(x.origin + x.name))
    return c || ctxs[kind === 'game' ? ctxs.length - 1 : 0]
  }
  const ev1 = async (expr, contextId) => {
    const r = await send('Runtime.evaluate', {
      expression: expr, returnByValue: true, awaitPromise: true,
      ...(contextId ? { contextId } : {}),
    })
    if (r.exceptionDetails) {
      const d = r.exceptionDetails
      return { __error: (d.exception && (d.exception.description || d.exception.value)) || d.text }
    }
    return r.result.value
  }

  // origin 对两个上下文是同一个,靠 url 分辨更准
  for (const c of ctxs) {
    c.__url = await ev1('location.href', c.id).catch(() => '?')
  }
  const byUrl = (kind) => ctxs.find((c) => kind === 'game'
    ? /gameContext/.test(String(c.__url)) : /gamePage/.test(String(c.__url)))

  if (has('dom')) {
    say('=== execution contexts ===')
    for (const c of ctxs) say(` id=${c.id} url=${c.__url}`)
    for (const kind of ['page', 'game']) {
      const c = byUrl(kind)
      if (!c) { say(`=== ${kind}: 没找到 ===`); continue }
      say(`=== ${kind} (ctx ${c.id}) ===`)
      say(JSON.stringify(await ev1(`(() => {
        const out = { godot: typeof GODOTSDK, wx: typeof wx, url: location.href };
        try {
          out.canvases = [...document.querySelectorAll('canvas')].map(c => ({ w: c.width, h: c.height, cls: c.className }));
          out.frames = [...document.querySelectorAll('iframe,webview')].map(f => f.tagName + ':' + (f.src || '').slice(0, 70));
          out.bodyBg = document.body ? getComputedStyle(document.body).backgroundColor : null;
        } catch (e) { out.domErr = String(e) }
        try { out.wxCanvas = typeof wx !== 'undefined' && !!wx.createCanvas } catch (e) {}
        return out;
      })()`, c.id), null, 1))
    }
    process.exit(0)
  }

  if (EVAL) {
    const c = byUrl(CTX)
    say(`ctx: ${c ? c.__url : '(默认)'}`)
    say('=> ' + JSON.stringify(await ev1(String(EVAL), c && c.id), null, 1))
    process.exit(0)
  }

  if (SHOT) {
    const r = await send('Page.captureScreenshot', { format: 'png' }, 30000)
    const buf = Buffer.from(r.data, 'base64')
    fs.writeFileSync(String(SHOT), buf)
    console.log(`screenshot -> ${SHOT} (${buf.length} bytes)`)
    process.exit(0)
  }

})()
