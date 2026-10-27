<script setup lang="ts">
/**
 * 工作台：全域河湖治理总览
 * 汇总河道水质、巡查履职、事件处置与预警信息，提供常用功能快捷入口。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Bell, Compass, DataLine, Monitor, Odometer, Refresh, Share } from '@element-plus/icons-vue'
import * as echarts from '@/utils/echarts'
import EChart from '@/components/EChart.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { fetchCharts, fetchSummary, fetchTrend, fetchWarns } from '@/api/dashboard'
import type { DashboardCharts, DashboardSummary, TrendPoint } from '@/api/dashboard'
import type { WarnInfo } from '@/types'

interface TrendData {
  qualityRate: TrendPoint[]
  resolveRate: TrendPoint[]
  patrolRate: TrendPoint[]
}

const router = useRouter()

const loading = ref(false)
const chartLoading = ref(false)
const summary = ref<DashboardSummary | null>(null)
const warns = ref<WarnInfo[]>([])
const charts = ref<DashboardCharts | null>(null)
const trend = ref<TrendData>({ qualityRate: [], resolveRate: [], patrolRate: [] })

const PIE_COLORS = ['#1d4ed8', '#16a34a', '#f59e0b', '#dc2626', '#7c3aed', '#0891b2']

/** 快捷操作入口 */
const quickActions = [
  { key: 'river', label: '河道档案', desc: '流域河道基础档案', icon: Share, path: '/river' },
  { key: 'patrol', label: '巡查管理', desc: '下发与跟踪巡查任务', icon: Compass, path: '/patrol' },
  { key: 'event', label: '事件中心', desc: '受理与处置河湖事件', icon: Bell, path: '/event' },
  { key: 'large-screen', label: '数据大屏', desc: '可视化指挥调度大屏', icon: Monitor, path: '/large-screen' },
]

/** 巡查完成率（百分比） */
const patrolRate = computed(() => {
  const total = summary.value?.patrolTotal ?? 0
  if (!total) return 0
  return Number((((summary.value?.patrolDone ?? 0) / total) * 100).toFixed(1))
})

/** 监测站点在线率（百分比） */
const stationRate = computed(() => {
  const total = summary.value?.stationTotal ?? 0
  if (!total) return 0
  return Number((((summary.value?.stationOnline ?? 0) / total) * 100).toFixed(1))
})

/** 河道等级分布 */
const riverLevelOption = computed<echarts.EChartsOption>(() => ({
  color: PIE_COLORS,
  tooltip: { trigger: 'item', formatter: '{b}：{c} 条（{d}%）' },
  legend: { bottom: 0, itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 12 } },
  series: [
    {
      name: '河道等级',
      type: 'pie',
      radius: ['42%', '68%'],
      center: ['50%', '44%'],
      itemStyle: { borderColor: '#fff', borderWidth: 2, borderRadius: 4 },
      label: { formatter: '{b}\n{c} 条' },
      data: charts.value?.riverLevel ?? [],
    },
  ],
}))

/** 事件类型分布 */
const eventTypeOption = computed<echarts.EChartsOption>(() => ({
  color: PIE_COLORS,
  tooltip: { trigger: 'item', formatter: '{b}：{c} 件（{d}%）' },
  legend: { bottom: 0, itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 12 } },
  series: [
    {
      name: '事件类型',
      type: 'pie',
      radius: ['42%', '68%'],
      center: ['50%', '44%'],
      itemStyle: { borderColor: '#fff', borderWidth: 2, borderRadius: 4 },
      label: { formatter: '{b}\n{c} 件' },
      data: charts.value?.eventType ?? [],
    },
  ],
}))

/** 水质达标率趋势 */
const qualityTrendOption = computed<echarts.EChartsOption>(() => ({
  color: ['#1d4ed8'],
  tooltip: { trigger: 'axis', valueFormatter: (value) => `${value}%` },
  grid: { left: 46, right: 20, top: 30, bottom: 34 },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: trend.value.qualityRate.map((item) => item.date),
    axisLabel: { fontSize: 11 },
  },
  yAxis: {
    type: 'value',
    min: 60,
    max: 100,
    axisLabel: { formatter: '{value}%' },
    splitLine: { lineStyle: { type: 'dashed' } },
  },
  series: [
    {
      name: '水质达标率',
      type: 'line',
      smooth: true,
      showSymbol: false,
      areaStyle: { opacity: 0.12 },
      lineStyle: { width: 2.5 },
      data: trend.value.qualityRate.map((item) => item.value),
    },
  ],
}))

/** 加载概览指标与预警 */
async function loadSummary(): Promise<void> {
  loading.value = true
  try {
    const [summaryData, warnData] = await Promise.all([fetchSummary(), fetchWarns()])
    summary.value = summaryData
    warns.value = warnData ?? []
  } catch (error) {
    console.error('[dashboard] 概览数据加载失败', error)
    ElMessage.error('概览数据加载失败，请稍后重试')
    summary.value = null
    warns.value = []
  } finally {
    loading.value = false
  }
}

/** 加载图表数据 */
async function loadChartData(): Promise<void> {
  chartLoading.value = true
  try {
    const [chartData, trendData] = await Promise.all([fetchCharts(), fetchTrend()])
    charts.value = chartData
    trend.value = trendData
  } catch (error) {
    console.error('[dashboard] 图表数据加载失败', error)
    ElMessage.error('图表数据加载失败，请稍后重试')
    charts.value = null
    trend.value = { qualityRate: [], resolveRate: [], patrolRate: [] }
  } finally {
    chartLoading.value = false
  }
}

