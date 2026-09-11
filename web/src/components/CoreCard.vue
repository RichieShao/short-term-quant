<script setup>
import { ref, computed } from 'vue'
import { signed, num, bandColor } from '../utils/format'

const props = defineProps({
  c: { type: Object, required: true },
  action: { type: Object, default: null },
  fresh: { type: Boolean, default: false },
})

const open = ref(false)

const scoreColor = computed(() => {
  const t = props.c.total || 0
  if (t >= 80) return '#ff7a45'
  if (t >= 60) return '#e9b75c'
  if (t >= 45) return '#5b8cff'
  return '#8a93a8'
})

const riskLevel = computed(() => (props.c.dev && props.c.dev.risk_level) || '')
const riskCls = computed(() =>
  riskLevel.value === '严重异动' ? 'red' : riskLevel.value === '高危接近' ? 'gold' : ''
)

// 容量格式化：>=1亿 → 亿，否则万
function fmtCap(v) {
  if (v == null) return ''
  if (v >= 1e8) return (v / 1e8).toFixed(1) + '亿'
  if (v >= 1e4) return Math.round(v / 1e4) + '万'
  return String(Math.round(v))
}
const amountText = computed(() => (props.c.amount != null ? fmtCap(props.c.amount) : ''))
const capText = computed(() => (props.c.float_cap != null ? fmtCap(props.c.float_cap) : ''))
const turnText = computed(() =>
  props.c.turnover != null ? (props.c.turnover * 100).toFixed(1) + '%' : '')

// 题材内排名（后端已算 ind_rank/ind_total）：#1 龙头金标，#2 次席蓝标
const indCls = computed(() =>
  props.c.ind_rank === 1 ? 'lead' : props.c.ind_rank === 2 ? 'second' : ''
)

// 连池天数（后端 streak = 今日之前的连续在池天数；含今日 = streak+1；0 → 新晋 badge 已示）
const stayText = computed(() => {
  const st = props.c.streak || 0
  return st >= 1 ? `连池${st + 1}日` : ''
})

// 动作配色：明确禁区(禁接力/规避清仓)=红；空仓=中性(不暗示可参与)；其余(观察/试错)=金
function actionCls(v) {
  if (v === '禁接力' || v === '规避/清仓') return 'red'
  if (v === '空仓') return ''
  return 'gold'
}
</script>

<template>
  <div class="card core" @click="open = !open">
    <div class="row between">
      <div class="row" style="gap: 10px; min-width: 0">
        <div :class="['grade', c.grade]">{{ c.grade }}</div>
        <div style="min-width: 0">
          <div class="nm">
            <div class="nm-top">
              <span v-if="indCls" :class="['ind-badge', indCls]">{{ c.ind_rank === 1 ? '龙头' : '#2' }}</span>
              {{ c.name }}
            </div>
            <!-- 代码独立一行小号置于名称下方（便于核对标的、避免与名称挤在同一行） -->
            <div class="nm-code mono">{{ c.code }}</div>
          </div>
          <div class="tiny muted ellipsis">
            {{ c.board }}板<template v-if="c.zttj"> · {{ c.zttj }}</template> · {{ c.industry || '其他' }} · {{ c.state }}
            <span v-if="stayText" class="badge-stay">{{ stayText }}</span>
            <span v-if="fresh" class="badge-fresh">新晋</span>
          </div>
        </div>
      </div>
      <div class="right">
        <div class="score mono" :style="{ color: scoreColor }">{{ num(c.total, 0) }}</div>
        <div class="tiny muted">评分</div>
      </div>
    </div>

    <!-- 容量行：成交额 / 流通市值 / 换手（仓位管理的实际依据） -->
    <div v-if="amountText || capText" class="cap-row tiny muted mono">
      <span v-if="amountText">成交 <b>{{ amountText }}</b></span>
      <span v-if="capText">流通 <b>{{ capText }}</b></span>
      <span v-if="turnText">换手 <b>{{ turnText }}</b></span>
    </div>

    <div class="bars">
      <div class="bitem">
        <div class="row between tiny muted"><span>地位 A</span><span class="mono">{{ num(c.sub_a,0) }}/40</span></div>
        <div class="bar"><i :style="{ width: (c.sub_a/40*100)+'%', background:'linear-gradient(90deg,#5b8cff,#7aa2ff)' }"></i></div>
      </div>
      <div class="bitem">
        <div class="row between tiny muted"><span>持续 B</span><span class="mono">{{ num(c.sub_b,0) }}/30</span></div>
        <div class="bar"><i :style="{ width: (c.sub_b/30*100)+'%', background:'linear-gradient(90deg,#e9b75c,#ffd58a)' }"></i></div>
      </div>
      <div class="bitem">
        <div class="row between tiny muted"><span>风险扣</span><span class="mono">-{{ num(c.risk_total,0) }}/30</span></div>
        <div class="bar"><i :style="{ width: (c.risk_total/30*100)+'%', background:'linear-gradient(90deg,#ff4d5e,#ff8a94)' }"></i></div>
      </div>
    </div>

    <div class="row wrap" style="gap: 6px; margin-top: 10px">
      <span v-if="action" class="tag" :class="actionCls(action.verb)">
        {{ action.verb }} · {{ action.position }}
      </span>
      <span v-if="riskLevel" class="tag" :class="riskCls">{{ riskLevel }}</span>
      <span v-if="c.dev" class="tag">10日 {{ signed(c.dev.dev_10d, 0) }}</span>
      <span v-if="c.dev" class="tag">30日 {{ signed(c.dev.dev_30d, 0) }}</span>
      <span v-for="s in (c.signals || []).slice(0, 3)" :key="s" class="tag">{{ s }}</span>
    </div>

    <div v-if="open" class="detail">
      <div class="divider"></div>

      <div v-if="c.dev" class="sec">
        <div class="tiny muted" style="margin-bottom: 6px">异动体检（基准 {{ c.dev.bench_name || '—' }}）</div>
        <div class="grid3">
          <div><div class="tiny muted">3日</div><div class="mono" :class="c.dev.dev_3d>=0?'up':'down'">{{ signed(c.dev.dev_3d,1) }}</div></div>
          <div><div class="tiny muted">10日</div><div class="mono" :class="c.dev.dev_10d>=0?'up':'down'">{{ signed(c.dev.dev_10d,1) }}</div></div>
          <div><div class="tiny muted">30日</div><div class="mono" :class="c.dev.dev_30d>=0?'up':'down'">{{ signed(c.dev.dev_30d,1) }}</div></div>
        </div>
        <div class="tiny muted" style="margin-top: 8px">
          距 30日严重异动(200%)：
          <b :class="c.dev.serious_30d_up ? 'up' : ''">
            {{ c.dev.serious_30d_up ? '已触发' : '余 ' + num((c.dev.headroom_30d_up||0)*100, 0) + 'pp' }}
          </b>
        </div>
      </div>

      <div v-if="(c.risk_items || []).length" class="sec">
        <div class="tiny muted" style="margin-bottom: 6px">风险扣分明细</div>
        <div v-for="r in c.risk_items" :key="r.name" class="rrow">
          <span class="tag red">-{{ num(r.score, 0) }}</span>
          <span class="small">{{ r.name }}</span>
        </div>
      </div>

      <div v-if="(c.notes || []).length" class="sec">
        <div class="tiny muted" style="margin-bottom: 6px">评分备注</div>
        <div v-for="(n, i) in c.notes" :key="i" class="small dim">· {{ n }}</div>
      </div>

      <div v-if="action && action.memo" class="sec small dim">{{ action.memo }}</div>
    </div>
  </div>
