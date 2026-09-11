/**
 * 每日快照定时任务（Node）
 *  定时触发器：交易日 16:05（daily_1605）→ 调 Python 计算 → 写入数据库 daily 集合（_id = 日期）
 *  兜底触发器：交易日 16:40（daily_1640）→ 幂等重跑，覆盖 16:05 失败 / 涨停数据延迟修正的情形
 *  非交易日由 snapshot_py 内部判定后 skip。
 *  计算与写库均带 3 次重试（指数退避），失败详情打印到函数日志。
 */
const cloudbase = require('@cloudbase/node-sdk')

const app = cloudbase.init({ env: cloudbase.SYMBOL_CURRENT_ENV })
const db = app.database()

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

/** 目标交易日（北京时间；force 补跑历史日期时用 event.date）。 */
function rDateOf(event) {
  const d = event && event.date
  if (d && /^\d{4}-\d{2}-\d{2}$/.test(String(d))) return String(d)
  return new Date(Date.now() + 8 * 3600 * 1000).toISOString().slice(0, 10)
}

/** 近 N 日核心池 code 集合（供"连续在池天数"；失败返回 null 不阻断）。 */
async function loadHistCores(limit = 10) {
  try {
    const r = await db.collection('daily').orderBy('date', 'desc').limit(limit).get()
    return (r.data || [])
      .filter((d) => Array.isArray(d.cores) && d.cores.length)
      .map((d) => ({ d: d.date, codes: d.cores.map((c) => c.code) }))
      .sort((a, b) => String(a.d).localeCompare(String(b.d)))
  } catch (e) {
    console.error('[daily_job] 历史核心池读取失败（在池天数本次跳过）:', e.message)
    return null
  }
}

/** 调 snapshot_py 算快照；数据源瞬时抖动时重试（非交易日 skip 不重试）。 */
async function computeSnapshot(event, maxTry = 3) {
  let lastErr = null
  for (let i = 1; i <= maxTry; i++) {
    try {
      const res = await app.callFunction({
        name: 'snapshot_py',
        data: {
          mode: event.mode || 'auto', date: event.date, cores: true,
          // 滚动校准：全量四元组 + 冻结 lu_min（无基线时不传，快照侧跳过）
          calib_rows: event.calib_rows, calib_lu_min: event.calib_lu_min,
          // 温度计历史分位：近 N 日 heat（样本不足由后端诚实降级）
          hist_heats: event.hist_heats,
          // 核心池：待回填的昨日记录 + 近 N 日在池 code 集合
          prev_cores: event.prev_cores,
          hist_cores: event.hist_cores,
        },
      }, { timeout: 60000 }) // SDK 默认 15s；涨停爆发日(93家)快照约 20-45s，必须放宽

      const r = res && res.result
      if (!r) lastErr = 'snapshot_py 返回为空'
      else if (r.skipped) return r // 非交易日，无需重试
      else if (r.ok) return r
      else lastErr = r.error || '计算失败'
    } catch (e) {
      lastErr = `callFunction 失败: ${e.message}`
    }
    console.error(`[daily_job] 第 ${i}/${maxTry} 次计算失败: ${lastErr}`)
    if (i < maxTry) await sleep(3000 * i)
  }
  return { ok: false, error: lastErr, tries: maxTry }
}

/** 写库，失败时重试。 */
async function saveSnapshot(date, snap, maxTry = 3) {
  let lastErr = null
  for (let i = 1; i <= maxTry; i++) {
    try {
      await db.collection('daily').doc(String(date)).set(snap)
      return null
    } catch (e) {
      lastErr = e.message
      console.error(`[daily_job] 第 ${i}/${maxTry} 次写库失败: ${lastErr}`)
      if (i < maxTry) await sleep(2000 * i)
    }
  }
  return lastErr
}

/**
 * 题材生命期增量聚合（themelife.agg）。
 * 幂等：仅当聚合 last < 当日日期才并入（同一交易日重复触发不重复累计）；
 * 无聚合基线(首次)时跳过并告警 —— 需先导入 seed 基线（seed_tl 云函数）。
 */
