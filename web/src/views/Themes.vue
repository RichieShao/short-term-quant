<script setup>
import { computed, ref } from 'vue'
import { useSnap } from '../stores/snap'
import { signed, pctCls } from '../utils/format'

const s = useSnap()

const list = computed(() => s.themes || [])
const max = computed(() => Math.max(1, ...list.value.map((t) => t.count)))

// 核心池代码集合（用于题材→核心池一键对齐）
const coreCodes = computed(() => new Set((s.cores || []).map((c) => c.code)))

// 每个题材派生：是否含核心池标的 + 龙头集中度（最高连板 / 涨停家数，越高越"一家独大"）
const enriched = computed(() =>
  list.value.map((t) => {
    const members = t.members || []
    const hitCodes = members.filter((m) => coreCodes.value.has(m.code)).map((m) => m.code)
    const concentration = t.count > 0 ? +(t.max_board / t.count).toFixed(2) : 0
    return { ...t, coreHits: hitCodes, hasCore: hitCodes.length > 0, concentration }
  })
)

const sel = ref(null)
function open(t) {
  sel.value = t
}
function close() {
  sel.value = null
}
</script>

<template>
  <div class="page">
    <div class="card">
      <div class="card-title">当日涨停题材分布</div>
      <div
        v-for="(t, i) in enriched"
        :key="t.name"
        class="trow"
        :class="{ top: i < 3, core: t.hasCore }"
        @click="open(t)"
      >
        <div class="tk">
          <span class="rank mono" :class="{ hot: i < 3 }">{{ i + 1 }}</span>
          <span class="tname">{{ t.name }}</span>
          <span v-if="t.max_board >= 2" class="tag gold">{{ t.max_board }}板</span>
          <span v-if="t.hasCore" class="tag red">含核心{{ t.coreHits.length }}</span>
        </div>
        <div class="tbar">
          <div class="bar">
            <i :style="{ width: (t.count / max) * 100 + '%' }"></i>
          </div>
        </div>
        <div class="tc">
          <span class="conc" :class="{ hi: t.concentration >= 1 }">{{ t.concentration }}</span>
          <span class="chev">›</span>
          <span class="cnt">{{ t.count }}<span class="tiny muted"> 家</span></span>
        </div>
      </div>
      <div v-if="!list.length" class="small muted">暂无题材数据</div>
    </div>

    <div class="tiny muted center">
      题材 = 东财行业分类；右侧数字为板块内涨停家数，进度条按家数排序 ·
      <b style="color: var(--gold)">含金</b>标含核心池标的、<b style="color: var(--t-1)">龙头集中</b>＝最高连板÷涨停家数（越高越一家独大）· 点击看成分股
    </div>

    <!-- 成分股弹层 -->
    <div v-if="sel" class="mask" @click.self="close">
      <div class="sheet">
        <div class="sheet-head">
          <div class="sheet-h">
            <div class="sheet-title">{{ sel.name }}</div>
            <div class="sheet-sub muted">
              板块内涨停 {{ sel.count }} 家 · 最高 {{ sel.max_board }} 板
            </div>
          </div>
          <button class="x" @click="close">✕</button>
        </div>
        <div class="sheet-list">
          <div v-for="m in sel.members" :key="m.code" class="mrow" :class="{ core: coreCodes.has(m.code) }">
            <div class="m-main">
              <span class="m-name">{{ m.name }}</span>
              <span v-if="coreCodes.has(m.code)" class="m-core">核心</span>
              <span class="m-code mono">{{ m.code }}</span>
            </div>
            <div class="m-meta">
              <span class="m-board" :class="{ hot: m.board >= 2 }">
                {{ m.zttj || (m.board + '板') }}
              </span>
              <span class="m-pct" :class="pctCls(m.pct)">{{ signed(m.pct) }}</span>
            </div>
          </div>
          <div v-if="!sel.members || !sel.members.length" class="small muted">
            暂无成分股数据
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.trow {
  display: grid;
  grid-template-columns: minmax(132px, 42vw) 1fr 62px;
  align-items: center;
  gap: 8px;
  padding: 9px 0;
  border-bottom: 1px dashed rgba(255, 255, 255, 0.05);
  cursor: pointer;
  transition: background 0.15s ease;
}
.trow:active { background: rgba(255, 255, 255, 0.04); }
.trow:last-child { border-bottom: 0; }
.tk { display: flex; align-items: center; gap: 4px; min-width: 0; }
.rank {
  width: 17px;
  height: 17px;
  border-radius: 5px;
  display: grid;
  place-items: center;
  font-size: 10.5px;
  background: rgba(255, 255, 255, 0.07);
  color: var(--t-3);
}
.rank.hot { background: var(--gold-dim); color: var(--gold); }
.tname { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; flex-shrink: 1; }
.tc { display: flex; align-items: center; justify-content: flex-end; gap: 3px; font-size: 14px; font-weight: 600; }
/* 徽章多时收缩但不消失 */
.tk .tag { flex-shrink: 0; }
.trow.top .tname { font-weight: 600; }
/* 含核心池标的的题材：整行左侧金色高亮条 + 渐变底色，带核心行一眼可辨 */
.trow.core {
  background: linear-gradient(90deg, rgba(233, 183, 92, 0.20), rgba(233, 183, 92, 0) 72%);
  box-shadow: inset 4px 0 0 0 var(--gold);
  padding-left: 10px;
}
.trow.core .tname { color: var(--gold); font-weight: 600; }
.chev { color: var(--t-3); font-size: 17px; line-height: 1; transform: translateY(-1px); }
/* 龙头集中度：最高连板 ÷ 涨停家数 */
.conc {
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  color: var(--t-3);
  min-width: 24px;
  text-align: right;
  font-weight: 600;
}
.conc.hi { color: var(--gold); }
.tc .tiny.muted { font-size: 10px; margin-left: -1px; }
.cnt { font-variant-numeric: tabular-nums; }
.center { text-align: center; }

