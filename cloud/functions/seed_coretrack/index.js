/**
 * 核心池次日追踪·手工种子（一次性/补灌）
 *  把指定历史交易日快照里的核心池写为 coretrack.pending（_id 固定 'pending'），
 *  让下一个 daily_job 运行时可对该日做次日表现回填。日常无需调用（daily_job 自动维护）；
 *  仅用于初次上线时的历史补灌 / 手工重灌。
 */
const cloudbase = require('@cloudbase/node-sdk')

const app = cloudbase.init({ env: cloudbase.SYMBOL_CURRENT_ENV })
const db = app.database()

exports.main = async (event = {}) => {
  const date = String(event.date || '')
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return { ok: false, error: '缺少 date（YYYY-MM-DD）' }
  }
  try { await db.createCollection('coretrack') } catch (e) { /* 已存在 */ }

  const r = await db.collection('daily').doc(date).get()
  const snap = (r.data && r.data[0]) || null
  if (!snap || !Array.isArray(snap.cores) || !snap.cores.length) {
    return { ok: false, error: `daily ${date} 无核心池数据` }
  }
  const items = snap.cores.map((c) => ({
    code: c.code, name: c.name, grade: c.grade || '?',
    board: c.board || 0, total: c.total || 0,
  }))
  const doc = { d: date, items, updated_at: Date.now() }
  delete doc._id
  await db.collection('coretrack').doc('pending').set(doc)
  // 手工纠正：reset_agg=true 时同时清空胜率累计（脏数据重灌用）
  if (event.reset_agg) {
    const rd = { grades: null, overall: null, settled_days: 0, last_settled: '', updated_at: Date.now() }
    delete rd._id
    await db.collection('coretrack').doc('agg').set(rd)
    return { ok: true, seeded_date: date, n: items.length, agg_reset: true }
  }
  return { ok: true, seeded_date: date, n: items.length, codes: items.map((x) => x.code) }
}
