/**
 * Pattern.vue 数据契约测试（轻量、零依赖新增）
 *
 * 用法：
 *   node tools/pattern_contract.mjs [快照JSON路径]
 *   默认读 ../.workbuddy/tmp/api_0911.json；也可先用
 *   curl -sS "<api>?action=day&date=YYYY-MM-DD" -o snap.json 落一份线上真实快照。
 *
 * 做法：用 @vue/compiler-sfc 把 Pattern.vue 的 <template> 编译成 render，
 * 再用 vue/server-renderer 拿**线上真实快照**渲染，断言字段与三个分支：
 *   ① 正常（21:00 后，当日榜已发布）② 16:40（当日榜未发布）③ 空数据兜底。
 *
 * 为什么需要它：模板是"手写字段名 ↔ 后端 JSON"的隐式契约，改后端字段名不会让
 * `npm run build` 报错，但线上会静默变空。本脚本把这条契约变成可执行断言。
 */
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'

const HERE = new URL('./', import.meta.url)
const vueFile = new URL('../src/views/Pattern.vue', HERE)
const renderFile = new URL('./.render.mjs', HERE)

// ---- 1) 编译模板 ----
const src = fs.readFileSync(vueFile, 'utf8')
const { descriptor, errors } = parse(src, { filename: 'Pattern.vue' })
if (errors && errors.length) {
  console.error('SFC 解析错误:', errors.map((e) => e.message).join('; '))
  process.exit(1)
}
const out = compileTemplate({
  source: descriptor.template.content,
  filename: 'Pattern.vue',
  id: 'pat-tpl',
  mode: 'module',
})
if (out.errors && out.errors.length) {
  console.error('模板编译错误:', out.errors.map((e) => e.message || e).join('; '))
  process.exit(1)
}
fs.writeFileSync(renderFile, out.code, 'utf8')
const { render } = await import(renderFile.href)

// ---- 2) 复刻 Pattern.vue 的 setup 绑定（与其 <script setup> 保持同步）----
const TREND_SRC = { agg: '东财·自累积', em: '东财多日', sina: '新浪口径' }
const money = (v) => {
  if (v == null || Number.isNaN(v)) return '—'
  const a = Math.abs(v)
  const sg = v < 0 ? '-' : '+'
  if (a >= 1e8) return sg + (a / 1e8).toFixed(2) + '亿'
  if (a >= 1e4) return sg + (a / 1e4).toFixed(0) + '万'
  return sg + a.toFixed(0)
}
function makeApp(S) {
  const pt = S.pattern
  return createSSRApp({
    render,
    setup() {
      const stage = (S.cycle && S.cycle.stage) || ''
      const band = (S.sentiment && S.sentiment.band) || ''
      return {
        s: { date: S.date, cycle: S.cycle, sentiment: S.sentiment },
        pt,
        hits: (pt && pt.hits) || [],
        watch: (pt && pt.watch) || [],
        stage, band,
        ebbHint: stage === '退潮' || /冰点|退潮/.test(band),
        fmt: (v, nd = 2) => (v == null ? '—' : Number(v).toFixed(nd)),
        pctCls: (v) => (v > 0 ? 'up' : v < 0 ? 'down' : ''),
        sign: (v) => (v > 0 ? '+' : ''),
        money, TREND_SRC,
        trendLabel: (f) => TREND_SRC[f.trend_src] || '样本积累中',
        lhbMeta: (pt && pt.lhb_meta) || null,
        flowMeta: (pt && pt.flow_meta) || null,
      }
    },
  })
}

// ---- 3) 断言 ----
const path = process.argv[2] || fileURLToPath(new URL('../../.workbuddy/tmp/api_0911.json', HERE))
if (!fs.existsSync(path)) {
  console.error(`快照文件不存在: ${path}\n先落一份：curl -sS "<api>?action=day&date=YYYY-MM-DD" -o ${path}`)
  process.exit(2)
}
const S = JSON.parse(fs.readFileSync(path, 'utf8')).snapshot
let bad = 0
const chk = (label, html, needle, want = true) => {
  const ok = html.includes(needle) === want
  if (!ok) bad++
  console.log(`${ok ? '✓' : '✗'} ${label}  «${needle}»${want ? '' : ' (期望无)'}`)
}

const html = await renderToString(makeApp(S))
console.log(`渲染字符数 = ${html.length}  (date=${S.date}, pattern=${S.pattern ? '有' : '无'})\n`)
chk('突破标题', html, '双线粘合突破')
chk('资金分徽章', html, '资金分')
chk('主力净额', html, '主力 +')
chk('超大/大/中/小拆解', html, '超大 ')
chk('近3日/5日累计', html, '近3日')
chk('连续净流入', html, '净流入')
chk('口径来源标', html, '新浪口径')
chk('席位明细折叠', html, '席位明细')
chk('上榜原因', html, '上榜原因')
chk('资金流统计', html, '资金流 ')
chk('龙虎榜统计', html, '龙虎榜 今 ')

// 分支②：16:40（当日榜未发布）→ 顶部提示在、不出现"未上榜"chip
const S2 = JSON.parse(JSON.stringify(S))
if (S2.pattern) {
  S2.pattern.lhb_meta = { today: S.date, today_n: null, prev: '2026-09-10', prev_n: 53, errors: [] }
  for (const r of S2.pattern.hits || []) r.lhb = null
}
const html2 = await renderToString(makeApp(S2))
chk('16:40 未发布提示', html2, '当日龙虎榜尚未发布')
chk('16:40 不误报未上榜', html2, '>未上榜<', false)

// 分支③：21:00（已发布但该股未上榜）→ 出现"未上榜"chip
const S3 = JSON.parse(JSON.stringify(S))
if (S3.pattern) {
  S3.pattern.lhb_meta = { today: S.date, today_n: 58, prev: '2026-09-10', prev_n: 53, errors: [] }
  for (const r of S3.pattern.hits || []) { r.lhb = null; r.lhb_prev = null }
}
const html3 = await renderToString(makeApp(S3))
chk('已发布未上榜chip', html3, '>未上榜<')

// 分支④：空数据兜底
const html4 = await renderToString(makeApp({ ...S, pattern: null }))
chk('空数据兜底', html4, '暂无形态数据')

console.log(bad === 0 ? '\n全部通过' : `\n${bad} 项未通过`)
process.exit(bad === 0 ? 0 : 1)
