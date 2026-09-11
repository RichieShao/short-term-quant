<script setup>
import { ref, computed, onMounted } from 'vue'
import { useSnap } from './stores/snap'
import TabBar from './components/TabBar.vue'
import Dashboard from './views/Dashboard.vue'
import Cores from './views/Cores.vue'
import Themes from './views/Themes.vue'
import Check from './views/Check.vue'
import Backtest from './views/Backtest.vue'
import Pattern from './views/Pattern.vue'

const views = {
  dashboard: Dashboard,
  cores: Cores,
  themes: Themes,
  check: Check,
  pattern: Pattern,
  backtest: Backtest,
}
const titles = {
  dashboard: '今日盘面',
  cores: '核心池',
  themes: '题材榜',
  check: '异动体检',
  pattern: '形态',
  backtest: '回测复盘',
}

const tab = ref('dashboard')
const s = useSnap()
const title = computed(() => titles[tab.value])

onMounted(() => s.load())
</script>

<template>
  <header class="topbar">
    <div>
      <div class="brand">短线量化 · 分析系统</div>
      <div class="tiny muted">{{ s.date || '加载中…' }} · 框架 v0.1-P4</div>
    </div>
    <button class="rf" :disabled="s.loading" @click="s.refresh()">
      {{ s.loading ? '更新中' : '刷新' }}
    </button>
  </header>

  <main>
    <div v-if="s.error" class="page">
      <div class="card err">
        <div class="card-title">数据加载失败</div>
        <div class="small dim">{{ s.error }}</div>
        <button class="btn" style="margin-top: 12px" @click="s.load()">重试</button>
      </div>
    </div>

    <div v-else-if="!s.snap" class="page">
      <div class="card skeleton-card">
        <div class="tiny muted">正在从云端读取最新快照…</div>
        <div class="sk" style="margin-top: 12px"></div>
        <div class="sk"></div>
        <div class="sk short"></div>
      </div>
    </div>

    <component v-else :is="views[tab]" />
  </main>

  <TabBar v-model="tab" />
</template>

<style scoped>
main {
  padding-bottom: calc(8px + env(safe-area-inset-bottom, 0px));
}
.topbar {
  position: sticky;
  top: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: calc(12px + env(safe-area-inset-top, 0px)) 16px 12px;
  background: rgba(10, 14, 26, 0.72);
  backdrop-filter: blur(20px) saturate(150%);
  -webkit-backdrop-filter: blur(20px) saturate(150%);
  border-bottom: 1px solid var(--line);
}
.brand {
  font-size: 16.5px;
  font-weight: 700;
  background: linear-gradient(92deg, #f3d9a4, #e9b75c 60%, #c98f3c);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.rf {
  padding: 7px 14px;
  border-radius: 999px;
  border: 1px solid rgba(233, 183, 92, 0.4);
  background: var(--gold-dim);
  color: var(--gold);
  font-size: 12.5px;
  cursor: pointer;
}
.rf:disabled { opacity: 0.5; }
.err { border-color: rgba(255, 77, 94, 0.35); }
.sk {
  height: 13px;
  border-radius: 7px;
  margin-bottom: 9px;
  background: linear-gradient(90deg, rgba(255,255,255,.05), rgba(255,255,255,.11), rgba(255,255,255,.05));
  background-size: 200% 100%;
  animation: sh 1.3s infinite linear;
}
.sk.short { width: 62%; }
@keyframes sh { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
</style>
