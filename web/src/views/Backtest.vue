<script setup>
import { ref, computed, onMounted } from 'vue'
import { callApi } from '../api/cloud'

/* 每日自动更新（每日收盘后随快照增量维护）：
   ① 题材生命期 —— 后端 themelife.agg（P4 口径：同花顺涨停题材）；
   ② 滚动校准 —— 后端 calib.agg（窗口/阶段分布/命中率随最新交易日重放自评，
      lu_min=81 于种子窗口一次性冻结，纯函数重放与 P4 基线同源零漂移）。
   前端拉取失败/基线未就绪时回退到下方 P4 静态基线（2026-09-02 定案）。 */

const tlLast = ref('')
const tlTop = ref(null) // [{name,peak,days,first,last}]

/* —— 滚动校准（calib）：动态优先，静态回退 —— */
const span = ref({ from: '2025-08-18', to: '2026-09-02', days: 254, src: '同花顺涨停池' })
const calibLast = ref('')
const pendingClimax = ref(null) // 近 3 日已形成、尚未确认的顶点候选数（后端无此字段时保持 null）

const scaleRows = [
  { k: '温度计刻度', old: '涨停 70 / 高度 6 / 连板 25', now: '涨停 100 / 高度 13 / 连板 28' },
  { k: '温度分档', old: '75 / 55 / 38 / 22', now: '72 / 58 / 45 / 33' },
  { k: '周期线', old: '72 / 55 / 32（三档）', now: '66 / 56 / 33 / 48（四线）' },
  { k: '高潮判定', old: '仅温度单一条件', now: '+ 最高板 ≥11 板 / 涨停 ≥90 家' },
]

/* 命中率：label/note/color 固定，hit/total 动态 */
const hitMeta = [
  { key: 'strict', label: '高潮顶点 · 严格口径', color: 'gold', note: '当日即判为高潮顶点' },
  { key: 'loose', label: '高潮顶点 · 宽松口径', color: 'red', note: '含前后 1 日容差' },
  { key: 'retreat', label: '退潮兑现', color: 'green', note: '标退潮后温度确实下行' },
]
const hitNums = ref({ climax_total: 37, strict: 25, loose: 37, retreat_total: 37, retreat_hit: 32 })
const hits = computed(() =>
  hitMeta.map((m) => {
    const total = m.key === 'retreat' ? hitNums.value.retreat_total : hitNums.value.climax_total
    const hit = m.key === 'retreat' ? hitNums.value.retreat_hit : hitNums.value[m.key]
    return { ...m, hit, total }
  })
)

/* 阶段分布：动态优先，静态回退 */
const STAGE_COLORS = { 震荡: '#5b8cff', 高潮: '#ff4d5e', 发酵: '#e9b75c', 启动: '#4dd0e1', 退潮: '#12c48b' }
const STAGE_ORDER = ['震荡', '高潮', '发酵', '启动', '退潮']
const stageNums = ref({ 震荡: 123, 高潮: 78, 发酵: 34, 启动: 17, 退潮: 2 })
const stages = computed(() =>
  STAGE_ORDER.map((name) => ({ name, n: stageNums.value[name] || 0, color: STAGE_COLORS[name] }))
)

/* 静态回退基线（P4 产物 2025-08-18 ~ 2026-09-02） */
const fallbackThemes = [
  ['商业航天', 39, 186, '2025-08-18 ~ 2026-08-31'],
  ['AI智能体', 32, 63, '2025-08-18 ~ 2026-08-28'],
  ['脑机接口', 30, 56, '2025-08-20 ~ 2026-09-01'],
  ['固态电池', 25, 182, '2025-08-18 ~ 2026-09-01'],
  ['中报预增', 24, 61, '2025-08-18 ~ 2026-08-26'],
  ['人形机器人', 23, 219, '2025-08-18 ~ 2026-09-02'],
  ['创新药', 22, 164, '2025-08-18 ~ 2026-09-02'],
  ['央企', 21, 239, '2025-08-18 ~ 2026-08-28'],
  ['天然气', 20, 62, '2025-08-21 ~ 2026-09-02'],
  ['海峡两岸', 19, 77, '2025-10-17 ~ 2026-09-01'],
  ['黄金', 18, 80, '2025-08-22 ~ 2026-08-26'],
  ['AI应用', 16, 120, '2025-08-18 ~ 2026-09-01'],
  ['存储芯片', 16, 155, '2025-08-18 ~ 2026-09-02'],
  ['白酒', 16, 23, '2025-08-19 ~ 2026-09-01'],
  ['液冷服务器', 15, 137, '2025-08-18 ~ 2026-09-02'],
]

