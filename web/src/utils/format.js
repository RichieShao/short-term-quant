export function pct(v, d = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return `${(v * 100).toFixed(d)}%`
}

export function signed(v, d = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return `${v > 0 ? '+' : ''}${(v * 100).toFixed(d)}%`
}

export function pctCls(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return 'flat'
  return v > 0 ? 'up' : v < 0 ? 'down' : 'flat'
}

const BAND_COLOR = {
  '亢奋-高潮': '#ff4d5e',
  '活跃-发酵': '#ff9f43',
  '温和-震荡': '#5b8cff',
  '偏冷-分歧': '#a78bfa',
  '冰点-退潮': '#12c48b',
}
export function bandColor(band) {
  return BAND_COLOR[band] || '#8a93a8'
}

const STAGE_COLOR = {
  启动: '#4dd0e1',
  发酵: '#5b8cff',
  高潮: '#ff9f43',
  震荡: '#a78bfa',
  退潮: '#12c48b',
}
export function stageColor(stage) {
  return STAGE_COLOR[stage] || '#8a93a8'
}

export function shortDate(d) {
  return d ? String(d).slice(5) : '—'
}

export function num(v, d = 0) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return Number(v).toFixed(d)
}
