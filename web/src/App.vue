<script setup>
// web/src/App.vue —— 外壳：移动底部 tab / 桌面左侧导航 + 主题切换 + 加载/错误态
// 数据仅用到 store 的 load()/fetchPrevCores()/loading/error/updatedAt/cores/themes/pattern，
// 若 getter 名与你的 snap.js 不符，请在下面 computed() 处一次性改名（见 BINDING-NOTES.md）。
import { ref, computed, onMounted } from 'vue'
import { useSnap } from './stores/snap'
import { initTheme } from './utils/theme'
import ThemeToggle from './components/ThemeToggle.vue'
import NavIcon from './components/NavIcon.vue'
import Dashboard from './views/Dashboard.vue'
import Cores from './views/Cores.vue'
import Themes from './views/Themes.vue'
import Check from './views/Check.vue'
import Pattern from './views/Pattern.vue'
import Backtest from './views/Backtest.vue'

const store = useSnap()
const tabs = [
  { k: 'dashboard', label: '盘面', icon: 'grid',     comp: Dashboard },
  { k: 'cores',     label: '核心', icon: 'cores',    comp: Cores },
  { k: 'themes',    label: '题材', icon: 'themes',   comp: Themes },
  { k: 'check',     label: '体检', icon: 'check',    comp: Check },
  { k: 'pattern',   label: '形态', icon: 'pattern',  comp: Pattern },
  { k: 'backtest',  label: '回测', icon: 'backtest', comp: Backtest }
]
const tab = ref('dashboard')
const current = computed(() => tabs.find(t => t.k === tab.value) || tabs[0])

const loading = computed(() => !!store.loading)
const error   = computed(() => store.error || '')
const updatedAt = computed(() => store.updatedAt || store.snap?.date || '')
const counts = computed(() => ({
  cores: (store.cores || []).length || 0,
  themes: (store.themes || []).length || 0,
  pattern: (store.pattern?.hits || []).length || 0
}))
function go (k) { tab.value = k }

onMounted(() => {
  initTheme()
  store.load && store.load()
  store.fetchPrevCores && store.fetchPrevCores()
})
</script>

<template>
  <div class="app">
    <div class="shell">
      <!-- 桌面：左侧导航 -->
      <aside class="sidebar">
        <div class="sb-brand"><div class="mk">九</div><b>短线量化</b></div>
        <div v-for="t in tabs" :key="t.k" class="it" :class="{ on: tab === t.k }" @click="tab = t.k">
          <NavIcon :name="t.icon" /><span>{{ t.label }}</span>
          <span v-if="counts[t.k]" class="cnt">{{ counts[t.k] }}</span>
        </div>
        <div class="sb-foot">短线量化 · v3<br>数据缺失以「—」标注<br>个人研究工具 · 不构成投资建议</div>
      </aside>

      <div class="main">
        <header class="topbar">
          <div class="tb-title"><span class="mk">九</span><span>短线<em>量化</em></span></div>
          <div class="tb-right">
            <span v-if="updatedAt">{{ updatedAt }}</span>
            <span class="rf"><i class="d"></i>盘后</span>
            <ThemeToggle />
          </div>
        </header>

        <div v-if="error" class="err">数据加载失败：{{ error }}</div>
        <div v-else-if="loading" class="load">
          <div class="sk skeleton-card"></div>
          <div class="sk skeleton-card short"></div>
          <div class="sk skeleton-card"></div>
        </div>
        <component v-else :is="current.comp" :key="current.k" @nav="go" />
      </div>
    </div>

    <!-- 移动：底部导航 -->
    <nav class="tabbar">
      <div v-for="t in tabs" :key="t.k" class="it" :class="{ on: tab === t.k }" @click="tab = t.k">
        <NavIcon :name="t.icon" /><span>{{ t.label }}</span>
      </div>
    </nav>
  </div>
</template>

<style scoped>
.main { min-width: 0; }
.load { display: flex; flex-direction: column; gap: 10px; }
</style>
