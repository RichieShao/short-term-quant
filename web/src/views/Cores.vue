<script setup>
import { ref, computed, onMounted } from 'vue'
import { useSnap } from '../stores/snap'
import { callApi } from '../api/cloud'
import CoreCard from '../components/CoreCard.vue'

const s = useSnap()
const filter = ref('all') // all/fresh/good/c
const sortMode = ref('score') // score/board/amount/headroom

/* 次日表现追踪（coretrack.agg，每日自动回填）：动态优先，未就绪显示积累中 */
const ct = ref(null)
const ctReady = ref(false)

const filters = [
  { k: 'all', label: '全部' },
  { k: 'fresh', label: '新晋' },
  { k: 'good', label: 'S/A 级' },
  { k: 'c', label: 'C 级（禁区）' },
]
const sorts = [
  { k: 'score', label: '综合' },
  { k: 'board', label: '高度' },
  { k: 'amount', label: '容量' },
  { k: 'headroom', label: '风控余量' },
]

// 进入核心池页即拉昨日核心池，供"新晋"信号对比
onMounted(() => {
  s.fetchPrevCores()
  loadCoreTrack()
})

async function loadCoreTrack() {
  try {
    const r = await callApi('coretrack')
    if (r && r.ok) {
      ct.value = r
      ctReady.value = true
    }
  } catch (e) {
    ctReady.value = false // 保持"积累中"占位
  }
}

const forbid = computed(() =>
  (s.actions?.per_stock || []).filter((a) => ['禁接力', '规避/清仓', '减/剔除'].includes(a.verb))
)
const actionOf = (code) => (s.actions?.per_stock || []).find((a) => a.code === code)

/* 过滤 + 排序键：headroom 用 30日异动余量 pp（大=安全） */
const sortKey = (c) => {
  if (sortMode.value === 'board') return c.board || 0
  if (sortMode.value === 'amount') return c.amount || 0
  if (sortMode.value === 'headroom') return (c.dev && c.dev.headroom_30d_up) || -1
  return c.total || 0
}
const filtered = computed(() => {
  let l = [...s.cores]
  if (filter.value === 'good') l = l.filter((c) => ['S', 'A'].includes(c.grade))
  if (filter.value === 'c') l = l.filter((c) => c.grade === 'C')
  if (filter.value === 'fresh') l = l.filter((c) => s.freshCodes.has(c.code))
  return l.sort((a, b) => sortKey(b) - sortKey(a))
})

/* 同题材聚组（组内已按当前排序键） */
const groups = computed(() => {
  const g = new Map()
  for (const c of filtered.value) {
    const ind = c.industry || '其他'
    if (!g.has(ind)) g.set(ind, [])
    g.get(ind).push(c)
  }
  const rows = [...g.entries()].map(([name, items]) => ({
    name,
    items,
    maxBoard: Math.max(...items.map((x) => x.board || 0)),
  }))
  return rows.sort((a, b) => b.maxBoard - a.maxBoard || b.items.length - a.items.length)
})

/* 今日可参与候选（最优候选突出）：S/A 且动作非禁区/空仓 且 未严重异动 */
const playable = computed(() => {
  const na = s.actions?.per_stock || []
  return s.cores.filter((c) => {
    if (!['S', 'A'].includes(c.grade)) return false
    const a = na.find((x) => x.code === c.code)
    if (a && ['禁接力', '规避/清仓', '减/剔除', '空仓'].includes(a.verb)) return false
    if (c.dev && c.dev.risk_level === '严重异动') return false
    return true
  })
})

/* 胜率统计展示（S/A/B/C 各档） */
const ctRows = computed(() => {
  const g = (ct.value && ct.value.grades) || {}
  return ['S', 'A', 'B', 'C']
    .map((k) => ({ key: k, v: g[k] }))
    .filter((x) => x.v && x.v.n > 0)
})
const ctText = computed(() => {
  if (!ctReady.value) return '每日收盘后自动回填，系统上线数日后出真实胜率'
  const c = ct.value
  return `已回填 ${c.settled_days || 0} 个交易日 · 截至 ${c.last || '—'}`
})

