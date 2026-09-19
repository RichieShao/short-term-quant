<script setup>
// web/src/components/NavIcon.vue —— 6 屏图标（stroke 继承 currentColor）
defineProps({ name: { type: String, required: true } })
const paths = {
  grid: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 12h18M12 3v18"/>',
  cores: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
  themes: '<path d="M4 18h16M6 14h12M9 10h6M11 6h2"/>',
  check: '<path d="M12 3v6M12 15v6M3 12h6M15 12h6"/>',
  pattern: '<path d="M3 17l6-6 4 4 8-8"/><path d="M21 7v5"/>',
  backtest: '<path d="M4 4v16h16"/><path d="M8 14l3-3 3 3 4-5"/>'
}
</script>

<template>
  <svg viewBox="0 0 24 24" v-html="paths[name] || paths.grid"></svg>
</template>
