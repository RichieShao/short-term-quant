<script setup>
// web/src/views/Dashboard.vue —— 今日盘面（首屏）。绑定已对齐 snap.js 真实 getter + snapshot 键。
// getters: market[] {name,pct(0-1),close} · sentiment {heat,band,lu,ld,zb_rate,max_board,conn,premium} · cycle {stage,trend,reasons,tone} · cores[] · actions {tone,rules,watch}
// snap: reversal {triggered,active,hint} · heat_detail.percentile {ready,pct}
import { useSnap } from '../stores/snap'
const s = useSnap()
const pc = v => v == null ? '—' : (v * 100).toFixed(1) + '%'
const sgn = v => v == null ? '—' : (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + '%'
const emit = defineEmits(['nav'])
const rev = () => s.snap?.reversal || {}
const pctl = () => s.snap?.heat_detail?.percentile || {}
</script>

<template>
  <section class="view">
    <div class="dcol">
      <!-- 英雄裁决 -->
      <div class="verdict rise">
        <div class="stage-line">
          <span class="dot"></span>
          <span class="stage-name">{{ s.cycle?.stage || '—' }}</span>
          <span v-if="rev().triggered || rev().active" class="tag brass" style="margin-left:auto">冰点反转</span>
        </div>
        <h3>{{ s.actions?.tone || s.cycle?.tone || '见下方操作矩阵' }}</h3>
        <div class="sub">{{ (s.cycle?.reasons && s.cycle.reasons.join(' · ')) || s.cycle?.tone || '' }}</div>
        <div class="vmeta">
          <span class="m">情绪 <b>{{ s.sentiment?.heat ?? '—' }}</b></span>
          <span class="m">涨停 <b>{{ s.sentiment?.lu ?? '—' }}</b></span>
          <span class="m">最高板 <b>{{ s.sentiment?.max_board ?? '—' }}</b></span>
          <span class="m" v-if="s.sentiment?.premium != null">昨日溢价 <b :class="s.sentiment.premium >= 0 ? 'up' : 'down'">{{ sgn(s.sentiment.premium) }}</b></span>
        </div>
      </div>

      <div class="dc">
        <!-- 指数 -->
        <div class="idx">
          <div v-for="ix in (s.market || [])" :key="ix.code || ix.name" class="c">
            <div class="nm">{{ ix.name }}</div>
            <div class="v">{{ ix.close ?? '—' }}</div>
            <div class="p" :class="(ix.pct ?? 0) >= 0 ? 'up' : 'down'">{{ sgn(ix.pct) }}</div>
          </div>
        </div>
        <!-- 温度计 -->
        <div class="card gauge" style="margin-top:14px">
          <div class="blk-h"><span class="card-title">情绪 · 温度计</span><span class="muted" style="font-size:11px">{{ pctl().ready ? ('分位 ' + pctl().pct + '%') : '' }}</span></div>
          <div class="big" style="margin:10px 0 11px"><span class="n">{{ s.sentiment?.heat ?? '—' }}</span><span class="lab muted">{{ s.sentiment?.band || '' }}</span></div>
          <div class="track"><div class="fill" :style="{ width: (s.sentiment?.heat || 0) + '%' }"></div><div class="knob" :style="{ left: (s.sentiment?.heat || 0) + '%' }"></div></div>
          <div class="scale"><span>冰点</span><span>震荡</span><span>发酵</span><span>高潮</span></div>
        </div>
      </div>
    </div>

    <!-- 核心 Top -->
    <div class="blk" style="margin-top:24px">
      <div class="blk-h"><span class="card-title">核心池 · 领先</span><span class="more" @click="emit('nav', 'cores')">全部 ›</span></div>
      <div class="card" style="padding:2px 15px">
        <div class="li" v-for="c in (s.cores || []).slice(0, 5)" :key="c.code">
          <span class="badge" :class="c.grade">{{ c.grade }}</span>
          <div class="grow">
            <div class="name">{{ c.name }}</div>
            <div class="sub">{{ c.board }}板{{ c.zttj ? ' · ' + c.zttj : '' }} · {{ c.industry || '—' }} · 带动{{ c.ind_total ?? 0 }}</div>
          </div>
          <div class="rt"><div class="score">{{ c.total }}</div><div class="sc-lab" :class="c.grade === 'C' ? 'down' : ''">{{ c.state || '' }}</div></div>
        </div>
        <div v-if="!(s.cores || []).length" class="muted" style="padding:14px;font-size:13px">暂无核心数据</div>
      </div>
    </div>

    <!-- 操作速览 -->
    <div v-if="(s.actions?.rules || []).length || (s.actions?.watch || []).length" class="blk" style="margin-top:20px">
      <div class="blk-h"><span class="card-title">操作速览</span><span class="more" @click="emit('nav', 'cores')">逐标的 ›</span></div>
      <div class="card">
        <div class="li" v-for="(r, i) in (s.actions?.rules || []).slice(0, 4)" :key="'r' + i"><div class="grow"><div class="name" style="font-size:13px;font-weight:500">{{ typeof r === 'string' ? r : (r.memo || r.verb) }}</div></div></div>
        <div v-for="(w, i) in (s.actions?.watch || []).slice(0, 3)" :key="'w' + i" class="sub" style="margin-top:4px">◇ {{ w }}</div>
      </div>
    </div>

    <!-- 形态 teaser -->
    <div v-if="(s.pattern?.hits || []).length" class="signal" style="margin-top:18px">
      <div class="st">◆ 形态扫描：{{ s.pattern.hits.length }} 只均线粘合突破</div>
      <div class="sd">MA7 / MA21 粘合 ≥3 日后上穿；出现在涨停日之前，属潜伏位。</div>
    </div>
  </section>
</template>

<style scoped>
.view { display: flex; flex-direction: column; gap: 2px; }
.dc { display: flex; flex-direction: column; }
</style>
