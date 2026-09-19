<script setup>
// web/src/views/Cores.vue —— 核心池。真实字段：
// cores[] {code,name,board,industry,state,grade,total,sub_a(≤40),sub_b(≤30),risk_total(≤30),zttj,ind_total,streak,amount,turnover(0-1),dev{risk_level,headroom_30d_up,...}}
// actions {stage,tone,per_stock[{code,verb,position,memo}]}; freshCodes:Set; prevCoreCodes:Set; fetchPrevCores()
import { ref, computed, onMounted } from 'vue'
import { useSnap } from '../stores/snap'
const s = useSnap()
const filters = ['全部', 'S 级', 'A 级', 'B 级', '禁接力']
const f = ref('全部')
const sel = ref(null)
const w = (v, m) => ((v || 0) / m * 100).toFixed(0) + '%'
const pc = v => v == null ? '—' : (v * 100).toFixed(1) + '%'
const list = computed(() => {
  const arr = (s.cores || []).slice()
  if (f.value === 'S 级') return arr.filter(c => c.grade === 'S')
  if (f.value === 'A 级') return arr.filter(c => c.grade === 'A')
  if (f.value === 'B 级') return arr.filter(c => c.grade === 'B')
  if (f.value === '禁接力') return arr.filter(c => c.grade === 'C' || (c.state || '').includes('禁'))
  return arr.sort((a, b) => (b.total || 0) - (a.total || 0))
})
const by = g => (s.cores || []).filter(c => c.grade === g).length
const verbOf = code => (s.actions?.per_stock || []).find(p => p.code === code)
const isNew = c => { try { return s.freshCodes && (s.freshCodes.has ? s.freshCodes.has(c) : s.freshCodes.includes?.(c)) } catch (e) { return false } }
onMounted(() => { s.fetchPrevCores && s.fetchPrevCores() })
</script>

<template>
  <section class="view">
    <div class="verdict rise">
      <div class="stage-line"><span class="dot"></span><span class="stage-name">{{ s.cycle?.stage || '—' }} · S/A 优先</span></div>
      <h3 style="font-size:24px">A 地位 · B 持续 − C 风险</h3>
      <div class="sub">total = (sub_a + sub_b) − risk_total，归一 0–100；S≥80 / A≥60 / B≥45 / 其余 C。</div>
    </div>

    <div class="filterrow" style="margin:18px 0 14px">
      <span v-for="x in filters" :key="x" class="fchip" :class="{ on: f === x }" @click="f = x">{{ x }}</span>
    </div>

    <div class="sumbar" style="margin-bottom:14px">
      <span class="s">S 级 <b>{{ by('S') }}</b></span>
      <span class="s">A 级 <b>{{ by('A') }}</b></span>
      <span class="s">B 级 <b>{{ by('B') }}</b></span>
      <span class="s">C/禁 <b>{{ by('C') }}</b></span>
      <span class="s">共 <b>{{ list.length }}</b> 只</span>
    </div>

    <!-- 桌面：数据表 -->
    <div class="desk">
      <div class="dtbl-wrap"><div class="dtbl-scroll"><table class="dtable">
        <thead><tr>
          <th>评级</th><th>名称 · 代码</th><th class="r">连板</th><th>板型</th><th class="r">带动</th>
          <th>地位 / 持续 / 风险</th><th class="r">总分</th><th>操作</th><th class="r">状态</th>
        </tr></thead>
        <tbody>
          <tr v-for="c in list" :key="c.code" :class="{ rowsel: sel === c.code }" @click="sel = c.code" style="cursor:pointer">
            <td><span class="badge" :class="c.grade">{{ c.grade }}</span></td>
            <td><span class="nm">{{ c.name }}</span> <span class="cd">{{ c.code }}</span><span v-if="isNew(c.code)" class="tag brass" style="margin-left:6px">新</span></td>
            <td class="r mono">{{ c.board }}</td>
            <td class="mono cd">{{ c.zttj || '—' }}</td>
            <td class="r mono">{{ c.ind_total ?? 0 }}</td>
            <td><span class="minibars" :title="`A${c.sub_a} B${c.sub_b} C-${c.risk_total}`">
              <i :style="{ '--w': w(c.sub_a, 40) }"></i><i :style="{ '--w': w(c.sub_b, 30) }"></i><i class="r" :style="{ '--w': w(c.risk_total, 30) }"></i>
            </span></td>
            <td class="r sc" :class="{ down: c.grade === 'C' }">{{ c.total }}</td>
            <td class="mono cd">{{ verbOf(c.code)?.verb || '—' }}<span v-if="verbOf(c.code)?.position" style="color:var(--brass)"> {{ verbOf(c.code).position }}</span></td>
            <td class="r"><span class="tag" :class="{ brass: c.grade === 'S', risk: c.grade === 'C' || (c.dev?.risk_level || '').includes('严重') }">{{ c.state || '—' }}</span></td>
          </tr>
          <tr v-if="!list.length"><td colspan="9" class="muted" style="padding:16px">该筛选下暂无标的</td></tr>
        </tbody>
      </table></div></div>
    </div>

    <!-- 移动：卡片 -->
    <div class="mob">
      <div class="cores-grid">
        <div v-for="c in list" :key="c.code" class="card" :style="{ borderColor: c.grade === 'C' ? 'var(--line-risk)' : 'var(--line)' }">
          <div class="li" style="border:0;padding-top:2px">
            <span class="badge" :class="c.grade">{{ c.grade }}</span>
            <div class="grow">
              <div class="name">{{ c.name }} <span class="mono" style="font-size:10px;color:var(--ink-3)">{{ c.code }}</span></div>
              <div class="sub">{{ c.board }}板 · {{ c.zttj || '' }} · {{ c.industry || '—' }} · 带动{{ c.ind_total ?? 0 }}</div>
            </div>
            <div class="rt"><div class="score" :class="{ down: c.grade === 'C' }">{{ c.total }}</div><div class="sc-lab">{{ c.state || '' }}</div></div>
          </div>
          <div class="bars">
            <div class="b"><div class="bar"><i :style="{ width: w(c.sub_a, 40) }"></i></div><div class="bl">A 地位 {{ c.sub_a ?? 0 }}/40</div></div>
            <div class="b"><div class="bar"><i :style="{ width: w(c.sub_b, 30) }"></i></div><div class="bl">B 持续 {{ c.sub_b ?? 0 }}/30</div></div>
            <div class="b risk"><div class="bar"><i :style="{ width: w(c.risk_total, 30) }"></i></div><div class="bl">C 风险 −{{ c.risk_total ?? 0 }}</div></div>
          </div>
        </div>
        <div v-if="!list.length" class="muted card" style="padding:16px;font-size:13px">该筛选下暂无标的</div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.view { display: flex; flex-direction: column; }
</style>
