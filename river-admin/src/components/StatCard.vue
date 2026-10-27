<script setup lang="ts">
/**
 * 数据指标卡片
 */
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    label: string
    value: number | string
    suffix?: string
    icon?: unknown
    color?: 'blue' | 'green' | 'orange' | 'red' | 'purple' | 'cyan'
    trend?: number
    trendLabel?: string
  }>(),
  { suffix: '', color: 'blue', trendLabel: '较上周' },
)

const COLOR_MAP = {
  blue: { bg: '#eff6ff', fg: '#1d4ed8' },
  green: { bg: '#ecfdf5', fg: '#16a34a' },
  orange: { bg: '#fff7ed', fg: '#ea580c' },
  red: { bg: '#fef2f2', fg: '#dc2626' },
  purple: { bg: '#f5f3ff', fg: '#7c3aed' },
  cyan: { bg: '#ecfeff', fg: '#0891b2' },
} as const

const palette = computed(() => COLOR_MAP[props.color] ?? COLOR_MAP.blue)
</script>

<template>
  <div class="rv-stat">
    <div class="rv-stat__icon" :style="{ background: palette.bg, color: palette.fg }">
      <el-icon v-if="icon" :size="22"><component :is="icon" /></el-icon>
    </div>
    <div class="rv-stat__body">
      <div class="rv-stat__label">{{ label }}</div>
      <div class="rv-stat__value rv-num">
        {{ value }}<span v-if="suffix" class="rv-stat__suffix">{{ suffix }}</span>
      </div>
      <div v-if="trend !== undefined" class="rv-stat__trend" :class="trend >= 0 ? 'is-up' : 'is-down'">
        <span class="rv-num">{{ trend >= 0 ? '+' : '' }}{{ trend }}%</span>
        <span class="rv-stat__trend-label">{{ trendLabel }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rv-stat {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px;
  background: var(--rv-surface);
  border: 1px solid var(--rv-border);
  border-radius: var(--rv-radius);
  box-shadow: var(--rv-shadow);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.rv-stat:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.1);
}

.rv-stat__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  flex-shrink: 0;
}

.rv-stat__body {
  min-width: 0;
}

.rv-stat__label {
  font-size: 13px;
  color: var(--rv-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rv-stat__value {
  font-size: 24px;
  font-weight: 600;
  line-height: 1.3;
  color: var(--rv-text);
}

.rv-stat__suffix {
  font-size: 13px;
  font-weight: 400;
  color: var(--rv-text-secondary);
  margin-left: 2px;
}

.rv-stat__trend {
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.rv-stat__trend.is-up {
  color: var(--rv-success);
}

.rv-stat__trend.is-down {
  color: var(--rv-danger);
}

.rv-stat__trend-label {
  color: var(--rv-text-secondary);
}
</style>