/** 跳转至指定功能模块 */
function goTo(path: string): void {
  router.push(path)
}

onMounted(() => {
  loadSummary()
  loadChartData()
})
</script>

<template>
  <div class="rv-page">
    <PageHeader title="工作台" description="全域河湖治理总览 · 实时掌握河道水质、巡查履职与事件处置态势">
      <template #extra>
        <el-button :icon="Refresh" :loading="loading" @click="loadSummary">刷新数据</el-button>
      </template>
    </PageHeader>

    <!-- 核心指标 -->
    <div v-loading="loading" class="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-4">
      <StatCard label="河道总数" :value="summary?.riverTotal ?? 0" suffix="条" :icon="Odometer" color="blue" />
      <StatCard label="水质达标率" :value="summary?.qualityRate ?? 0" suffix="%" :icon="DataLine" color="green" />
      <StatCard label="巡查完成率" :value="patrolRate" suffix="%" :icon="Compass" color="cyan" />
      <StatCard label="待处理事件" :value="summary?.eventPending ?? 0" suffix="件" :icon="Bell" color="red" />
    </div>

    <!-- 图表区 -->
    <div class="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-4">
      <div class="rv-card">
        <div class="rv-card-header">
          <span class="rv-card-title">河道等级分布</span>
        </div>
        <div class="rv-card-body">
          <EChart :option="riverLevelOption" height="300px" :loading="chartLoading" />
        </div>
      </div>

      <div class="rv-card">
        <div class="rv-card-header">
          <span class="rv-card-title">事件类型分布</span>
        </div>
        <div class="rv-card-body">
          <EChart :option="eventTypeOption" height="300px" :loading="chartLoading" />
        </div>
      </div>

      <div class="rv-card">
        <div class="rv-card-header">
          <span class="rv-card-title">水质达标率趋势</span>
        </div>
        <div class="rv-card-body">
          <EChart :option="qualityTrendOption" height="300px" :loading="chartLoading" />
        </div>
      </div>
    </div>

    <!-- 预警与快捷操作 -->
    <div class="grid grid-cols-1 xl:grid-cols-3 gap-4">
      <div class="rv-card xl:col-span-2">
        <div class="rv-card-header">
          <span class="rv-card-title">近期预警</span>
          <el-button link type="primary" @click="goTo('/event')">前往事件中心</el-button>
        </div>
        <div v-loading="loading" class="rv-card-body">
          <el-empty v-if="!warns.length" description="暂无预警信息" :image-size="80" />
          <ul v-else class="rv-warn-list">
            <li v-for="item in warns" :key="item.id" class="rv-warn">
              <StatusTag :status="item.level" />
              <div class="rv-warn__main">
                <div class="rv-warn__title">{{ item.title }}</div>
                <div class="rv-warn__meta">{{ item.type }} · 涉及对象：{{ item.target }}</div>
              </div>
              <span class="rv-warn__time">{{ item.time }}</span>
            </li>
          </ul>
        </div>
      </div>

      <div class="rv-card">
        <div class="rv-card-header">
          <span class="rv-card-title">快捷操作</span>
        </div>
        <div class="rv-card-body">
          <div class="grid grid-cols-2 gap-3">
            <button v-for="item in quickActions" :key="item.key" class="rv-action" type="button" @click="goTo(item.path)">
              <el-icon :size="20"><component :is="item.icon" /></el-icon>
              <span class="rv-action__label">{{ item.label }}</span>
              <span class="rv-action__desc">{{ item.desc }}</span>
            </button>
          </div>

          <div class="rv-status-list">
            <div class="rv-status-item">
              <span>监测站点在线率</span>
              <el-progress :percentage="stationRate" :stroke-width="10" text-inside />
            </div>
            <div class="rv-status-item">
              <span>事件办结量</span>
              <strong class="rv-num">{{ summary?.eventDone ?? 0 }} 件</strong>
            </div>
            <div class="rv-status-item">
              <span>逾期巡查任务</span>
              <strong class="rv-num">{{ summary?.patrolOverdue ?? 0 }} 项</strong>
            </div>
            <div class="rv-status-item">
              <span>待审核公众举报</span>
              <strong class="rv-num">{{ summary?.reportPending ?? 0 }} 条</strong>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rv-warn-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.rv-warn {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 4px;
  border-bottom: 1px dashed var(--rv-border);
}

.rv-warn:last-child {
  border-bottom: none;
}

.rv-warn__main {
  flex: 1;
  min-width: 0;
}

.rv-warn__title {
  font-size: 13px;
  color: var(--rv-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rv-warn__meta {
  margin-top: 2px;
  font-size: 12px;
  color: var(--rv-text-secondary);
}

.rv-warn__time {
  font-size: 12px;
  color: var(--rv-text-secondary);
  white-space: nowrap;
}

.rv-action {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 12px;
  border: 1px solid var(--rv-border);
  border-radius: var(--rv-radius);
  background: var(--rv-surface);
  color: var(--rv-primary);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.rv-action:hover {
  border-color: var(--rv-primary);
  box-shadow: 0 6px 16px rgba(29, 78, 216, 0.12);
}

.rv-action__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--rv-text);
}

.rv-action__desc {
  font-size: 12px;
  color: var(--rv-text-secondary);
}

.rv-status-list {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px dashed var(--rv-border);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.rv-status-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
  color: var(--rv-text-secondary);
}

.rv-status-item strong {
  color: var(--rv-text);
}
</style>
