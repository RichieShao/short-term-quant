<script setup>
defineProps({ modelValue: { type: String, required: true } })
defineEmits(['update:modelValue'])

const tabs = [
  { key: 'dashboard', label: '盘面', path: 'M3 13h4l3-8 4 16 3-8h4' },
  { key: 'cores', label: '核心池', path: 'M12 3l2.5 5.6 6.1.7-4.5 4.2 1.2 6-5.3-3-5.3 3 1.2-6L3.4 9.3l6.1-.7z' },
  { key: 'themes', label: '题材', path: 'M4 5h16M4 12h10M4 19h6M17 12l3 3-3 3' },
  { key: 'check', label: '体检', path: 'M11 19a8 8 0 100-16 8 8 0 000 16zM21 21l-4.3-4.3' },
  { key: 'pattern', label: '形态', path: 'M3 17l5-6 4 4 5-7 4 5' },
  { key: 'backtest', label: '复盘', path: 'M4 20V9M10 20V4M16 20v-7M22 20H2' },
]
</script>

<template>
  <nav class="tabbar" role="tablist" aria-label="主导航">
    <div class="track">
      <button
        v-for="t in tabs"
        :key="t.key"
        class="tab"
        :class="{ on: modelValue === t.key }"
        role="tab"
        :aria-selected="modelValue === t.key"
        @click="$emit('update:modelValue', t.key)"
      >
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor"
             stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
          <path :d="t.path" />
        </svg>
        <span>{{ t.label }}</span>
      </button>
    </div>
  </nav>
</template>

<style scoped>
/* HDS HdsTabs 悬浮底栏（Web 模仿）：两端圆角胶囊 + 系统级材质毛玻璃 + 安全区边距；去掉选中框，仅用激活项变色标识 */
.tabbar {
  position: fixed;
  left: 50%;
  transform: translateX(-50%);
  bottom: calc(18px + env(safe-area-inset-bottom, 0px));
  z-index: 40;
  width: min(94vw, 372px);
  padding: 6px;
  border-radius: 999px;
  /* systemMaterialEffect：多层半透明 + 强饱和模糊，模拟鸿蒙系统材质 */
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.10), rgba(255, 255, 255, 0) 38%),
    rgba(16, 22, 36, 0.62);
  backdrop-filter: blur(26px) saturate(185%);
  -webkit-backdrop-filter: blur(26px) saturate(185%);
  border: 1px solid rgba(255, 255, 255, 0.10);
  /* 悬浮投影 + 内高光边（玻璃质感） */
  box-shadow:
    0 14px 36px rgba(0, 0, 0, 0.50),
    0 2px 6px rgba(0, 0, 0, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.14),
    inset 0 0 0 1px rgba(255, 255, 255, 0.04);
}
/* 顶部高光描边，强化材质厚度 */
.tabbar::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.16), rgba(255, 255, 255, 0) 30%);
  pointer-events: none;
}
.track {
  position: relative;
  display: flex;
  align-items: stretch;
  width: 100%;
}
.tab {
  position: relative;
  z-index: 1;
  flex: 1 1 0;
  min-width: 0;
  min-height: 48px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  padding: 7px 0;
  border: 0;
  background: none;
  color: var(--t-3);
  font-size: 10.5px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: color 0.2s ease, transform 0.2s ease;
}
.tab.on {
  color: var(--gold);
}
.tab.on svg {
  filter: drop-shadow(0 0 7px rgba(233, 183, 92, 0.50));
  transform: translateY(-1px);
}
.tab.on span {
  font-weight: 600;
}
.tab span {
  letter-spacing: 0.2px;
}
</style>
