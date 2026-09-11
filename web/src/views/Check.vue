<script setup>
import { ref, computed, onMounted } from 'vue'
import { callApi } from '../api/cloud'
import { useSnap } from '../stores/snap'
import SparkLine from '../components/SparkLine.vue'
import { signed, num } from '../utils/format'

const s = useSnap()
const lab = computed(() => s.lab)

const code = ref('')
const loading = ref(false)
const err = ref('')
const data = ref(null)

async function query() {
  const c = String(code.value).trim()
  if (!c) return
  loading.value = true
  err.value = ''
  data.value = null
  try {
    const r = await callApi('stock', { code: c, full: '1' })
    if (r && r.ok) data.value = r
    else err.value = (r && r.error) || '查询失败'
  } catch (e) {
    err.value = e.message || String(e)
  } finally {
    loading.value = false
  }
}

const dev = (k) => (data.value && data.value.dev ? data.value.dev[k] : null)
const lvlCls = computedLvl()

function computedLvl() {
  return () => {
    const l = data.value && data.value.dev && data.value.dev.risk_level
    if (l === '严重异动') return 'red'
    if (l === '高危接近') return 'gold'
    return ''
  }
}

const closes = () => (data.value?.klines || []).map((k) => k.c)

// ---- 分析系统·实验室（Lab）渲染辅助 ----
const MAX_LAB = 15
/* 自选盯票池：云端存一份 codes（无登录态，多设备共享），点选即体检 */
const wl = ref([])
const wlQuotes = ref([])
const wlInput = ref('')
const wlBusy = ref(false)

async function loadQuotes() {
  if (!wl.value.length) return (wlQuotes.value = [])
  try {
    const r = await callApi('quotes', { codes: wl.value.join(',') })
    wlQuotes.value = (r && r.list) || []
  } catch (e) {
    wlQuotes.value = []
  }
}
async function saveWatchlist(codes) {
  wlBusy.value = true
  try {
    const r = await callApi('watchlist', { codes })
    wl.value = (r && r.codes) || codes
    await loadQuotes()
  } catch (e) { /* 忽略 */ } finally {
    wlBusy.value = false
  }
}
async function loadWatchlist() {
  try {
    const r = await callApi('watchlist')
    wl.value = (r && r.codes) || []
    await loadQuotes()
  } catch (e) { /* 忽略 */ }
}
function addWl() {
  const v = String(wlInput.value || '').trim()
  if (!v) return
  const m = /^(\d{6})$/.exec(v)
  const c = m ? (/^(6|9)/.test(m[1]) ? 'sh' + m[1] : 'sz' + m[1]) : v
  if (!wl.value.includes(c)) saveWatchlist([...wl.value, c])
  wlInput.value = ''
}
function delWl(c) {
  saveWatchlist(wl.value.filter((x) => x !== c))
}
function pickWl(c) {
  code.value = c.replace(/^(sh|sz|bj)/, '')
  query()
}
onMounted(loadWatchlist)

const labShow = ref(MAX_LAB)
const showLabAll = () => { labShow.value = lab.value.ranks.length }
const showLabPart = () => { labShow.value = MAX_LAB }

const ranks = computed(() => lab.value ? (lab.value.ranks || []).slice(0, labShow.value) : [])
const vetoed = computed(() => (lab.value && lab.value.vetoed) || [])
const weights = computed(() => {
  const w = (lab.value && lab.value.weights) || {}
  return { q: Math.round((w.q || 0) * 100), e: 100 - Math.round((w.q || 0) * 100) }
})

