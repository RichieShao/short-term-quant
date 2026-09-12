<script setup>
import { computed } from 'vue'
import { useSnap } from '../stores/snap'

const s = useSnap()
const pt = computed(() => s.pattern)
const hits = computed(() => (pt.value && pt.value.hits) || [])
const watch = computed(() => (pt.value && pt.value.watch) || [])
const stage = computed(() => (s.cycle && s.cycle.stage) || '')
// 周期 band 才是「冰点-退潮」的真实载体（stage 取值只有 启动/发酵/高潮/震荡/退潮，无「冰点」）
const band = computed(() => (s.sentiment && s.sentiment.band) || '')
const ebbHint = computed(() => stage.value === '退潮' || /冰点|退潮/.test(band.value))

const fmt = (v, nd = 2) => (v == null ? '—' : Number(v).toFixed(nd))
const pctCls = (v) => (v > 0 ? 'up' : v < 0 ? 'down' : '')
const sign = (v) => (v > 0 ? '+' : '')

// 金额（元 → 亿/万，带正负号）；资金流入为正（涨红）
const money = (v) => {
  if (v == null || Number.isNaN(v)) return '—'
  const a = Math.abs(v)
  const sg = v < 0 ? '-' : '+'
  if (a >= 1e8) return sg + (a / 1e8).toFixed(2) + '亿'
  if (a >= 1e4) return sg + (a / 1e4).toFixed(0) + '万'
  return sg + a.toFixed(0)
}
const TREND_SRC = { agg: '东财·自累积', em: '东财多日', sina: '新浪口径' }
const trendLabel = (f) => TREND_SRC[f.trend_src] || '样本积累中'
const lhbMeta = computed(() => (pt.value && pt.value.lhb_meta) || null)
const flowMeta = computed(() => (pt.value && pt.value.flow_meta) || null)
const poolMeta = computed(() => (pt.value && pt.value.pool_meta) || null)
const staleCodes = computed(() => (pt.value && pt.value.stale_codes) || [])
const holderMeta = computed(() => (pt.value && pt.value.holder_meta) || null)
const newsMeta = computed(() => (pt.value && pt.value.news_meta) || null)

// ---- 资金性质（季报底色）----
// 展示顺序：越"强信号"的类别越靠前；游资不在此列（季报拿不到，由龙虎榜席位给）。
const HOLDER_ORDER = ['国家队', '社保基金', 'QFII', '险资', '公募基金', '私募',
  '北向资金', '产业资本', '牛散']
const holderCats = (h) => (h && h.cats
  ? HOLDER_ORDER.filter((c) => h.cats[c]).map((c) => ({ cat: c, d: h.cats[c] }))
  : [])
const holderOrg = (h) => (h && h.org
  ? HOLDER_ORDER.filter((c) => h.org[c]).map((c) => ({ cat: c, d: h.org[c] }))
  : [])
// 龙虎榜席位性质（T+0 的"谁在买"）
const SEAT_ORDER = ['机构专用', '北向专用', '游资营业部']
const seatKinds = (lhb) => {
  const k = (lhb && lhb.kinds) || {}
  return SEAT_ORDER.filter((x) => k[x]).map((x) => ({ kind: x, d: k[x] }))
}
// 万股 → 带正负号的展示
const wan = (v) => (v == null ? '—' : (v > 0 ? '+' : '') + Number(v).toFixed(0) + '万股')
// ---- 消息面定性（「上涨逻辑」）----
// 利好=涨红、风险=警示橙、题材/资金=金、静默不渲染
const newsTagCls = (tag) => (tag === '风险·警示' ? 'risk'
  : tag === '利好·公告' ? 'good' : '')
</script>