async function updateThemeLife(date, thsTags, maxTry = 3) {
  if (!thsTags || !thsTags.date || !thsTags.counts) return null
  if (String(thsTags.date) !== String(date)) return null // 只并入快照当日
  const counts = thsTags.counts || {}
  if (!Object.keys(counts).length) return null
  let lastErr = null
  for (let i = 1; i <= maxTry; i++) {
    try {
      const aggRef = db.collection('themelife').doc('agg')
      const cur = await aggRef.get()
      let agg = (cur.data && cur.data[0]) || null
      if (!agg || !agg.themes) {
        console.error('[daily_job] themelife agg 不存在，跳过增量（需先导入 seed 基线）')
        return { ok: false, skipped: 'no-baseline' }
      }
      if (agg.last >= String(date)) return { ok: true, skipped: 'dup' } // 同日幂等
      for (const [tag, c] of Object.entries(counts)) {
        const a = agg.themes[tag] || { days: 0, peak: 0, first: String(date), last: String(date) }
        a.days = (a.days || 0) + 1
        a.peak = Math.max(a.peak || 0, c)
        if (!a.first || String(date) < a.first) a.first = String(date)
        if (!a.last || String(date) > a.last) a.last = String(date)
        agg.themes[tag] = a
      }
      agg.last = String(date)
      agg.updated_at = Date.now()
      // CloudBase 不允许回写 _id（get 返回的 doc 自带），set 前剥离
      delete agg._id
      await aggRef.set(agg)
      return { ok: true }
    } catch (e) {
      lastErr = e.message
      console.error(`[daily_job] 第 ${i}/${maxTry} 次题材聚合失败: ${lastErr}`)
      if (i < maxTry) await sleep(2000 * i)
    }
  }
  return { ok: false, error: lastErr }
}

/**
 * 滚动校准（P4）：读 calib.series（历史四元组 + 冻结 lu_min）→ 随快照事件传给
 * snapshot_py 重放（追加当日三元组）→ 回写 series（含今日）与 agg（自评结果）。
 * 幂等：series 末行 >= 当日 → dup 跳过（同日多次触发安全，重复计算逐位一致）；
 * 无基线时跳过并告警 —— 需先跑 seed_calib 云函数导入种子。
 */
async function updateCalib(date, calibRes, maxTry = 3) {
  if (!calibRes) return { ok: false, skipped: 'no-input' }
  if (!calibRes.ok) return { ok: false, skipped: calibRes.error || 'snapshot_py calib 失败' }
  let lastErr = null
  for (let i = 1; i <= maxTry; i++) {
    try {
      const ref = db.collection('calib')
      const sr = await ref.doc('series').get()
      const series = (sr.data && sr.data[0]) || null
      if (!series || !Array.isArray(series.rows) || !series.rows.length) {
        return { ok: false, skipped: 'no-baseline' }
      }
      const rows = series.rows.filter((r) => String(r.d || '') < String(date))
      if (calibRes.today_row) rows.push(calibRes.today_row)
      rows.sort((a, b) => String(a.d).localeCompare(String(b.d)))

      // 回写 series（含今日三元组）
      const sdoc = { rows, lu_min: series.lu_min, seed_end: series.seed_end, updated_at: Date.now() }
      delete sdoc._id
      await ref.doc('series').set(sdoc)

      // 回写 agg（复盘页三卡数据源：window/stages/hits + last）
      const ev = calibRes.eval || {}
      const adoc = {
        window: ev.window || null,
        stages: ev.stages || {},
        hits: ev.hits || {},
        last_heat: ev.last_heat, last_stage: ev.last_stage,
        // 待确认顶点数：近 3 日已形成但前瞻窗口未满，尚未计入命中率分母
        pending_climax: (ev.pending_climax === undefined ? null : ev.pending_climax),
        last: String(date),
        updated_at: Date.now(),
      }
      delete adoc._id
      await ref.doc('agg').set(adoc)
      return { ok: true, days: rows.length, last: String(date) }
    } catch (e) {
      lastErr = e.message
      console.error(`[daily_job] 第 ${i}/${maxTry} 次校准聚合失败: ${lastErr}`)
      if (i < maxTry) await sleep(2000 * i)
    }
  }
  return { ok: false, error: lastErr }
}

/** 取近 N 日情绪温度（供温度计历史分位；失败返回 null，主流程不阻断）。 */
async function loadRecentHeats(limit = 120) {
  try {
    const r = await db.collection('daily').orderBy('date', 'desc').limit(limit).get()
    return (r.data || [])
      .map((d) => (d.sentiment && typeof d.sentiment.heat === 'number' ? d.sentiment.heat : null))
      .filter((x) => x !== null)
  } catch (e) {
    console.error('[daily_job] 历史温度读取失败（分位本次跳过）:', e.message)
    return null
  }
}

/** 读校准基线（失败/无基线返回 null，主快照流程不因此阻断）。 */
async function loadCalibBaseline() {
  try {
    const r = await db.collection('calib').doc('series').get()
    const s = (r.data && r.data[0]) || null
    if (s && Array.isArray(s.rows) && s.rows.length) {
      return { rows: s.rows, lu_min: s.lu_min }
    }
  } catch (e) {
    console.error('[daily_job] calib.series 读取失败（滚动校准本次跳过）:', e.message)
  }
  return null
}

/** 读最近一条待回填的核心池记录（coretrack.pending，_id=交易日）。
 *  仅当早于当日才回填；已回填/空记录由 snapshot_py 判 skipped。 */