function verbCls(v) {
  if (v === '禁接力' || v === '规避/清仓' || v === '减/剔除') return 'red'
  if (v === '空仓') return ''
  return 'gold'
}
function labCls(v) {
  if (v == null) return ''
  if (v >= 75) return 'lab-hi'
  if (v >= 62) return 'lab-md'
  return ''
}
const STAGE_CLS = { 启动: 'st-start', 发酵: 'st-ferment', 高潮: 'st-peak', 退潮: 'st-ebb', 震荡: 'st-shock' }
function stageCls(st) { return STAGE_CLS[st] || '' }
function peakWarn(i) { return (lab.value && lab.value.stage === '高潮') && i < 3 }
function vetoReds(v) { return (v.flags || []).filter((f) => f.lv === 'red') }
function vetoYellows(v) { return (v.flags || []).filter((f) => f.lv === 'yellow') }
function flagTxt(r) {
  const ys = (r.flags || []).filter((f) => f.lv === 'yellow')
  return ys.map((f) => f.t).join('；')
}
function greenTxt(r) {
  return (r.greens || []).map((g) => g.t + (g.date ? '（' + g.date.slice(5) + '）' : '')).join('；')
}
function fmtYi(v) { return v == null ? '—' : num(v, 0) + '亿' }
function fmtPe(r) {
  if (r.pe == null) return 'PE —'
  return 'PE ' + num(r.pe, 0) + (r.pe_src === 'TTM' ? '' : '(动)')
}
</script>

