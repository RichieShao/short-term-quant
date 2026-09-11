<script setup>
import { computed, ref, onMounted } from 'vue'
import { useSnap } from '../stores/snap'
import { callApi } from '../api/cloud'
import HeatGauge from '../components/HeatGauge.vue'
import SparkLine from '../components/SparkLine.vue'
import CycleBar from '../components/CycleBar.vue'
import { pct, signed, pctCls, bandColor, stageColor, shortDate, num } from '../utils/format'

const s = useSnap()

const sent = computed(() => s.sentiment || {})
const cyc = computed(() => s.cycle || {})
const heatSeries = computed(() => (s.series || []).map((x) => x.heat))

/**
 * 数据新鲜度判定（北京时间）。
 *  快照日 == 今天           → 无提示
 *  工作日且已过 17:00 仍非当日 → warn（可能休市，也可能定时任务失败）
 *  落后 ≥9 个自然日          → bad（超过最长法定连休，基本可判定任务中断）
 *  其余（周末/隔夜/短假）     → info 中性告知
 */
const stale = computed(() => {
  const d = s.date
  if (!d) return null
  const bj = new Date(Date.now() + 8 * 3600 * 1000) // 换算北京时间
  const today = bj.toISOString().slice(0, 10)
  if (d === today) return null
  const lag = Math.round((Date.parse(today) - Date.parse(d)) / 86400000)
  if (lag >= 9) return { lv: 'bad', t: `快照已 ${lag} 天未更新，请检查每日定时任务` }
  const dow = bj.getUTCDay()
  if (dow >= 1 && dow <= 5 && bj.getUTCHours() >= 17)
    return { lv: 'warn', t: `今日已收盘，快照仍为 ${d}；若非休市可手动重算` }
  return { lv: 'info', t: `当前展示 ${d} 收盘快照` }
})

// 冰点反转信号监测（退潮/冰点期快照自动激活；口径=溢价转正+首板批量，同现才触发）
const rev = computed(() => (s.snap && s.snap.reversal) || null)

/* 温度计增强：分项构成 / 动量 / 历史分位（纯展示，不改温度本身） */
const heatDetail = computed(() => (s.snap && s.snap.heat_detail) || {})
const bd = computed(() => heatDetail.value.breakdown || {})
const bdParts = computed(() => {
  const list = bd.value.parts || []
  return list.map((p) => {
    let rawText = '—'
    if (p.raw != null) {
      if (p.key === 'zb') rawText = (p.raw * 100).toFixed(1) + '%'
      else if (p.key === 'premium') rawText = (p.raw * 100).toFixed(2) + '%'
      else rawText = p.raw + (p.unit || '')
    }
    const isPenalty = p.max == null
    const ratio = isPenalty ? Math.min(1, Math.abs(p.ratio || 0)) : Math.min(1, p.ratio || 0)
    return {
      ...p,
      rawText,
      isPenalty,
      barW: Math.max(2, ratio * 100) + '%',
      scoreText: (p.score > 0 && isPenalty ? '-' : '') + Math.abs(p.score).toFixed(1),
      maxText: isPenalty ? '最多 -20' : '/ ' + p.max,
      cls: p.missing ? 'miss' : isPenalty ? 'pen' : '',
    }
  })
})
const mom = computed(() => heatDetail.value.momentum || {})
const momText = computed(() => {
  const m = mom.value
  if (m.d3 == null) return ''
  const v = m.d3
  return `近3日 ${v > 0 ? '+' : ''}${v} · ${m.trend}`
})
const pctInfo = computed(() => {
  const p = heatDetail.value.percentile || {}
  if (!p.ready) return { ok: false, t: `历史分位：样本积累中 ${p.n || 0}/${p.need || 12} 日` }
  return {
    ok: true,
    t: `历史分位 ${p.pct}%（${p.quartile}）${p.low_sample ? ' · 样本偏少' : ''}`,
    label: p.label,
    low: !!p.low_sample,
  }
})