/* 历史回放（含实操口径 + 周期分层）：检验「周期定位 × 核心识别」是否真的分层有效 */
const rp = computed(() => (ct.value && ct.value.replay) || null)
const fmtPct = (v) => (v == null ? '—' : (v > 0 ? '+' : '') + v + '%')
const rpStageRows = computed(() => {
  const r = rp.value
  if (!r || !r.by_stage) return []
  return Object.entries(r.by_stage)
    .map(([k, v]) => ({ k, ...v }))
    .filter((x) => x.n)
    .sort((a, b) => (b.avg_real == null ? -999 : b.avg_real) - (a.avg_real == null ? -999 : a.avg_real))
})
const rpGradeRows = computed(() => {
  const r = rp.value
  if (!r || !r.by_grade) return []
  return Object.entries(r.by_grade)
    .map(([k, v]) => ({ k, ...v }))
    .filter((x) => x.n)
    .sort((a, b) => (b.avg_real == null ? -999 : b.avg_real) - (a.avg_real == null ? -999 : a.avg_real))
})
</script>

<template>
  <div class="page">
    <!-- 次日表现追踪（各档真实胜率，每日自动回填） -->
    <div class="card" v-if="ctRows.length || !ctReady">
      <div class="card-title">
        核心池次日表现 · 真实回填
        <span class="tiny muted" style="font-weight: 400">晋级 = 次日仍涨停且连板晋级</span>
      </div>
      <div class="tiny muted" style="margin: 2px 0 8px">
        <template v-if="ctReady"><span class="tl-live">● 每交易日自动回填</span> · {{ ctText }}</template>
        <template v-else>{{ ctText }}</template>
      </div>
      <div v-if="ctRows.length" class="ct-grid">
        <div v-for="r in ctRows" :key="r.key" class="ct-cell" :class="r.key">
          <div class="ct-g">{{ r.key }} 级</div>
          <div class="ct-main mono" :class="(r.v.avg_pct || 0) >= 0 ? 'up' : 'down'">
            {{ r.v.avg_pct != null ? (r.v.avg_pct > 0 ? '+' : '') + r.v.avg_pct + '%' : '—' }}
          </div>
          <div class="tiny muted">次日均幅 · 晋级 {{ r.v.adv_rate }}%（{{ r.v.adv }}/{{ r.v.n }}）</div>
        </div>
      </div>
      <div v-if="ctReady && !ctRows.length" class="small muted">近几日核心池样本为空（退潮期高标稀少），继续积累。</div>
      <div v-if="ctReady && ct.overall && ct.overall.n" class="tiny muted mt">
        总样本 {{ ct.overall.n }} 只 · 次日晋级率 {{ ct.overall.adv_rate }}% · 次日均幅
        <b :class="(ct.overall.avg_pct || 0) >= 0 ? 'up' : 'down'">
          {{ ct.overall.avg_pct > 0 ? '+' : '' }}{{ ct.overall.avg_pct }}%
        </b>
      </div>
    </div>

    <!-- 历史回放 · 周期分层（实操口径，检验框架「周期 × 核心」是否分层有效） -->
    <div class="card" v-if="rp">
      <div class="card-title">
        历史回放 · 周期分层
        <span class="tiny muted" style="font-weight: 400">
          {{ rp.window.from }} ~ {{ rp.window.to }} · {{ rp.n }} 样本
        </span>
      </div>
      <div class="tiny muted" style="margin: 2px 0 8px">
        <b>实操</b> = 次日开盘买入 → 第三日收盘卖出（T+1 制度下真能拿到）；
        <b>理论</b> = 当日收盘 → 次日收盘（涨停收盘买不进，偏乐观，只看强度）
      </div>
      <div class="rp-table">
        <div class="rp-row rp-head tiny muted">
          <span>周期阶段</span><span>样本</span><span>晋级率</span><span>实操</span><span>理论</span>
        </div>
        <div v-for="x in rpStageRows" :key="x.k" class="rp-row">
          <span>{{ x.k }}</span>
          <span class="mono">{{ x.n }}<i v-if="x.n < 10" class="rp-few">少</i></span>
          <span class="mono">{{ x.adv_rate }}%</span>
          <span class="mono" :class="(x.avg_real || 0) >= 0 ? 'up' : 'down'">{{ fmtPct(x.avg_real) }}</span>
          <span class="mono dim">{{ fmtPct(x.avg_close) }}</span>
        </div>
      </div>
      <div class="rp-grades">
        <div v-for="x in rpGradeRows" :key="x.k" class="rp-g">
          <span class="tag">{{ x.k }} 级</span>
          <b class="mono" :class="(x.avg_real || 0) >= 0 ? 'up' : 'down'">{{ fmtPct(x.avg_real) }}</b>
          <span class="tiny muted">n={{ x.n }} · 晋级 {{ x.adv_rate }}%</span>
        </div>
      </div>
      <div class="tiny muted mt">{{ rp.note }}</div>
    </div>

    <!-- 今日可参与候选 -->
    <div v-if="playable.length" class="card cand">
      <div class="card-title">今日可参与候选 · {{ playable.length }}</div>
      <div class="row wrap" style="gap: 6px">
        <span v-for="c in playable" :key="c.code" class="tag gold">{{ c.name }} {{ c.board }}板</span>
      </div>
      <div class="tiny muted mt">S/A 级、动作非禁区/空仓、未触发严重异动。仍按周期基调控制仓位。</div>
    </div>

    <div class="card" v-if="s.actions">
      <div class="card-title">今日操作清单 · {{ s.actions.stage }}</div>
      <div class="small dim" style="margin-bottom: 10px">{{ s.actions.tone }}</div>
      <div class="row wrap" style="gap: 8px">
        <div class="stat">
          <div class="mono big">{{ s.cores.length }}</div>
          <div class="tiny muted">高标</div>
        </div>
        <div class="stat">
          <div class="mono big up">{{ forbid.length }}</div>
          <div class="tiny muted">禁接力/规避</div>
        </div>
        <div class="stat">
          <div class="mono big gold">
            {{ s.cores.filter((c) => ['S', 'A'].includes(c.grade)).length }}
          </div>
          <div class="tiny muted">S/A 级</div>
        </div>
      </div>
    </div>

    <div class="chips">
      <div class="chipg">
        <button
          v-for="f in filters"
          :key="f.k"
          class="chip"
          :class="{ on: filter === f.k }"
          @click="filter = f.k"
        >
          {{ f.label }}
        </button>
      </div>
      <div class="chipg">
        <button
          v-for="sf in sorts"
          :key="sf.k"
          class="chip sort"
          :class="{ on: sortMode === sf.k }"
          @click="sortMode = sf.k"
        >
          {{ sf.label }}⇅
        </button>
      </div>
    </div>

    <!-- 同题材聚组 -->
    <template v-for="g in groups" :key="g.name">
      <div class="grp-head">
        <span class="grp-name">{{ g.name }}</span>
        <span class="tiny muted mono">{{ g.items.length }} 只 · 最高 {{ g.maxBoard }} 板</span>
      </div>
      <CoreCard
        v-for="c in g.items"
        :key="c.code"
        :c="c"
        :action="actionOf(c.code)"
        :fresh="s.freshCodes.has(c.code)"
      />
    </template>

    <div v-if="!groups.length" class="card">
      <div class="small muted">
        {{ filter === 'fresh' && s.prevCoreCodes === null
          ? '暂无昨日快照，无法判断新晋（系统上线不足 2 个交易日时属正常）。'
          : '当前快照无高标数据（连板≥2 板）。' }}
      </div>
    </div>

    <div class="tiny muted center">
      总分 = 地位(40) + 持续(30) − 风险(30)，归一 0-100；S≥80 / A≥60 / B≥45 / C&lt;45 ·
      <b style="color: #67e8f9">新晋</b> = 今日在核心池、昨日不在 ·
      <b style="color: #ffd58a">龙头/#2</b> = 题材内按(板高, 总分)排名 · 排序可切 综合/高度/容量/风控余量
    </div>
  </div>
