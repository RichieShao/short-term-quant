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

/**
 * 资金流自累积表（flow_hist）读取 → 注入 snapshot_py 的 flow_agg。
 *
 * 背景：东财唯一的多日资金流接口 push2his/fflow/daykline 已失效（沙箱 + 云端双双
 * RemoteDisconnected），故多日趋势改由"每日落一行"的自累积表提供；未满窗时代码侧
 * 自动降级新浪口径并标 trend_src=sina。
 *
 * 实现：直接取最近 500 条按 date 倒序（池约 40~90 只/日 → 覆盖 6~12 个交易日），
 * 每只票只保留最近 5 个交易日，避免依赖 where+command 的过滤写法。
 * 失败返回 null（主流程不阻断，代码侧降级新浪）。
 */
/**
 * 读自累积资金流表，按 code 聚成"近 N 日主力净额序列"。
 *
 * ⚠ 容量口径（2026-09-11 池子放开后调整）：形态候选池从 40 扩到 ~190
 * （涨停 ∪ 核心 ∪ 全市场异动池），每天落库 ~190 行。原来 maxDocs=500 只够
 * 2.6 天，导致 sum5 / 连续天数**永远凑不满**。现取 3000 行（≈15 天）并每票留 8 日，
 * 给停牌/缺席留出容差。集合长期约 190 行/日（≈4.7 万行/年），必要时给 date 建索引。
 */
async function loadFlowAgg(maxDocs = 3000) {
  try {
    try { await db.createCollection('flow_hist') } catch (e) { /* 已存在 */ }
    const r = await db.collection('flow_hist').orderBy('date', 'desc').limit(maxDocs).get()
    const byCode = {}
    for (const d of r.data || []) {
      const c = d.code
      if (!c || !d.date) continue
      const arr = byCode[c] || (byCode[c] = [])
      if (arr.length < 8) arr.push({ d: d.date, m: d.m })
    }
    for (const k of Object.keys(byCode)) {
      byCode[k].sort((a, b) => String(a.d).localeCompare(String(b.d)))
    }
    return Object.keys(byCode).length ? byCode : null
  } catch (e) {
    console.error('[daily_job] flow_hist 读取失败（多日资金流降级新浪）:', e.message)
    return null
  }
}

/** 写当日资金流样本（flow_hist，_id = code|date，幂等 upsert）。 */
async function saveFlowRows(date, rows, maxTry = 2) {
  const list = (rows || []).filter((r) => r && r.code && r.date)
  if (!list.length) return { ok: false, skipped: 'no-rows' }
  try { await db.createCollection('flow_hist') } catch (e) { /* 已存在 */ }
  let ok = 0
  for (let i = 0; i < list.length; i += 20) {
    const chunk = list.slice(i, i + 20)
    try {
      await Promise.all(chunk.map((r) => {
        const doc = {
          code: r.code, date: String(r.date),
          m: r.m, x: r.x, l: r.l,
          src: 'em', updated_at: Date.now(),
        }
        delete doc._id
        return db.collection('flow_hist').doc(`${r.code}|${r.date}`).set(doc)
      }))
      ok += chunk.length
    } catch (e) {
      console.error(`[daily_job] flow_hist 写入失败（批次 ${i / 20}）: ${e.message}`)
      if (i === 0) await sleep(1500)
    }
  }
  return { ok: ok > 0, n: ok, total: list.length }
}

/**
 * 资金性质底色缓存（holder_cache，_id = code）读取 → 注入 snapshot_py 的 holder_map。
 *
 * 数据是**季报口径**（东财 F10 十大流通股东分类：公募/北向/QFII/社保/险资/私募/
 * 产业资本/国家队/牛散），日内不变 ⇒ 不该每天重拉。刷新决策在 Python 侧
 * （`holders.need_refresh`：报告期已过期 且 距上次抓取 ≥7 天），本函数只负责整包传下去。
 *
 * 池约 190 只 → 缓存 190 条，limit(400) 一次取全（约 300KB）。
 * 失败返回 null：形态照跑，只是没有底色（不阻断主流程）。
 */
