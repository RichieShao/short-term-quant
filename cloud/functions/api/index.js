/**
 * 前端统一接口（Node）
 *  两种调用方式都支持：
 *   1) HTTP 访问服务（需在控制台建 /quant-api 路由）
 *   2) 前端 JS SDK 的 app.callFunction({name:'api'}) —— 免路由，需开启匿名登录
 *
 * action:
 *   latest            最新一日快照
 *   day&date=         指定日快照
 *   history&limit=    最近 N 日摘要
 *   stock&code=       个股异动体检（full=1 追加核心评分）
 *   refresh&date=     触发补跑并写库
 *   health            系统健康（最近任务运行记录 + 当日计算错误）
 *   watchlist         自选盯票池（GET 读取；POST/带 codes 写入）
 *   quotes&codes=     批量实时行情（服务端代拉，规避跨域）
 */
const cloudbase = require('@cloudbase/node-sdk')
const https = require('https')

/** HTTPS GET JSON（Node14 无 fetch）；东财主域风控时换 push2delay 备用域重试一次。 */
function getJSON(url) {
  const once = (u) => new Promise((resolve, reject) => {
    const req = https.get(u, { headers: { 'user-agent': 'quant-api' }, timeout: 15000 }, (res) => {
      let b = ''
      res.setEncoding('utf-8')
      res.on('data', (c) => { b += c })
      res.on('end', () => { try { resolve(JSON.parse(b)) } catch (e) { reject(e) } })
    })
    req.on('error', reject)
    req.on('timeout', () => req.destroy(new Error('timeout')))
  })
  return once(url).catch((e) => {
    if (url.includes('push2.eastmoney.com')) {
      return once(url.replace('push2.eastmoney.com', 'push2delay.eastmoney.com'))
    }
    throw e
  })
}

// 懒初始化：避免模块加载期 init 失败导致整函数无法响应（表现为 HTTP 200 空 body）
let _app = null
function getApp() {
  if (!_app) _app = cloudbase.init({ env: cloudbase.SYMBOL_CURRENT_ENV })
  return _app
}
function getDb() {
  return getApp().database()
}

const CORS = {
  'Content-Type': 'application/json; charset=utf-8',
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
}

function parseParams(event) {
  const q = Object.assign({}, event.queryStringParameters || {})
  if (event.body) {
    try {
      Object.assign(q, typeof event.body === 'string' ? JSON.parse(event.body) : event.body)
    } catch (e) { /* 非 JSON body 忽略 */ }
  }
  if (event.action) q.action = event.action
  return q
}

