<script setup>
// web/src/views/Check.vue —— 异动体检。默认展示 Lab 体检榜（snap.lab.ranks 真实数据）；
// 输入代码 → callApi('stock',{code,full:'1'}) 拿单股偏离复核：
//   dev{risk_level,dev_3d,dev_10d,dev_30d,headroom_30d_up,near_serious,limit_pct,normal_3d_triggered,same_dir_up_count}
//   score{grade,state,total,sub_a,sub_b,risk_total,risk_items[]}  market{stage,heat,band,max_board}
import { ref } from 'vue'
import { useSnap } from '../stores/snap'
import { callApi } from '../api/cloud'
const s = useSnap()
const q = ref(''); const st = ref(null); const busy = ref(false); const err = ref('')
const pc = v => v == null ? '—' : (v * 100).toFixed(1) + '%'
const sgn = v => v == null ? '—' : (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + '%'
const dev = () => st.value?.dev || {}
const score = () => st.value?.score || {}
const mk = () => st.value?.market || {}
const ranks = () => s.lab?.ranks || []
async function lookup () {
  const c = q.value.trim(); if (!c) return
  busy.value = true; err.value = ''; try {
    const r = await callApi('stock', { code: c, full: '1' })
    if (r && r.ok) st.value = r; else err.value = (r && r.error) || '未查询到该标的'
  } catch (e) { err.value = String(e) } finally { busy.value = false }
}
</script>

<template>
  <section class="view">
    <div class="search">
      <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4-4" /></svg>
      <input v-model="q" :placeholder="busy ? '查询中…' : '输入代码，回车体检 · 如 600001'" @keyup.enter="lookup" />
      <button class="btn solid" style="padding:5px 13px" @click="lookup">体检</button>
    </div>
    <div class="err" v-if="err">{{ err }}</div>

    <!-- 单股详情（已查询） -->
    <div v-if="st" class="desk"><div class="md">
      <div class="dcard">
        <div class="stage-line"><span class="dot risk"></span><span class="stage-name">{{ dev().risk_level || '—' }} · {{ st.name }}</span><span class="muted mono" style="margin-left:auto;font-size:11px">{{ st.code }}</span></div>
        <div class="bignum"><div><div class="eyebrow" style="margin-bottom:6px">3 日偏离值 · vs {{ dev().bench_name || '基准' }}</div><div class="n up">{{ sgn(dev().dev_3d) }}</div></div>
          <div style="text-align:right;padding-bottom:6px"><div class="muted" style="font-size:11px">距严重·30日</div><div class="mono" style="font-size:13px;font-weight:700;color:var(--risk)">{{ dev().near_serious ? '逼近' : (dev().headroom_30d_up != null ? '余量 ' + pc(dev().headroom_30d_up) : '—') }}</div></div></div>
        <div class="dtbl-wrap" style="margin-top:16px;border:0"><table class="dtable">
          <thead><tr><th>窗口</th><th class="r">偏离值</th><th class="r">判定</th></tr></thead>
          <tbody>
            <tr><td>3 日</td><td class="r mono" :class="dev().normal_3d_triggered ? 'up' : ''">{{ sgn(dev().dev_3d) }}</td><td class="r"><span class="tag" :class="dev().normal_3d_triggered ? 'risk' : ''">{{ dev().normal_3d_triggered ? '普通异动' : '正常' }}</span></td></tr>
            <tr><td>10 日</td><td class="r mono">{{ sgn(dev().dev_10d) }}</td><td class="r muted mono">同向 {{ dev().same_dir_up_count ?? 0 }} 次</td></tr>
            <tr><td>30 日</td><td class="r mono">{{ sgn(dev().dev_30d) }}</td><td class="r"><span class="tag" :class="dev().serious_30d_up ? 'risk' : ''">{{ dev().serious_30d_up ? '严重异动' : '未触发' }}</span></td></tr>
          </tbody>
        </table></div>
      </div>
      <div class="dcard">
        <div class="eyebrow" style="margin-bottom:8px">核心评分</div>
        <div class="bignum" style="margin-bottom:10px"><div class="hit"><span class="n" style="font-size:34px">{{ score().total ?? '—' }}</span><span class="badge" :class="score().grade" style="margin-left:6px">{{ score().grade }}</span></div></div>
        <div class="bars">
          <div class="b"><div class="bar"><i :style="{ width: ((score().sub_a || 0) / 40 * 100) + '%' }"></i></div><div class="bl">A {{ score().sub_a ?? 0 }}/40</div></div>
          <div class="b"><div class="bar"><i :style="{ width: ((score().sub_b || 0) / 30 * 100) + '%' }"></i></div><div class="bl">B {{ score().sub_b ?? 0 }}/30</div></div>
          <div class="b risk"><div class="bar"><i :style="{ width: ((score().risk_total || 0) / 30 * 100) + '%' }"></i></div><div class="bl">C −{{ score().risk_total ?? 0 }}</div></div>
        </div>
        <div class="muted" style="font-size:12px;margin-top:8px">{{ score().state || '' }}</div>
        <div class="kv" style="margin-top:10px"><span class="k">周期 · 情绪</span><span class="v">{{ mk().stage || '—' }} / {{ mk().heat ?? '—' }}</span></div>
        <div class="kv"><span class="k">最高板</span><span class="v">{{ mk().max_board ?? '—' }}</span></div>
        <div v-for="(ri, i) in (score().risk_items || []).slice(0, 4)" :key="i" class="tag risk" style="margin:6px 6px 0 0">{{ ri.name }} −{{ ri.score }}</div>
      </div>
    </div></div>

    <!-- 体检榜（真实 lab.ranks） -->
    <div class="blk" style="margin-top:16px">
      <div class="blk-h"><span class="card-title">Lab 体检榜 · 池 {{ s.lab?.pool_n ?? '—' }} · 否决 {{ s.lab?.veto_n ?? 0 }}</span><span class="muted mono" style="font-size:11px">lab = q×30% + e×70%</span></div>
      <div class="desk"><div class="dtbl-wrap"><div class="dtbl-scroll"><table class="dtable">
        <thead><tr><th>#</th><th>名称 · 代码</th><th class="r">板</th><th class="r">Lab</th><th class="r">质量 q</th><th class="r">情绪 e</th><th class="r">评级</th><th>处置</th></tr></thead>
        <tbody>
          <tr v-for="(r, i) in ranks().slice(0, 20)" :key="r.code">
            <td class="mono">{{ i + 1 }}</td>
            <td><span class="nm">{{ r.name }}</span> <span class="cd">{{ r.code }}</span></td>
            <td class="r mono">{{ r.board || '—' }}</td>
            <td class="r sc">{{ r.lab ?? '—' }}</td>
            <td class="r mono">{{ r.q ?? '—' }}</td>
            <td class="r mono" :class="(r.e ?? 0) >= 75 ? 'up' : ''">{{ r.e ?? '—' }}</td>
            <td class="r"><span v-if="r.grade" class="badge" :class="r.grade">{{ r.grade }}</span></td>
            <td><span class="pill">{{ r.verb || '—' }}</span></td>
          </tr>
          <tr v-if="!ranks().length"><td colspan="8" class="muted" style="padding:16px">暂无体检数据</td></tr>
        </tbody>
      </table></div></div></div>
      <div class="mob"><div class="card" style="padding:2px 15px">
        <div class="li" v-for="(r, i) in ranks().slice(0, 12)" :key="r.code">
          <span class="rk">{{ i + 1 }}</span>
          <div class="grow"><div class="name">{{ r.name }} <span class="mono" style="font-size:10px;color:var(--ink-3)">{{ r.code }}</span></div><div class="sub">q {{ r.q ?? '—' }} · e {{ r.e ?? '—' }} · {{ r.verb || '—' }}</div></div>
          <div class="rt"><div class="score">{{ r.lab ?? '—' }}</div><div class="sc-lab">Lab</div></div>
        </div>
        <div v-if="!ranks().length" class="muted" style="padding:14px;font-size:13px">暂无体检数据</div>
      </div></div>
    </div>
  </section>
</template>

<style scoped>
.view { display: flex; flex-direction: column; gap: 12px; }
.search { margin-bottom: 2px; }
.search input { border: 0; outline: none; background: transparent; color: var(--ink); font: inherit; font-size: 13px; flex: 1; min-width: 0; }
</style>