const displayThemes = computed(() => {
  if (tlTop.value && tlTop.value.length) {
    return tlTop.value.map((t) => ({
      name: t.name,
      peak: t.peak,
      days: t.days,
      span: (t.first && t.last && t.first !== t.last) ? t.first + ' ~ ' + t.last : (t.first || t.last || ''),
    }))
  }
  return fallbackThemes.map((t) => ({ name: t[0], peak: t[1], days: t[2], span: t[3] }))
})
const maxCount = computed(() => Math.max(...displayThemes.value.map((t) => t.peak)))
const stageTotal = computed(() => stages.value.reduce((a, b) => a + b.n, 0))
const maxStage = computed(() => Math.max(...stages.value.map((s) => s.n)))

onMounted(async () => {
  /* 题材生命期（themelife）+ 滚动校准（calib）：各自独立拉取互不阻断 */
  try {
    const r = await callApi('themelife')
    if (r && r.ok && Array.isArray(r.top) && r.top.length) {
      tlTop.value = r.top
      tlLast.value = r.last || ''
    }
  } catch (e) { /* 保持静态回退 */ }
  try {
    const r = await callApi('calib')
    if (r && r.ok && r.window && r.window.days) {
      span.value = {
        from: r.window.from || span.value.from,
        to: r.window.to || span.value.to,
        days: r.window.days,
        src: span.value.src,
      }
      if (r.hits && r.hits.climax_total) hitNums.value = r.hits
      if (r.stages && Object.keys(r.stages).length) stageNums.value = r.stages
      if (typeof r.pending_climax === 'number') pendingClimax.value = r.pending_climax
      calibLast.value = r.last || ''
    }
  } catch (e) { /* 保持静态回退 */ }
})
</script>

