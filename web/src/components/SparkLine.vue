<script>
let _sparkSeq = 0
</script>
<script setup>
import { computed } from 'vue'

const props = defineProps({
  values: { type: Array, default: () => [] },
  width: { type: Number, default: 300 },
  height: { type: Number, default: 62 },
  color: { type: String, default: '#e9b75c' },
})

// 每个实例分配唯一渐变 id，避免多 SparkLine 同屏时 url(#sparkFill) 串色
const gid = `spark-${++_sparkSeq}`

const pts = computed(() => {
  const v = props.values.filter((x) => x !== null && x !== undefined)
  if (v.length < 2) return { line: '', area: '', dots: [] }
  const min = Math.min(...v)
  const max = Math.max(...v)
  const span = max - min || 1
  const pad = 6
  const stepX = (props.width - pad * 2) / (v.length - 1)
  const coords = v.map((y, i) => [
    pad + i * stepX,
    props.height - pad - ((y - min) / span) * (props.height - pad * 2),
  ])
  const line = coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const area = `${pad},${props.height - pad} ${line} ${(props.width - pad).toFixed(1)},${props.height - pad}`
  return { line, area, dots: coords }
})
</script>

<template>
  <svg :width="width" :height="height" :viewBox="`0 0 ${width} ${height}`" class="spark">
    <defs>
      <linearGradient :id="gid" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" :stop-color="color" stop-opacity="0.28" />
        <stop offset="100%" :stop-color="color" stop-opacity="0" />
      </linearGradient>
    </defs>
    <polygon v-if="pts.area" :points="pts.area" :fill="`url(#${gid})`" />
    <polyline
      v-if="pts.line"
      :points="pts.line" fill="none" :stroke="color"
      stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
    />
    <circle
      v-for="(d, i) in pts.dots"
      :key="i"
      :cx="d[0]" :cy="d[1]" :r="i === pts.dots.length - 1 ? 3.4 : 1.9"
      :fill="i === pts.dots.length - 1 ? color : 'rgba(255,255,255,.35)'"
    />
  </svg>
</template>

<style scoped>
.spark { display: block; width: 100%; }
</style>
