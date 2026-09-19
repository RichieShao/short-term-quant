<script setup>
// web/src/components/ThemeToggle.vue
import { ref } from 'vue'
import { currentTheme, applyTheme } from '../utils/theme'
const theme = ref(currentTheme())
function set (t) { theme.value = t; applyTheme(t) }
</script>

<template>
  <div class="theme-toggle" role="group" aria-label="主题切换">
    <button class="tt" :class="{ on: theme === 'light' }" type="button" @click="set('light')">
      <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4.2"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4"/></svg>
      <span class="lb">浅色</span>
    </button>
    <button class="tt" :class="{ on: theme === 'dark' }" type="button" @click="set('dark')">
      <svg viewBox="0 0 24 24"><path d="M20 14.5A8 8 0 1 1 9.5 4a6.4 6.4 0 0 0 10.5 10.5Z"/></svg>
      <span class="lb">深色</span>
    </button>
  </div>
</template>

<style scoped>
.lb { display: inline; }
@media (max-width: 420px) { .lb { display: none; } .theme-toggle .tt { padding: 6px 8px; } }
</style>