<template>
  <div class="page">
    <!-- 校准窗口 -->
    <div class="card">
      <div class="card-title">回测校准窗口</div>
      <div class="tiny muted" style="margin: 2px 0 8px">
        <template v-if="calibLast">
          <span class="tl-live">● 随最新交易日滚动重算</span> · 截至 {{ calibLast }}
        </template>
        <template v-else>静态基线（2026-09-02 定案）· 实时数据暂不可达时回退</template>
      </div>
      <div class="kv">
        <div class="kvi">
          <div class="k mono">{{ span.days }}</div>
          <div class="v">交易日</div>
        </div>
        <div class="kvi">
          <div class="k mono sm">{{ span.from }}</div>
          <div class="v">起始</div>
        </div>
        <div class="kvi">
          <div class="k mono sm">{{ span.to }}</div>
          <div class="v">截止</div>
        </div>
      </div>
      <div class="tiny muted mt">
        数据源：{{ span.src }}（东财历史池仅 ~15 交易日不可测，故改用同花顺，历史窗口约 1 年）。
        每日收盘后把当日新样本纳入回放重新自评，顶点门槛（涨停家数 p75=81）自种子窗口冻结。
      </div>
    </div>

    <!-- 刻度变更 -->
    <div class="card">
      <div class="card-title">刻度校准：旧 → 新</div>
      <div v-for="r in scaleRows" :key="r.k" class="srow">
        <div class="skey">{{ r.k }}</div>
        <div class="sold mono">{{ r.old }}</div>
        <div class="sarrow muted">→</div>
        <div class="snow mono">{{ r.now }}</div>
      </div>
      <div class="tiny muted mt">
        旧刻度（涨停 70 / 高度 6）在全年回放中饱和：连续 5 日全被判为「高潮」，失去区分度。新刻度取样本
        p88~p92 分位，使分档随真实热度展开。
      </div>
    </div>

    <!-- 命中率 -->
    <div class="card">
      <div class="card-title">转折点自评命中率</div>
      <div v-for="h in hits" :key="h.label" class="hrow">
        <div class="row between">
          <span class="hlabel">{{ h.label }}</span>
          <span class="hpct mono" :class="h.color">{{ ((h.hit / h.total) * 100).toFixed(1) }}%</span>
        </div>
        <div class="bar mt6">
          <i :class="h.color" :style="{ width: (h.hit / h.total) * 100 + '%' }"></i>
        </div>
        <div class="tiny muted mt4">
          {{ h.hit }} / {{ h.total }} · {{ h.note }}
        </div>
      </div>
      <div v-if="pendingClimax !== null" class="tiny muted pend">
        近 3 日待确认顶点 <b class="mono">{{ pendingClimax }}</b> 个 —— 顶点须在其后 3 个交易日内
        回落 ≥30% 才计入分母，因此命中率通常每 5–7 个交易日才变动 1 个单位，而非每日跳动。
      </div>
    </div>

    <!-- 五阶段分布 -->
    <div class="card">
      <div class="card-title">周期阶段分布（{{ stageTotal }} 日）</div>
      <div v-for="s in stages" :key="s.name" class="strow">
        <div class="stname">{{ s.name }}</div>
        <div class="stbar">
          <div class="bar">
            <i :style="{ width: (s.n / maxStage) * 100 + '%', background: s.color }"></i>
          </div>
        </div>
        <div class="stn mono">{{ s.n }}</div>
      </div>
      <div class="tiny muted mt">
        单位：历史交易日（非标的数）。分布形态健康：震荡为主、高潮次之、启动与退潮为少数极端态，符合真实市场节奏。
      </div>
    </div>

    <!-- 题材生命期 -->
    <div class="card">
      <div class="card-title">题材生命期 TOP15</div>
      <div class="tiny muted" style="margin: 2px 0 6px">
        <template v-if="tlLast">
          <span class="tl-live">● 每交易日收盘自动更新</span> · 截至 {{ tlLast }}
        </template>
        <template v-else>静态基线（2026-09-02 定案）· 实时数据暂不可达时回退</template>
      </div>
      <div v-for="(t, i) in displayThemes" :key="t.name" class="throw">
        <span class="rank mono" :class="{ hot: i < 3 }">{{ i + 1 }}</span>
        <span class="tname">{{ t.name }}</span>
        <div class="tbar">
          <div class="bar">
            <i :style="{ width: (t.peak / maxCount) * 100 + '%' }"></i>
          </div>
          <div class="tl-sub tiny muted">{{ t.days }} 个交易日出现 · {{ t.span }}</div>
        </div>
        <span class="tpeak mono">{{ t.peak }}<span class="tiny muted">峰</span></span>
      </div>
      <div class="tiny muted mt">
        峰值 = 单日板块内涨停家数最高值；长生命期题材（如央企 239 日）多为轮动型底座，非主升题材。
      </div>
    </div>

    <!-- 口径声明 -->
    <div class="card warn">
      <div class="card-title">口径声明（务必阅读）</div>
      <ul class="notes">
        <li>
          <b>离线 vs 在线</b>：回放只喂涨停池，缺少炸板 / 跌停 / 隔日溢价三项输入，离线温度上限约
          82.5；在线全量输入一般比离线高 5–8 分。分档阈值按<b>离线口径</b>标定，故在线读数会整体偏高一档左右，属预期内。
        </li>
        <li>
          <b>自评循环性</b>：高潮顶点 / 退潮的标签由「涨停家数生长曲线」定义，而判定规则同样吃涨停数据
          —— 命中率是<b>自洽性检查</b>而非独立样本外检验，68% / 86% 仅作启发式参考，不具备统计显著性。
        </li>
        <li>
          <b>样本窗口</b>：{{ span.days }} 个交易日集中在 2025-08 起（随交易日滚动延展），未覆盖熊市深水区与极端政策市，结论外推需谨慎。
        </li>
      </ul>

      <!-- 按顺序看 -->
      <div class="guide">
        <div class="guide-h">📖 怎么按顺序看（本系统正确读法）</div>
        <p class="guide-lead">
          五页是一套「先判环境 → 找主线 → 定标的 → 查异动 → 校口径」的闭环，<b>从大到小再回到口径</b>。
          读数的顺序错了，容易把「高潮日」误当「可追日」。建议每天按 ①→⑤ 走一遍：
        </p>
        <ol class="steps">
          <li>
            <span class="st-no">①</span><b>盘面</b>：先看大盘涨跌与<b>温度计分档</b>（冰点/偏冷/活跃/高潮）和<b>周期定位</b>（启动/发酵/高潮/震荡/退潮）。
            <span class="st-why">先定「今天值不值得做」——温低、周期在退潮时管住手，别急着翻票。</span>
          </li>
          <li>
            <span class="st-no">②</span><b>题材</b>：看主线题材的<b>强度</b>（涨停家数）与<b>生命期</b>（是否刚启动 / 已高位钝化）。
            <span class="st-why">环境允许时，钱只在主线里；挑强度上升、未钝化的题材，回避连涨多日的老题材。</span>
          </li>
          <li>
            <span class="st-no">③</span><b>核心池</b>：系统按评分卡排出的核心标的（含连板高度、题材地位、容量）。
            <span class="st-why">从主线里锁定具体候选——优先核心池内、"地位靠前 + 仍在 ① 的安全周期"的标的。</span>
          </li>
          <li>
            <span class="st-no">④</span><b>体检</b>：对候选个股查<b>3/10/30 日偏离值</b>与<b>严重异动余量</b>（距触发监管阈值还差多少）。
            <span class="st-why">下手前最后一关：偏离过大或余量过薄 = 随时触异动停牌，仓位与买点要相应收。这是"核心×周期×仓位×风控"里的风控落点。</span>
          </li>
          <li>
            <span class="st-no">⑤</span><b>复盘（本页）</b>：看刻度校准、命中率自评与上方<b>口径声明</b>。
            <span class="st-why">理解前面所有数字是怎么算出来的、哪条是启发式——读数偏高是离线/在线口径差异，命中率只是自洽性检查。看完这页才不会被数字带着走。</span>
          </li>
        </ol>
        <p class="guide-tip">
          💡 一句话：<b>盘面定生死 → 题材定方向 → 核心池定标的 → 体检定风控 → 复盘定认知</b>。
          其中 ① 是总开关，⑤ 是校准器；中间三页是从环境下钻到个股的标准动作。
        </p>
      </div>
    </div>

    <div class="tiny muted center">
      P4 校准于 2026-09-02 完成 · 命中率/阶段分布随交易日滚动重算（同源重放零漂移）· 完整回放明细见 .workbuddy/p4/replay_table.md
    </div>
  </div>
