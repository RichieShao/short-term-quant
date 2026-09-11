<script setup>
import { computed } from 'vue'
import { bandColor } from '../utils/format'

const props = defineProps({
  value: { type: Number, default: 0 },
  band: { type: String, default: '' },
  size: { type: Number, default: 138 },
})

// 内部坐标固定为 size，渲染尺寸由 CSS 自适应（min(size, 30vw)），避免窄屏挤压
const R = computed(() => props.size / 2 - 9)
const C = computed(() => 2 * Math.PI * R.value)
const color = computed(() => bandColor(props.band))
const offset = computed(() => C.value * (1 - Math.max(0, Math.min(100, props.value)) / 100))
</script>

<template>
  <div class="gauge" :style="{ width: `min(${size}px, 30vw)`, height: `min(${size}px, 30vw)` }">
    <svg :width="size" :height="size" viewBox="0 0 138 138" preserveAspectRatio="xMidYMid meet" style="width:100%;height:100%">
      <defs>
        <linearGradient :id="`gg-${size}`" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" :stop-color="color" stop-opacity="0.55" />
          <stop offset="100%" :stop-color="color" />
        </linearGradient>
      </defs>
      <circle
        :cx="size / 2" :cy="size / 2" :r="R"
        fill="none" stroke="rgba(255,255,255,0.07)" stroke-width="9"
      />
      <circle
        :cx="size / 2" :cy="size / 2" :r="R"
        fill="none" :stroke="`url(#gg-${size})`" stroke-width="9" stroke-linecap="round"
        :stroke-dasharray="C" :stroke-dashoffset="offset"
        :transform="`rotate(-90 ${size / 2} ${size / 2})`"
        style="transition: stroke-dashoffset .7s cubic-bezier(.22,.9,.3,1)"
      />
    </svg>
    <div class="center">
      <div class="v mono" :style="{ color }">{{ Math.round(value) }}</div>
      <div class="b">{{ band }}</div>
    </div>
  </div>
</template>

<style scoped>
.gauge { position: relative; display: grid; place-items: center; flex-shrink: 0; }
svg { position: absolute; inset: 0; }
.center { text-align: center; line-height: 1.15; }
.v { font-size: clamp(30px, 9vw, 38px); font-weight: 700; letter-spacing: -1px; }
.b { font-size: 11.5px; color: var(--t-2); margin-top: 2px; }
</style>