<template>
  <div class="page">
    <!-- 分析系统 · 实验室（价值框架蒸馏 × 当日候选池） -->
    <div class="card lab">
      <div class="lab-head">
        <div class="lab-badge">Lab</div>
        <div class="grow">
          <div class="card-title" style="margin: 0">分析系统 · 实验室</div>
          <div class="tiny muted">蒸馏自《股市进阶之道》三位一体 + 14维四族，对当日候选池跑 5 道闸门</div>
        </div>
      </div>

      <template v-if="lab">
        <div class="row wrap lab-stats" style="gap: 6px">
          <span class="tag">{{ s.date }} 候选 {{ lab.pool_n }} 只</span>
          <span v-if="lab.stage" class="tag st" :class="stageCls(lab.stage)">周期 · {{ lab.stage }}</span>
          <span class="tag gold">质地 {{ weights.q }}% × 情绪 {{ weights.e }}%</span>
          <span v-if="lab.veto_n" class="tag red">排雷 {{ lab.veto_n }}</span>
          <span v-if="lab.missing_n" class="tag">缺数据 {{ lab.missing_n }}</span>
        </div>

        <!-- 融合榜 -->
        <div class="lab-sec-head tiny muted">Lab 融合榜 · 排雷后按 质地×情绪 排序（越高越兼顾两者）</div>
        <div v-if="!ranks.length" class="small dim" style="margin-top: 6px">无候选（候选池为空或全部被排雷）</div>
        <div v-for="(r, i) in ranks" :key="r.code" class="lab-row" :class="verbCls(r.verb)">
          <div class="lab-left">
            <div class="mono lab-score" :class="labCls(r.lab)">{{ r.lab != null ? r.lab : '—' }}</div>
            <div class="lab-bar"><i :class="labCls(r.lab)" :style="{ width: Math.max(0, Math.min(100, r.lab || 0)) + '%' }"></i></div>
          </div>
          <div class="grow">
            <div class="lab-line1">
              <span class="lab-name">{{ r.name }}</span>
              <span class="lab-chip">{{ r.board }}板</span>
              <span v-if="peakWarn(i)" class="lab-chip peak-warn">高潮慎接</span>
              <span v-if="r.in_core" class="lab-chip core">核心{{ r.grade || '' }}</span>
              <span v-if="r.verb" class="lab-chip v" :class="verbCls(r.verb)">{{ r.verb }}</span>
              <span v-if="r.q == null" class="lab-chip miss">数据缺失</span>
            </div>
            <div class="lab-line2 tiny dim">
              质地{{ r.q != null ? r.q : '—' }} · 情绪{{ r.e }} · {{ fmtYi(r.mv_yi) }} · {{ fmtPe(r) }}
              <template v-if="r.pb != null"> · PB {{ num(r.pb, 1) }}</template>
              <template v-if="r.turn != null"> · 换手 {{ num(r.turn, 0) }}%</template>
            </div>
            <div v-if="greenTxt(r)" class="lab-green tiny">{{ greenTxt(r) }}</div>
            <div v-if="flagTxt(r)" class="lab-flag tiny">{{ flagTxt(r) }}</div>
            <div class="lab-note tiny dim">{{ r.note }}</div>
          </div>
        </div>
        <div v-if="lab.ranks.length > MAX_LAB" class="row center" style="margin-top: 8px">
          <button class="btn mini" @click="labShow.value >= lab.ranks.length ? showLabPart() : showLabAll()">
            {{ labShow.value >= lab.ranks.length ? '收起' : '展开全部 ' + lab.ranks.length + ' 只' }}
          </button>
        </div>

        <!-- 排雷红灯 -->
        <template v-if="vetoed.length">
          <div class="divider"></div>
          <div class="lab-sec-head tiny" style="color: var(--up)">排雷一票否决 · 直接排除</div>
          <div v-for="v in vetoed" :key="v.code" class="lab-veto-card">
            <div class="lab-veto-top">
              <span class="lab-veto-name">{{ v.name }}</span>
              <span class="lab-chip">{{ v.board }}板</span>
              <span class="lab-chip v red">一票否决</span>
            </div>
            <div class="lab-veto-reason">{{ v.veto_reason }}</div>
            <div v-if="vetoReds(v).length" class="lab-veto-flags">
              <span v-for="(f, k) in vetoReds(v)" :key="k" class="lab-chip v red">{{ f.t }}</span>
            </div>
            <div v-if="vetoYellows(v).length" class="lab-veto-flags">
              <span v-for="(f, k) in vetoYellows(v)" :key="k" class="lab-chip v gold">{{ f.t }}</span>
            </div>
            <div class="lab-veto-meta tiny dim">
              {{ fmtYi(v.mv_yi) }} · {{ fmtPe(v) }}<template v-if="v.pb != null"> · PB {{ num(v.pb, 1) }}</template><template v-if="v.industry"> · {{ v.industry }}</template>
            </div>
            <div v-if="v.note" class="lab-note tiny dim">{{ v.note }}</div>
          </div>
        </template>

        <div class="divider"></div>
        <details class="lab-meta">
          <summary class="tiny muted">口径声明（务必读一次）</summary>
          <div class="lab-meta-body small dim">
            <div>G1 排雷闸：{{ (lab.meta && lab.meta.g1) || '名称含 ST/*ST → 一票否决' }}</div>
            <div>质地分：{{ (lab.meta && lab.meta.q_note) || '' }}</div>
            <div>情绪分：{{ (lab.meta && lab.meta.e_note) || '' }}</div>
            <template v-if="lab.meta && lab.meta.sources">
              <div style="margin-top: 4px">深度数据源（真实机读，随快照入库）：</div>
              <div v-for="(v, k) in lab.meta.sources" :key="k">· {{ k }}：{{ v }}</div>
            </template>
            <div v-if="lab.meta && lab.meta.not_wired && lab.meta.not_wired.length" class="lab-notwired">
              诚实声明：{{ lab.meta.not_wired.join('、') }}
            </div>
            <div style="margin-top: 4px">实验性质评分，仅供研究，不构成投资建议；引擎 verb（禁接力/规避）优先级高于 Lab 分。</div>
          </div>
        </details>
      </template>

      <template v-else>
        <div class="small dim" style="margin-top: 10px">
          当日快照暂无实验室结果 —— 每日 16:05/16:40 收盘后自动生成；
          若已过 17:00 仍无，可点右上角「刷新」触发重算。历史日期快照不计算实验室。
        </div>
      </template>
    </div>

    <!-- 自选盯票池 -->
    <div class="card">
      <div class="card-title">
        我的自选 · {{ wl.length }}
        <span class="tiny muted" style="font-weight: 400">点选即体检 · 云端共享</span>
      </div>
      <div class="row" style="gap: 8px">
        <input
          v-model="wlInput"
          class="input grow"
          placeholder="添加代码，如 600865"
          @keyup.enter="addWl"
        />
        <button class="btn" :disabled="wlBusy" @click="addWl">添加</button>
      </div>
      <div v-if="wlQuotes.length" class="wl-list">
        <div v-for="q in wlQuotes" :key="q.code" class="wl-item" @click="pickWl(q.code)">
          <div style="min-width: 0">
            <div class="wl-name ellipsis">{{ q.name || q.code }}</div>
            <div class="wl-code mono">{{ q.code }}</div>
          </div>
          <div class="right">
            <div class="mono" :class="(q.pct || 0) >= 0 ? 'up' : 'down'">
              {{ q.price != null ? q.price : '—' }}
            </div>
            <div class="tiny mono" :class="(q.pct || 0) >= 0 ? 'up' : 'down'">
              {{ q.pct != null ? (q.pct > 0 ? '+' : '') + q.pct + '%' : '—' }}
            </div>
          </div>
          <button class="wl-del" @click.stop="delWl(q.code)">×</button>
        </div>
      </div>
      <div v-else-if="wl.length" class="tiny muted mt">行情加载中…</div>
      <div v-else class="tiny muted mt">暂无自选。添加后可在体检页与首页快速回看。</div>
    </div>

    <div class="card">
      <div class="card-title">异动体检 · 输入个股代码</div>
      <div class="row" style="gap: 8px">
        <input
          v-model="code"
          class="input grow"
          placeholder="如 601086 / 003005 / 688981"
          @keyup.enter="query"
        />
        <button class="btn" :disabled="loading" @click="query">
          {{ loading ? '查询中' : '查询' }}
        </button>
      </div>
      <div class="tiny muted" style="margin-top: 8px">
        计算 3/10/30 日累计偏离值、距严重异动红线余量；涨停股附带核心评分
      </div>
    </div>

    <div v-if="err" class="card err">
      <div class="small">{{ err }}</div>
    </div>

    <template v-if="data">
      <div class="card">
        <div class="row between">
          <div>
            <div class="nm">{{ data.name }}</div>
            <div class="tiny muted mono">
              {{ String(data.code).slice(2) }} · 基准 {{ data.bench_name }} · 数据截至
              {{ data.last_date }}
            </div>
          </div>
          <div class="right">
            <div class="mono px">{{ num(data.last_close, 2) }}</div>
            <div v-if="data.board" class="tag gold">{{ data.board }}板</div>
          </div>
        </div>

        <div class="divider"></div>
        <div class="grid3">
          <div class="dv">
            <div class="tiny muted">3日偏离</div>
            <div class="mono big" :class="dev('dev_3d') >= 0 ? 'up' : 'down'">{{ signed(dev('dev_3d'), 1) }}</div>
          </div>
          <div class="dv">
            <div class="tiny muted">10日偏离</div>
            <div class="mono big" :class="dev('dev_10d') >= 0 ? 'up' : 'down'">{{ signed(dev('dev_10d'), 1) }}</div>
          </div>
          <div class="dv">
            <div class="tiny muted">30日偏离</div>
            <div class="mono big" :class="dev('dev_30d') >= 0 ? 'up' : 'down'">{{ signed(dev('dev_30d'), 1) }}</div>
          </div>
        </div>

        <div class="headroom">
          <div class="row between tiny muted" style="margin-bottom: 5px">
            <span>30日严重异动线 (+200%)</span>
            <span class="mono">
              {{ dev('serious_30d_up') ? '已触发' : '余 ' + num((dev('headroom_30d_up') || 0) * 100, 0) + 'pp' }}
            </span>
          </div>
          <div class="bar">
            <i
              :style="{
                width: Math.min(100, Math.max(0, ((dev('dev_30d') || 0) / 2) * 100)) + '%',
                background: dev('serious_30d_up')
                  ? 'linear-gradient(90deg,#ff4d5e,#ff8a94)'
                  : (dev('near_serious') ? 'linear-gradient(90deg,#ff9f43,#ffd58a)' : 'linear-gradient(90deg,#e9b75c,#ffd58a)'),
              }"
            ></i>
          </div>
          <div class="row wrap" style="gap: 6px; margin-top: 10px">
            <span v-if="dev('risk_level')" class="tag" :class="lvlCls()">{{ dev('risk_level') }}</span>
            <span v-if="dev('normal_3d_triggered')" class="tag">3日普通异动</span>
            <span class="tag">10日同向 {{ num(dev('same_dir_up_count')) }}/4</span>
            <span v-if="dev('limit_pct') != null" class="tag">涨跌幅限制 {{ dev('limit_pct') }}%</span>
          </div>
        </div>

        <div class="divider"></div>
        <div class="tiny muted" style="margin-bottom: 4px">近 30 日收盘走势</div>
        <SparkLine :values="closes()" />
      </div>

      <div v-if="data.score" class="card">
        <div class="card-title">核心评分（涨停股）</div>
        <div class="row" style="gap: 12px; align-items: center">
          <div :class="['grade', data.score.grade]">{{ data.score.grade }}</div>
          <div class="grow">
            <div class="row between">
              <span class="nm">{{ data.score.state }}</span>
              <span class="mono big">{{ num(data.score.total, 0) }}</span>
            </div>
            <div class="tiny muted">
              地位 {{ num(data.score.sub_a, 0) }}/40 · 持续 {{ num(data.score.sub_b, 0) }}/30 · 风险
              -{{ num(data.score.risk_total, 0) }}
            </div>
          </div>
        </div>
        <div v-for="r in data.score.risk_items || []" :key="r.name" class="rrow">
          <span class="tag red">-{{ num(r.score, 0) }}</span>
          <span class="small">{{ r.name }}</span>
        </div>
      </div>

      <div v-if="data.market" class="card">
        <div class="card-title">所属交易日市场环境</div>
        <div class="small dim">
          {{ data.market.date }} · 温度 {{ num(data.market.heat, 0) }}（{{ data.market.band }}） ·
          周期 {{ data.market.stage }} · 最高 {{ data.market.max_board }} 板
        </div>
      </div>
    </template>

    <div class="tiny muted center">偏离值 = 个股区间涨幅 − 对应指数区间涨幅（复合口径）</div>
  </div>