async function loadPendingCores(today) {
  try {
    const r = await db.collection('coretrack').doc('pending').get()
    const p = (r.data && r.data[0]) || null
    if (p && Array.isArray(p.items) && p.items.length && String(p.d) < String(today)) {
      return { d: p.d, items: p.items }
    }
  } catch (e) {
    console.error('[daily_job] coretrack.pending 读取失败（次日追踪本次跳过）:', e.message)
  }
  return null
}

/** 写当日核心池为待回填记录（_id = 日期；失败不阻断主流程）。 */
async function savePendingCores(date, cores, maxTry = 2) {
  if (!Array.isArray(cores)) return null
  const items = cores.map((c) => ({
    code: c.code, name: c.name, grade: c.grade || '?',
    board: c.board || 0, total: c.total || 0,
  }))
  for (let i = 1; i <= maxTry; i++) {
    try {
      await db.collection('coretrack').doc('pending').set({ d: String(date), items, updated_at: Date.now() })
      return { ok: true, n: items.length }
    } catch (e) {
      console.error(`[daily_job] 第 ${i}/${maxTry} 次写 pending 失败: ${e.message}`)
      if (i < maxTry) await sleep(1500 * i)
    }
  }
  return { ok: false }
}

/** 次日表现累计（coretrack.agg）：按档位累计 晋级数/次日涨幅。
 *  幂等：仅当 回填日(prev_date) > agg.last_settled 才累计（重复触发/补跑不重复入账）。
 *
 *  ⚠️ 存储结构兼容（2026-09-07 修复）：早期版本把 finalize 后的 {n,adv,adv_rate,avg_pct}
 *  （无 sum_pct）直接存库，第二次结算时 grp.sum_pct += pct → undefined+number=NaN →
 *  avg_pct 永久污染为 null。现在 fromStored() 从库里还原可累计源（优先 sum_pct，
 *  老结构用 avg_pct×n 反推），并随文档回写 sum_pct，新旧结构均安全。 */
async function settleCoreTrack(prevDate, results, maxTry = 3) {
  if (!prevDate || !Array.isArray(results) || !results.length) {
    return { ok: false, skipped: 'no-results' }
  }
  let lastErr = null
  for (let i = 1; i <= maxTry; i++) {
    try {
      const ref = db.collection('coretrack').doc('agg')
      const cur = await ref.get()
      const agg = (cur.data && cur.data[0]) || null
      const st = (agg && agg.last_settled) || ''
      if (st >= prevDate) return { ok: true, skipped: 'dup' } // 已入账

      const initGrade = () => ({ n: 0, adv: 0, sum_pct: 0 })
      const fromStored = (x) => {
        if (!x) return initGrade()
        let sum_pct = 0
        if (typeof x.sum_pct === 'number' && !Number.isNaN(x.sum_pct)) {
          sum_pct = x.sum_pct
        } else if (typeof x.avg_pct === 'number' && !Number.isNaN(x.avg_pct) && x.n) {
          sum_pct = x.avg_pct * x.n // 老结构：由均值反推总量
        }
        return { n: x.n || 0, adv: x.adv || 0, sum_pct }
      }
      const prev = (agg && agg.grades) || {}
      const g = {
        S: fromStored(prev.S), A: fromStored(prev.A),
        B: fromStored(prev.B), C: fromStored(prev.C),
      }
      const over = fromStored(agg && agg.overall)
      for (const it of results) {
        const grp = g[it.grade] || initGrade()
        grp.n += 1
        if (it.adv) grp.adv += 1
        if (typeof it.pct === 'number' && !Number.isNaN(it.pct)) grp.sum_pct += it.pct
        g[it.grade] = grp
        over.n += 1
        if (it.adv) over.adv += 1
        if (typeof it.pct === 'number' && !Number.isNaN(it.pct)) over.sum_pct += it.pct
      }
      const finalize = (x) => ({
        n: x.n, adv: x.adv, sum_pct: Math.round(x.sum_pct * 100) / 100,
        adv_rate: x.n ? Math.round((x.adv / x.n) * 100) : null,
        avg_pct: x.n ? Math.round((x.sum_pct / x.n) * 100) / 100 : null,
      })
      const doc = {
        grades: {
          S: finalize(g.S), A: finalize(g.A), B: finalize(g.B), C: finalize(g.C),
        },
        overall: finalize(over),
        settled_days: ((agg && agg.settled_days) || 0) + 1,
        last_settled: String(prevDate),
        last: String(prevDate),
        updated_at: Date.now(),
      }
      delete doc._id
      await ref.set(doc)
      return { ok: true, prev_date: prevDate }
    } catch (e) {
      lastErr = e.message
      console.error(`[daily_job] 第 ${i}/${maxTry} 次核心池胜率累计失败: ${lastErr}`)
      if (i < maxTry) await sleep(2000 * i)
    }
  }
  return { ok: false, error: lastErr }
}