/* 系统健康（job_runs 留痕）：任务中断/数据源报错时直接在首页看到原因 */
const health = ref(null)
const hRuns = computed(() => (health.value && health.value.runs) || [])
const hLast = computed(() => hRuns.value[0] || null)
const hErrs = computed(() => (health.value && health.value.last_errors) || null)
const hTime = (ts) => {
  if (!ts) return '—'
  return new Date(ts + 8 * 3600 * 1000).toISOString().slice(5, 16).replace('T', ' ')
}
onMounted(async () => {
  try {
    const r = await callApi('health', { n: 8 })
    if (r && r.ok) health.value = r
  } catch (e) { /* 健康卡为辅助信息，失败不打扰 */ }
})

const revCond = computed(() => {
  const r = rev.value
  if (!r || !r.active) return null
  return {
    prem: `${signed(r.premium, 2)}%（${r.premium_ok ? '✓ 已转正' : '未转正'}）`,
    fb: `${r.fb_today} 家 / 5日均 ${r.fb_ma5}（${r.fb_ok ? '✓ 放量' : '未放量'}）`,
  }
})

const metrics = computed(() => {
  const x = sent.value
  return [
    { k: '涨停', v: x.lu ?? '—', cls: 'up' },
    { k: '跌停', v: x.ld ?? '—', cls: 'down' },
    { k: '炸板率', v: x.zb_rate != null ? Math.round(x.zb_rate * 100) + '%' : '—', cls: '' },
    { k: '最高板', v: x.max_board != null ? x.max_board + '板' : '—', cls: '' },
    { k: '连板家数', v: x.conn ?? '—', cls: '' },
    { k: '昨涨停溢价', v: signed(x.premium, 1), cls: pctCls(x.premium) },
  ]
})

// 首板启动：前排首板（按首封时间升序）与行业分布（盘面总览，更前置的"刚启动"信号）
const TOP_FIRST = 10
const TOP_IND = 5
const topFirst = computed(() => s.firstboards.slice(0, TOP_FIRST))
const topIndustries = computed(() => s.firstboardsIndustries.slice(0, TOP_IND))
function fmtSeal(v) {
  if (v == null) return '—'
  const t = String(v).padStart(6, '0')
  return t.slice(0, 2) + ':' + t.slice(2, 4)
}

// 连板天梯明细：每个板位的实际个股（≥2 板），由低到高；展示时反转为 高→低
const ladderDetail = computed(() => (s.snap && s.snap.ladder_detail) || [])
const maxBoard = computed(() =>
  ladderDetail.value.length ? Math.max(...ladderDetail.value.map((d) => d.board)) : 0)
const ladderConn = computed(() => ladderDetail.value.reduce((a, d) => a + d.count, 0))
const maxCount = computed(() =>
  ladderDetail.value.length ? Math.max(...ladderDetail.value.map((d) => d.count)) : 1)
const ladderDetailDesc = computed(() => [...ladderDetail.value].sort((a, b) => b.board - a.board))
// 中位断层：最高板与最低板之间缺失的板位
const gapNote = computed(() => {
  const bs = ladderDetail.value.map((d) => d.board).sort((a, b) => a - b)
  if (bs.length < 2) return ''
  const miss = []
  for (let b = bs[0]; b <= bs[bs.length - 1]; b++) if (!bs.includes(b)) miss.push(b)
  return miss.length
    ? `中位断层：${miss.map((b) => b + '板').join('、')} 无人接 → 退潮期不接力中位`
    : ''
})
// 高度色阶：低板青蓝(199°) → 高板红橙(12°)
function boardColor(b) {
  const hi = maxBoard.value > 2 ? maxBoard.value : 3
  const t = hi > 2 ? (b - 2) / (hi - 2) : 0
  return `hsl(${Math.round(199 - t * 187)}, 85%, 62%)`
}
function barW(c) {
  return Math.max(10, Math.round((c / maxCount.value) * 100)) + '%'
}