async function loadHolderCache(maxDocs = 400) {
  try {
    try { await db.createCollection('holder_cache') } catch (e) { /* 已存在 */ }
    const r = await db.collection('holder_cache').limit(maxDocs).get()
    const out = {}
    for (const d of r.data || []) {
      const c = d.code || d._id
      if (c) out[c] = d
    }
    return Object.keys(out).length ? out : null
  } catch (e) {
    console.error('[daily_job] holder_cache 读取失败（资金性质底色缺失）:', e.message)
    return null
  }
}

/**
 * 读用户自选票（watchlist 集合，_id='default' 单文档 codes 数组，前端 api 云函数维护）。
 * 扫描时并入候选池（第四源「自选」，无条件入池、同权扫描）。
 * 失败返回 []：形态照跑，只是没有自选票（不阻断主流程）。
 */
async function loadSelfWatch(maxN = 30) {
  try {
    const r = await db.collection('watchlist').doc('default').get()
    const w = (r.data && r.data[0]) || null
    return ((w && w.codes) || []).map((x) => String(x).trim().toLowerCase())
      .filter(Boolean).slice(0, maxN)
  } catch (e) {
    console.error('[daily_job] watchlist 读取失败（自选票不并入）:', e.message)
    return []
  }
}

/**
 * 写资金性质底色（holder_cache，_id = code，幂等 upsert）。
 * 只写"本次新抓到的票"（缓存命中的不重写），故日常通常 no-rows。
 */
async function saveHolderRows(rows, maxTry = 2) {
  const list = (rows || []).filter((r) => r && r.code)
  if (!list.length) return { ok: false, skipped: 'no-rows' }
  try { await db.createCollection('holder_cache') } catch (e) { /* 已存在 */ }
  let ok = 0
  for (let i = 0; i < list.length; i += 20) {
    const chunk = list.slice(i, i + 20)
    try {
      await Promise.all(chunk.map((r) => {
        const doc = Object.assign({}, r)
        delete doc._id
        doc.updated_at = Date.now()
        return db.collection('holder_cache').doc(String(r.code)).set(doc)
      }))
      ok += chunk.length
    } catch (e) {
      console.error(`[daily_job] holder_cache 写入失败（批次 ${i / 20}）: ${e.message}`)
      if (i === 0) await sleep(1500)
    }
  }
  return { ok: ok > 0, n: ok, total: list.length }
}

/**
 * 分批同步资金性质底色（snapshot_py action=holder_sync）。
 *
 * ⚠ 必须分批（2026-09-12 踩坑）：一条记录约 1KB，190 只 ≈180KB，直接整包回传会撞上
 *   "嵌套 callFunction 响应体过大被平台截断"——Python 返回 179 条、Node 只收到 10 条，
 *   而且**不报错**。分 40 只/批（≈40KB）后稳定完整。
 *
 * 返回 ``{ok, n, ask_n, rows}``；单批失败只丢该批，不阻断。
 */
async function syncHolders(codes, date, holderMap, force, batch = 40) {
  const uniq = [...new Set((codes || []).filter(Boolean))]
  if (!uniq.length) return { ok: false, skipped: 'no-need', n: 0, rows: [] }
  const rows = []
  for (let i = 0; i < uniq.length; i += batch) {
    const chunk = uniq.slice(i, i + batch)
    try {
      const out = await app.callFunction({
        name: 'snapshot_py',
        data: { action: 'holder_sync', codes: chunk, date, holder_map: holderMap, force: !!force },
      }, { timeout: 60000 })
      const r = out && out.result
      if (r && r.ok && Array.isArray(r.holder_rows)) {
        rows.push(...r.holder_rows)
        console.log(`[daily_job] holder_sync 第 ${i / batch + 1} 批: ${r.holder_rows.length}/${chunk.length}`)
      } else {
        console.error(`[daily_job] holder_sync 第 ${i / batch + 1} 批失败: ${(r && r.error) || '无返回'}`)
      }
    } catch (e) {
      console.error(`[daily_job] holder_sync 第 ${i / batch + 1} 批异常: ${e.message}`)
    }
  }
  return { ok: rows.length > 0, n: rows.length, ask_n: uniq.length, rows }
}

