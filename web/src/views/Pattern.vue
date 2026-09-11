<script setup>
import { computed } from 'vue'
import { useSnap } from '../stores/snap'

const s = useSnap()
const pt = computed(() => s.pattern)
const hits = computed(() => (pt.value && pt.value.hits) || [])
const watch = computed(() => (pt.value && pt.value.watch) || [])
const stage = computed(() => (s.cycle && s.cycle.stage) || '')
const ebbHint = computed(() => stage.value === '退潮' || stage.value === '冰点')
const fmt = (v, nd = 2) => (v == null ? '—' : Number(v).toFixed(nd))
const pctCls = (v) => (v > 0 ? 'up' : v < 0 ? 'down' : '')
const sign = (v) => (v > 0 ? '+' : '')
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
          <span class="tag">{{ pt.time_ms }}ms</span>
        </div>

        <div v-if="ebbHint" class="pat-hint tiny">
          当前周期「{{ stage }}」：退潮期整体不建议参与，形态仅作观察，别当买入信号。
        </div>

        <div class="pat-sec tiny muted">突破（粘合后上穿 MA21）</div>
        <div v-if="!hits.length" class="small dim" style="margin-top: 6px">今日无标的触发突破</div>
        <div v-for="r in hits" :key="r.code" class="pat-row hit">
          <div class="pat-line1">
            <span class="pat-name">{{ r.name }}</span>
            <span class="pat-chip">{{ r.board }}板</span>
            <span v-if="r.in_core" class="pat-chip core">核心</span>
            <span class="pat-chip vol" :class="r.vol_ok ? 'ok' : ''">
              量比 {{ fmt(r.vol_ratio) }}<template v-if="r.vol_ok"> · 放量</template>
            </span>
          </div>
          <div class="pat-line2 tiny dim">
            收 {{ r.close }}（<span :class="pctCls(r.pct)">{{ sign(r.pct) }}{{ r.pct }}%</span>）· MA7 {{ r.ma7 }} · MA21 {{ r.ma21 }} · 粘合 {{ r.glue }}% · 已粘合 {{ r.glue_days }} 日
          </div>
        </div>

        <template v-if="watch.length">
          <div class="divider"></div>
          <div class="pat-sec tiny muted">粘合中（尚未突破，观察）</div>
          <div v-for="r in watch" :key="r.code" class="pat-row">
            <div class="pat-line1">
              <span class="pat-name">{{ r.name }}</span>
              <span class="pat-chip">{{ r.board }}板</span>
              <span v-if="r.in_core" class="pat-chip core">核心</span>
              <span class="pat-chip dim-chip">粘合 {{ r.glue_days }} 日</span>
            </div>
            <div class="pat-line2 tiny dim">
              收 {{ r.close }}（<span :class="pctCls(r.pct)">{{ sign(r.pct) }}{{ r.pct }}%</span>）· MA7 {{ r.ma7 }} · MA21 {{ r.ma21 }} · 粘合 {{ r.glue }}%
            </div>
          </div>
        </template>

        <div class="divider"></div>
        <details class="pat-meta">
          <summary class="tiny muted">口径与免责（务必读一次）</summary>
          <div class="pat-meta-body small dim">
            <div>候选池：当日涨停 ∪ 核心池（与 Lab 同池，{{ pt.scan_n }} 只）。</div>
            <div>参数：MA{{ pt.params.ma_fast }} / MA{{ pt.params.ma_slow }}；粘合阈值 {{ (pt.params.glue_pct * 100).toFixed(1) }}%；持续 ≥{{ pt.params.glue_days }} 日；放量线 {{ pt.params.vol_mult }}×。</div>
            <div>K线为<b>前复权</b>，按本项目惯例仅作形态判断，不与涨跌幅 / 偏离值混用。</div>
            <div v-if="pt.errors && pt.errors.length" style="color: var(--orange)">部分标的取数失败：{{ pt.errors.join('；') }}</div>
            <div style="margin-top: 4px">纯技术形态，供研究参考，不构成投资建议；需与周期定位、Lab 排雷、verb 风控交叉验证后使用。</div>
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
.pat-line2 { margin-top: 2px; line-height: 1.5; }
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
