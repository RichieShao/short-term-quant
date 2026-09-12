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
// 资金性质（季报底色）：与 Pattern.vue 的 <script setup> 保持同步
const HOLDER_ORDER = ['国家队', '社保基金', 'QFII', '险资', '公募基金', '私募',
  '北向资金', '产业资本', '牛散']
const holderCats = (h) => (h && h.cats
  ? HOLDER_ORDER.filter((c) => h.cats[c]).map((c) => ({ cat: c, d: h.cats[c] }))
  : [])
const holderOrg = (h) => (h && h.org
  ? HOLDER_ORDER.filter((c) => h.org[c]).map((c) => ({ cat: c, d: h.org[c] }))
  : [])
const SEAT_ORDER = ['机构专用', '北向专用', '游资营业部']
const seatKinds = (lhb) => {
  const k = (lhb && lhb.kinds) || {}
  return SEAT_ORDER.filter((x) => k[x]).map((x) => ({ kind: x, d: k[x] }))
}
const wan = (v) => (v == null ? '—' : (v > 0 ? '+' : '') + Number(v).toFixed(0) + '万股')
// 消息面定性（上涨逻辑）：与 Pattern.vue 保持同步
const newsTagCls = (tag) => (tag === '风险·警示' ? 'risk'
  : tag === '利好·公告' ? 'good' : '')
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
        poolMeta: (pt && pt.pool_meta) || null,
        staleCodes: (pt && pt.stale_codes) || [],
        holderMeta: (pt && pt.holder_meta) || null,
        newsMeta: (pt && pt.news_meta) || null,
        // 自选标的（SSR 不跑 onMounted/fetch，用静态值验证渲染契约）
        selfs: (pt && pt.selfs) || [],
        selfCodes: S.selfCodes || [],
        selfInput: '', selfBusy: false, selfErr: '',
        selfHint: S.selfHint || '',
        normCode: (raw) => {
          const n = String(raw || '').trim()
          if (!/^\d{6}$/.test(n)) return ''
          if (/^(43|83|87|88|92)/.test(n)) return 'bj' + n
          if (/^(60|68|9)/.test(n)) return 'sh' + n
          if (/^(00|30|20|15|16)/.test(n)) return 'sz' + n
          return 'sh' + n
        },
        addSelf: () => {}, delSelf: () => {},
        selfLabel: (c) => {
          const r = ((pt && pt.selfs) || []).find((x) => x.code === c)
          return (r && r.name) ? r.name : c
        },
        distMa21: (r) => ((r.close - r.ma21) / r.ma21) * 100,
        holderCats, holderOrg, seatKinds, wan, newsTagCls,
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
// P1 候选池三源（后端已给 pool_meta 时必须渲染池子构成）
if (S.pattern && S.pattern.pool_meta) {
  chk('候选池构成标签', html, '池 涨停')
  chk('候选池说明', html, '候选池（三源合并 + 自选）')
  chk('异动池口径', html, '按量比取前 ')
}
// P1 池子来源 chip：异动池的票显示"放量"而非"N板"
if (S.pattern && (S.pattern.hits || []).some((r) => r.pool === 'active')) {
  chk('异动池 chip 放量', html, '>放量<')
}
// P3 K线新鲜度：正常日 latest_bar == date，不应误报"滞后"
if (S.pattern && S.pattern.latest_bar === S.pattern.date) {
  chk('正常日不误报滞后', html, 'K线新鲜度')
  chk('正常日无滞后告警', html, '已<b>全部剔除、不产出信号</b>', false)
}

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

// 分支⑤：P3 —— 有标的数据滞后 → 顶部告警 + 剔除清单 + 不出现在信号里
const S5 = JSON.parse(JSON.stringify(S))
if (S5.pattern) {
  S5.pattern.fresh = false
  S5.pattern.stale_n = 3
  S5.pattern.latest_bar = '2026-09-09'
  S5.pattern.stale_codes = [
    { code: 'sh600001', name: '滞后甲', bar_date: '2026-09-09' },
    { code: 'sz000002', name: '滞后乙', bar_date: '2026-09-08' },
  ]
}
const html5 = await renderToString(makeApp(S5))
chk('P3 滞后告警', html5, '已<b>全部剔除、不产出信号</b>')
chk('P3 滞后计数标签', html5, '>滞后 3<')
chk('P3 剔除清单', html5, '滞后甲')
chk('P3 未列完提示', html5, '另 1 只')

// 分支⑥：新浪反爬限流 → 提示 + 资金分降为可用项加权
const S6 = JSON.parse(JSON.stringify(S))
if (S6.pattern && S6.pattern.flow_meta) {
  S6.pattern.flow_meta.sina_blocked = true
  for (const r of S6.pattern.hits || []) { if (r.flow) r.flow_parts = 1 }
}
const html6 = await renderToString(makeApp(S6))
chk('新浪限流提示', html6, '触发反爬限流')
chk('资金分项数标记', html6, '·1项<')