</template>

<style scoped>
.chips {
  display: flex; justify-content: space-between; gap: 8px;
  margin: 10px 0 4px; flex-wrap: wrap;
}
.chipg { display: flex; gap: 8px; flex-wrap: wrap; }
.chip {
  padding: 6px 13px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.04);
  color: var(--t-2);
  font-size: 12.5px;
  cursor: pointer;
}
.chip.on { color: var(--gold); border-color: rgba(233, 183, 92, 0.45); background: var(--gold-dim); }
.chip.sort { font-size: 11.5px; padding: 5px 11px; }

.stat {
  flex: 1;
  text-align: center;
  padding: 9px 6px;
  border-radius: var(--r-md);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--line);
}
.big { font-size: 19px; font-weight: 700; }
.gold { color: var(--gold); }
.up { color: var(--up); }
.down { color: var(--down); }
.center { text-align: center; margin-top: 4px; }
.tl-live { color: var(--gold); font-weight: 600; }
.mt { margin-top: 8px; }

/* 历史回放 · 周期分层表 */
.rp-table { margin-top: 2px; }
.rp-row {
  display: grid;
  grid-template-columns: 1.4fr 0.8fr 0.9fr 0.9fr 0.9fr;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-radius: var(--r-sm);
  font-size: 12.5px;
}
.rp-row:nth-child(even) { background: rgba(255, 255, 255, 0.035); }
.rp-head { padding-bottom: 4px; font-size: 10.5px; border-bottom: 1px solid var(--line); }
.rp-row > span:not(:first-child) { text-align: right; }
.rp-few {
  margin-left: 4px;
  padding: 0 4px;
  border-radius: 4px;
  font-size: 9.5px;
  font-style: normal;
  color: #ffd58a;
  background: rgba(255, 213, 138, 0.14);
}
.rp-grades { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.rp-g {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 9px;
  border-radius: var(--r-sm);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--line);
  font-size: 12px;
}

