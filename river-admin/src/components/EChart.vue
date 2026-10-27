<script setup lang="ts">
/**
 * ECharts 图表容器
 * 统一处理实例创建、配置更新、容器自适应与销毁。
 */
import { onBeforeUnmount, onMounted, ref, shallowRef, watch, nextTick } from 'vue'
import * as echarts from '@/utils/echarts'

const props = withDefaults(
  defineProps<{
    option: echarts.EChartsOption
    height?: string
    loading?: boolean
  }>(),
  { height: '320px', loading: false },
)

const emit = defineEmits<{ (e: 'ready', instance: echarts.ECharts): void }>()

const container = ref<HTMLDivElement | null>(null)
const chart = shallowRef<echarts.ECharts | null>(null)
let resizeObserver: ResizeObserver | null = null

function render(): void {
  if (!chart.value) return
  chart.value.setOption(props.option, true)
}

onMounted(async () => {
  await nextTick()
  if (!container.value) return
  chart.value = echarts.init(container.value)
  render()
  emit('ready', chart.value)

  resizeObserver = new ResizeObserver(() => chart.value?.resize())
  resizeObserver.observe(container.value)
})

watch(
  () => props.option,
  () => render(),
  { deep: true },
)

watch(
  () => props.loading,
  (value) => {
    if (!chart.value) return
    if (value) {
      chart.value.showLoading('default', { text: '加载中', color: '#1d4ed8' })
    } else {
      chart.value.hideLoading()
    }
  },
)

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  chart.value?.dispose()
  chart.value = null
})
</script>

<template>
  <div ref="container" class="rv-echart" :style="{ height }" />
</template>

<style scoped>
.rv-echart {
  width: 100%;
}
</style>