/**
 * 资金性质缺口自愈：若 pattern.holder_meta.need 非空（冷启动 / 季报换季），
 * 分批抓取 → 写库 → 用"缓存 + 新记录"重算一次形态，使**当次快照就带上底色**。
 * 日常 need 为空 → 零额外开销、零额外请求。
 *
 * ``rerun(cache)`` 由调用方提供（夜间路径重跑 pattern_only；盘后路径只重算形态块）。
 */
async function fillHolders(pat, holderCache, rerun) {
  const need = (pat && pat.holder_meta && pat.holder_meta.need) || []
  if (!need.length) return { pat, write: { ok: false, skipped: 'no-need' } }
  const sync = await syncHolders(need, null, holderCache, false)
  if (!sync.rows.length) {
    // 抓取全失败（东财 F10 抖动）→ 保留原 pat，不阻断主流程
    return { pat, write: { ok: false, skipped: 'sync-empty' }, sync_n: 0, need_n: need.length }
  }
  const write = await saveHolderRows(sync.rows)
  const cache = Object.assign({}, holderCache || {})
  for (const r of sync.rows) cache[r.code] = r
  let pat2 = pat
  try {
    pat2 = (await rerun(cache)) || pat
  } catch (e) {
    console.error('[daily_job] 资金性质重算失败（保留无底色版本）:', e.message)
  }
  return { pat: pat2, write, sync_n: sync.rows.length, need_n: need.length }
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
          // 资金流自累积（近 N 日主力净额）→ 形态模块算近3/5日累计 + 连续净流入天数
          // ⚠ 2026-09-12 修复：run() 一直在读 flow_agg 并挂到 event，但此前**没有
          //   往下传**，导致盘后主快照的多日资金流被静默丢弃（只有 21:00 的
          //   pattern_only 用上了），同一只票 16:40 与 21:00 的资金分口径不一致。
          flow_agg: event.flow_agg,
          // 资金性质底色缓存（季报口径，日内不变）——Python 侧只补缺失/过期的票
          holder_map: event.holder_map,
          // 用户自选票（第四源，无条件入池、同权扫描）
          self_codes: event.self_codes,
        },
      }, { timeout: 110000 }) // SDK 默认 15s；涨停爆发日快照约 20-45s，再叠加形态的资金流/龙虎榜拉取，必须放宽

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

/**
 * 是否夜间补充运行（21:00）。
 *
 * 当日龙虎榜约 18:00 后才发布，16:05/16:40 的快照里 pattern.lhb 必为空。
 * 判定三重兜底：显式 mode=night / 触发器名 night_2100 / 北京时 >=19:00 的定时触发。
 * mode=force（手动补跑）**不**判为夜间，避免"补跑历史日"被误当夜间补充。
 */
function isNightRun(event) {
  if (!event) return false
  if (event.mode === 'night') return true
  if (event.mode === 'force') return false
  const tn = String(event.TriggerName || event.triggerName || '')
  if (tn === 'night_2100') return true
  const h = new Date(Date.now() + 8 * 3600 * 1000).getUTCHours() // 北京时小时
  return h >= 19
}

/**
 * 夜间补充：只重算形态块（此时当日龙虎榜已发布），再把结果合并回当天 daily 文档。
 *
 * ⚠️ 合并方式：读全量文档 → 只替换 snapshot.pattern → 整体 set 回写。
 *    绝不"只 set pattern"式整体覆盖（历史上 themelife/coretrack 聚合被整体覆盖吞字段）。
 * 池子取当日 daily 文档里的 cores，保证与 16:40 那次同池，只补龙虎榜/资金流。
 */
