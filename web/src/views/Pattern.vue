<script setup>
// web/src/views/Pattern.vue —— 形态（MA7/MA21 粘合突破）。
// pattern {scan_n,hit_n,hits[],watch[],selfs[],params{...}}; 行: {code,name,board,pool('zt'|'active'),in_core,in_self,vol_ok,vol_ratio,flow_score,glue_days,glue,pct,close,ma7,ma21,flow{main_net,main_ratio,...}}
// ⚠ pattern.pct 已是显示单位（不 ×100）。
import { useSnap } from '../stores/snap'
const s = useSnap()
const rawpct = v => v == null ? '—' : (v >= 0 ? '+' : '') + v + '%'
const vol = v => v == null ? '—' : v + '×'
</script>

<template>
  <section class="view">
    <div class="verdict rise">
      <div class="stage-line"><span class="dot"></span><span class="stage-name">MA7 / MA21 粘合突破 · 扫描 {{ s.pattern?.scan_n ?? '—' }}</span></div>
      <h3 style="font-size:26px">涨停日之前的潜伏位 · 命中 <em>{{ s.pattern?.hit_n ?? (s.pattern?.hits || []).length }}</em> 只</h3>
      <div class="sub">粘合 ≤2.5% 持续 ≥3 日、收盘上穿 MA21 且 MA7 向上。放量 1.5× 仅作提示，不卡信号。</div>
    </div>

    <!-- 桌面：表格 + 观察右栏 -->
    <div class="desk" style="margin-top:18px"><div class="md">
      <div class="dtbl-wrap"><div class="dtbl-scroll"><table class="dtable">
        <thead><tr><th>名称 · 代码</th><th class="r">连板</th><th class="r">粘合</th><th class="r">量比</th><th class="r">涨幅</th><th class="r">flow</th><th class="r">池</th><th class="r">状态</th></tr></thead>
        <tbody>
          <tr v-for="p in (s.pattern?.hits || [])" :key="p.code">
            <td><span class="nm">{{ p.name }}</span> <span class="cd">{{ p.code }}</span></td>
            <td class="r mono">{{ p.board || '—' }}</td>
            <td class="r mono">{{ p.glue_days ?? 0 }} 日</td>
            <td class="r mono" :class="p.vol_ok ? 'up' : 'muted'">{{ vol(p.vol_ratio) }}</td>
            <td class="r mono" :class="(p.pct ?? 0) >= 0 ? 'up' : 'down'">{{ rawpct(p.pct) }}</td>
            <td class="r sc">{{ p.flow_score ?? '—' }}</td>
            <td class="r"><span class="pill">{{ p.pool === 'zt' ? '涨停池' : '放量池' }}</span></td>
            <td class="r"><span class="tag brass">突破</span></td>
          </tr>
          <tr v-if="!(s.pattern?.hits || []).length"><td colspan="8" class="muted" style="padding:16px">今日无新增突破</td></tr>
        </tbody>
      </table></div></div>
      <div class="dcard" v-if="(s.pattern?.watch || []).length">
        <div class="eyebrow" style="margin-bottom:8px">粘合中 · 待突破（{{ s.pattern.watch.length }}）</div>
        <div class="li" v-for="n in s.pattern.watch.slice(0, 10)" :key="n.code">
          <div class="grow"><div class="name" style="font-size:13px">{{ n.name }}</div><div class="sub">{{ n.code }} · 粘合{{ n.glue_days ?? 0 }}日</div></div>
          <span class="pill">{{ n.pool === 'zt' ? '涨停' : '放量' }}</span>
        </div>
      </div>
    </div></div>

    <!-- 移动：卡片 -->
    <div class="mob">
      <div class="cores-grid" style="margin-top:18px">
        <div v-for="p in (s.pattern?.hits || [])" :key="p.code" class="card">
          <div class="li" style="border:0;padding-top:2px">
            <div class="grow"><div class="name">{{ p.name }} <span class="mono" style="font-size:10px;color:var(--ink-3)">{{ p.code }}</span></div>
              <div class="sub">粘合{{ p.glue_days ?? 0 }}日 · 量比{{ vol(p.vol_ratio) }} · {{ rawpct(p.pct) }}</div></div>
            <div class="rt"><div class="score">{{ p.flow_score ?? '—' }}</div><div class="sc-lab">突破</div></div>
          </div>
          <div class="chips" style="margin-top:10px">
            <span v-if="p.vol_ok" class="tag brass">放量确认</span>
            <span v-if="(p.flow_score ?? 0) >= 70" class="tag">主力净流入</span>
            <span class="pill">{{ p.pool === 'zt' ? '涨停池' : '放量池' }}</span>
          </div>
        </div>
        <div v-if="!(s.pattern?.hits || []).length" class="muted card" style="padding:16px;font-size:13px">今日无新增突破</div>
      </div>
      <div v-if="(s.pattern?.watch || []).length" class="card" style="margin-top:12px;padding:2px 15px">
        <div class="card-title" style="padding:10px 0 0">待突破 · {{ s.pattern.watch.length }}</div>
        <div class="li" v-for="n in s.pattern.watch.slice(0, 6)" :key="n.code">
          <div class="grow"><div class="name" style="font-size:13px">{{ n.name }}</div><div class="sub">粘合{{ n.glue_days ?? 0 }}日</div></div>
          <span class="pill">观察</span>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.view { display: flex; flex-direction: column; }
</style>
