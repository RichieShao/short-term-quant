/**
 * 端到端冒烟测试（无浏览器环境）
 *
 * 主通道：HTTP 访问路由（免鉴权）
 *   https://<env>.service.tcloudbase.com/quant-api
 *
 * 用法：node test/e2e.mjs
 */
const ENV_ID = 'richieshao-1980-d9f5588r8f7850a1'
const API = `https://${ENV_ID}.service.tcloudbase.com/quant-api`

async function get(action, params = {}) {
  const usp = new URLSearchParams({ action, ...params })
  const r = await fetch(`${API}?${usp}`, { cache: 'no-store' })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

function assert(cond, msg) {
  if (!cond) {
    console.error('   ✗', msg)
    process.exit(1)
  }
  console.log('   ✓', msg)
}

console.log('— 1. latest（最新快照）')
const latest = await get('latest')
assert(latest.ok, 'ok')
const s = latest.snapshot
assert(s && s.date, `date = ${s && s.date}`)
assert(s.sentiment, `heat = ${s.sentiment && s.sentiment.heat} / ${s.sentiment && s.sentiment.band}`)
assert(s.cycle, `stage = ${s.cycle && s.cycle.stage}`)
assert((s.cores || []).length >= 0, `cores = ${(s.cores || []).length}`)
assert((s.themes || []).length >= 0, `themes = ${(s.themes || []).length}`)
assert(s.generated_at, `generated_at = ${s.generated_at}（应为北京时间）`)

console.log('— 2. history（历史序列）')
const his = await get('history', { limit: 5 })
assert(his.ok && Array.isArray(his.list), `list = ${(his.list || []).length} 条`)
console.log('     ', (his.list || []).map((d) => `${d.date}:${d.heat}/${d.stage}`).join('  '))

console.log('— 3. stock（个股异动体检）')
const st = await get('stock', { code: '601086', full: '1' })
assert(st.ok, `name = ${st.name}`)
assert(st.dev, `dev_10d = ${st.dev && st.dev.dev_10d}, risk = ${st.dev && st.dev.risk_level}`)
assert((st.klines || []).length > 0, `klines = ${(st.klines || []).length} 根`)

console.log('— 4. themelife（题材生命期聚合）')
const tl = await get('themelife')
assert(tl.ok, `ok / last = ${tl.last}`)
assert((tl.top || []).length > 0, `top = ${(tl.top || []).length} 条`)
assert(tl.top[0].peak >= 20, `top1 = ${tl.top[0].name} peak=${tl.top[0].peak}`)
console.log('     ', (tl.top || []).slice(0, 5).map((t) => `${t.name}:${t.peak}峰/${t.days}日`).join('  '))

console.log('— 5. calib（滚动校准自评）')
const cb = await get('calib')
assert(cb.ok, `ok / last = ${cb.last}`)
assert(cb.window && cb.window.days >= 254, `window = ${cb.window && cb.window.days} 日 (${cb.window && cb.window.from}~${cb.window && cb.window.to})`)
assert(cb.stages && Object.keys(cb.stages).length === 5, `stages = ${JSON.stringify(cb.stages)}`)
assert(cb.hits && cb.hits.climax_total > 0, `hits = 顶点 ${cb.hits && cb.hits.strict}/${cb.hits && cb.hits.climax_total}(严) ${cb.hits && cb.hits.loose}/${cb.hits && cb.hits.climax_total}(宽) 退潮 ${cb.hits && cb.hits.retreat_hit}/${cb.hits && cb.hits.retreat_total}`)
console.log('     ', `last_stage = ${cb.last_stage}, last_heat = ${cb.last_heat}`)

console.log('— 6. coretrack（核心池次日表现）')
const ctr = await get('coretrack')
assert(ctr.ok, `ok / settled_days = ${ctr.settled_days}`)
assert(ctr.overall && ctr.overall.n > 0, `overall = n ${ctr.overall && ctr.overall.n}, 晋级率 ${ctr.overall && ctr.overall.adv_rate}%`)
console.log('     ', `各档 ${Object.entries(ctr.grades || {}).filter(([, v]) => v && v.n).map(([k, v]) => `${k}:${v.n}只/晋级${v.adv_rate}%`).join('  ')}`)

console.log('\n✓ 端到端通道验证通过')