async function runNight(event) {
  const t0 = Date.now()
  const date = rDateOf(event)
  const ref = db.collection('daily').doc(String(date))
  let day = null
  try {
    const r = await ref.get()
    day = (r.data && r.data[0]) || null
  } catch (e) {
    return { ok: false, error: `读当日 daily 失败: ${e.message}`, date }
  }
  if (!day) return { ok: false, error: `当日 daily 文档不存在（${date}），夜间补充跳过`, date }

  const cores = (day.cores || []).map((c) => ({ code: c.code, name: c.name, board: c.board }))
  const flowAgg = await loadFlowAgg()
  const holderCache = await loadHolderCache()
  const selfCodes = await loadSelfWatch()

  // 重算形态（可带不同 holder_map）；抽成闭包供"缺口自愈"复跑一次
  const callPattern = async (holderMap) => {
    let lastErr = 'pattern_only 无返回'
    for (let i = 1; i <= 3; i++) {
      try {
        const out = await app.callFunction({
          name: 'snapshot_py',
          data: {
            action: 'pattern_only', date, cores, flow_agg: flowAgg,
            holder_map: holderMap,
            // 用户自选票（第四源）——夜间重算与日间同口径
            self_codes: selfCodes,
            // 显式全量刷新（补灌/季报换季时用），日常不传
            holder_refresh_all: !!event.holder_refresh_all,
          },
        }, { timeout: 110000 }) // 形态+资金流+龙虎榜实测 15~25s（冷启动走新浪兜底时更久），SDK 默认 15s 必超时
        const res = out && out.result
        if (res && res.ok) return res
        lastErr = (res && res.error) || 'pattern_only 失败'
      } catch (e) {
        lastErr = `callFunction 失败: ${e.message}`
      }
      console.error(`[daily_job] 夜间补充第 ${i}/3 次失败: ${lastErr}`)
      if (i < 3) await sleep(3000 * i)
    }
    return null
  }

  const res = await callPattern(holderCache)
  if (!res) return { ok: false, error: 'pattern_only 三次均失败', date }

  const flowWrite = await saveFlowRows(date, res.pattern.flow_rows)
  // 资金性质缺口自愈：冷启动/季报换季时先分批抓取写库，再用完整缓存重算一次
  const hf = await fillHolders(res.pattern, holderCache,
    (cache) => callPattern(cache).then((x) => (x && x.pattern) || null))
  const pat = hf.pat
  // 合并回写：保留既有全部字段，只换 pattern。
  // ⚠️ daily 文档就是"扁平快照本体"（saveSnapshot 直接 set(snap)，api 直接把它当 snapshot 返回），
  //    所以 pattern 在**顶层**，不是 doc.snapshot.pattern。
  const doc = Object.assign({}, day)
  delete doc._id
  doc.pattern = pat
  // 清理误写产生的多余嵌套键（2026-09-11 首版曾误按 doc.snapshot.pattern 合并）
  if (doc.snapshot) delete doc.snapshot
  doc._updatedAt = Date.now()
  try {
    await ref.set(doc)
  } catch (e) {
    return { ok: false, error: `合并回写失败: ${e.message}`, date }
  }
  return {
    ok: true, date, night: true,
    hit_n: pat.hit_n, watch_n: pat.watch_n, scan_n: pat.scan_n,
    lhb_today: (pat.lhb_meta || {}).today, lhb_today_n: (pat.lhb_meta || {}).today_n,
    flow_srcs: (pat.flow_meta || {}).srcs, flow_rows: (pat.flow_rows || []).length,
    flow_agg_codes: flowAgg ? Object.keys(flowAgg).length : 0,
    flow_write: flowWrite,
    holder_meta: pat.holder_meta, holder_write: hf.write,
    holder_sync_n: hf.sync_n || 0, holder_need_n: hf.need_n || 0,
    news_meta: pat.news_meta, self_n: pat.self_n,
    costMs: Date.now() - t0,
  }
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
  // 资金流自累积：近 N 日样本注入形态模块（算近3/5日累计 + 连续净流入天数）
  const flowAgg = await loadFlowAgg()
  if (flowAgg) event.flow_agg = flowAgg
  // 资金性质底色缓存（季报口径）：整包注入，Python 侧按需补拉缺失/过期的票
  const holderCache = await loadHolderCache()
  if (holderCache) event.holder_map = holderCache
  // 用户自选票（第四源）：并入候选池，无条件入池、同权扫描
  const selfCodes = await loadSelfWatch()
  if (selfCodes.length) event.self_codes = selfCodes

  const r = await computeSnapshot(event)
  if (!r || !r.ok) return r || { ok: false, error: 'snapshot_py 无返回' } // skipped / error 原样透传

  const snap = r.snapshot
  // 资金性质缺口自愈（冷启动 / 季报换季）：分批抓取写库 → 用完整缓存**只重算形态块**
  // （不重跑整个快照）。日常 need 为空 → 直接跳过，零额外开销。
  const coresForPat = (snap.cores || []).map((c) => ({ code: c.code, name: c.name, board: c.board }))
  const hf = await fillHolders(snap.pattern, holderCache, async (cache) => {
    if (!snap.pattern) return null
    try {
      const out = await app.callFunction({
        name: 'snapshot_py',
        data: { action: 'pattern_only', date: r.date, cores: coresForPat,
                flow_agg: flowAgg, holder_map: cache, self_codes: selfCodes },
      }, { timeout: 110000 })
      const r2 = out && out.result
      return (r2 && r2.ok && r2.pattern) || null
    } catch (e) {
      console.error('[daily_job] 形态块重算失败（保留无底色版本）:', e.message)
      return null
    }
  })
  snap.pattern = hf.pat
  snap._updatedAt = Date.now()
  const err = await saveSnapshot(r.date, snap)
  if (err) return { ok: false, error: `写库失败: ${err}`, date: r.date }

  // 资金流样本落库（flow_hist）：供次日及以后算多日累计；失败不阻断主流程
  const flowWrite = await saveFlowRows(r.date, (snap.pattern || {}).flow_rows || [])
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
    pattern: snap.pattern ? {
      hit_n: snap.pattern.hit_n, watch_n: snap.pattern.watch_n,
      flow_srcs: (snap.pattern.flow_meta || {}).srcs,
      lhb_today_n: (snap.pattern.lhb_meta || {}).today_n,
      holder_meta: snap.pattern.holder_meta,
    } : null,
    flow_agg_codes: flowAgg ? Object.keys(flowAgg).length : 0,
    flow_write: flowWrite,
    holder_write: hf.write, holder_sync_n: hf.sync_n || 0, holder_need_n: hf.need_n || 0,
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
      mode: (event && event.mode) || (out.night ? 'night' : 'auto'),
      // 触发器名留痕：用于确认 21:00 夜间触发器是否按预期按下发名判定
      trigger: (event && (event.TriggerName || event.triggerName)) || null,
      subs: {
        calib: out.calib ? (out.calib.ok ? 'ok' : (out.calib.skipped || 'fail')) : null,
        themelife: out.themelife ? (out.themelife.ok ? 'ok' : (out.themelife.skipped || 'fail')) : null,
        core_track: out.core_track ? ((out.core_track.settle || {}).ok ? 'ok'
          : (out.core_track.settle || {}).skipped || 'fail') : null,
        flow_write: out.flow_write ? (out.flow_write.ok ? `n=${out.flow_write.n}` : (out.flow_write.skipped || 'fail')) : null,
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
    out = isNightRun(event) ? await runNight(event) : await run(event)
  } catch (e) {
    out = { ok: false, error: (e && e.message) || String(e) }
  }
  await writeRunLog(t0, out, event)
  return out
}