exports.main = async (event = {}) => {
  const isHttp = Boolean(event.httpMethod || event.queryStringParameters)
  const okResp = (data) =>
    isHttp ? { statusCode: 200, headers: CORS, body: JSON.stringify(data) } : data

  try {
    if (event.httpMethod === 'OPTIONS') {
      return { statusCode: 204, headers: CORS, body: '' }
    }

    const q = parseParams(event)
    const action = q.action || 'latest'
    const db = getDb()

    if (action === 'latest' || action === 'day') {
      let data
      if (action === 'day' && q.date) {
        const r = await db.collection('daily').doc(String(q.date)).get()
        data = (r.data && r.data[0]) || null
      } else {
        const r = await db.collection('daily').orderBy('date', 'desc').limit(1).get()
        data = (r.data && r.data[0]) || null
      }
      if (!data) return okResp({ ok: false, error: '暂无快照数据，请先触发 daily_job' })
      return okResp({ ok: true, snapshot: data })
    }

    if (action === 'history') {
      const limit = Math.min(Number(q.limit) || 10, 60)
      const r = await db.collection('daily').orderBy('date', 'desc').limit(limit).get()
      const list = (r.data || []).map((d) => ({
        date: d.date,
        heat: d.sentiment && d.sentiment.heat,
        band: d.sentiment && d.sentiment.band,
        stage: d.cycle && d.cycle.stage,
        lu: d.sentiment && d.sentiment.lu,
      }))
      return okResp({ ok: true, list })
    }

    if (action === 'stock') {
      const code = String(q.code || '').trim()
      if (!code) return okResp({ ok: false, error: '缺少 code' })
      const res = await getApp().callFunction({
        name: 'snapshot_py',
        data: { action: 'stock', code, full: String(q.full || '') === '1' },
      }, { timeout: 60000 })
      return okResp((res && res.result) || { ok: false, error: '计算函数无返回' })
    }

    if (action === 'refresh') {
      const res = await getApp().callFunction({
        name: 'snapshot_py',
        data: { mode: 'force', date: q.date },
      }, { timeout: 110000 }) // 放宽到 110s：涨停爆发日全量快照 20-45s，再叠加形态资金流/龙虎榜，SDK 默认 15s 必超时
      const r = (res && res.result) || {}
      if (r.ok && r.snapshot) {
        r.snapshot._updatedAt = Date.now()
        await db.collection('daily').doc(String(r.date)).set(r.snapshot)
      }
      return okResp(r)
    }

    if (action === 'themelife') {
      // 题材生命期聚合（每日由 daily_job 增量维护）→ 按峰值取 TOP N
      const r = await db.collection('themelife').doc('agg').get()
      const agg = (r.data && r.data[0]) || null
      if (!agg || !agg.themes) {
        return okResp({ ok: false, error: '题材生命期基线未就绪（等待每日任务聚合或先导入种子）' })
      }
      const n = Math.min(Number(q.n) || 15, 30)
      const top = Object.entries(agg.themes)
        .map(([name, a]) => ({
          name,
          peak: a.peak || 0,
          days: a.days || 0,
          first: a.first || '',
          last: a.last || '',
        }))
        .sort((x, y) => y.peak - x.peak || y.days - x.days)
        .slice(0, n)
      return okResp({ ok: true, last: agg.last, total_themes: Object.keys(agg.themes).length, top })
    }

    if (action === 'calib') {
      // 滚动校准自评（复盘页三卡数据源）：daily_job 每交易日随快照增量维护
      const r = await db.collection('calib').doc('agg').get()
      const agg = (r.data && r.data[0]) || null
      if (!agg || !agg.window) {
        return okResp({ ok: false, error: '校准聚合未就绪（等待每日任务或先导入种子）' })
      }
      return okResp({
        ok: true,
        window: agg.window,
        stages: agg.stages || {},
        hits: agg.hits || {},
        last_stage: agg.last_stage,
        last_heat: agg.last_heat,
        last: agg.last,
        // 待确认顶点数（旧版本 agg 无此字段时为 null，前端回退为不展示）
        pending_climax: (agg.pending_climax === undefined ? null : agg.pending_climax),
      })
    }

    if (action === 'coretrack') {
      // 核心池次日表现追踪：S/A/B/C 各档累计晋级率/次日平均涨幅（每交易日自动回填）
      const r = await db.collection('coretrack').doc('agg').get()
      const agg = (r.data && r.data[0]) || null
      if (!agg || !agg.grades) {
        return okResp({ ok: false, error: '胜率统计未就绪（每日回填自动累计，需连续运行数个交易日）' })
      }
      return okResp({
        ok: true,
        grades: agg.grades,
        overall: agg.overall || null,
        settled_days: agg.settled_days || 0,
        last: agg.last || '',
        // 历史回放（实操口径 + 周期分层）：本地回放脚本产出后回写，可随时重跑刷新
        replay: agg.replay || null,
      })
    }

    if (action === 'health') {
      // 系统健康：最近 N 次任务运行记录 + 当日快照的计算错误（无记录时诚实说明）
      const n = Math.min(Number(q.n) || 10, 30)
      let runs = []
      try {
        const r = await db.collection('job_runs').orderBy('ts', 'desc').limit(n).get()
        runs = r.data || []
      } catch (e) {
        runs = []
      }
      let lastErrors = null
      let lastDate = null
      try {
        const s = await db.collection('daily').orderBy('date', 'desc').limit(1).get()
        const s0 = (s.data && s.data[0]) || null
        if (s0) {
          lastDate = s0.date
          lastErrors = s0.errors || null
        }
      } catch (e) { /* 忽略 */ }
      const bad = runs.filter((r) => !r.ok)
      return okResp({
        ok: true, runs, last_date: lastDate, last_errors: lastErrors,
        fail_count: bad.length, last_fail: bad[0] || null,
      })
    }

    if (action === 'watchlist') {
      // 自选盯票池：单文档 _id='default' 存 codes（无登录态，多设备共享一份）
      try { await db.createCollection('watchlist') } catch (e) { /* 已存在 */ }
      const incoming = Array.isArray(q.codes)
        ? q.codes
        : (typeof q.codes === 'string' && q.codes.length ? q.codes.split(',') : null)
      if (incoming) {
        const doc = {
          codes: incoming.map((x) => String(x).trim()).filter(Boolean).slice(0, 30),
          updated_at: Date.now(),
        }
        delete doc._id
        await db.collection('watchlist').doc('default').set(doc)
        return okResp({ ok: true, codes: doc.codes })
      }
      const r = await db.collection('watchlist').doc('default').get()
      const w = (r.data && r.data[0]) || null
      return okResp({ ok: true, codes: (w && w.codes) || [] })
    }

    if (action === 'quotes') {
      // 批量实时行情：服务端代拉东财 ulist（前端受限跨域，且主域风控有备用域）
      const codes = String(q.codes || '').split(',').map((x) => x.trim())
        .filter(Boolean).slice(0, 30)
      if (!codes.length) return okResp({ ok: true, list: [] })
      const secids = codes.map((c) => {
        const m = /^(sh|sz|bj)?(\d{6})$/.exec(c)
        if (!m) return null
        const pre = m[1] || (/^(6|9)/.test(m[2]) ? 'sh' : 'sz')
        return (pre === 'sh' ? '1.' : '0.') + m[2]
      }).filter(Boolean)
      if (!secids.length) return okResp({ ok: true, list: [] })
      const url = 'https://push2.eastmoney.com/api/qt/ulist.np/get'
        + `?secids=${encodeURIComponent(secids.join(','))}`
        + '&fields=f2,f3,f12,f13,f14&fltt=2&invt=2&ut=fa5fd1943c7b386f172d6893dbfba10b'
      const txt = await getJSON(url)
      const arr = ((txt && txt.data) || {}).diff || []
      const list = arr.map((x) => ({
        code: (x.f13 === 1 ? 'sh' : 'sz') + String(x.f12),
        name: x.f14,
        price: typeof x.f2 === 'number' ? x.f2 : null,
        pct: typeof x.f3 === 'number' ? x.f3 : null,
      }))
      return okResp({ ok: true, list })
    }

    return okResp({ ok: false, error: `未知 action: ${action}` })
  } catch (e) {
    // 任何异常都返回 JSON 错误体，避免 HTTP 200 空 body（前端会误判为数据加载失败）
    const msg = (e && (e.message || e.stack)) || String(e)
    console.error('[api] error:', msg)
    return okResp({ ok: false, error: msg })
  }
}