</template>

<style scoped>
.kv { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.kvi {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  padding: 10px 8px;
  text-align: center;
}
.kvi .k { font-size: 20px; font-weight: 700; color: var(--gold); }
.kvi .k.sm { font-size: 13px; color: var(--t-1); }
.kvi .v { font-size: 11px; color: var(--t-3); margin-top: 2px; }

.mt { margin-top: 10px; }
.mt6 { margin-top: 6px; }
.mt4 { margin-top: 4px; }

.srow {
  display: grid;
  grid-template-columns: 74px 1fr 14px 1fr;
  align-items: center;
  gap: 6px;
  padding: 8px 0;
  border-bottom: 1px dashed rgba(255, 255, 255, 0.05);
  font-size: 11.5px;
}
.srow:last-child { border-bottom: 0; }
.skey { color: var(--t-2); font-size: 12px; min-width: 0; }
.sold { color: var(--t-3); text-decoration: line-through; min-width: 0; overflow-wrap: anywhere; }
.sarrow { text-align: center; }
.snow { color: var(--gold); font-weight: 600; min-width: 0; overflow-wrap: anywhere; }

.hrow { padding: 9px 0; border-bottom: 1px dashed rgba(255, 255, 255, 0.05); }
.hrow:last-child { border-bottom: 0; }
.hlabel { font-size: 13px; }
.hpct { font-size: 15px; font-weight: 700; }
.hpct.gold { color: var(--gold); }
.hpct.red { color: var(--up); }
.hpct.green { color: var(--down); }
.pend {
  margin-top: 10px;
  padding-top: 9px;
  border-top: 1px solid var(--line);
  line-height: 1.7;
}
.pend b { color: var(--gold); font-size: 13px; }
.bar > i.gold { background: linear-gradient(90deg, var(--gold), var(--orange)); }
.bar > i.red { background: linear-gradient(90deg, #ff7a45, var(--up)); }
.bar > i.green { background: linear-gradient(90deg, #34d399, var(--down)); }

.strow { display: grid; grid-template-columns: 40px 1fr 34px; align-items: center; gap: 10px; padding: 6px 0; }
.stname { font-size: 13px; color: var(--t-2); }
.stn { text-align: right; font-size: 13px; font-weight: 600; }

.throw { display: grid; grid-template-columns: 20px 76px 1fr 42px; align-items: center; gap: 8px; padding: 6px 0; }
.rank {
  width: 17px; height: 17px; border-radius: 5px;
  display: grid; place-items: center; font-size: 10.5px;
  background: rgba(255, 255, 255, 0.07); color: var(--t-3);
}
.rank.hot { background: var(--gold-dim); color: var(--gold); }
.tname { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tbar { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.tl-sub { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tl-live { color: var(--gold); font-weight: 600; }
.tpeak { text-align: right; font-size: 13px; font-weight: 600; }

.warn { border-color: rgba(233, 183, 92, 0.28); background: rgba(233, 183, 92, 0.05); }
.notes { margin: 0; padding-left: 16px; }
.notes li { font-size: 12px; color: var(--t-2); line-height: 1.65; margin-bottom: 7px; }
.notes li:last-child { margin-bottom: 0; }
.notes b { color: var(--t-1); }

/* 按顺序看（口径声明子节） */
.guide { margin-top: 14px; padding-top: 13px; border-top: 1px dashed rgba(233, 183, 92, 0.22); }
.guide-h { font-size: 13px; font-weight: 700; color: var(--gold); margin-bottom: 8px; }
.guide-lead { font-size: 11.5px; color: var(--t-2); line-height: 1.7; margin: 0 0 10px; }
.guide-lead b { color: var(--t-1); }
.steps { list-style: none; margin: 0; padding: 0; }
.steps > li {
  position: relative;
  padding: 8px 0 8px 30px;
  font-size: 12px;
  color: var(--t-2);
  line-height: 1.62;
  border-left: 2px solid rgba(233, 183, 92, 0.22);
  margin-left: 6px;
}
.steps > li:last-child { border-left-color: transparent; }
.st-no {
  position: absolute;
  left: -6px;
  top: 7px;
  width: 18px; height: 18px;
  border-radius: 50%;
  background: var(--gold-dim);
  color: var(--gold);
  font-size: 11px;
  font-weight: 700;
  display: grid; place-items: center;
}
.steps b { color: var(--t-1); }
.st-why { display: block; margin-top: 3px; font-size: 11px; color: var(--t-3); line-height: 1.6; }
.guide-tip {
  margin: 11px 0 0;
  padding: 9px 11px;
  border-radius: var(--r-sm);
  background: rgba(233, 183, 92, 0.08);
  border: 1px solid rgba(233, 183, 92, 0.2);
  font-size: 11.5px;
  color: var(--t-2);
  line-height: 1.7;
}
.guide-tip b { color: var(--gold); }

.center { text-align: center; }
</style>