</template>

<style scoped>
.core { cursor: pointer; }
.nm { font-size: 15.5px; font-weight: 600; }
.nm-top { display: flex; align-items: center; min-width: 0; }
.nm-code {
  margin-top: 2px;
  font-size: 10.5px;
  font-weight: 500;
  letter-spacing: 0.4px;
  color: var(--t-3, #7c8aa0);
  opacity: 0.85;
}
.ellipsis { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 190px; }
/* 新晋核心：与昨日核心池对比新进池，青色高亮，暗示"刚启动" */
.badge-fresh {
  display: inline-block;
  margin-left: 6px;
  padding: 0 6px;
  border-radius: 5px;
  font-size: 10px;
  font-weight: 700;
  color: #06121a;
  background: linear-gradient(90deg, #4dd0e1, #67e8f9);
  vertical-align: middle;
}
/* 题材内地位：龙头金标 / 次席蓝标 */
.ind-badge {
  display: inline-block;
  margin-right: 5px;
  padding: 1px 6px;
  border-radius: 5px;
  font-size: 10px;
  font-weight: 700;
  vertical-align: 1px;
}
.ind-badge.lead { color: #3a2500; background: linear-gradient(90deg, #ffd58a, var(--gold)); }
.ind-badge.second { color: #eaf6ff; background: rgba(91, 140, 255, 0.55); }
/* 连池天数 */
.badge-stay {
  display: inline-block;
  margin-left: 6px;
  padding: 0 6px;
  border-radius: 5px;
  font-size: 10px;
  font-weight: 600;
  color: #bfdbfe;
  background: rgba(91, 140, 255, 0.16);
  border: 1px solid rgba(91, 140, 255, 0.3);
  vertical-align: middle;
}
/* 容量行 */
.cap-row {
  display: flex; gap: 12px;
  margin: 8px 0 0;
  padding: 6px 9px;
  border-radius: var(--r-sm);
  background: rgba(255, 255, 255, 0.03);
  border: 1px dashed rgba(255, 255, 255, 0.06);
  flex-wrap: wrap;
}
.cap-row b { color: var(--t-2); font-weight: 600; }
.right { text-align: right; }
.score { font-size: 22px; font-weight: 700; line-height: 1.1; }
.bars { display: flex; gap: 10px; margin-top: 12px; }
.bitem { flex: 1; }
.bitem .bar { margin-top: 4px; }
.sec { margin-top: 10px; }
.grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; text-align: center; }
.rrow { display: flex; align-items: center; gap: 8px; margin-bottom: 5px; }
</style>
