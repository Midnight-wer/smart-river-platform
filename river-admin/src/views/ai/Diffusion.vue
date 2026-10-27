<script setup lang="ts">
/**
 * 污染扩散模拟：基于 AI 扩散模型推演污染物三维扩散范围与浓度衰减过程
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Aim, MagicStick, Refresh, Timer } from '@element-plus/icons-vue'
import * as echarts from '@/utils/echarts'
// echarts-gl 副作用注册 scatter3D / grid3D 扩展
import 'echarts-gl'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import EChart from '@/components/EChart.vue'
import { fetchDiffusion } from '@/api/ai'
import type { DiffusionPoint } from '@/api/ai'
import { toFixed } from '@/utils/format'

interface PollutantOption {
  value: string
  label: string
  color: string
  /** 浓度衰减系数 */
  decay: number
  /** 初始浓度（mg/L） */
  initial: number
}

const POLLUTANT_OPTIONS: PollutantOption[] = [
  { value: 'COD', label: 'COD 化学需氧量', color: '#2563eb', decay: 0.05, initial: 120 },
  { value: '氨氮', label: '氨氮 NH3-N', color: '#16a34a', decay: 0.085, initial: 45 },
  { value: '总磷', label: '总磷 TP', color: '#f59e0b', decay: 0.065, initial: 8 },
]

/** 单个网格对应的实际扩散距离（米） */
const GRID_DISTANCE = 5

const points = ref<DiffusionPoint[]>([])
const loading = ref(false)

/** 污染物类型 */
const pollutant = ref('COD')
/** 投放点下游距离（米） */
const originX = ref(20)
/** 投放点横向偏移（米） */
const originY = ref(0)
/** 扩散时长（小时） */
const duration = ref(24)

const currentPollutant = computed<PollutantOption>(
  () => POLLUTANT_OPTIONS.find((item) => item.value === pollutant.value) ?? POLLUTANT_OPTIONS[0],
)

/** 按扩散时长截取参与推演的网格点 */
const activePoints = computed<DiffusionPoint[]>(() =>
  points.value.filter((item) => item.x <= duration.value),
)

/** 三维散点数据：X 为下游距离，Y 为横向偏移，Z 为浓度因子 */
const scatterData = computed<[number, number, number][]>(() =>
  activePoints.value.map((item) => [
    Number((originX.value + item.x * GRID_DISTANCE).toFixed(1)),
    Number((originY.value + (item.y - 50) * 0.8).toFixed(1)),
    Number(item.z.toFixed(1)),
  ]),
)

/** 浓度衰减序列 */
const decayData = computed(() => {
  const model = currentPollutant.value
  return activePoints.value.map((item) => ({
    hour: item.x,
    concentration: Number((model.initial * Math.exp(-model.decay * item.x)).toFixed(2)),
    radius: Number((item.x * GRID_DISTANCE).toFixed(1)),
  }))
})

const peakConcentration = computed(() => {
  if (!decayData.value.length) return 0
  return Number(Math.max(...decayData.value.map((item) => item.concentration)).toFixed(2))
})

const averageConcentration = computed(() => {
  if (!decayData.value.length) return 0
  const total = decayData.value.reduce((sum, item) => sum + item.concentration, 0)
  return Number((total / decayData.value.length).toFixed(2))
})

const maxRadius = computed(() => {
  if (!decayData.value.length) return 0
  return Math.max(...decayData.value.map((item) => item.radius))
})

/** 三维扩散散点图 */
const scatterOption = computed<echarts.EChartsOption>(() => {
  const model = currentPollutant.value
  return {
    tooltip: {
      formatter: (params: any) => {
        const value = params?.value ?? []
        return `下游距离：${value[0]} m<br/>横向偏移：${value[1]} m<br/>浓度因子：${value[2]}`
      },
    },
    grid3D: {
      boxWidth: 130,
      boxDepth: 90,
      boxHeight: 70,
      axisLine: { lineStyle: { color: '#94a3b8' } },
      axisLabel: { color: '#64748b' },
      axisPointer: { lineStyle: { color: '#94a3b8' } },
      light: { main: { intensity: 1.1, shadow: false }, ambient: { intensity: 0.45 } },
      viewControl: { distance: 190, alpha: 22, beta: 38, autoRotate: false },
    },
    xAxis3D: {
      name: '下游距离(m)',
      min: 0,
      max: 220,
      axisLabel: { color: '#64748b' },
      nameTextStyle: { color: '#64748b' },
    },
    yAxis3D: {
      name: '横向偏移(m)',
      min: -45,
      max: 45,
      axisLabel: { color: '#64748b' },
      nameTextStyle: { color: '#64748b' },
    },
    zAxis3D: {
      name: '浓度因子',
      min: -45,
      max: 45,
      axisLabel: { color: '#64748b' },
      nameTextStyle: { color: '#64748b' },
    },
    series: [
      {
        name: `${model.value} 扩散点`,
        type: 'scatter3D',
        symbolSize: 9,
        itemStyle: { color: model.color, opacity: 0.85 },
        emphasis: { itemStyle: { color: '#dc2626' } },
        data: scatterData.value,
      },
    ],
  } as any
})