/* 弹层 */
.mask {
  position: fixed;
  inset: 0;
  z-index: 60;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  animation: fade 0.18s ease;
}
.sheet {
  width: 100%;
  max-width: 560px;
  max-height: 72vh;
  display: flex;
  flex-direction: column;
  background: #131826;
  border: 1px solid var(--line);
  border-radius: 18px 18px 0 0;
  padding: 16px 16px calc(16px + var(--safe-b));
  box-shadow: 0 -12px 40px rgba(0, 0, 0, 0.5);
  animation: slide 0.22s cubic-bezier(0.2, 0.8, 0.2, 1);
}
.sheet-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line);
}
.sheet-title { font-size: 17px; font-weight: 700; }
.sheet-sub { font-size: 12px; margin-top: 3px; }
.x {
  border: 0;
  background: rgba(255, 255, 255, 0.07);
  color: var(--t-2);
  width: 28px;
  height: 28px;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  flex-shrink: 0;
}
.sheet-list {
  margin-top: 8px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}
.mrow {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 11px 2px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}
.mrow:last-child { border-bottom: 0; }
.m-main { display: flex; align-items: baseline; gap: 8px; min-width: 0; }
.m-name { font-size: 15px; font-weight: 600; }
.m-code { font-size: 11px; color: var(--t-3); }
.m-meta { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.m-board {
  font-size: 11.5px;
  padding: 2px 7px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.07);
  color: var(--t-2);
}
.m-board.hot { background: var(--gold-dim); color: var(--gold); }
.m-pct { font-size: 14px; font-weight: 700; font-variant-numeric: tabular-nums; }
/* 成分股含核心池标的 */
.mrow.core { background: rgba(233, 183, 92, 0.07); border-radius: var(--r-sm); padding-left: 8px; padding-right: 8px; }
.m-core {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 5px;
  background: var(--gold-dim);
  color: var(--gold);
  flex-shrink: 0;
}
@keyframes fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes slide { from { transform: translateY(100%); } to { transform: translateY(0); } }
</style>