/** 核心池次日追踪：读 pending 传 snapshot_py 回填 → 写当日 pending → 累计 agg。 */
async function coreTrackFlow(date, r, maxTry = 2) {
  const coreTrack = r.core_track
  // 1) 有回填结果 → 累计（幂等由 agg.last_settled 保证）；否则透传 skipped 原因
  let settle = {
    ok: false,
    skipped: coreTrack ? (coreTrack.skipped || coreTrack.error || 'no-input') : 'no-input',
  }
  if (coreTrack && coreTrack.ok) {
    settle = await settleCoreTrack(coreTrack.prev_date, coreTrack.results, maxTry)
  }
  // 2) 写今日核心池为明日待回填（先累计再覆盖 pending，避免同一记录重复入账）
  const saved = await savePendingCores(date, (r.snapshot && r.snapshot.cores) || [], maxTry)
  return { settle, saved }
}

async function run(event = {}) {
  const t0 = Date.now()
  // 滚动校准基线：提前读取，随事件传给 snapshot_py（读失败不阻断主流程）
  const calibBase = await loadCalibBaseline()
  if (calibBase) {
    event.calib_rows = calibBase.rows
    event.calib_lu_min = calibBase.lu_min
  }
  // 温度计历史分位：取近 120 日 heat（读失败不阻断主流程，后端会降级为"样本积累中"）
  const hists = await loadRecentHeats(120)
  if (hists && hists.length) event.hist_heats = hists
  // 核心池次日追踪：最近一条待回填记录（快照日即 today，取 yesterday）
  const pending = await loadPendingCores(rDateOf(event))
  if (pending) event.prev_cores = pending
  // 核心池在池天数：近 10 日核心池 code 集合
  const histCores = await loadHistCores(10)
  if (histCores && histCores.length) event.hist_cores = histCores

  const r = await computeSnapshot(event)
  if (!r || !r.ok) return r || { ok: false, error: 'snapshot_py 无返回' } // skipped / error 原样透传

  const snap = r.snapshot
  snap._updatedAt = Date.now()
  const err = await saveSnapshot(r.date, snap)
  if (err) return { ok: false, error: `写库失败: ${err}`, date: r.date }

  // 题材生命期聚合（失败不阻断主流程，仅记返回）
  const tl = await updateThemeLife(r.date, snap.ths_tags)
  // 滚动校准聚合（失败不阻断主流程）
  const calib = calibBase ? await updateCalib(r.date, r.calib) : { ok: false, skipped: 'no-baseline' }
  // 核心池次日表现追踪：回填昨日 → 累计胜率 → 写今日待回填
  const ct = await coreTrackFlow(r.date, r)
  return {
    ok: true,
    date: r.date,
    heat: snap.sentiment && snap.sentiment.heat,
    stage: snap.cycle && snap.cycle.stage,
    cores: (snap.cores || []).length,
    themelife: tl,
    calib,
    core_track: ct,
    costMs: Date.now() - t0,
  }
}

/**
 * 运行记录（job_runs）：每次触发（含定时/手动/失败）都留痕，供前端"系统健康"展示。
 * 非交易日 skip 记为正常（ok=true, skipped 有值）；写记录失败不影响主流程。
 */
async function writeRunLog(t0, out, event) {
  try {
    try { await db.createCollection('job_runs') } catch (e) { /* 已存在 */ }
    const rec = {
      d: out.date || rDateOf(event),
      ts: Date.now(),
      ok: !!(out.ok || out.skipped),      // 非交易日 skip 视为正常
      skipped: out.skipped || null,
      cost_ms: Date.now() - t0,
      error: (out.ok || out.skipped) ? null : (out.error || 'unknown'),
      mode: (event && event.mode) || 'auto',
      subs: {
        calib: out.calib ? (out.calib.ok ? 'ok' : (out.calib.skipped || 'fail')) : null,
        themelife: out.themelife ? (out.themelife.ok ? 'ok' : (out.themelife.skipped || 'fail')) : null,
        core_track: out.core_track ? ((out.core_track.settle || {}).ok ? 'ok'
          : (out.core_track.settle || {}).skipped || 'fail') : null,
      },
    }
    delete rec._id
    await db.collection('job_runs').add(rec)
  } catch (e) {
    console.error('[daily_job] 写运行记录失败:', e.message)
  }
}

exports.main = async (event = {}) => {
  const t0 = Date.now()
  let out
  try {
    out = await run(event)
  } catch (e) {
    out = { ok: false, error: (e && e.message) || String(e) }
  }
  await writeRunLog(t0, out, event)
  return out
}