<template>
  <div class="page">
    <div class="card pat">
      <div class="pat-head">
        <div class="pat-badge">MA</div>
        <div class="grow">
          <div class="card-title" style="margin: 0">双线粘合突破 · MA7/MA21</div>
          <div class="tiny muted">腾讯日K前复权 · 粘合 ≤2.5% 持续 ≥3 日 → 收盘上穿 MA21 且 MA7 上翘 · 量能 ≥5日均量×1.5 为确认旗标</div>
        </div>
      </div>

      <div v-if="!pt" class="small dim" style="margin-top: 10px">
        暂无形态数据（仅在最新交易日盘后计算，历史日不补算）
      </div>

      <template v-else>
        <div class="row wrap pat-stats" style="gap: 6px">
          <span class="tag">{{ s.date }} 扫描 {{ pt.scan_n }} 只</span>
          <span class="tag gold">突破 {{ pt.hit_n }}</span>
          <span class="tag">粘合观察 {{ pt.watch_n }}</span>
          <span v-if="poolMeta" class="tag">
            池 涨停{{ poolMeta.zt_n }}<template v-if="poolMeta.active_n"> + 异动{{ poolMeta.active_n }}</template><template v-if="poolMeta.core_n"> + 核心{{ poolMeta.core_n }}</template>
          </span>
          <span v-if="pt.stale_n" class="tag stale">滞后 {{ pt.stale_n }}</span>
          <span v-if="flowMeta" class="tag">资金流 {{ flowMeta.hit_n }}/{{ flowMeta.ask_n }}</span>
          <span v-if="holderMeta" class="tag">
            资金性质 {{ holderMeta.cached_n == null ? '—' : holderMeta.cached_n }}/{{ holderMeta.ask_n == null ? '—' : holderMeta.ask_n }}<template v-if="holderMeta.need_n"> · 待补 {{ holderMeta.need_n }}</template>
          </span>
          <span v-if="newsMeta && !newsMeta.error" class="tag">
            消息面 {{ newsMeta.ok_n == null ? '—' : newsMeta.ok_n }}/{{ newsMeta.ask_n == null ? '—' : newsMeta.ask_n }}<template v-if="newsMeta.dist && newsMeta.dist['风险·警示']"> · <span class="news-risk-n">⚠{{ newsMeta.dist['风险·警示'] }}</span></template>
          </span>
          <span v-if="lhbMeta" class="tag">龙虎榜 今 {{ lhbMeta.today_n == null ? '—' : lhbMeta.today_n }} · 昨 {{ lhbMeta.prev_n == null ? '—' : lhbMeta.prev_n }}</span>
          <span class="tag">{{ pt.time_ms }}ms</span>
        </div>

        <div v-if="ebbHint" class="pat-hint tiny">
          当前周期「{{ stage }}」{{ band ? '（' + band + '）' : '' }}：退潮期整体不建议参与，形态仅作观察，别当买入信号。
        </div>
        <!-- P3：K线新鲜度守卫 -->
        <div v-if="pt.fresh === false" class="pat-hint tiny">
          ⚠ 有 <b>{{ pt.stale_n }}</b> 只标的的 K 线最后一根不是 {{ pt.date }}（停牌 / 行情未更新），
          已<b>全部剔除、不产出信号</b>——避免用旧 bar 算出"假突破"。
          <template v-if="pt.latest_bar">当前池内最新 K 线日：{{ pt.latest_bar }}。</template>
          <details class="stale-det">
            <summary>查看剔除清单</summary>
            <div v-for="x in staleCodes" :key="x.code" class="seat">
              {{ x.code }} {{ x.name }} — K线最后日 {{ x.bar_date }}
            </div>
            <div v-if="pt.stale_n > staleCodes.length" class="dim">…另 {{ pt.stale_n - staleCodes.length }} 只</div>
          </details>
        </div>
        <div v-if="lhbMeta && !lhbMeta.today_n" class="pat-hint tiny info">
          当日龙虎榜尚未发布（约 18:00 后才出）：本次为盘后 16:05/16:40 快照，
          <b>21:00 夜间任务</b>会把当日榜补算进本页。下方「昨上榜」为前一交易日榜，任何时点都可用。
        </div>
        <div v-if="flowMeta && flowMeta.sina_blocked" class="pat-hint tiny info">
          新浪资金流接口本次已触发反爬限流：多日累计（近3/5日、连续天数）整体缺失，
          资金分已自动降为「可用项重新加权」（看每行的「N项」标记）。
          <b>长期解是东财自累积</b>——每交易日落一行，约 3 个交易日后 agg 会接管、不再依赖新浪。
        </div>
        <div v-if="holderMeta && holderMeta.error" class="pat-hint tiny info">
          资金性质（季报底色）本轮抓取异常：{{ holderMeta.error }}。形态与资金流不受影响，
          仅本页缺少"谁在持有"的底色标签。
        </div>

        <div class="pat-sec tiny muted">突破（粘合后上穿 MA21）· 按资金分排序</div>
        <div v-if="!hits.length" class="small dim" style="margin-top: 6px">今日无标的触发突破</div>
        <div v-for="r in hits" :key="r.code" class="pat-row hit">
          <div class="pat-line1">
            <span class="pat-name">{{ r.name }}</span>
            <span v-if="r.pool === 'zt'" class="pat-chip">{{ r.board }}板</span>
            <span v-else-if="r.pool === 'active'" class="pat-chip act">放量</span>
            <span v-if="r.in_core" class="pat-chip core">核心</span>
            <span class="pat-chip vol" :class="r.vol_ok ? 'ok' : ''">
              量比 {{ fmt(r.vol_ratio) }}<template v-if="r.vol_ok"> · 放量</template>
            </span>
            <span v-if="r.flow_score != null" class="pat-chip flow">
              资金分 {{ r.flow_score }}<template v-if="r.flow_parts > 0 && r.flow_parts < 3">·{{ r.flow_parts }}项</template>
            </span>
            <span v-if="r.lhb" class="pat-chip lhb">上榜</span>
            <span v-else-if="lhbMeta && lhbMeta.today_n" class="pat-chip dim-chip">未上榜</span>
          </div>
          <div class="pat-line2 tiny dim">
            收 {{ r.close }}（<span :class="pctCls(r.pct)">{{ sign(r.pct) }}{{ r.pct }}%</span>）· MA7 {{ r.ma7 }} · MA21 {{ r.ma21 }} · 粘合 {{ r.glue }}% · 已粘合 {{ r.glue_days }} 日
          </div>

          <div v-if="r.flow" class="pat-flow tiny">
            <span :class="pctCls(r.flow.main_net)">
              主力 {{ money(r.flow.main_net) }} · 净占比 {{ fmt(r.flow.main_ratio, 2) }}%
            </span>
            <span class="dim">
              · 超大 {{ money(r.flow.xl_net) }} / 大 {{ money(r.flow.l_net) }} / 中 {{ money(r.flow.m_net) }} / 小 {{ money(r.flow.s_net) }}
            </span>
            <span class="dim">
              · 近3日 <b :class="pctCls(r.flow.sum3)">{{ money(r.flow.sum3) }}</b>
              · 近5日 <b :class="pctCls(r.flow.sum5)">{{ money(r.flow.sum5) }}</b>
              · 连续 {{ r.flow.streak > 0 ? '净流入' + r.flow.streak + '日' : (r.flow.streak < 0 ? '净流出' + (-r.flow.streak) + '日' : '—') }}
            </span>
            <span class="src" :class="r.flow.trend_src === 'sina' ? 'warn' : ''">{{ trendLabel(r.flow) }}</span>
          </div>
          <div v-else class="pat-flow tiny dim">资金流：无数据（北交所旧段 / 停牌 / 接口未返回）</div>

          <div v-if="r.lhb || r.lhb_prev" class="pat-lhb tiny">
            <span v-if="r.lhb" class="lhb-today">上榜 {{ r.lhb.date }}
              <span v-for="(t, i) in r.lhb.tags" :key="i" class="lhb-tag">{{ t }}</span>
            </span>
            <span v-if="r.lhb_prev" class="lhb-prev">{{ r.lhb ? '· ' : '' }}昨上榜({{ r.lhb_prev.date }})
              <span v-for="(t, i) in r.lhb_prev.tags" :key="i" class="lhb-tag prev">{{ t }}</span>
            </span>
            <details v-if="r.lhb" class="lhb-det">
              <summary>席位明细</summary>
              <div class="lhb-box">
                <div><b>上榜原因</b>：{{ (r.lhb.reasons || []).join('；') || '—' }}</div>
                <div v-if="r.lhb.explain"><b>资金标签</b>：{{ r.lhb.explain }}</div>
                <div>
                  <b>买卖</b>：买 {{ money(r.lhb.buy_amt) }} / 卖 {{ money(r.lhb.sell_amt) }}
                  / 净 {{ money(r.lhb.net_amt) }}（占成交 {{ fmt(r.lhb.net_ratio, 2) }}%）
                </div>
                <div v-if="r.lhb.inst">
                  <b>机构席位</b>：买 {{ money(r.lhb.inst.buy) }} / 卖 {{ money(r.lhb.inst.sell) }}
                  / 净 <b :class="pctCls(r.lhb.inst.net)">{{ money(r.lhb.inst.net) }}</b>
                </div>
                <div v-else class="dim">机构席位：无</div>
                <div v-if="seatKinds(r.lhb).length" class="seatkinds">
                  <b>席位性质</b>（当日谁在买）：
                  <span v-for="(s, i) in seatKinds(r.lhb)" :key="i"
                        class="seatkind" :class="{ inst: s.kind === '机构专用', north: s.kind === '北向专用' }">
                    {{ s.kind }} {{ s.d.n }} 席 · 净{{ money(s.d.net) }}
                  </span>
                </div>
                <div v-if="(r.lhb.seats_buy || []).length">
                  <b>买入席位</b>：
                  <div v-for="(x, i) in r.lhb.seats_buy" :key="i" class="seat">
                    {{ x.name }} — 买 {{ money(x.buy) }} / 卖 {{ money(x.sell) }} / 净 {{ money(x.net) }}
                  </div>
                </div>
                <div v-if="(r.lhb.seats_sell || []).length">
                  <b>卖出席位</b>：
                  <div v-for="(x, i) in r.lhb.seats_sell" :key="i" class="seat">
                    {{ x.name }} — 买 {{ money(x.buy) }} / 卖 {{ money(x.sell) }} / 净 {{ money(x.net) }}
                  </div>
                </div>
                <div class="dim">
                  上榜后：1日 {{ fmt(r.lhb.fwd && r.lhb.fwd.d1, 2) }}% · 2日 {{ fmt(r.lhb.fwd && r.lhb.fwd.d2, 2) }}%
                  · 5日 {{ fmt(r.lhb.fwd && r.lhb.fwd.d5, 2) }}% · 10日 {{ fmt(r.lhb.fwd && r.lhb.fwd.d10, 2) }}%
                </div>
              </div>
            </details>
          </div>

          <div v-if="r.holder && !r.holder.failed" class="pat-holder tiny">
            <span class="hold-lead">资金性质</span>
            <span v-for="(t, i) in r.holder.tags" :key="i" class="hold-tag">{{ t }}</span>
            <span class="dim">· 报告期 {{ r.holder.date }}</span>
            <details class="hold-det">
              <summary>明细</summary>
              <div class="hold-box">
                <div class="hold-cap">十大流通股东口径（占流通股 %）</div>
                <div v-for="(x, i) in holderCats(r.holder)" :key="i" class="hold-row">
                  <span class="hold-cat">{{ x.cat }}</span>
                  <span>{{ x.d.n }} 家 · {{ fmt(x.d.pct, 3) }}%</span>
                  <span v-if="x.d.chg != null" :class="pctCls(x.d.chg)">{{ wan(x.d.chg) }}</span>
                  <span v-if="x.d.new" class="hold-new">新进 {{ x.d.new }}</span>
                  <span class="dim hold-names">{{ (x.d.top || []).join('、') }}</span>
                </div>
                <template v-if="holderOrg(r.holder).length">
                  <div class="hold-cap">全体机构口径（比十大完整，二者不可相加）</div>
                  <div v-for="(x, i) in holderOrg(r.holder)" :key="'o' + i" class="hold-row org">
                    <span class="hold-cat">{{ x.cat }}</span>
                    <span>{{ x.d.n == null ? '—' : x.d.n }} 家 · {{ fmt(x.d.pct, 3) }}%</span>
                  </div>
                </template>
                <div v-if="r.holder.ctrl" class="hold-row">
                  <span class="hold-cat">实际控制人</span><span>{{ r.holder.ctrl }}</span>
                </div>
                <div v-if="r.holder.hnum != null" class="hold-row">
                  <span class="hold-cat">股东户数</span>
                  <span>{{ r.holder.hnum.toLocaleString() }} 户</span>
                  <span v-if="r.holder.hnum_chg != null" :class="pctCls(r.holder.hnum_chg)">
                    {{ sign(r.holder.hnum_chg) }}{{ fmt(r.holder.hnum_chg, 1) }}%
                  </span>
                  <span class="dim">{{ r.holder.focus || '' }} {{ r.holder.hnum_date || '' }}</span>
                </div>
                <div v-if="r.holder.h_pct" class="hold-row dim">
                  <span class="hold-cat">H 股（港交所名义持有）</span>
                  <span>{{ fmt(r.holder.h_pct, 2) }}% · 非北向，仅备注</span>
                </div>
                <div v-if="(r.holder.recent || []).length" class="hold-cap">近期持股变动（临时公告口径，比季报新）</div>
                <div v-for="(x, i) in r.holder.recent" :key="'r' + i" class="hold-row subtle">
                  <span class="hold-cat">{{ x.d }}</span>
                  <span class="dim hold-names">{{ x.name }}</span>
                  <span :class="pctCls(x.chg)">{{ x.chg == null ? '—' : (x.chg > 0 ? '增持' : '减持') + (Math.abs(x.chg) / 1e4).toFixed(0) + '万股' }}</span>
                  <span class="dim">{{ x.why }}</span>
                </div>
                <div class="hold-foot dim">
                  季报口径，滞后最多 1 个季度 —— 描述「谁在持有」，不是「今天谁在买」；
                  当日谁在买请看龙虎榜席位的「席位性质」。
                </div>
              </div>
            </details>
          </div>
          <div v-else-if="holderMeta && !holderMeta.error" class="pat-holder tiny dim">
            资金性质：无数据（未进入十大流通股东披露 / 接口未返回）
          </div>

          <div v-if="r.news && r.news.tag && r.news.tag !== '静默'" class="pat-holder tiny">
            <span class="hold-lead">消息面</span>
            <span class="hold-tag" :class="newsTagCls(r.news.tag)">{{ r.news.tag }}</span>
            <span v-if="r.news.when" class="dim">{{ r.news.when }}</span>
            <span v-if="r.news.why" class="dim">· {{ r.news.why }}</span>
            <details v-if="(r.news.titles || []).length" class="hold-det">
              <summary>相关消息 {{ r.news.titles.length }} 条</summary>
              <div class="hold-box news-box">
                <div v-for="(t, i) in r.news.titles" :key="'n' + i" class="news-line tiny dim">{{ t }}</div>
                <div class="hold-foot dim">
                  F10 资讯口径（公告 + 相关新闻），关键词定性宁缺勿滥；
                  T 15:00 收盘后的消息不参与利好/题材定性（风险警示例外，宁可错杀）。
                </div>
              </div>
            </details>
          </div>
        </div>

        <template v-if="watch.length">
          <div class="divider"></div>
          <div class="pat-sec tiny muted">粘合中（尚未突破，观察）</div>
          <div v-for="r in watch" :key="r.code" class="pat-row">
            <div class="pat-line1">
              <span class="pat-name">{{ r.name }}</span>
              <span v-if="r.pool === 'zt'" class="pat-chip">{{ r.board }}板</span>
              <span v-else-if="r.pool === 'active'" class="pat-chip act">放量</span>
              <span v-if="r.in_core" class="pat-chip core">核心</span>
              <span class="pat-chip dim-chip">粘合 {{ r.glue_days }} 日</span>
              <span v-if="r.lhb" class="pat-chip lhb">上榜</span>
            </div>
            <div class="pat-line2 tiny dim">
              收 {{ r.close }}（<span :class="pctCls(r.pct)">{{ sign(r.pct) }}{{ r.pct }}%</span>）· MA7 {{ r.ma7 }} · MA21 {{ r.ma21 }} · 粘合 {{ r.glue }}%
            </div>
            <div v-if="r.holder && r.holder.tags && r.holder.tags.length" class="pat-holder tiny dim">
              <span class="hold-lead">资金性质</span>
              <span v-for="(t, i) in r.holder.tags" :key="i" class="hold-tag sm">{{ t }}</span>
            </div>
            <div v-if="r.news && r.news.tag && r.news.tag !== '静默'" class="pat-holder tiny dim">
              <span class="hold-lead">消息</span>
              <span class="hold-tag sm" :class="newsTagCls(r.news.tag)">{{ r.news.tag }}</span>
              <span v-if="r.news.when" class="dim">{{ r.news.when }}</span>
              <span v-if="r.news.why" class="dim">· {{ r.news.why }}</span>
            </div>
            <div v-if="r.flow" class="pat-flow tiny dim">
              主力 <b :class="pctCls(r.flow.main_net)">{{ money(r.flow.main_net) }}</b>
              · 净占比 {{ fmt(r.flow.main_ratio, 2) }}%
              · 近3日 {{ money(r.flow.sum3) }}
              · 连续 {{ r.flow.streak > 0 ? '净流入' + r.flow.streak + '日' : (r.flow.streak < 0 ? '净流出' + (-r.flow.streak) + '日' : '—') }}
              <span class="src" :class="r.flow.trend_src === 'sina' ? 'warn' : ''">{{ trendLabel(r.flow) }}</span>
            </div>
          </div>
        </template>

        <div class="divider"></div>
        <details class="pat-meta">
          <summary class="tiny muted">口径与免责（务必读一次）</summary>
          <div class="pat-meta-body small dim">
            <div v-if="poolMeta">
              <b>候选池（三源合并）</b>：当日涨停 <b>{{ poolMeta.zt_n }}</b>
              ∪ 核心池 <b>{{ poolMeta.core_n }}</b>
              ∪ 全市场异动池 <b>{{ poolMeta.active_n }}</b> = <b>{{ poolMeta.total_n }}</b> 只。
              <span v-if="poolMeta.only_zt_effective" style="color: var(--orange)">
                ⚠ 异动池本轮为空，池子退化为"仅涨停池"。
              </span>
              异动池口径：{{ poolMeta.criteria.min_pct }}% ≤ 涨幅 &lt; 涨停，且成交额 ≥
              {{ (poolMeta.criteria.amount_min / 1e8).toFixed(0) }}亿，且（量比 ≥
              {{ poolMeta.criteria.vol_min }} 或 换手 ≥ {{ poolMeta.criteria.turn_min }}%），
              按量比取前 {{ poolMeta.criteria.extra_max }} 只。
            </div>
            <div v-else>候选池：当日涨停 ∪ 核心池（历史快照无池子构成信息）。</div>
            <template v-if="holderMeta">
              <div>
                <b>资金性质（季报底色）</b>：把十大流通股东按「公募 / 北向 / QFII / 社保 / 险资 /
                私募 / 产业资本 / 国家队 / 牛散」九类归并（游资不在其中——季报披露不到，由龙虎榜席位回答）。
                数据源为东财 F10 股东研究，<b>报告期滞后最多 1 个季度</b>：它说明<b>谁在持有</b>，
                不说明<b>今天谁在买</b>。缓存 {{ holderMeta.cached_n }} 只 / 池 {{ holderMeta.ask_n }} 只
                （季报换季才刷新，日内零开销）<template v-if="holderMeta.need_n">，本轮待补 {{ holderMeta.need_n }} 只</template>。
                <template v-if="holderMeta.error">⚠ 本轮抓取异常：{{ holderMeta.error }}</template>
              </div>
              <div>
                「十大流通股东口径」与「全体机构口径」<b>是两个不同分母，不能相加</b>：
                前者只统计进入前十大的股东（门槛效应，会低估公募）；后者取自东财机构持仓汇总
                （如茅台进十大的公募仅 1 家 0.365%，全体则有 1697 家合计 3.60%）。
                其中 <b>H 股</b>（<code>香港中央结算(代理人)有限公司</code> / <code>HKSCC NOMINEES</code>）
                单独列出并<b>不计入北向</b>——只有精确的 <code>香港中央结算有限公司</code> 才是沪深股通（北向）。
              </div>
              <div>
                龙虎榜「<b>席位性质</b>」补上了 T+0 的"谁在买"：机构专用 / 沪深股通专用 / 游资营业部。
                与季报底色叠加看更完整（例：底色"公募抱团" + 当日"机构专用净买"）。
              </div>
            </template>
            <div v-if="newsMeta">
              <b>消息面（上涨逻辑）</b>：对信号票抓 T-1 与 T 两天的东财 F10 资讯
              （公告 + 相关新闻），按「<b>性质 × 时点</b>」定性——
              利好·公告（业绩预增/中标/并购/回购等公司行为）＞ 题材·共振（行业或个股新闻）＞
              资金·独行（窗口内无消息，最"干净"的技术突破）；<b>风险·警示</b>
              （减持/澄清/问询/预亏等）优先级最高且<b>宁可错杀</b>。
              时点取定性依据那条的挂网时间；T 15:00 收盘后的消息不参与利好/题材定性
              （风险例外）。关键词定性会有误判，仅供参考，不构成依据。
              <template v-if="newsMeta.error">⚠ 本轮抓取异常：{{ newsMeta.error }}</template>
            </div>
            <div v-if="pt.latest_bar">
              <b>K线新鲜度</b>：池内最新 K 线日 <b>{{ pt.latest_bar }}</b>
              <template v-if="pt.latest_bar === pt.date">（= 快照日，正常）</template>
              <span v-else style="color: var(--orange)">（≠ 快照日 {{ pt.date }}，行情未更新）</span>；
              滞后标的 <b>{{ pt.stale_n }}</b> 只已剔除，不产出信号（防"旧 bar 假突破"）。
            </div>
            <div>参数：MA{{ pt.params.ma_fast }} / MA{{ pt.params.ma_slow }}；粘合阈值 {{ (pt.params.glue_pct * 100).toFixed(1) }}%；持续 ≥{{ pt.params.glue_days }} 日；放量线 {{ pt.params.vol_mult }}×。</div>
            <div>K线为<b>前复权</b>，按本项目惯例仅作形态判断，不与涨跌幅 / 偏离值混用。</div>
            <div>
              资金流为<b>东财口径</b>（主力净额 = 大单 + 超大单），仅加字段并<b>参与排序</b>，
              <b>不参与突破判定</b>（命中数不受影响）。资金分 = 当日净占比 0.5 + 近3日累计 0.3 + 连续天数 0.2，
              各因子先做<b>池内百分位</b>；缺失项自动剔除并<b>重新归一</b>（行尾「N项」= 实际参与因子数）。
            </div>
            <div v-if="flowMeta && flowMeta.srcs">
              多日趋势来源分布：<span v-for="(n, k) in flowMeta.srcs" :key="k">{{ k }}={{ n }} </span>。
              <b>agg</b> = 东财自累积（每日落一行，需连续运行数个交易日）·
              <b>sina</b> = 新浪口径兜底（净流入额口径，绝对值与东财不可比，仅看方向/趋势）·
              <b>none</b> = 非信号票，按需不拉取（趋势只用于信号票的排序/展示）。
            </div>
            <div>
              龙虎榜：当日榜（T，约 18:00 后发布，16:05/16:40 快照为空，21:00 夜间任务补算）
              与前一交易日榜（T-1）<b>两者都存</b>；上榜加标签，未上榜按常态处理。
              净买/净卖为<b>龙虎榜席位口径</b>，非全市场资金流。
            </div>
            <div v-if="flowMeta && flowMeta.errors && flowMeta.errors.length" style="color: var(--orange)">资金流部分失败：{{ flowMeta.errors.join('；') }}</div>
            <div v-if="lhbMeta && lhbMeta.errors && lhbMeta.errors.length" style="color: var(--orange)">龙虎榜部分失败：{{ lhbMeta.errors.join('；') }}</div>
            <div v-if="pt.flow_rows" class="dim">当日已落库资金流样本 {{ pt.flow_rows.length }} 条（供次日算多日累计）。</div>
            <div v-if="pt.errors && pt.errors.length" style="color: var(--orange)">部分标的取数失败：{{ pt.errors.join('；') }}</div>
            <div style="margin-top: 4px">纯技术形态 + 资金/席位辅助，供研究参考，不构成投资建议；需与周期定位、Lab 排雷、verb 风控交叉验证后使用。</div>
          </div>
        </details>
      </template>
    </div>
  </div>
