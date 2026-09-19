<script setup>
// web/src/views/Themes.vue —— 题材榜。真实字段：themes[] {name, count(今日涨停家数), max_board(最高板), members[{code,name,board,pct,zttj}]}
// 题材"峰值/天数/生命周期"来自 callApi('themelife')，不在此快照内；此页展示当日题材广度分布与成分。
import { computed } from 'vue'
import { useSnap } from '../stores/snap'
const s = useSnap()
const list = computed(() => (s.themes || []).slice().sort((a, b) => (b.count || 0) - (a.count || 0)))
const maxCount = computed(() => Math.max(1, ...list.value.map(t => t.count || 0)))
const coreSet = computed(() => new Set((s.cores || []).map(c => c.code)))
const top = computed(() => list.value[0] || {})
const hasCore = t => (t.members || []).some(m => coreSet.value.has(m.code))
const pct = v => v == null ? '—' : (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + '%'
</script>

<template>
  <section class="view">
    <div class="verdict rise">
      <div class="stage-line"><span class="dot"></span><span class="stage-name">主线题材 · {{ top.name || '—' }}</span></div>
      <h3 style="font-size:26px">{{ top.name || '—' }}<template v-if="top.count"> · {{ top.count }} 家 · 最高 {{ top.max_board }} 板</template></h3>
      <div class="sub">按今日涨停家数排序；家数=题材广度，最高板=题材高度。</div>
    </div>

    <!-- 桌面：表格 + 主线详情 -->
    <div class="desk" style="margin-top:18px"><div class="md">
      <div class="dtbl-wrap"><div class="dtbl-scroll"><table class="dtable">
        <thead><tr><th>#</th><th>题材</th><th class="r">家数</th><th class="r">最高板</th><th class="r">核心</th><th style="width:150px">广度</th><th class="r">龙头</th></tr></thead>
        <tbody>
          <tr v-for="(t, i) in list.slice(0, 15)" :key="t.name">
            <td class="mono">{{ i + 1 }}</td>
            <td><span class="nm">{{ t.name }}</span></td>
            <td class="r mono">{{ t.count ?? 0 }}</td>
            <td class="r mono">{{ t.max_board ?? 0 }}</td>
            <td class="r"><span v-if="hasCore(t)" class="tag brass">有</span><span v-else class="muted">—</span></td>
            <td><div class="hbar"><i :style="{ width: ((t.count || 0) / maxCount * 100) + '%' }"></i></div></td>
            <td class="mono cd">{{ (t.members || []).slice().sort((a,b)=>(b.board||0)-(a.board||0))[0]?.name || '—' }}</td>
          </tr>
          <tr v-if="!list.length"><td colspan="7" class="muted" style="padding:16px">暂无题材数据</td></tr>
        </tbody>
      </table></div></div>
      <div class="dcard" v-if="top.name">
        <div class="eyebrow" style="margin-bottom:10px">主线成分</div>
        <div style="font-family:var(--font-disp);font-size:22px;font-weight:600">{{ top.name }}</div>
        <div class="muted" style="font-size:12px;margin-top:2px">{{ top.count ?? 0 }} 家 · 最高 {{ top.max_board ?? 0 }} 板</div>
        <div class="kv" style="margin-top:12px"><span class="k">今日涨停家</span><span class="v">{{ top.count ?? 0 }}</span></div>
        <div class="kv"><span class="k">含核心</span><span class="v" :class="hasCore(top) ? 'up' : ''">{{ hasCore(top) ? '是' : '否' }}</span></div>
        <div class="sub" style="margin:12px 0 6px;font-family:var(--font-mono);font-size:10.5px;color:var(--ink-3)">成分（按板高）</div>
        <div class="li" v-for="m in (top.members || []).slice().sort((a,b)=>(b.board||0)-(a.board||0)).slice(0,6)" :key="m.code" style="padding:7px 0">
          <div class="grow"><div class="name" style="font-size:13px">{{ m.name }}</div><div class="sub">{{ m.code }} · {{ m.board || 0 }}板</div></div>
          <span class="mono" :class="(m.pct ?? 0) >= 0 ? 'up' : 'down'">{{ pct(m.pct) }}</span>
        </div>
      </div>
    </div></div>

    <!-- 移动：列表 -->
    <div class="mob" style="margin-top:18px">
      <div class="card" style="padding:2px 15px">
        <div class="li" v-for="(t, i) in list.slice(0, 15)" :key="t.name">
          <span class="rk">{{ i + 1 }}</span>
          <div class="grow">
            <div class="name">{{ t.name }}</div>
            <div class="sub">{{ t.count ?? 0 }} 家 · 最高 {{ t.max_board ?? 0 }} 板</div>
            <div class="hbar" style="margin-top:6px"><i :style="{ width: ((t.count || 0) / maxCount * 100) + '%' }"></i></div>
          </div>
          <span class="tag" :class="i === 0 ? 'brass' : ''">{{ i === 0 ? '主线' : (hasCore(t) ? '有核' : '') }}</span>
        </div>
        <div v-if="!list.length" class="muted" style="padding:14px;font-size:13px">暂无题材数据</div>
      </div>
      <div class="grid2" style="margin-top:12px">
        <div class="stat-s"><div class="l">题材数</div><div class="v">{{ list.length }}</div></div>
        <div class="stat-s"><div class="l">最高板</div><div class="v">{{ top.max_board ?? '—' }}</div></div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.view { display: flex; flex-direction: column; }
</style>