// 分支⑦：资金性质底色（季报）+ 席位性质（T+0）—— 注入确定性数据，验证渲染契约
const S7 = JSON.parse(JSON.stringify(S))
const h0 = S7.pattern && (S7.pattern.hits || [])[0]
if (h0) {
  S7.pattern.holder_meta = { ask_n: 190, cached_n: 190, need_n: 0, need: [] }
  h0.holder = {
    date: '2026-06-30', ctrl: '李振国,李喜燕', hnum: 848658, hnum_chg: -0.8,
    focus: '非常分散', hnum_date: '2026-08-31', h_pct: 0,
    tags: ['社保持仓', '北向重仓', '公募抱团'],
    cats: {
      社保基金: { n: 1, pct: 0.45, chg: -636.6, new: 0, top: ['全国社保基金一一八组合'] },
      北向资金: { n: 1, pct: 3.51, chg: 915.5, new: 0, top: ['香港中央结算有限公司'] },
      公募基金: { n: 2, pct: 0.881, chg: null, new: 1, top: ['华泰柏瑞中证光伏产业ETF'] },
    },
    org: { 公募基金: { n: 549, pct: 5.363 }, 社保基金: { n: 1, pct: 0.45 } },
    recent: [{ d: '2026-08-05', name: '香港中央结算有限公司', chg: -6920580, pct: 18.9, why: '临时公告' }],
  }
  // 席位性质：覆盖三种性质中的两种，断言渲染与文案
  h0.lhb = Object.assign({}, h0.lhb || {}, {
    on: true, date: S.date, tags: [], reasons: [], fwd: {},
    seats_buy: [], seats_sell: [],
    kinds: {
      机构专用: { n: 2, buy: 1.2e8, sell: 0, net: 1.2e8, seats: ['机构专用'] },
      游资营业部: { n: 1, buy: 5e7, sell: 0, net: 5e7, seats: ['华鑫证券上海分公司'] },
    },
  })
}
const html7 = await renderToString(makeApp(S7))
if (h0) {
  chk('资金性质统计条', html7, '资金性质 190/190')
  chk('资金性质底色标签', html7, '公募抱团')
  chk('十大流通股东口径', html7, '十大流通股东口径')
  chk('分类行·社保', html7, '全国社保基金一一八组合')
  chk('分类行·减持万股', html7, '-637万股')
  chk('新进标记', html7, '新进 1')
  chk('全体机构口径', html7, '全体机构口径')
  chk('实控人行', html7, '实际控制人')
  chk('股东户数行', html7, '股东户数')
  chk('近期持股变动', html7, '近期持股变动')
  chk('季报口径声明', html7, '滞后最多 1 个季度')
  chk('口径块·资金性质', html7, '资金性质（季报底色）')
  chk('口径块·H股陷阱', html7, '不计入北向')
  chk('席位性质', html7, '席位性质')
  chk('机构专用席位', html7, '机构专用 2 席')
  chk('游资营业部席位', html7, '游资营业部 1 席')
}

// 分支⑦b：failed 占位记录（北交所等无 F10 数据）→ 不渲染明细块、落到"无数据"兜底
const S7b = JSON.parse(JSON.stringify(S))
const h1 = S7b.pattern && (S7b.pattern.hits || [])[1]
if (h1 && h0) {
  S7b.pattern.holder_meta = { ask_n: 190, cached_n: 189, need_n: 0, need: [] }
  h1.holder = { code: h1.code, failed: 1, fetched: S.date }
}
const html7b = await renderToString(makeApp(S7b))
if (h1 && h0) {
  chk('failed 占位不崩', html7b, '双线粘合突破')
  chk('failed 占位落到无数据兜底', html7b, '资金性质：无数据')
}

// 分支⑨：消息面定性（上涨逻辑）—— 统计条/突破卡明细/粘合卡标签/口径块/静默不渲染
const S9 = JSON.parse(JSON.stringify(S))
if (S9.pattern) {
  S9.pattern.news_meta = { ask_n: 75, ok_n: 74, dist: { '题材·共振': 52, '资金·独行': 16, '利好·公告': 4, '风险·警示': 2 } }
  const h0n = (S9.pattern.hits || [])[0]
  if (h0n) h0n.news = {
    tag: '利好·公告', when: 'T-1盘后', why: '华胜天成:签订重大合同公告', n: 5,
    titles: ['华胜天成:签订重大合同公告', '华胜天成等成立数智科技公司 含AI业务'],
  }
  const h1n = (S9.pattern.hits || [])[1]
  if (h1n) h1n.news = { tag: '风险·警示', when: 'T盘后', why: '关于控股股东减持计划的预披露公告', n: 3 }
  const w0 = (S9.pattern.watch || [])[0]
  if (w0) w0.news = { tag: '题材·共振', when: 'T盘中', why: 'CPO概念股震荡回升', n: 4 }
  const h2n = (S9.pattern.hits || [])[2]
  if (h2n) h2n.news = { tag: '静默' }
}
const html9 = await renderToString(makeApp(S9))
chk('消息面统计条', html9, '消息面 74/75')
chk('消息面风险计数', html9, '⚠2')
chk('突破卡·消息面块', html9, '利好·公告')
chk('突破卡·时点', html9, 'T-1盘后')
chk('突破卡·明细标题', html9, '相关消息 2 条')
chk('突破卡·风险时点', html9, 'T盘后')
chk('粘合卡·消息标签', html9, '题材·共振')
chk('口径块·消息面', html9, '消息面（上涨逻辑）')
chk('口径块·宁可错杀', html9, '宁可错杀')
chk('静默不渲染', html9, '静默', false)

