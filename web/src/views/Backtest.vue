<script setup>
// web/src/views/Backtest.vue —— 回测复盘（只验证周期分类，非盈亏）。数据来自 callApi：
//   'calib'    → {ok, window{from,to,days}, hits{climax_total,strict,loose,retreat_total,retreat_hit}, stages{}, pending_climax, last}
//   'themelife'→ {ok, top[{name,peak,days,first,last}], last}
import { ref, computed, onMounted } from 'vue'
import { callApi } from '../api/cloud'
const cal = ref(null); const life = ref([]); const err = ref('')
const rate = (a, b) => b ? Math.round((a / b) * 100) + '%' : '—'
const hits = () => cal.value?.hits || {}
const climax = () => rate(hits().strict, hits().climax_total)
const climaxLoose = () => rate(hits().loose, hits().climax_total)
const retreat = () => rate(hits().retreat_hit, hits().retreat_total)
const maxPeak = computed(() => Math.max(1, ...life.value.map(t => t.peak || 0)))
onMounted(async () => {
  try {
    const c = await callApi('calib'); if (c && c.ok) cal.value = c
    const t = await callApi('themelife', { n: 12 }); if (t && t.ok) life.value = t.top || []
    if (!c?.ok) err.value = c?.error || 'calib 数据不可用'
  } catch (e) { err.value = String(e) }
})
</script>

<template>
  <section class="view">
    <div class="verdict rise"><div class="stage-line"><span class="dot"></span><span class="stage-name">周期分类自洽性 · 非盈亏回测</span><span class="pill" style="margin-left:auto">{{ cal?.window?.from || '—' }} → {{ cal?.window?.to || '—' }}</span></div></div>

    <!-- 桌面 -->
    <div class="desk">
      <div class="drow3">
        <div class="dcard"><div class="eyebrow" style="margin-bottom:9px">高潮命中率</div><div class="hit"><span class="n good">{{ climax() }}</span><span class="muted mono" style="font-size:11px">严格</span></div><div class="muted" style="font-size:11px;margin-top:4px">宽松 {{ climaxLoose() }} · 样本 {{ hits().climax_total ?? '—' }}</div></div>
        <div class="dcard"><div class="eyebrow" style="margin-bottom:9px">退潮命中率</div><div class="hit"><span class="n bad">{{ retreat() }}</span><span class="muted mono" style="font-size:11px">严格</span></div><div class="muted" style="font-size:11px;margin-top:4px">样本 {{ hits().retreat_total ?? '—' }} · 最需补强</div></div>
        <div class="dcard"><div class="eyebrow" style="margin-bottom:9px">窗口</div><div class="hit"><span class="n">{{ cal?.window?.days ?? '—' }}</span><span class="muted mono" style="font-size:11px">交易日</span></div><div class="muted" style="font-size:11px;margin-top:4px">pending_climax：{{ cal?.pending_climax ?? '—' }}</div></div>
      </div>
      <div class="md">
        <div class="dtbl-wrap"><div class="dtbl-scroll"><table class="dtable">
          <thead><tr><th>#</th><th>题材</th><th class="r">峰值</th><th class="r">持续</th><th class="r">首现</th><th class="r">最近</th><th style="width:120px">广度</th></tr></thead>
          <tbody>
            <tr v-for="(t, i) in life" :key="t.name">
              <td class="mono">{{ i + 1 }}</td><td><span class="nm">{{ t.name }}</span></td>
              <td class="r mono">{{ t.peak ?? 0 }}</td><td class="r mono">{{ t.days ?? 0 }}</td>
              <td class="mono cd">{{ t.first || '—' }}</td><td class="mono cd">{{ t.last || '—' }}</td>
              <td><div class="hbar"><i :style="{ width: ((t.peak || 0) / maxPeak * 100) + '%' }"></i></div></td>
            </tr>
            <tr v-if="!life.length"><td colspan="7" class="muted" style="padding:16px">加载题材持续性数据…</td></tr>
          </tbody>
        </table></div></div>
        <div class="dcard">
          <div class="eyebrow" style="margin-bottom:8px">分阶段命中</div>
          <template v-if="cal?.stages && Object.keys(cal.stages).length">
            <div class="kv" v-for="(v, k) in cal.stages" :key="k"><span class="k">{{ k }}</span><span class="v">{{ typeof v === 'object' ? (v.hit + '/' + v.n) : v }}</span></div>
          </template>
          <div v-else class="muted" style="font-size:12px">暂无阶段统计</div>
          <div class="muted" style="font-size:11px;margin-top:10px">校准为人工调表（不自优化）；数据缺失以「—」标注。</div>
        </div>
      </div>
    </div>

    <!-- 移动 -->
    <div class="mob">
      <div class="grid2">
        <div class="card"><div class="eyebrow" style="margin-bottom:9px">高潮命中</div><div class="hit"><span class="n good">{{ climax() }}</span></div></div>
        <div class="card"><div class="eyebrow" style="margin-bottom:9px">退潮命中</div><div class="hit"><span class="n bad">{{ retreat() }}</span></div></div>
      </div>
      <div class="card" style="margin-top:12px;padding:2px 15px">
        <div class="li" v-for="(t, i) in life.slice(0, 10)" :key="t.name">
          <span class="rk">{{ i + 1 }}</span>
          <div class="grow"><div class="name">{{ t.name }}</div><div class="sub">峰值{{ t.peak ?? 0 }} · {{ t.days ?? 0 }} 日</div></div>
          <div class="hbar" style="width:60px"><i :style="{ width: ((t.peak || 0) / maxPeak * 100) + '%' }"></i></div>
        </div>
        <div v-if="!life.length" class="muted" style="padding:14px;font-size:13px">加载中…</div>
      </div>
    </div>
    <div class="muted" v-if="err && !cal" style="font-size:12px">{{ err }}</div>
  </section>
</template>

<style scoped>
.view { display: flex; flex-direction: column; gap: 16px; }
</style>
