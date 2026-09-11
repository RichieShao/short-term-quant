<script setup>
import { stageColor } from '../utils/format'

defineProps({
  stage: { type: String, default: '' },
  trend: { type: String, default: '' },
})

const stages = ['启动', '发酵', '高潮', '震荡', '退潮']
</script>

<template>
  <div class="cycle">
    <div
      v-for="(s, i) in stages"
      :key="s"
      class="node"
      :class="{ on: s === stage, passed: stages.indexOf(stage) > i }"
    >
      <div class="line" v-if="i > 0"></div>
      <div
        class="dot"
        :style="
          s === stage
            ? { background: stageColor(s), boxShadow: `0 0 14px ${stageColor(s)}` }
            : {}
        "
      ></div>
      <div class="lb">{{ s }}</div>
    </div>
  </div>
</template>

<style scoped>
.cycle { display: flex; align-items: flex-start; justify-content: space-between; }
.node { flex: 1; position: relative; text-align: center; }
.line {
  position: absolute;
  top: 6px;
  left: -50%;
  width: 100%;
  height: 2px;
  background: rgba(255, 255, 255, 0.09);
}
.node.passed .line { background: rgba(233, 183, 92, 0.35); }
.dot {
  position: relative;
  width: 13px;
  height: 13px;
  margin: 0 auto 6px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid var(--line-strong);
}
.lb { font-size: 12px; color: var(--t-3); }
.node.on .lb { color: var(--t-1); font-weight: 600; }
</style>