// 需人工确认：把后台生成的 "名称 等级(分数分)：理由" 文本解析为结构化卡片
const watchItems = computed(() => {
  const list = (s.actions && s.actions.watch) || []
  const re = /^(.+?)\s+([SABC])级\((\d+)分\)[：:]\s*(.*)$/
  return list.map((w) => {
    const m = w.match(re)
    if (!m) return { name: '', grade: '', score: '', body: w, status: '' }
    const body = m[4]
    let status = ''
    if (/可升\s*A\s*级参与/.test(body)) status = 'gold'
    else if (body.includes('仍不足参与')) status = 'muted'
    else if (body.includes('禁接力')) status = 'red'
    return { name: m[1], grade: m[2], score: m[3], body, status }
  })
})
function statusText(st) {
  return st === 'gold' ? '可升A参与' : st === 'muted' ? '暂不足' : st === 'red' ? '禁接力' : ''
}
</script>

<template>
  <div class="page">
    <!-- 数据新鲜度 -->
    <div v-if="stale" class="banner" :class="stale.lv">
      <span class="dot"></span>
      <span class="small grow">{{ stale.t }}</span>
      <button v-if="stale.lv !== 'info'" class="btn" :disabled="s.loading" @click="s.refresh()">
        {{ s.loading ? '重算中…' : '立即重算' }}
      </button>
    </div>

    <!-- 冰点反转信号监测（退潮/冰点期自动激活） -->
    <div v-if="rev && rev.active" class="banner rev" :class="rev.triggered ? 'fire' : 'watch'">
      <span class="dot"></span>
      <span class="small grow">
        <b>冰点反转信号 · {{ rev.triggered ? '🔥 已触发' : '监测中' }}</b>
        <template v-if="revCond">　溢价 {{ revCond.prem }}　·　首板 {{ revCond.fb }}</template>
        <div v-if="rev.hint" class="rev-hint">{{ rev.hint }}</div>
      </span>
    </div>

    <!-- 大盘 -->
    <div class="card">
      <div class="card-title">大盘环境</div>
      <div class="idx">
        <div v-for="m in s.market" :key="m.code" class="idx-item">
          <div class="tiny muted">{{ m.name }}</div>
          <div class="mono v" :class="pctCls(m.pct)">{{ signed(m.pct) }}</div>
          <div class="tiny muted mono">{{ num(m.close, 2) }}</div>
        </div>
        <div v-if="!s.market.length" class="small muted">指数数据不可用</div>
      </div>
    </div>

    <!-- 温度计 -->
    <div class="card heat">
      <div class="card-title">
        情绪温度计
        <span v-if="momText" class="hd-mom mono" :class="mom.d3 > 0 ? 'up' : mom.d3 < 0 ? 'down' : ''">
          {{ momText }}
        </span>
      </div>
      <div class="row" style="gap: 16px; align-items: center">
        <HeatGauge :value="sent.heat || 0" :band="sent.band" />
        <div class="grow">
          <div class="grid2">
            <div v-for="m in metrics" :key="m.k" class="mtr">
              <div class="tiny muted">{{ m.k }}</div>
              <div class="mono mv" :class="m.cls">{{ m.v }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 历史分位 -->
      <div class="hd-pct" :class="{ ready: pctInfo.ok }">
        <div class="pct-bar">
          <i :style="{ width: (pctInfo.ok ? (heatDetail.percentile.pct || 0) : (heatDetail.percentile.n / heatDetail.percentile.need) * 100) + '%' }"></i>
        </div>
        <span class="tiny">{{ pctInfo.t }}<template v-if="pctInfo.label"> · {{ pctInfo.label }}</template></span>
      </div>

      <!-- 温度构成拆解 -->
      <div class="divider"></div>
      <div class="hd-h">
        <span>温度构成（权重 40/20/15/10/15，跌停最多 -20）</span>
        <span class="tiny muted mono">合计 {{ bd.heat }} / 原始 {{ bd.raw_total }}</span>
      </div>
      <div v-for="p in bdParts" :key="p.key" class="bd-row">
        <span class="bd-label">{{ p.label }}</span>
        <span class="bd-raw mono tiny">{{ p.rawText }}</span>
        <div class="bd-bar">
          <div class="bar"><i :class="p.cls" :style="{ width: p.barW }"></i></div>
        </div>
        <span class="bd-score mono" :class="p.cls">{{ p.scoreText }}<span class="tiny muted"> {{ p.maxText }}</span></span>
      </div>
      <div class="tiny muted mt">
        各项由「原始值 ÷ 刻度」线性给分（刻度经 P4 一年回放校准：涨停 100 家 / 高板 13 板 / 连板 28 家）。
        <template v-if="bd.missing_keys && bd.missing_keys.length">
          本日缺 {{ bd.missing_keys.join('、') }} 输入 → 对应项按降级口径处理。
        </template>
      </div>

      <div class="divider"></div>
      <div class="tiny muted" style="margin-bottom: 4px">近 6 日温度走势</div>
      <SparkLine :values="heatSeries" :color="bandColor(sent.band)" />
      <div class="row between tiny muted mono" style="margin-top: 2px">
        <span v-for="x in s.series" :key="x.date">{{ shortDate(x.date) }}</span>
      </div>
    </div>

    <!-- 周期 -->
    <div class="card">
      <div class="card-title">周期定位</div>
      <div class="row" style="gap: 8px; align-items: baseline">
        <span class="stage" :style="{ color: stageColor(cyc.stage) }">{{ cyc.stage }}</span>
        <span class="tag">{{ cyc.trend || '—' }}</span>
        <span class="tag gold">{{ sent.lu }} 家涨停</span>
      </div>
      <div style="margin: 14px 0 6px">
        <CycleBar :stage="cyc.stage" :trend="cyc.trend" />
      </div>
      <div v-for="(r, i) in cyc.reasons || []" :key="i" class="small dim reason">· {{ r }}</div>
      <div v-if="cyc.tone" class="tone">
        <span class="tag gold">操作基调</span>
        <span class="small">{{ cyc.tone }}</span>
      </div>
    </div>

    <!-- 首板启动（总览：更前置的"刚启动"信号，置于天梯之前形成 1板→2+板 梯度） -->
    <div class="card fb" v-if="s.firstboards.length">
      <div class="card-title">首板启动 · {{ s.firstboards.length }} 只 1 板</div>
      <div class="small dim fb-sub">
        更前置的「刚启动」信号：连板≥2 进入核心池的前一站。按首封时间排序，前排即日内资金最先点火的方向。
      </div>
      <div class="fb-list">
        <div class="fb-row" v-for="x in topFirst" :key="x.code">
          <span class="fb-time mono">{{ fmtSeal(x.first_seal) }}</span>
          <span class="fb-name">{{ x.name }}</span>
          <span class="fb-ind">{{ x.industry || '—' }}</span>
          <span class="fb-pct" :class="pctCls(x.pct)">{{ pct(x.pct) }}</span>
        </div>
      </div>
      <div class="tiny muted fb-more" v-if="s.firstboards.length > topFirst.length">
        仅显示前 {{ topFirst.length }} 只，全量 {{ s.firstboards.length }} 只
      </div>
      <div class="fb-ind-head tiny muted">首板行业分布 · TOP{{ TOP_IND }}</div>
      <div class="row wrap" style="gap: 6px; margin-top: 6px">
        <span class="fb-chip" v-for="it in topIndustries" :key="it.name">
          {{ it.name }} · {{ it.count }}
        </span>
      </div>
    </div>

    <!-- 连板天梯（细化：每个板位列出实际个股 + 空间龙/中位断层标注） -->
    <div class="card ladder" v-if="s.snap && (s.snap.ladder_detail || s.snap.ladder_text)">
      <div class="card-title">连板天梯
        <span class="lt-sub" v-if="ladderDetail.length">最高 {{ maxBoard }}板 · 连板 {{ ladderConn }}只</span>
      </div>
      <template v-if="ladderDetail.length">
        <div v-if="gapNote" class="lt-gap">{{ gapNote }}</div>
        <div class="lt-rungs">
          <div class="lt-rung" v-for="lv in ladderDetailDesc" :key="lv.board"
               :style="{ borderLeftColor: boardColor(lv.board) }">
            <div class="lt-head">
              <span class="lt-badge" :style="{ background: boardColor(lv.board) }">{{ lv.board }}板</span>
              <span v-if="lv.board === maxBoard" class="lt-tag dragon">空间龙</span>
              <span class="lt-count">{{ lv.count }}只</span>
              <span class="lt-bar"><i :style="{ width: barW(lv.count), background: boardColor(lv.board) }"></i></span>
            </div>
            <div class="lt-chips">
              <span class="lt-chip" v-for="st in lv.stocks" :key="st.code">{{ st.name }}</span>
            </div>
          </div>
        </div>
        <div class="tiny muted lt-foot">天梯读法：高度定天花板(空间龙) → 梯队看是否连续(断层=中位弱) → 密度看 2 板广度(低位生源)</div>
      </template>
      <div v-else class="small mono dim">{{ s.snap.ladder_text }}</div>
    </div>

    <!-- 纪律 -->
    <div class="card" v-if="(s.actions && (s.actions.rules || []).length) || (s.actions && (s.actions.watch || []).length)">
      <div class="card-title">今日纪律</div>
      <div v-for="(r, i) in s.actions.rules || []" :key="'r' + i" class="small dim rule">· {{ r }}</div>
      <template v-if="watchItems.length">
        <div class="divider"></div>
        <div class="tiny muted" style="margin-bottom: 6px">需人工确认</div>
        <div v-for="(w, i) in watchItems" :key="'w' + i" class="watch-item" :class="w.status === 'gold' ? 'w-gold' : w.status === 'red' ? 'w-red' : ''">
          <div class="watch-head">
            <span class="watch-name">{{ w.name }}</span>
            <span class="watch-grade" v-if="w.grade">{{ w.grade }}级</span>
            <span class="watch-score" v-if="w.score">{{ w.score }}分</span>
            <span v-if="w.status" class="watch-status" :class="w.status">{{ statusText(w.status) }}</span>
          </div>
          <div class="watch-body small dim">{{ w.body }}</div>
        </div>
      </template>
    </div>

    <!-- 系统健康：任务运行留痕（正常时一行小字，异常时高亮并给出原因） -->
    <div class="card health" v-if="hLast" :class="{ 'hl-bad': !hLast.ok || hErrs || health.fail_count > 0 }">
      <div class="card-title">系统健康</div>
      <div class="tiny muted">
        最近运行 {{ hLast.d }} {{ hTime(hLast.ts) }} · 耗时
        {{ hLast.cost_ms ? (hLast.cost_ms / 1000).toFixed(1) + 's' : '—' }} ·
        <b :class="hLast.ok ? 'up' : 'down'">{{ hLast.ok ? (hLast.skipped ? '跳过（非交易日）' : '成功') : '失败' }}</b>
        <span v-if="hLast.error"> · {{ hLast.error }}</span>
      </div>
      <div v-if="hErrs && hErrs.length" class="small dim mt">
        当日计算告警：{{ hErrs.join('；') }}
      </div>
      <div v-if="health.fail_count > 0" class="tiny muted mt">
        近 {{ hRuns.length }} 次运行失败 {{ health.fail_count }} 次 · 最近失败：
        {{ health.last_fail ? health.last_fail.d + ' ' + (health.last_fail.error || '') : '—' }}
      </div>
      <div v-else class="tiny muted mt">每交易日 16:05 / 16:40 自动更新，失败会在此留痕。</div>
    </div>

    <div class="tiny muted center">
      数据快照 {{ s.snap && s.snap.generated_at ? s.snap.generated_at : '—' }} 生成 · 仅供个人研究
    </div>
  </div>
</template>

<style scoped>
.idx { display: flex; gap: 10px; }
.idx-item {
  flex: 1;
  padding: 10px 8px;
  border-radius: var(--r-md);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--line);
  text-align: center;
}
.idx-item .v { font-size: 16px; font-weight: 700; margin: 2px 0; }
.grid2 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px 8px; }
.mv { font-size: 15.5px; font-weight: 600; }
.stage { font-size: 19px; font-weight: 700; }
.reason { margin-top: 5px; }
.tone { margin-top: 12px; display: flex; align-items: flex-start; gap: 8px; }
.rule { margin-bottom: 5px; }
.center { text-align: center; margin-top: 6px; }