</template>

<style scoped>
.nm { font-size: 16px; font-weight: 600; }
.right { text-align: right; }
.px { font-size: 17px; font-weight: 700; }
.grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; text-align: center; }
.dv {
  padding: 9px 4px;
  border-radius: var(--r-md);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--line);
}
.big { font-size: 16.5px; font-weight: 700; }
.headroom { margin-top: 14px; }
.rrow { display: flex; align-items: center; gap: 8px; margin-top: 6px; }
.err { border-color: rgba(255, 77, 94, 0.35); }
.center { text-align: center; }

/* ===== 分析系统 · 实验室 ===== */
.card.lab {
  border-color: rgba(233, 183, 92, 0.35);
  background: linear-gradient(180deg, rgba(233, 183, 92, 0.09), rgba(233, 183, 92, 0.015) 130px), var(--card);
}
.lab-head { display: flex; align-items: center; gap: 10px; }

/* 自选盯票池 */
.wl-list { margin-top: 10px; }
.wl-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 9px;
  border-radius: var(--r-sm);
  background: rgba(255, 255, 255, 0.035);
  border: 1px solid var(--line);
  margin-bottom: 6px;
  cursor: pointer;
}
.wl-item > div:first-child { flex: 1; min-width: 0; }
.wl-name { font-size: 14px; font-weight: 600; }
.wl-code { font-size: 10.5px; color: var(--t-3); opacity: 0.85; margin-top: 2px; }
.wl-del {
  border: none;
  background: transparent;
  color: var(--t-3);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  padding: 0 2px;
}
.ellipsis { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lab-badge {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.5px;
  color: #0c1018;
  background: linear-gradient(135deg, #f3d9a4, #e9b75c 55%, #c98f3c);
  padding: 6px 9px;
  border-radius: 10px;
  box-shadow: 0 2px 10px rgba(233, 183, 92, 0.35);
}
.lab-stats { margin-top: 12px; }
.lab-sec-head { margin: 12px 0 4px; }
.lab-row {
  display: flex;
  gap: 10px;
  padding: 9px 2px;
  border-bottom: 1px solid var(--line);
}
.lab-row:last-child { border-bottom: none; }
.lab-row.red { background: linear-gradient(90deg, rgba(255, 77, 94, 0.06), rgba(255, 77, 94, 0) 80%); }
.lab-left { flex-shrink: 0; width: 46px; }
.lab-score {
  font-size: 19px;
  font-weight: 800;
  line-height: 1;
  padding-top: 2px;
  color: var(--t-2);
}
.lab-score.lab-hi { color: var(--gold); text-shadow: 0 0 14px rgba(233, 183, 92, 0.4); }
.lab-score.lab-md { color: #e8ecf4; }
.lab-line1 { display: flex; align-items: center; gap: 5px; flex-wrap: wrap; }
.lab-name { font-weight: 700; color: var(--t-1); font-size: 13.5px; }
.lab-chip {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid var(--line);
  color: var(--t-2);
  white-space: nowrap;
}
.lab-chip.core { color: var(--gold); border-color: rgba(233, 183, 92, 0.4); background: var(--gold-dim); }
.lab-chip.v.gold { color: var(--gold); }
.lab-chip.v.red { color: #fff; background: var(--up); border-color: var(--up); }
.lab-chip.miss { color: var(--orange); border-color: rgba(255, 159, 67, 0.4); }
.lab-line2 { margin-top: 2px; }
.lab-green { color: var(--gold); margin-top: 2px; line-height: 1.4; }
.lab-green::before { content: '◆ '; opacity: 0.85; }
.lab-flag { color: var(--orange); margin-top: 2px; line-height: 1.4; }
.lab-note { margin-top: 3px; line-height: 1.45; }
.lab-veto {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 5px 2px;
}
.lab-veto-name { font-weight: 700; font-size: 13px; }
.btn.mini { font-size: 11px; padding: 4px 12px; }
details.lab-meta { margin-top: 10px; }
details.lab-meta summary { cursor: pointer; }
.lab-meta-body { margin-top: 8px; padding: 8px 10px; border-radius: var(--r-sm); background: rgba(255, 255, 255, 0.03); border: 1px solid var(--line); line-height: 1.6; }
.lab-notwired { margin-top: 3px; color: var(--orange); }

/* Lab 档位色带（lab 分越高条越长，颜色按档位） */
.lab-bar { margin-top: 5px; height: 3px; border-radius: 2px; background: rgba(255, 255, 255, 0.09); overflow: hidden; }
.lab-bar i { display: block; height: 100%; border-radius: 2px; background: rgba(255, 255, 255, 0.26); }
.lab-bar i.lab-hi { background: linear-gradient(90deg, #c98f3c, var(--gold)); }
.lab-bar i.lab-md { background: linear-gradient(90deg, #3d6fb5, #6ea8fe); }

/* 周期阶段标签色 */
.st-start { color: #ffb454 !important; border-color: rgba(255, 180, 84, 0.45) !important; background: rgba(255, 180, 84, 0.14) !important; }
.st-ferment { color: #ff9a5a !important; border-color: rgba(255, 154, 90, 0.45) !important; background: rgba(255, 154, 90, 0.14) !important; }
.st-peak { color: #ff6b78 !important; border-color: rgba(255, 107, 120, 0.5) !important; background: rgba(255, 77, 94, 0.16) !important; }
.st-ebb { color: #3ecf8e !important; border-color: rgba(62, 207, 142, 0.45) !important; background: rgba(62, 207, 142, 0.13) !important; }
.st-shock { color: #93a4bd !important; border-color: rgba(147, 164, 189, 0.4) !important; background: rgba(147, 164, 189, 0.12) !important; }

/* 高潮期榜首「慎接」角标 */
.lab-chip.peak-warn { color: #fff; background: var(--up); border-color: var(--up); font-weight: 700; letter-spacing: 0.2px; }

/* 排雷否决票：原因默认展开 */
.lab-veto-card {
  padding: 8px 10px;
  margin-bottom: 7px;
  border-radius: var(--r-sm);
  background: rgba(255, 77, 94, 0.06);
  border: 1px solid rgba(255, 77, 94, 0.28);
  border-left: 3px solid var(--up);
}
.lab-veto-top { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
.lab-veto-reason { margin-top: 4px; font-size: 12.5px; color: var(--up); line-height: 1.45; }
.lab-veto-flags { margin-top: 5px; display: flex; flex-wrap: wrap; gap: 4px; }
.lab-veto-meta { margin-top: 4px; }
</style>