/* 胜率卡 */
.ct-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(118px, 1fr)); gap: 8px; }
.ct-cell {
  padding: 9px 10px;
  border-radius: var(--r-md);
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.04);
  text-align: center;
}
.ct-g { font-size: 11px; font-weight: 700; letter-spacing: 1px; }
.ct-cell.S .ct-g { color: #ffd58a; }
.ct-cell.A .ct-g { color: #ff9d66; }
.ct-cell.B .ct-g { color: #9db8ff; }
.ct-cell.C .ct-g { color: var(--t-3); }
.ct-main { font-size: 19px; font-weight: 700; margin: 3px 0 1px; }

/* 可参与候选 */
.cand {
  border-color: rgba(233, 183, 92, 0.4);
  background: linear-gradient(180deg, rgba(233, 183, 92, 0.08), rgba(233, 183, 92, 0.02));
}

/* 题材聚组头 */
.grp-head {
  display: flex; align-items: baseline; justify-content: space-between;
  margin: 14px 2px 8px;
  padding-bottom: 5px;
  border-bottom: 1px dashed rgba(255, 255, 255, 0.08);
}
.grp-head:first-of-type { margin-top: 10px; }
.grp-name {
  font-size: 13.5px; font-weight: 700;
  color: var(--t-1);
  padding-left: 8px;
  border-left: 3px solid var(--gold);
  line-height: 1.2;
}
</style>