/* 需人工确认卡片 */
.watch-item {
  padding: 8px 10px;
  border-radius: var(--r-sm);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--line);
  margin-bottom: 7px;
}
.watch-item:last-child { margin-bottom: 0; }
.watch-item.w-gold { border-left: 3px solid var(--gold); }
.watch-item.w-red { border-left: 3px solid var(--up); }
.watch-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 4px; }
.watch-name { font-weight: 700; color: var(--t-1, #e8ecf4); font-size: 13px; }
.watch-grade {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 5px;
  background: var(--gold-dim, rgba(233, 183, 92, 0.15));
  color: var(--gold);
  border: 1px solid rgba(233, 183, 92, 0.3);
}
.watch-score { font-size: 11px; color: var(--t-2); }
.watch-status { margin-left: auto; font-size: 10.5px; font-weight: 700; padding: 2px 9px; border-radius: 999px; }
.watch-status.gold { color: #0c1018; background: var(--gold); }
.watch-status.muted { color: var(--t-2); background: rgba(255, 255, 255, 0.08); border: 1px solid var(--line); }
.watch-status.red { color: #fff; background: var(--up); }
.watch-body { line-height: 1.5; font-size: 12px; }

/* 数据新鲜度提示条 */
.banner {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 9px 12px;
  margin-bottom: 12px;
  border-radius: var(--r-md);
  border: 1px solid var(--line);
  background: var(--card);
}
.banner .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--t-3);
}
.banner.info { color: var(--t-2); }
.banner.warn {
  color: var(--orange);
  border-color: rgba(255, 159, 67, 0.34);
  background: linear-gradient(180deg, rgba(255, 159, 67, 0.11), rgba(255, 159, 67, 0.05));
}
.banner.warn .dot { background: var(--orange); box-shadow: 0 0 8px rgba(255, 159, 67, 0.75); }
.banner.bad {
  color: var(--up);
  border-color: rgba(255, 77, 94, 0.36);
  background: linear-gradient(180deg, rgba(255, 77, 94, 0.12), rgba(255, 77, 94, 0.05));
}
.banner.bad .dot { background: var(--up); box-shadow: 0 0 8px rgba(255, 77, 94, 0.8); }
.banner .btn { flex-shrink: 0; font-size: 11.5px; padding: 5px 10px; }

/* 冰点反转信号监测条 */
.banner.rev { align-items: flex-start; }
.banner.rev .small { line-height: 1.55; }
.banner.rev .rev-hint { margin-top: 3px; font-size: 11px; color: var(--t-3); }
.banner.rev.watch {
  color: var(--orange);
  border-color: rgba(255, 159, 67, 0.34);
  background: linear-gradient(180deg, rgba(255, 159, 67, 0.1), rgba(255, 159, 67, 0.04));
}
.banner.rev.watch .dot {
  background: var(--orange);
  box-shadow: 0 0 8px rgba(255, 159, 67, 0.75);
  animation: revPulse 2s ease-in-out infinite;
}
.banner.rev.fire {
  color: var(--gold);
  border-color: rgba(233, 183, 92, 0.5);
  background: linear-gradient(180deg, rgba(233, 183, 92, 0.16), rgba(233, 183, 92, 0.06));
  box-shadow: 0 0 14px rgba(233, 183, 92, 0.18);
}
.banner.rev.fire .dot {
  background: var(--gold);
  box-shadow: 0 0 10px rgba(233, 183, 92, 0.9);
  animation: revPulse 1s ease-in-out infinite;
}
.banner.rev.fire .rev-hint { color: var(--gold); opacity: 0.85; }
@keyframes revPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

/* 温度计增强：动量 / 历史分位 / 构成拆解 */
.card-title { position: relative; }
/* 系统健康：异常时琥珀描边提示 */
.health.hl-bad {
  border-color: rgba(255, 213, 138, 0.45);
  background: rgba(255, 213, 138, 0.05);
}
.hd-mom {
  position: absolute; right: 0; top: 0;
  font-size: 11px; font-weight: 600; color: var(--t-3);
}
.hd-mom.up { color: var(--up); }
.hd-mom.down { color: var(--down); }

.hd-pct { margin-top: 10px; }
.hd-pct .pct-bar {
  height: 5px; border-radius: 999px; overflow: hidden;
  background: rgba(255, 255, 255, 0.07); margin-bottom: 4px;
}
.hd-pct .pct-bar > i {
  display: block; height: 100%; border-radius: 999px;
  background: linear-gradient(90deg, var(--blue), var(--gold));
  transition: width 0.7s cubic-bezier(0.22, 0.9, 0.3, 1);
}
.hd-pct.ready .pct-bar > i { background: linear-gradient(90deg, var(--gold), var(--orange)); }
.hd-pct .tiny { color: var(--t-3); }
.hd-pct.ready .tiny { color: var(--gold); }

.hd-h {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 8px; font-size: 11.5px; color: var(--t-2); margin-bottom: 8px;
}
.bd-row {
  display: grid; grid-template-columns: 68px 52px 1fr 78px;
  align-items: center; gap: 8px; padding: 4px 0;
}
.bd-label { font-size: 11.5px; color: var(--t-2); white-space: nowrap; }
.bd-raw { text-align: right; color: var(--t-3); font-size: 11px; }
.bd-score { text-align: right; font-size: 11.5px; font-weight: 600; color: var(--t-1); }
.bd-score .tiny { font-weight: 400; }
.bd-score.pen, .bd-row .bar > i.pen {
  color: var(--down);
  background: linear-gradient(90deg, var(--down), #34d399);
}
.bd-score.miss, .bd-label + .bd-raw.miss { color: var(--t-3); opacity: 0.6; }
.bd-row .bar > i.miss {
  background: repeating-linear-gradient(
    45deg, rgba(255, 255, 255, 0.14) 0 3px, rgba(255, 255, 255, 0.05) 3px 6px);
}

/* 首板启动卡片 */
.fb-sub { margin-bottom: 10px; line-height: 1.5; }
.fb-list {
  display: flex;
  flex-direction: column;
  max-height: 300px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}
.fb-row {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr) minmax(0, 1fr) 60px;
  align-items: center;
  gap: 6px;
  padding: 7px 4px;
  border-bottom: 1px solid var(--line);
  font-size: 12.5px;
}
.fb-row:last-child { border-bottom: none; }
.fb-time { color: #67e8f9; font-size: 12px; }
.fb-name { color: var(--t-1, #e8ecf4); font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.fb-ind { color: var(--t-2); font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.fb-pct { text-align: right; font-weight: 700; }
.fb-more { margin-top: 4px; }
.fb-ind-head { margin-top: 12px; margin-bottom: 2px; }
.fb-chip {
  padding: 3px 9px;
  border-radius: 999px;
  background: var(--gold-dim);
  border: 1px solid rgba(233, 183, 92, 0.35);
  color: var(--gold);
  font-size: 11.5px;
  white-space: nowrap;
}

/* 连板天梯（细化） */
.lt-sub { font-size: 11px; font-weight: 500; color: var(--t-2); margin-left: 8px; }
.lt-gap {
  font-size: 11.5px;
  color: var(--orange);
  background: rgba(255, 159, 67, 0.1);
  border: 1px solid rgba(255, 159, 67, 0.3);
  border-radius: var(--r-sm);
  padding: 5px 8px;
  margin-bottom: 10px;
  line-height: 1.5;
}
.lt-rungs { display: flex; flex-direction: column; gap: 8px; }
.lt-rung {
  border-left: 3px solid var(--line);
  border-radius: var(--r-sm);
  background: rgba(255, 255, 255, 0.03);
  padding: 8px 10px;
}
.lt-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.lt-badge {
  font-size: 12px;
  font-weight: 700;
  color: #0c1018;
  padding: 2px 8px;
  border-radius: 6px;
  white-space: nowrap;
}
.lt-tag {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 999px;
  white-space: nowrap;
}
.lt-tag.dragon { color: #0c1018; background: var(--gold); }
.lt-count { font-size: 11.5px; color: var(--t-2); font-weight: 600; white-space: nowrap; }
.lt-bar {
  flex: 1;
  height: 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.07);
  overflow: hidden;
  min-width: 24px;
}
.lt-bar > i { display: block; height: 100%; border-radius: 999px; min-width: 6px; }
.lt-chips { display: flex; flex-wrap: wrap; gap: 5px; }
.lt-chip {
  font-size: 11.5px;
  padding: 2px 7px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid var(--line);
  color: var(--t-1);
  white-space: nowrap;
}
.lt-foot { margin-top: 10px; line-height: 1.5; }
</style>