</template>

<style scoped>
.card.pat {
  border-color: rgba(110, 168, 254, 0.32);
  background: linear-gradient(180deg, rgba(110, 168, 254, 0.09), rgba(110, 168, 254, 0.015) 130px), var(--card);
}
.pat-head { display: flex; align-items: center; gap: 10px; }
.pat-badge {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.5px;
  color: #0c1018;
  background: linear-gradient(135deg, #cfe2fb, #6ea8fe 55%, #3d6fb5);
  padding: 6px 9px;
  border-radius: 10px;
  box-shadow: 0 2px 10px rgba(110, 168, 254, 0.35);
}
.pat-stats { margin-top: 12px; }
.pat-sec { margin: 12px 0 4px; }
.pat-hint {
  margin-top: 10px;
  padding: 7px 10px;
  border-radius: var(--r-sm);
  color: #ff6b78;
  background: rgba(255, 77, 94, 0.10);
  border: 1px solid rgba(255, 77, 94, 0.28);
  line-height: 1.5;
}
.pat-hint.info {
  color: var(--t-2);
  background: rgba(110, 168, 254, 0.08);
  border-color: rgba(110, 168, 254, 0.28);
}
.pat-row { padding: 9px 2px; border-bottom: 1px solid var(--line); }
.pat-row:last-child { border-bottom: none; }
.pat-row.hit { background: linear-gradient(90deg, rgba(110, 168, 254, 0.07), rgba(110, 168, 254, 0) 80%); }
.pat-line1 { display: flex; align-items: center; gap: 5px; flex-wrap: wrap; }
.pat-name { font-weight: 700; color: var(--t-1); font-size: 13.5px; }
.pat-chip {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid var(--line);
  color: var(--t-2);
  white-space: nowrap;
}
.pat-chip.core { color: var(--gold); border-color: rgba(233, 183, 92, 0.4); background: var(--gold-dim); }
.pat-chip.vol.ok { color: var(--gold); border-color: rgba(233, 183, 92, 0.4); }
.pat-chip.dim-chip { color: var(--t-3); }
.pat-chip.flow { color: #8fc0ff; border-color: rgba(110, 168, 254, 0.45); background: rgba(110, 168, 254, 0.12); }
.pat-chip.lhb { color: #ffb27a; border-color: rgba(255, 150, 80, 0.45); background: rgba(255, 150, 80, 0.12); }
.pat-chip.stale { color: #ff6b78; border-color: rgba(255, 77, 94, 0.4); background: rgba(255, 77, 94, 0.12); }
/* 候选池来源：全市场异动池（放量、未涨停） */
.pat-chip.act { color: #7ee0b8; border-color: rgba(62, 207, 142, 0.42); background: rgba(62, 207, 142, 0.12); }
.pat-stats .tag.stale { color: #ff6b78; border-color: rgba(255, 77, 94, 0.4); background: rgba(255, 77, 94, 0.10); }
details.stale-det { margin-top: 4px; }
details.stale-det summary { cursor: pointer; color: var(--t-3); }
details.stale-det .seat { padding-left: 10px; color: var(--t-2); }
.pat-line2 { margin-top: 2px; line-height: 1.5; }
.pat-flow { margin-top: 3px; line-height: 1.7; }
.pat-flow .src {
  margin-left: 4px;
  font-size: 10px;
  padding: 0 5px;
  border-radius: 999px;
  color: #8fc0ff;
  border: 1px solid rgba(110, 168, 254, 0.35);
}
.pat-flow .src.warn { color: #ffd479; border-color: rgba(233, 183, 92, 0.45); }
.pat-lhb { margin-top: 4px; line-height: 1.7; }
.lhb-today { color: #ffb27a; font-weight: 600; }
.lhb-prev { color: var(--t-3); margin-left: 6px; }
.lhb-tag {
  display: inline-block;
  margin-left: 4px;
  padding: 0 5px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 500;
  color: #ffb27a;
  background: rgba(255, 150, 80, 0.13);
  border: 1px solid rgba(255, 150, 80, 0.35);
}
.lhb-tag.prev { color: var(--t-2); background: rgba(255, 255, 255, 0.05); border-color: var(--line); }
details.lhb-det { margin-top: 3px; }
details.lhb-det summary { cursor: pointer; color: var(--t-3); font-size: 10px; }
.lhb-box {
  margin-top: 5px;
  padding: 7px 9px;
  border-radius: var(--r-sm);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--line);
  line-height: 1.7;
}
.lhb-box .seat { padding-left: 10px; color: var(--t-2); }
/* 席位性质（T+0 的"谁在买"） */
.seatkinds { margin-top: 2px; }
.seatkind {
  display: inline-block;
  margin: 1px 4px 1px 0;
  padding: 0 5px;
  border-radius: 999px;
  font-size: 10px;
  color: var(--t-2);
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--line);
}
.seatkind.inst { color: #8fc0ff; border-color: rgba(110, 168, 254, 0.45); background: rgba(110, 168, 254, 0.12); }
.seatkind.north { color: #7ee0b8; border-color: rgba(62, 207, 142, 0.42); background: rgba(62, 207, 142, 0.12); }

/* 资金性质（季报底色） */
.pat-holder { margin-top: 3px; line-height: 1.7; }
.hold-lead { font-weight: 600; color: var(--t-2); margin-right: 4px; }
.hold-tag {
  display: inline-block;
  margin: 0 3px 0 0;
  padding: 0 6px;
  border-radius: 999px;
  font-size: 10px;
  color: var(--gold);
  background: var(--gold-dim);
  border: 1px solid rgba(233, 183, 92, 0.4);
  white-space: nowrap;
}
.hold-tag.sm { opacity: 0.88; }
/* 消息面定性：利好=涨红、风险=警示橙 */
.hold-tag.good { color: #ff8f9d; background: rgba(255, 77, 94, 0.12); border-color: rgba(255, 77, 94, 0.45); }
.hold-tag.risk { color: #ffd479; background: rgba(233, 183, 92, 0.12); border-color: rgba(233, 183, 92, 0.5); }
.news-box { display: flex; flex-direction: column; gap: 2px; }
.news-line { line-height: 1.6; }
.news-risk-n { color: #ffd479; font-weight: 600; }
details.hold-det { margin-top: 3px; }
details.hold-det summary { cursor: pointer; color: var(--t-3); font-size: 10px; }
.hold-box {
  margin-top: 5px;
  padding: 7px 9px;
  border-radius: var(--r-sm);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--line);
  line-height: 1.7;
}
.hold-cap {
  margin-top: 5px;
  padding-top: 5px;
  color: var(--t-3);
  font-size: 10px;
  border-top: 1px dashed var(--line);
}
.hold-cap:first-child { margin-top: 0; padding-top: 0; border-top: none; }
.hold-row { display: flex; gap: 6px; flex-wrap: wrap; align-items: baseline; }
.hold-row.org, .hold-row.subtle { opacity: 0.9; }
.hold-cat { flex-shrink: 0; min-width: 80px; color: var(--t-1); font-weight: 600; }
.hold-new {
  padding: 0 5px;
  border-radius: 999px;
  font-size: 10px;
  color: #ffb27a;
  background: rgba(255, 150, 80, 0.12);
  border: 1px solid rgba(255, 150, 80, 0.35);
}
.hold-names { flex: 1 1 auto; min-width: 0; }
.hold-foot { margin-top: 6px; padding-top: 5px; border-top: 1px dashed var(--line); line-height: 1.6; }
.up { color: #ff5d6c; }
.down { color: #3ecf8e; }
details.pat-meta { margin-top: 10px; }
details.pat-meta summary { cursor: pointer; }
.pat-meta-body {
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: var(--r-sm);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--line);
  line-height: 1.6;
}
</style>