// 分支⑩：自选标的 —— 底部管理区 + selfs 票卡 + 池构成含自选
const S10 = JSON.parse(JSON.stringify(S))
if (S10.pattern) {
  S10.pattern.pool_meta = Object.assign({}, S10.pattern.pool_meta || {},
    { self_n: 2, total_n: 192 })
  S10.pattern.selfs = [{
    code: 'sh601012', name: '隆基绿能', state: '自选', close: 11.32, pct: -3.25,
    ma7: 11.726, ma21: 12.131, glue: 3.34, glue_days: 0,
    flow: { main_net: -1.52e8, streak: -4, trend_src: 'agg' },
    holder: {
      tags: ['社保持仓', '北向重仓', '公募抱团'], date: '2026-06-30',
      cats: {
        '社保基金': { n: 1, pct: 2.104, chg: 12.3, new: 0, top: ['自选样本社保组合'] },
        '北向资金': { n: 1, pct: 2.365, chg: -2759.8, new: 0, top: ['香港中央结算有限公司'] },
      },
      org: { '社保基金': { n: 3, pct: 2.41 } },
      ctrl: '自选样本实控人', hnum: 115000, hnum_chg: -2.1, hnum_date: '2026-06-30',
      recent: [{ d: '09-02', name: '自选样本近期股东', chg: 812, why: '深股通' }],
    },
    news: { tag: '资金·独行', when: '', why: '', n: 3,
      titles: ['自选样本消息甲', '自选样本消息乙', '自选样本消息丙'] },
  }]
}
S10.selfCodes = ['sh601012', 'sz002594']
const html10 = await renderToString(makeApp(S10))
chk('自选区标题', html10, '自选标的（每日随池扫描')
chk('自选输入框', html10, '6 位代码')
chk('自选添加按钮', html10, '添加')
chk('自选上限', html10, '2/30')
chk('自选chips名称', html10, '隆基绿能')
chk('自选票卡chip', html10, '>自选<')
chk('自选距MA21', html10, '距 MA21')
chk('自选资金流', html10, '净流出4日')
chk('自选底色', html10, '北向重仓')
// 自选票卡明细折叠（与突破卡同款）
chk('自选资金性质明细入口', html10, '· 报告期 2026-06-30')
chk('自选资金明细十大口径', html10, '自选样本社保组合')
chk('自选资金明细全体机构', html10, '自选样本实控人')
chk('自选资金明细近期变动', html10, '自选样本近期股东')
chk('自选消息明细条数', html10, '相关消息 3 条')
chk('自选消息明细标题', html10, '自选样本消息甲')
console.log('__DUMP10__' + JSON.stringify((html10.match(/异动池 <b>[\s\S]{0,120}/) || [])[0]))
chk('口径块·四源', html10, '∪ 自选 <b>2</b>')
chk('口径块标题', html10, '候选池（三源合并 + 自选）')

// 分支⑪：自选添加成功提示（新标的不立即进榜，须等下次扫描）
const S11 = JSON.parse(JSON.stringify(S10))
S11.selfHint = '已加入自选 ✓ 卡片将在下次扫描（交易日 16:05 / 21:00）后进榜'
const html11 = await renderToString(makeApp(S11))
chk('自选添加提示', html11, '已加入自选 ✓ 卡片将在下次扫描')
chk('自选提示进榜时点', html11, '16:05 / 21:00')

// 分支⑧：无资金性质数据 → 不崩、且不渲染任何资金性质标签/说明
const S8 = JSON.parse(JSON.stringify(S))
if (S8.pattern) {
  S8.pattern.holder_meta = null
  for (const r of S8.pattern.hits || []) r.holder = null
  for (const r of S8.pattern.watch || []) r.holder = null
}
const html8 = await renderToString(makeApp(S8))
chk('无资金性质不崩', html8, '双线粘合突破')
chk('无资金性质时不渲染说明', html8, '季报底色', false)

console.log(bad === 0 ? '\n全部通过' : `\n${bad} 项未通过`)
process.exit(bad === 0 ? 0 : 1)