/** 浓度衰减折线图 */
const decayOption = computed<echarts.EChartsOption>(() => {
  const model = currentPollutant.value
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['浓度衰减', '扩散半径'], bottom: 0, itemWidth: 14, itemHeight: 8 },
    grid: { left: 56, right: 56, top: 40, bottom: 44 },
    xAxis: {
      type: 'category',
      name: '时间(h)',
      data: decayData.value.map((item) => item.hour),
      axisLabel: { color: '#64748b' },
    },
    yAxis: [
      { type: 'value', name: '浓度(mg/L)', axisLabel: { color: '#64748b' } },
      { type: 'value', name: '半径(m)', axisLabel: { color: '#64748b' } },
    ],
    series: [
      {
        name: '浓度衰减',
        type: 'line',
        smooth: true,
        itemStyle: { color: model.color },
        areaStyle: { color: model.color, opacity: 0.18 },
        data: decayData.value.map((item) => item.concentration),
      },
      {
        name: '扩散半径',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        itemStyle: { color: '#94a3b8' },
        lineStyle: { type: 'dashed' },
        data: decayData.value.map((item) => item.radius),
      },
    ],
  }
})

/** 加载扩散模拟数据 */
async function load(): Promise<void> {
  loading.value = true
  try {
    points.value = await fetchDiffusion()
  } catch (error) {
    console.error('[污染扩散模拟] 扩散数据加载失败', error)
    ElMessage.error('扩散模拟数据加载失败')
    points.value = []
  } finally {
    loading.value = false
  }
}

/** 重新推演 */
async function handleSimulate(): Promise<void> {
  await load()
  ElMessage.success(`已完成 ${currentPollutant.value.value} 污染物扩散推演`)
}

onMounted(load)
</script>

<template>
  <div class="rv-page">
    <PageHeader title="污染扩散模拟" description="基于 AI 扩散模型推演污染物扩散范围与浓度衰减过程">
      <template #extra>
        <el-button :icon="Refresh" @click="load">刷新数据</el-button>
        <el-button type="primary" :icon="MagicStick" @click="handleSimulate">重新推演</el-button>
      </template>
    </PageHeader>

    <el-alert
      class="mb-4"
      type="info"
      :closable="false"
      show-icon
      title="模型说明"
      description="扩散结果由 AI 水动力-水质耦合模型推理生成，属于模拟推演结果，仅供现场研判与应急处置参考，不作为行政处罚依据。"
    />

    <!-- 推演指标 -->
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4 mb-4">
      <StatCard label="参与推演网格点" :value="activePoints.length" suffix="个" color="blue" :icon="Aim" />
      <StatCard label="峰值浓度" :value="peakConcentration" suffix="mg/L" color="red" />
      <StatCard label="平均浓度" :value="averageConcentration" suffix="mg/L" color="orange" />
      <StatCard label="最大扩散半径" :value="maxRadius" suffix="m" color="green" :icon="Timer" />
    </div>

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-12">
      <!-- 参数区 -->
      <div class="rv-card xl:col-span-4">
        <div class="rv-card-header">
          <span class="rv-card-title">推演参数</span>
          <span class="rv-text-secondary">调整参数后图表实时重算</span>
        </div>
        <div class="rv-card-body">
          <el-form label-position="top">
            <el-form-item label="污染物类型">
              <el-select v-model="pollutant" class="w-full">
                <el-option
                  v-for="item in POLLUTANT_OPTIONS"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>

            <el-form-item :label="`投放点下游距离：${originX} m`">
              <el-slider v-model="originX" :min="0" :max="200" :step="5" />
            </el-form-item>

            <el-form-item :label="`投放点横向偏移：${originY} m`">
              <el-slider v-model="originY" :min="-40" :max="40" :step="5" />
            </el-form-item>

            <el-form-item :label="`扩散时长：${duration} h`">
              <el-slider v-model="duration" :min="1" :max="40" :step="1" />
            </el-form-item>
          </el-form>

          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="污染物">{{ currentPollutant.label }}</el-descriptions-item>
            <el-descriptions-item label="初始浓度">{{ currentPollutant.initial }} mg/L</el-descriptions-item>
            <el-descriptions-item label="衰减系数">{{ currentPollutant.decay }}</el-descriptions-item>
            <el-descriptions-item label="模拟时长">{{ duration }} 小时</el-descriptions-item>
            <el-descriptions-item label="模拟点数">{{ activePoints.length }} 个</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>

      <!-- 可视化区 -->
      <div class="xl:col-span-8">
        <div class="rv-card mb-4">
          <div class="rv-card-header">
            <span class="rv-card-title">污染物三维扩散分布</span>
            <span class="rv-text-secondary">散点位置为模型推演的浓度场</span>
          </div>
          <div class="rv-card-body">
            <EChart :option="scatterOption" height="380px" :loading="loading" />
          </div>
        </div>

        <div class="rv-card">
          <div class="rv-card-header">
            <span class="rv-card-title">浓度衰减过程</span>
            <span class="rv-text-secondary">峰值 {{ peakConcentration }} mg/L</span>
          </div>
          <div class="rv-card-body">
            <EChart :option="decayOption" height="300px" :loading="loading" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
