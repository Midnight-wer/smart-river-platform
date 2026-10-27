<script setup lang="ts">
/**
 * 数据大屏：四川省河道治理监控中心
 * 采用 1920x1080 固定画布 + transform 缩放自适应屏幕，
 * 展示河道概况、今日巡查、趋势分析、河道分布地图、水质趋势、实时预警与底部统计。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft,
  Bell,
  Compass,
  DataLine,
  FullScreen,
  MapLocation,
  Monitor,
  Tickets,
  TrendCharts,
  User,
  Warning,
} from '@element-plus/icons-vue'
import * as echarts from '@/utils/echarts'
import EChart from '@/components/EChart.vue'
import StatusTag from '@/components/StatusTag.vue'
import { fetchCharts, fetchSummary, fetchTrend, fetchWarns } from '@/api/dashboard'
import type { DashboardCharts, DashboardSummary, TrendPoint } from '@/api/dashboard'
import { fetchWaterTrend } from '@/api/water'
import { fetchAssessments } from '@/api/assessment'
import { fetchReports } from '@/api/public'
import { fetchPatrols } from '@/api/patrol'
import type { AdminLevel, Assessment, PageResult, PatrolTask, PublicReport, WarnInfo, WaterTrendPoint } from '@/types'
import { formatDateTime } from '@/utils/format'

/* ------------------------------ 画布常量 ------------------------------ */
const STAGE_WIDTH = 1920
const STAGE_HEIGHT = 1080

/** 地图经纬度范围（模拟四川范围） */
const MAP_LON = { min: 97, max: 108 }
const MAP_LAT = { min: 26, max: 34 }
const MAP_VIEW_WIDTH = 1000
const MAP_VIEW_HEIGHT = 620

/** 主题色 */
const COLOR_CYAN = '#22d3ee'
const COLOR_BLUE = '#3b82f6'
const COLOR_PURPLE = '#a78bfa'
const COLOR_ORANGE = '#f59e0b'
const COLOR_PINK = '#f472b6'
const PALETTE = [COLOR_CYAN, COLOR_BLUE, COLOR_PURPLE, COLOR_ORANGE, COLOR_PINK, '#34d399']

/** 河长层级 */
const CHIEF_LEVELS: Array<{ label: string; level: AdminLevel }> = [
  { label: '省级', level: 'province' },
  { label: '市级', level: 'city' },
  { label: '县级', level: 'county' },
  { label: '乡镇级', level: 'town' },
]

interface MapPoint {
  name: string
  lon: number
  lat: number
  /** 河道点为水质达标率，设备点为在线率 */
  value: number
}

interface DevicePoint extends MapPoint {
  deviceType: string
}

/* ------------------------------ 地图静态数据 ------------------------------ */
/** 四川省轮廓（模拟经纬度点集） */
const PROVINCE_BOUNDARY: Array<[number, number]> = [
  [97.5, 32.5],
  [98.5, 33.4],
  [100.0, 33.2],
  [101.2, 33.0],
  [102.4, 32.9],
  [103.3, 32.8],
  [103.9, 32.7],
  [104.6, 32.9],
  [105.6, 32.7],
  [106.6, 32.6],
  [107.6, 32.4],
  [108.3, 32.1],
  [108.2, 31.5],
  [107.6, 31.2],
  [107.3, 30.6],
  [106.6, 30.0],
  [106.4, 29.3],
  [105.9, 28.7],
  [105.2, 28.4],
  [104.6, 28.3],
  [104.1, 28.4],
  [103.6, 28.2],
  [103.0, 28.4],
  [102.3, 28.2],
  [101.9, 27.5],
  [101.7, 26.6],
  [101.2, 26.3],
  [100.6, 26.3],
  [100.1, 26.7],
  [99.5, 27.4],
  [99.2, 28.2],
  [99.5, 29.2],
  [99.0, 30.0],
  [98.6, 31.0],
  [97.8, 31.6],
]

/** 主要水系走向 */
const MAP_RIVERS: Array<{ name: string; points: Array<[number, number]> }> = [
  { name: '岷江', points: [[103.62, 30.99], [104.07, 30.66], [103.9, 30.4], [104.2, 29.8], [104.63, 28.75]] },
  { name: '沱江', points: [[104.07, 30.66], [104.64, 30.13], [105.0, 29.4], [105.44, 28.87]] },
  { name: '嘉陵江', points: [[105.84, 32.44], [106.08, 30.84], [106.6, 30.2], [106.3, 29.9], [106.65, 29.0]] },
  { name: '涪江', points: [[104.68, 31.47], [105.0, 31.0], [105.57, 30.31]] },
  { name: '渠江', points: [[106.9, 31.9], [106.97, 30.84], [107.5, 31.21], [106.8, 29.8]] },
  { name: '雅砻江', points: [[100.0, 31.6], [100.9, 30.6], [101.3, 29.3], [101.72, 26.58]] },
  { name: '大渡河', points: [[100.3, 30.2], [101.5, 30.0], [102.23, 29.91], [103.0, 29.7], [103.77, 29.55]] },
  { name: '金沙江', points: [[99.4, 27.6], [100.6, 27.2], [102.4, 26.9], [104.63, 28.75]] },
  { name: '青衣江', points: [[102.6, 30.4], [103.0, 29.98], [103.5, 29.6], [103.9, 29.55]] },
  { name: '安宁河', points: [[102.1, 28.6], [102.26, 27.89], [101.9, 27.2], [101.72, 26.58]] },
  { name: '白龙江', points: [[104.0, 32.7], [104.8, 32.6], [105.84, 32.44]] },
  { name: '綦江', points: [[106.9, 28.9], [106.65, 29.0]] },
]

/** 河道分布监测点（模拟坐标） */
const RIVER_POINTS: MapPoint[] = [
  { name: '岷江都江堰段', lon: 103.62, lat: 30.99, value: 96.5 },
  { name: '岷江成都段', lon: 104.07, lat: 30.66, value: 98.2 },
  { name: '沱江资阳段', lon: 104.64, lat: 30.13, value: 93.7 },
  { name: '沱江泸州段', lon: 105.44, lat: 28.87, value: 91.4 },
  { name: '嘉陵江广元段', lon: 105.84, lat: 32.44, value: 95.1 },
  { name: '嘉陵江南充段', lon: 106.08, lat: 30.84, value: 94.6 },
  { name: '涪江绵阳段', lon: 104.68, lat: 31.47, value: 97.3 },
  { name: '涪江遂宁段', lon: 105.57, lat: 30.31, value: 92.8 },
  { name: '渠江达州段', lon: 107.5, lat: 31.21, value: 90.2 },
  { name: '雅砻江甘孜段', lon: 100.0, lat: 31.6, value: 96.9 },
  { name: '雅砻江攀枝花段', lon: 101.72, lat: 26.58, value: 88.6 },
  { name: '大渡河泸定段', lon: 102.23, lat: 29.91, value: 97.8 },
  { name: '大渡河乐山段', lon: 103.77, lat: 29.55, value: 95.5 },
  { name: '金沙江宜宾段', lon: 104.63, lat: 28.75, value: 94.2 },
  { name: '青衣江雅安段', lon: 103.0, lat: 29.98, value: 98.9 },
  { name: '安宁河西昌段', lon: 102.26, lat: 27.89, value: 93.4 },
  { name: '綦江重庆段', lon: 106.65, lat: 29.0, value: 92.1 },
  { name: '白龙江广元段', lon: 104.8, lat: 32.6, value: 97.2 },
]

/** 重点干流（波纹标记） */
const KEY_RIVER_NAMES = ['岷江成都段', '嘉陵江南充段', '雅砻江甘孜段', '金沙江宜宾段', '大渡河乐山段']

/** 监测设备分布 */
const DEVICE_POINTS: DevicePoint[] = [
  { name: '无人机巡查-01', lon: 104.2, lat: 30.5, value: 100, deviceType: '无人机' },
  { name: '无人机巡查-02', lon: 106.2, lat: 30.9, value: 100, deviceType: '无人机' },
  { name: '无人机巡查-03', lon: 102.9, lat: 29.8, value: 100, deviceType: '无人机' },
  { name: '水质监测站-都江堰', lon: 103.6, lat: 31.0, value: 98, deviceType: '监测站' },
  { name: '水质监测站-南充', lon: 106.1, lat: 30.8, value: 96, deviceType: '监测站' },
  { name: '水质监测站-攀枝花', lon: 101.7, lat: 26.6, value: 94, deviceType: '监测站' },
  { name: '水质监测站-乐山', lon: 103.8, lat: 29.6, value: 99, deviceType: '监测站' },
  { name: '雨量站-甘孜', lon: 100.0, lat: 31.6, value: 92, deviceType: '雨量站' },
  { name: '雨量站-雅安', lon: 103.0, lat: 30.0, value: 95, deviceType: '雨量站' },
  { name: '雨量站-广元', lon: 105.8, lat: 32.4, value: 93, deviceType: '雨量站' },
  { name: '雨量站-凉山', lon: 102.2, lat: 27.9, value: 91, deviceType: '雨量站' },
]

/* ------------------------------ 组件状态 ------------------------------ */
const router = useRouter()

const scale = ref(1)
const loading = ref(false)
const isFullscreen = ref(false)
const map3d = ref(false)
const clock = ref('')
const today = ref('')

const summary = ref<DashboardSummary | null>(null)
const warns = ref<WarnInfo[]>([])
const charts = ref<DashboardCharts | null>(null)
const trend = ref<{ qualityRate: TrendPoint[]; resolveRate: TrendPoint[]; patrolRate: TrendPoint[] }>({
  qualityRate: [],
  resolveRate: [],
  patrolRate: [],
})
const waterTrend = ref<WaterTrendPoint[]>([])
const assessments = ref<Assessment[]>([])
const reports = ref<PublicReport[]>([])
const reportTotal = ref(0)
const patrols = ref<PatrolTask[]>([])

/** 数字滚动动画目标值 */
const numRiverTotal = ref(0)
const numRiverNormal = ref(0)
const numRiverWarn = ref(0)
const numPatrolTotal = ref(0)
const numPatrolDone = ref(0)
const numPatrolDoing = ref(0)
const numPatrolOverdue = ref(0)
const numEventPending = ref(0)
const numChiefTotal = ref(0)
const numStationOnline = ref(0)
const numReportTotal = ref(0)
const numReportValid = ref(0)
const numReward = ref(0)

/** 概览默认值（接口失败兜底） */
const DEFAULT_SUMMARY: DashboardSummary = {
  riverTotal: 0,
  riverNormal: 0,
  riverWarn: 0,
  qualityRate: 0,
  patrolTotal: 0,
  patrolDone: 0,
  patrolDoing: 0,
  patrolOverdue: 0,
  eventTotal: 0,
  eventPending: 0,
  eventDone: 0,
  chiefTotal: 0,
  stationOnline: 0,
  stationTotal: 0,
  reportPending: 0,
}

/** 加载项名称，用于失败日志 */
const LOAD_LABELS = [
  '概览数据',
  '预警数据',
  '图表分布数据',
  '趋势数据',
  '水质趋势数据',
  '履职考核数据',
  '公众举报数据',
  '巡查任务数据',
]

let clockTimer: number | undefined
const frameIds = new Set<number>()

/* ------------------------------ 通用方法 ------------------------------ */
/** 从 allSettled 结果中取值，失败时使用默认值 */
function pickResult<T>(result: PromiseSettledResult<unknown> | undefined, fallback: T): T {
  if (!result) return fallback
  return result.status === 'fulfilled' ? (result.value as T) : fallback
}

/** 数字滚动动画 */
function animateNumber(target: number, setter: (value: number) => void, duration = 900): void {
  const started = performance.now()
  let frameId = 0
  const tick = (now: number): void => {
    const progress = Math.min((now - started) / duration, 1)
    const eased = 1 - Math.pow(1 - progress, 3)
    setter(Math.round(target * eased))
    if (progress < 1) {
      frameId = requestAnimationFrame(tick)
      frameIds.add(frameId)
    } else {
      frameIds.delete(frameId)
    }
  }
  frameId = requestAnimationFrame(tick)
  frameIds.add(frameId)
}

/** 屏幕缩放 */
function updateScale(): void {
  const ratio = Math.min(window.innerWidth / STAGE_WIDTH, window.innerHeight / STAGE_HEIGHT)
  scale.value = Number(ratio.toFixed(4))
}

/** 实时时钟 */
function updateClock(): void {
  const now = new Date()
  clock.value = now.toLocaleTimeString('zh-CN', { hour12: false })
  today.value = now.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    weekday: 'long',
  })
}

/** 返回后台 */
function goBack(): void {
  router.push('/dashboard')
}

/** 全屏切换 */
async function toggleFullscreen(): Promise<void> {
  try {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen()
    } else {
      await document.exitFullscreen()
    }
  } catch (error) {
    console.error('[large-screen] 全屏切换失败', error)
    ElMessage.warning('全屏切换失败，请检查浏览器权限设置')
  }
}

/** 同步全屏状态 */
function syncFullscreenState(): void {
  isFullscreen.value = Boolean(document.fullscreenElement)
}

/** 地图 3D 切换 */
function toggleMap3d(): void {
  map3d.value = !map3d.value
}

/* ------------------------------ 数据加载 ------------------------------ */
async function loadAll(): Promise<void> {
  loading.value = true
  try {
    const results = await Promise.allSettled([
      fetchSummary(),
      fetchWarns(),
      fetchCharts(),
      fetchTrend(),
      fetchWaterTrend(),
      fetchAssessments({ page: 1, pageSize: 30 }),
      fetchReports({ page: 1, pageSize: 6 }),
      fetchPatrols({ page: 1, pageSize: 6 }),
    ])

    results.forEach((item, index) => {
      if (item.status === 'rejected') {
        console.error(`[large-screen] ${LOAD_LABELS[index]}加载失败`, item.reason)
      }
    })

    summary.value = pickResult(results[0], DEFAULT_SUMMARY)
    warns.value = pickResult<WarnInfo[]>(results[1], [])
    charts.value = pickResult<DashboardCharts | null>(results[2], null)
    trend.value = pickResult(results[3], { qualityRate: [], resolveRate: [], patrolRate: [] })
    waterTrend.value = pickResult<WaterTrendPoint[]>(results[4], [])

    const assessmentResult = pickResult<PageResult<Assessment> | null>(results[5], null)
    assessments.value = assessmentResult?.list ?? []
    const reportResult = pickResult<PageResult<PublicReport> | null>(results[6], null)
    reports.value = reportResult?.list ?? []
    reportTotal.value = reportResult?.total ?? 0
    const patrolResult = pickResult<PageResult<PatrolTask> | null>(results[7], null)
    patrols.value = patrolResult?.list ?? []

    applyNumberAnimation()
  } catch (error) {
    console.error('[large-screen] 大屏数据加载失败', error)
  } finally {
    loading.value = false
  }
}

/** 触发关键数字滚动 */
function applyNumberAnimation(): void {
  const data = summary.value ?? DEFAULT_SUMMARY
  animateNumber(data.riverTotal, (value) => (numRiverTotal.value = value))
  animateNumber(data.riverNormal, (value) => (numRiverNormal.value = value))
  animateNumber(data.riverWarn, (value) => (numRiverWarn.value = value))
  animateNumber(data.patrolTotal, (value) => (numPatrolTotal.value = value))
  animateNumber(data.patrolDone, (value) => (numPatrolDone.value = value))
  animateNumber(data.patrolDoing, (value) => (numPatrolDoing.value = value))
  animateNumber(data.patrolOverdue, (value) => (numPatrolOverdue.value = value))
  animateNumber(data.eventPending, (value) => (numEventPending.value = value))
  animateNumber(data.chiefTotal, (value) => (numChiefTotal.value = value))
  animateNumber(data.stationOnline, (value) => (numStationOnline.value = value))
  animateNumber(reportTotal.value, (value) => (numReportTotal.value = value))

  const validCount = reports.value.filter((item) => item.status !== '已驳回').length
  animateNumber(validCount, (value) => (numReportValid.value = value))
  const reward = reports.value.reduce((sum, item) => sum + (item.reward || 0), 0)
  animateNumber(reward, (value) => (numReward.value = value))
}

/* ------------------------------ 计算属性 ------------------------------ */
/** 监测站点在线率 */
const stationOnlineRate = computed(() => {
  const total = summary.value?.stationTotal ?? 0
  if (!total) return 0
  return Number((((summary.value?.stationOnline ?? 0) / total) * 100).toFixed(1))
})

/** 公众举报有效率 */
const reportValidRate = computed(() => {
  if (!reports.value.length) return 0
  const valid = reports.value.filter((item) => item.status !== '已驳回').length
  return Number(((valid / reports.value.length) * 100).toFixed(1))
})

/** 最近巡查任务 */
const recentPatrols = computed(() =>
  [...patrols.value].sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1)).slice(0, 4),
)

/** 近期公众举报 */
const recentReports = computed(() => reports.value.slice(0, 3))

/** 各层级巡查率 / 解决率对比 */
const dutyCompare = computed(() =>
  CHIEF_LEVELS.map((item) => {
    const rows = assessments.value.filter((row) => row.level === item.level)
    const average = (key: 'patrolRate' | 'resolveRate'): number => {
      if (!rows.length) return 0
      const sum = rows.reduce((total, row) => total + (row[key] || 0), 0)
      return Math.round(sum / rows.length)
    }
    return {
      label: item.label,
      hasData: rows.length > 0,
      count: charts.value?.chiefDuty?.find((row) => row.name === item.label)?.value ?? 0,
      patrolRate: average('patrolRate'),
      resolveRate: average('resolveRate'),
    }
  }),
)

/** 顶部预警滚动条内容（复制一份实现无缝循环） */
const tickerItems = computed(() => {
  const list = warns.value
  if (!list.length) return []
  return [...list, ...list]
})

const tickerDuration = computed(() => Math.max(20, warns.value.length * 5))

/** 右侧预警滚动列表（复制一份实现无缝循环） */
const warnScrollItems = computed(() => {
  const list = warns.value
  if (!list.length) return []
  return [...list, ...list]
})

const warnScrollDuration = computed(() => Math.max(15, warns.value.length * 4))

/* ------------------------------ 图表配置 ------------------------------ */
/** 河道等级分布环形图 */
const riverLevelOption = computed<echarts.EChartsOption>(() => ({
  color: PALETTE,
  tooltip: { trigger: 'item', formatter: '{b}：{c} 条（{d}%）' },
  legend: {
    bottom: 0,
    itemWidth: 8,
    itemHeight: 8,
    itemGap: 8,
    textStyle: { color: '#8aa3c7', fontSize: 10 },
  },
  title: {
    text: String(charts.value?.riverLevel?.reduce((sum, item) => sum + item.value, 0) ?? 0),
    left: 'center',
    top: '30%',
    textStyle: { color: COLOR_CYAN, fontSize: 15, fontWeight: 700 },
  },
  series: [
    {
      name: '河道等级',
      type: 'pie',
      radius: ['40%', '64%'],
      center: ['50%', '42%'],
      avoidLabelOverlap: true,
      itemStyle: { borderColor: '#07142e', borderWidth: 2 },
      label: { show: false },
      data: charts.value?.riverLevel ?? [],
    },
  ],
}))

/** 事件类型玫瑰图 */
const eventTypeOption = computed<echarts.EChartsOption>(() => ({
  color: PALETTE,
  tooltip: { trigger: 'item', formatter: '{b}：{c} 件（{d}%）' },
  legend: {
    bottom: 0,
    itemWidth: 8,
    itemHeight: 8,
    itemGap: 8,
    textStyle: { color: '#8aa3c7', fontSize: 10 },
  },
  series: [
    {
      name: '事件类型',
      type: 'pie',
      roseType: 'radius',
      radius: ['22%', '68%'],
      center: ['50%', '40%'],
      itemStyle: { borderColor: '#07142e', borderWidth: 1 },
      label: { show: false },
      data: charts.value?.eventType ?? [],
    },
  ],
}))

/** 趋势分析折线图 */
const trendOption = computed<echarts.EChartsOption>(() => ({
  color: [COLOR_CYAN, COLOR_ORANGE, COLOR_PURPLE],
  tooltip: { trigger: 'axis', valueFormatter: (value) => `${value}%` },
  legend: {
    top: 0,
    itemWidth: 10,
    itemHeight: 6,
    textStyle: { color: '#8aa3c7', fontSize: 10 },
  },
  grid: { left: 40, right: 16, top: 26, bottom: 22 },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: trend.value.qualityRate.map((item) => item.date),
    axisLine: { lineStyle: { color: 'rgba(148,163,184,0.3)' } },
    axisLabel: { color: '#7c93b5', fontSize: 10 },
    axisTick: { show: false },
  },
  yAxis: {
    type: 'value',
    min: 60,
    max: 100,
    axisLabel: { color: '#7c93b5', fontSize: 10, formatter: '{value}' },
    splitLine: { lineStyle: { color: 'rgba(148,163,184,0.12)' } },
  },
  series: [
    {
      name: '水质达标率',
      type: 'line',
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 2 },
      areaStyle: { opacity: 0.12 },
      data: trend.value.qualityRate.map((item) => item.value),
    },
    {
      name: '问题解决率',
      type: 'line',
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 2 },
      areaStyle: { opacity: 0.08 },
      data: trend.value.resolveRate.map((item) => item.value),
    },
    {
      name: '巡河完成率',
      type: 'line',
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 2 },
      data: trend.value.patrolRate.map((item) => item.value),
    },
  ],
}))

/** 水质趋势（pH / 溶解氧 / COD / 氨氮） */
const waterOption = computed<echarts.EChartsOption>(() => ({
  color: [COLOR_CYAN, COLOR_BLUE, COLOR_PURPLE, COLOR_PINK],
  tooltip: { trigger: 'axis' },
  legend: {
    top: 0,
    itemWidth: 10,
    itemHeight: 6,
    textStyle: { color: '#8aa3c7', fontSize: 10 },
  },
  grid: { left: 42, right: 74, top: 28, bottom: 22 },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: waterTrend.value.map((item) => item.date),
    axisLine: { lineStyle: { color: 'rgba(148,163,184,0.3)' } },
    axisLabel: { color: '#7c93b5', fontSize: 10 },
    axisTick: { show: false },
  },
  yAxis: [
    {
      type: 'value',
      name: 'pH / DO',
      nameTextStyle: { color: '#7c93b5', fontSize: 10 },
      axisLabel: { color: '#7c93b5', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(148,163,184,0.12)' } },
    },
    {
      type: 'value',
      name: 'COD',
      nameTextStyle: { color: '#7c93b5', fontSize: 10 },
      axisLabel: { color: '#7c93b5', fontSize: 10 },
      splitLine: { show: false },
    },
    {
      type: 'value',
      name: '氨氮',
      position: 'right',
      offset: 38,
      nameTextStyle: { color: '#7c93b5', fontSize: 10 },
      axisLabel: { color: '#7c93b5', fontSize: 10 },
      splitLine: { show: false },
    },
  ],
  series: [
    {
      name: 'pH',
      type: 'line',
      smooth: true,
      showSymbol: false,
      data: waterTrend.value.map((item) => item.ph),
    },
    {
      name: '溶解氧',
      type: 'line',
      smooth: true,
      showSymbol: false,
      data: waterTrend.value.map((item) => item.do),
    },
    {
      name: 'COD',
      type: 'line',
      smooth: true,
      showSymbol: false,
      yAxisIndex: 1,
      data: waterTrend.value.map((item) => item.cod),
    },
    {
      name: '氨氮',
      type: 'line',
      smooth: true,
      showSymbol: false,
      yAxisIndex: 2,
      data: waterTrend.value.map((item) => item.nh3n),
    },
  ],
}))

/** 河长履职柱状图 */
const chiefDutyOption = computed<echarts.EChartsOption>(() => ({
  color: [COLOR_CYAN],
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: 34, right: 12, top: 24, bottom: 22 },
  xAxis: {
    type: 'category',
    data: CHIEF_LEVELS.map((item) => item.label),
    axisLine: { lineStyle: { color: 'rgba(148,163,184,0.3)' } },
    axisLabel: { color: '#7c93b5', fontSize: 10 },
    axisTick: { show: false },
  },
  yAxis: {
    type: 'value',
    axisLabel: { color: '#7c93b5', fontSize: 10 },
    splitLine: { lineStyle: { color: 'rgba(148,163,184,0.12)' } },
  },
  series: [
    {
      name: '河长数量',
      type: 'bar',
      barWidth: 14,
      itemStyle: {
        borderRadius: [2, 2, 0, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: COLOR_CYAN },
          { offset: 1, color: 'rgba(59,130,246,0.15)' },
        ]),
      },
      data: (charts.value?.chiefDuty ?? []).map((item) => item.value),
    },
  ],
}))

/** 按水质达标率取色 */
function rateColor(rate: number): string {
  if (rate >= 96) return COLOR_CYAN
  if (rate >= 92) return COLOR_BLUE
  return COLOR_ORANGE
}

/** 河道分布地图 */
const mapOption = computed<echarts.EChartsOption>(() => ({
  grid: { left: 0, right: 0, top: 0, bottom: 0 },
  tooltip: {
    trigger: 'item',
    backgroundColor: 'rgba(4, 14, 34, 0.94)',
    borderColor: 'rgba(34, 211, 238, 0.55)',
    borderWidth: 1,
    padding: [8, 12],
    textStyle: { color: '#dbeafe', fontSize: 12 },
    formatter: (params: unknown) => {
      const list = Array.isArray(params) ? params : [params]
      const item = list[0] as
        | { seriesName?: string; data?: { name: string; lon: number; lat: number; rate: number; deviceType?: string } }
        | undefined
      const data = item?.data
      if (!data) return ''
      if (item?.seriesName === '监测设备') {
        return [
          `<div style="font-weight:600">${data.name}</div>`,
          `<div>设备类型：${data.deviceType ?? '-'}</div>`,
          `<div>在线率：${data.rate}%</div>`,
          `<div>坐标：${data.lon.toFixed(2)}°E / ${data.lat.toFixed(2)}°N</div>`,
        ].join('')
      }
      return [
        `<div style="font-weight:600">${data.name}</div>`,
        `<div>水质达标率：${data.rate}%</div>`,
        `<div>坐标：${data.lon.toFixed(2)}°E / ${data.lat.toFixed(2)}°N</div>`,
      ].join('')
    },
  },
  xAxis: { type: 'value', min: MAP_LON.min, max: MAP_LON.max, show: false },
  yAxis: { type: 'value', min: MAP_LAT.min, max: MAP_LAT.max, show: false },
  series: [
    {
      name: '河道分布',
      type: 'scatter',
      symbolSize: 9,
      itemStyle: {
        opacity: 0.95,
        shadowBlur: 12,
        shadowColor: 'rgba(34,211,238,0.6)',
      },
      data: RIVER_POINTS.map((item) => ({
        name: item.name,
        value: [item.lon, item.lat, item.value],
        lon: item.lon,
        lat: item.lat,
        rate: item.value,
        itemStyle: { color: rateColor(item.value) },
      })),
    },
    {
      name: '重点干流',
      type: 'effectScatter',
      symbolSize: 16,
      rippleEffect: { scale: 3, brushType: 'stroke', period: 4 },
      itemStyle: { color: COLOR_CYAN, shadowBlur: 18, shadowColor: 'rgba(34,211,238,0.9)' },
      data: RIVER_POINTS.filter((item) => KEY_RIVER_NAMES.includes(item.name)).map((item) => ({
        name: item.name,
        value: [item.lon, item.lat, item.value],
        lon: item.lon,
        lat: item.lat,
        rate: item.value,
      })),
    },
    {
      name: '监测设备',
      type: 'scatter',
      symbolSize: 10,
      data: DEVICE_POINTS.map((item) => ({
        name: item.name,
        value: [item.lon, item.lat, item.value],
        lon: item.lon,
        lat: item.lat,
        rate: item.value,
        deviceType: item.deviceType,
        symbol: item.deviceType === '无人机' ? 'triangle' : item.deviceType === '雨量站' ? 'diamond' : 'circle',
        itemStyle: {
          color: item.deviceType === '无人机' ? COLOR_ORANGE : item.deviceType === '雨量站' ? COLOR_PURPLE : COLOR_CYAN,
          shadowBlur: 10,
          shadowColor:
            item.deviceType === '无人机'
              ? 'rgba(245,158,11,0.8)'
              : item.deviceType === '雨量站'
                ? 'rgba(167,139,250,0.8)'
                : 'rgba(34,211,238,0.8)',
        },
      })),
    },
  ],
}))

/* ------------------------------ 地图投影与几何 ------------------------------ */
/** 经纬度 → SVG 视图坐标 */
function project(lon: number, lat: number): [number, number] {
  const x = ((lon - MAP_LON.min) / (MAP_LON.max - MAP_LON.min)) * MAP_VIEW_WIDTH
  const y = ((MAP_LAT.max - lat) / (MAP_LAT.max - MAP_LAT.min)) * MAP_VIEW_HEIGHT
  return [Number(x.toFixed(1)), Number(y.toFixed(1))]
}

/** 经纬度点集 → 平滑路径 */
function buildPath(points: Array<[number, number]>): string {
  const coords = points.map(([lon, lat]) => project(lon, lat))
  if (!coords.length) return ''
  let path = `M ${coords[0][0]} ${coords[0][1]}`
  for (let index = 1; index < coords.length; index += 1) {
    const [x0, y0] = coords[index - 1]
    const [x1, y1] = coords[index]
    path += ` Q ${x0} ${y0} ${((x0 + x1) / 2).toFixed(1)} ${((y0 + y1) / 2).toFixed(1)}`
  }
  const last = coords[coords.length - 1]
  path += ` L ${last[0]} ${last[1]}`
  return path
}

const provincePath = computed(() => buildPath([...PROVINCE_BOUNDARY, PROVINCE_BOUNDARY[0]]))

const riverPaths = computed(() =>
  MAP_RIVERS.map((river) => ({ name: river.name, path: buildPath(river.points) })),
)

/** 背景网格线 */
const gridLines = computed(() => {
  const verticals: Array<{ x1: number; y1: number; x2: number; y2: number }> = []
  const horizontals: Array<{ x1: number; y1: number; x2: number; y2: number }> = []
  for (let lon = MAP_LON.min; lon <= MAP_LON.max; lon += 1) {
    const x = project(lon, MAP_LAT.max)[0]
    verticals.push({ x1: x, y1: 0, x2: x, y2: MAP_VIEW_HEIGHT })
  }
  for (let lat = MAP_LAT.min; lat <= MAP_LAT.max; lat += 1) {
    const y = project(MAP_LON.min, lat)[1]
    horizontals.push({ x1: 0, y1: y, x2: MAP_VIEW_WIDTH, y2: y })
  }
  return { verticals, horizontals }
})

/** 经纬度刻度标签 */
const axisLabels = computed(() => {
  const lonLabels = [97, 100, 103, 106, 108].map((lon) => ({
    text: `${lon}°E`,
    x: project(lon, MAP_LAT.min)[0],
    y: MAP_VIEW_HEIGHT - 8,
  }))
  const latLabels = [34, 32, 30, 28, 26].map((lat) => ({
    text: `${lat}°N`,
    x: 8,
    y: project(MAP_LON.min, lat)[1] - 4,
  }))
  return { lonLabels, latLabels }
})

/* ------------------------------ 生命周期 ------------------------------ */
onMounted(() => {
  updateScale()
  updateClock()
  clockTimer = window.setInterval(updateClock, 1000)
  window.addEventListener('resize', updateScale)
  document.addEventListener('fullscreenchange', syncFullscreenState)
  loadAll()
})

onBeforeUnmount(() => {
  if (clockTimer) window.clearInterval(clockTimer)
  clockTimer = undefined
  window.removeEventListener('resize', updateScale)
  document.removeEventListener('fullscreenchange', syncFullscreenState)
  frameIds.forEach((id) => cancelAnimationFrame(id))
  frameIds.clear()
})
</script>

<template>
  <div class="ls-root">
    <div class="ls-stage" :style="{ transform: `translate(-50%, -50%) scale(${scale})` }">
      <!-- 顶部标题栏 -->
      <header class="ls-header">
        <div class="ls-header__left">
          <div class="ls-brand">
            <span class="ls-brand__mark">智河通</span>
            <span class="ls-brand__text">智慧河长协同治理平台 · RIVER CHIEF PLATFORM</span>
          </div>
          <div class="ls-clock">
            <span class="ls-clock__time">{{ clock }}</span>
            <span class="ls-clock__date">{{ today }}</span>
          </div>
        </div>
        <h1 class="ls-header__title">四川省河道治理监控中心</h1>
        <div class="ls-header__right">
          <el-button class="ls-header__btn" size="small" :icon="ArrowLeft" @click="goBack">返回后台</el-button>
          <el-button class="ls-header__btn" size="small" :icon="FullScreen" @click="toggleFullscreen">
            {{ isFullscreen ? '退出全屏' : '全屏' }}
          </el-button>
        </div>
      </header>

      <!-- 预警滚动条 -->
      <div class="ls-ticker">
        <span class="ls-ticker__label">
          <el-icon :size="14"><Warning /></el-icon>
          实时预警
        </span>
        <div class="ls-ticker__viewport">
          <div v-if="warns.length" class="ls-ticker__track" :style="{ animationDuration: `${tickerDuration}s` }">
            <span v-for="(item, index) in tickerItems" :key="`${item.id}-${index}`" class="ls-ticker__item">
              <span class="ls-ticker__level" :class="`is-${item.level}`">{{ item.level }}</span>
              {{ item.title }} · {{ item.target }} · {{ item.time }}
            </span>
          </div>
          <span v-else class="ls-ticker__empty">暂无预警信息</span>
        </div>
      </div>

      <!-- 主体三栏 -->
      <section class="ls-main">
        <!-- 左栏 -->
        <div class="ls-col">
          <!-- 河道概况 -->
          <section class="ls-panel ls-panel--river">
            <div class="ls-panel__head">
              <span class="ls-panel__bar"></span>
              <el-icon :size="15" class="ls-panel__icon"><MapLocation /></el-icon>
              <span class="ls-panel__title">河道概况</span>
              <span class="ls-panel__en">RIVER OVERVIEW</span>
            </div>
            <div class="ls-panel__body">
              <div class="ls-stats">
                <div class="ls-stat">
                  <div class="ls-stat__value">{{ numRiverTotal }}</div>
                  <div class="ls-stat__label">河道总数</div>
                </div>
                <div class="ls-stat">
                  <div class="ls-stat__value is-green">{{ numRiverNormal }}</div>
                  <div class="ls-stat__label">正常河道</div>
                </div>
                <div class="ls-stat">
                  <div class="ls-stat__value is-orange">{{ numRiverWarn }}</div>
                  <div class="ls-stat__label">预警河道</div>
                </div>
              </div>
              <div class="ls-chart ls-chart--left">
                <EChart :option="riverLevelOption" height="100%" :loading="loading" />
              </div>
            </div>
          </section>

          <!-- 今日巡查 -->
          <section class="ls-panel ls-panel--patrol">
            <div class="ls-panel__head">
              <span class="ls-panel__bar"></span>
              <el-icon :size="15" class="ls-panel__icon"><Compass /></el-icon>
              <span class="ls-panel__title">今日巡查</span>
              <span class="ls-panel__en">TODAY PATROL</span>
            </div>
            <div class="ls-panel__body">
              <div class="ls-stats">
                <div class="ls-stat">
                  <div class="ls-stat__value">{{ numPatrolTotal }}</div>
                  <div class="ls-stat__label">巡查总数</div>
                </div>
                <div class="ls-stat">
                  <div class="ls-stat__value is-green">{{ numPatrolDone }}</div>
                  <div class="ls-stat__label">已完成</div>
                </div>
                <div class="ls-stat">
                  <div class="ls-stat__value is-blue">{{ numPatrolDoing }}</div>
                  <div class="ls-stat__label">进行中</div>
                </div>
              </div>
              <div class="ls-chart ls-chart--left">
                <EChart :option="eventTypeOption" height="100%" :loading="loading" />
              </div>
            </div>
          </section>

          <!-- 趋势分析 -->
          <section class="ls-panel ls-panel--trend">
            <div class="ls-panel__head">
              <span class="ls-panel__bar"></span>
              <el-icon :size="15" class="ls-panel__icon"><TrendCharts /></el-icon>
              <span class="ls-panel__title">趋势分析</span>
              <span class="ls-panel__en">TREND ANALYSIS</span>
            </div>
            <div class="ls-panel__body">
              <div class="ls-chart ls-chart--trend">
                <EChart :option="trendOption" height="100%" :loading="loading" />
              </div>
            </div>
          </section>
        </div>

        <!-- 中间地图 -->
        <section class="ls-panel ls-panel--map">
          <div class="ls-panel__head">
            <span class="ls-panel__bar"></span>
            <el-icon :size="15" class="ls-panel__icon"><MapLocation /></el-icon>
            <span class="ls-panel__title">四川省河道分布地图</span>
            <span class="ls-panel__en">RIVER DISTRIBUTION MAP</span>
            <el-button
              class="ls-map__3d"
              size="small"
              :type="map3d ? 'primary' : 'default'"
              @click="toggleMap3d"
            >
              {{ map3d ? '2D' : '3D' }}
            </el-button>
          </div>
          <div class="ls-map" :class="{ 'is-3d': map3d }">
            <div class="ls-map__stage">
              <svg class="ls-map__svg" :viewBox="`0 0 ${MAP_VIEW_WIDTH} ${MAP_VIEW_HEIGHT}`" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="lsMapBg" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#08203f" stop-opacity="0.9" />
                    <stop offset="100%" stop-color="#04132c" stop-opacity="0.6" />
                  </linearGradient>
                  <linearGradient id="lsRiver" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stop-color="#22d3ee" stop-opacity="0.9" />
                    <stop offset="100%" stop-color="#3b82f6" stop-opacity="0.5" />
                  </linearGradient>
                </defs>
                <rect x="0" y="0" :width="MAP_VIEW_WIDTH" :height="MAP_VIEW_HEIGHT" fill="url(#lsMapBg)" />
                <g class="ls-map__grid">
                  <line
                    v-for="(line, index) in gridLines.verticals"
                    :key="`v-${index}`"
                    :x1="line.x1"
                    :y1="line.y1"
                    :x2="line.x2"
                    :y2="line.y2"
                  />
                  <line
                    v-for="(line, index) in gridLines.horizontals"
                    :key="`h-${index}`"
                    :x1="line.x1"
                    :y1="line.y1"
                    :x2="line.x2"
                    :y2="line.y2"
                  />
                </g>
                <path class="ls-map__province" :d="provincePath" />
                <g class="ls-map__rivers">
                  <path v-for="river in riverPaths" :key="river.name" :d="river.path" />
                </g>
                <g class="ls-map__axis">
                  <text
                    v-for="label in axisLabels.lonLabels"
                    :key="`lon-${label.text}`"
                    :x="label.x"
                    :y="label.y"
                    text-anchor="middle"
                  >
                    {{ label.text }}
                  </text>
                  <text
                    v-for="label in axisLabels.latLabels"
                    :key="`lat-${label.text}`"
                    :x="label.x"
                    :y="label.y"
                  >
                    {{ label.text }}
                  </text>
                </g>
              </svg>
              <div class="ls-map__chart">
                <EChart :option="mapOption" height="100%" :loading="loading" />
              </div>
            </div>
            <div class="ls-map__legend">
              <span class="ls-map__legend-item"><i class="ls-dot is-cyan"></i>河道分布</span>
              <span class="ls-map__legend-item"><i class="ls-dot is-blue"></i>重点干流</span>
              <span class="ls-map__legend-item"><i class="ls-dot is-orange"></i>无人机</span>
              <span class="ls-map__legend-item"><i class="ls-dot is-cyan"></i>监测站</span>
              <span class="ls-map__legend-item"><i class="ls-dot is-purple"></i>雨量站</span>
            </div>
            <div class="ls-map__scan"></div>
          </div>
          <div class="ls-map__bar">
            <div class="ls-map__stat">
              <span class="ls-map__num">{{ numRiverTotal }}</span>
              <span class="ls-map__label">河道总数</span>
            </div>
            <div class="ls-map__stat">
              <span class="ls-map__num">{{ stationOnlineRate }}%</span>
              <span class="ls-map__label">监测站点在线率</span>
            </div>
            <div class="ls-map__stat">
              <span class="ls-map__num">{{ numChiefTotal }}</span>
              <span class="ls-map__label">河长总数</span>
            </div>
            <div class="ls-map__stat">
              <span class="ls-map__num">{{ numEventPending }}</span>
              <span class="ls-map__label">待处理事件</span>
            </div>
            <div class="ls-map__stat">
              <span class="ls-map__num">{{ numPatrolOverdue }}</span>
              <span class="ls-map__label">逾期巡查</span>
            </div>
          </div>
        </section>

        <!-- 右栏 -->
        <div class="ls-col">
          <!-- 水质趋势 -->
          <section class="ls-panel ls-panel--water">
            <div class="ls-panel__head">
              <span class="ls-panel__bar"></span>
              <el-icon :size="15" class="ls-panel__icon"><DataLine /></el-icon>
              <span class="ls-panel__title">水质趋势</span>
              <span class="ls-panel__en">WATER QUALITY TREND</span>
            </div>
            <div class="ls-panel__body">
              <div class="ls-chart ls-chart--water">
                <EChart :option="waterOption" height="100%" :loading="loading" />
              </div>
            </div>
          </section>

          <!-- 实时预警 -->
          <section class="ls-panel ls-panel--warn">
            <div class="ls-panel__head">
              <span class="ls-panel__bar"></span>
              <el-icon :size="15" class="ls-panel__icon"><Bell /></el-icon>
              <span class="ls-panel__title">实时预警</span>
              <span class="ls-panel__en">REAL-TIME ALERT</span>
            </div>
            <div class="ls-panel__body">
              <el-empty v-if="!warns.length" description="暂无预警信息" :image-size="60" />
              <div v-else class="ls-warn__viewport">
                <div class="ls-warn__track" :style="{ animationDuration: `${warnScrollDuration}s` }">
                  <ul class="ls-warn__list">
                    <li v-for="(item, index) in warnScrollItems" :key="`w-${item.id}-${index}`" class="ls-warn__item">
                      <StatusTag :status="item.level" />
                      <div class="ls-warn__main">
                        <div class="ls-warn__title">{{ item.title }}</div>
                        <div class="ls-warn__meta">{{ item.type }} · {{ item.target }}</div>
                      </div>
                      <span class="ls-warn__time">{{ item.time }}</span>
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          </section>
        </div>
      </section>

      <!-- 底部三栏 -->
      <section class="ls-bottom">
        <!-- 河长履职统计 -->
        <section class="ls-panel ls-panel--duty">
          <div class="ls-panel__head">
            <span class="ls-panel__bar"></span>
            <el-icon :size="15" class="ls-panel__icon"><User /></el-icon>
            <span class="ls-panel__title">河长履职统计</span>
            <span class="ls-panel__en">CHIEF DUTY</span>
          </div>
          <div class="ls-panel__body ls-duty">
            <div class="ls-chart ls-chart--duty">
              <EChart :option="chiefDutyOption" height="100%" :loading="loading" />
            </div>
            <div class="ls-duty__rows">
              <div v-for="row in dutyCompare" :key="row.label" class="ls-duty__row">
                <span class="ls-duty__label">{{ row.label }}</span>
                <div class="ls-duty__bar">
                  <span class="ls-duty__bar-name">巡查率</span>
                  <el-progress
                    v-if="row.hasData"
                    class="ls-duty__progress"
                    :percentage="row.patrolRate"
                    :show-text="false"
                    :stroke-width="7"
                    color="#22d3ee"
                  />
                  <span v-else class="ls-duty__progress is-empty"></span>
                  <span class="ls-duty__value">{{ row.hasData ? `${row.patrolRate}%` : '-' }}</span>
                </div>
                <div class="ls-duty__bar">
                  <span class="ls-duty__bar-name">解决率</span>
                  <el-progress
                    v-if="row.hasData"
                    class="ls-duty__progress"
                    :percentage="row.resolveRate"
                    :show-text="false"
                    :stroke-width="7"
                    color="#a78bfa"
                  />
                  <span v-else class="ls-duty__progress is-empty"></span>
                  <span class="ls-duty__value">{{ row.hasData ? `${row.resolveRate}%` : '-' }}</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- 智能调度中心 -->
        <section class="ls-panel ls-panel--dispatch">
          <div class="ls-panel__head">
            <span class="ls-panel__bar"></span>
            <el-icon :size="15" class="ls-panel__icon"><Monitor /></el-icon>
            <span class="ls-panel__title">智能调度中心</span>
            <span class="ls-panel__en">SMART DISPATCH</span>
          </div>
          <div class="ls-panel__body">
            <div class="ls-chips">
              <span class="ls-chip">任务总数 <b>{{ numPatrolTotal }}</b></span>
              <span class="ls-chip is-blue">进行中 <b>{{ numPatrolDoing }}</b></span>
              <span class="ls-chip is-orange">已逾期 <b>{{ numPatrolOverdue }}</b></span>
            </div>
            <el-empty v-if="!recentPatrols.length" description="暂无巡查任务" :image-size="60" />
            <ul v-else class="ls-tasks">
              <li v-for="task in recentPatrols" :key="task.id" class="ls-task">
                <el-tag size="small" effect="plain" type="info">{{ task.type }}</el-tag>
                <span class="ls-task__title">{{ task.title }}</span>
                <span class="ls-task__chief">河长：{{ task.chiefName }}</span>
                <span class="ls-task__deadline">截止：{{ formatDateTime(task.deadline, 'MM-DD HH:mm') }}</span>
                <StatusTag :status="task.status" />
              </li>
            </ul>
          </div>
        </section>

        <!-- 公众参与统计 -->
        <section class="ls-panel ls-panel--public">
          <div class="ls-panel__head">
            <span class="ls-panel__bar"></span>
            <el-icon :size="15" class="ls-panel__icon"><Tickets /></el-icon>
            <span class="ls-panel__title">公众参与统计</span>
            <span class="ls-panel__en">PUBLIC PARTICIPATION</span>
          </div>
          <div class="ls-panel__body">
            <div class="ls-public__stats">
              <div class="ls-public__stat">
                <span class="ls-public__num">{{ numReportTotal }}</span>
                <span class="ls-public__label">举报数量</span>
              </div>
              <div class="ls-public__stat">
                <span class="ls-public__num is-green">{{ reportValidRate }}%</span>
                <span class="ls-public__label">举报有效率</span>
              </div>
              <div class="ls-public__stat">
                <span class="ls-public__num is-orange">{{ numReward }}</span>
                <span class="ls-public__label">已发放积分</span>
              </div>
            </div>
            <el-empty v-if="!recentReports.length" description="暂无公众举报" :image-size="60" />
            <ul v-else class="ls-public__list">
              <li v-for="item in recentReports" :key="item.id" class="ls-public__item">
                <span class="ls-public__title">{{ item.title }}</span>
                <StatusTag :status="item.status" />
              </li>
            </ul>
          </div>
        </section>
      </section>
    </div>
  </div>
</template>

<style scoped>
/* ------------------------------ 根容器 ------------------------------ */
.ls-root {
  position: relative;
  width: 100%;
  height: 100vh;
  overflow: hidden;
  background:
    radial-gradient(1200px 620px at 50% -5%, rgba(23, 78, 140, 0.38), transparent 65%),
    radial-gradient(900px 520px at 8% 105%, rgba(8, 145, 178, 0.2), transparent 62%),
    linear-gradient(180deg, #050b1f 0%, #07142e 58%, #03081a 100%);
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
  color: #dbeafe;
}

.ls-root::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(34, 211, 238, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(34, 211, 238, 0.05) 1px, transparent 1px);
  background-size: 60px 60px;
  pointer-events: none;
}

/* ------------------------------ 画布 ------------------------------ */
.ls-stage {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 1920px;
  height: 1080px;
  padding: 12px;
  transform-origin: center center;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ------------------------------ 标题栏 ------------------------------ */
.ls-header {
  position: relative;
  flex: none;
  height: 70px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 18px;
  background: linear-gradient(90deg, rgba(9, 30, 66, 0) 0%, rgba(14, 46, 96, 0.6) 50%, rgba(9, 30, 66, 0) 100%);
  border-bottom: 1px solid rgba(34, 211, 238, 0.28);
}

.ls-header__left {
  display: flex;
  align-items: center;
  gap: 18px;
  min-width: 420px;
}

.ls-brand {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ls-brand__mark {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #07142e;
  background: linear-gradient(135deg, #22d3ee, #3b82f6);
  padding: 3px 10px;
  border-radius: 3px;
  box-shadow: 0 0 14px rgba(34, 211, 238, 0.45);
}

.ls-brand__text {
  font-size: 12px;
  letter-spacing: 1px;
  color: rgba(148, 197, 255, 0.85);
}

.ls-clock {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.ls-clock__time {
  font-family: 'DIN Alternate', 'Bahnschrift', Consolas, monospace;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 1px;
  color: #22d3ee;
  text-shadow: 0 0 12px rgba(34, 211, 238, 0.6);
  font-variant-numeric: tabular-nums;
}

.ls-clock__date {
  font-size: 12px;
  color: #7c93b5;
}

.ls-header__title {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  margin: 0;
  font-size: 30px;
  font-weight: 700;
  letter-spacing: 6px;
  color: #e0f2fe;
  text-shadow: 0 0 18px rgba(34, 211, 238, 0.75);
  white-space: nowrap;
}

.ls-header__title::after {
  content: '';
  position: absolute;
  left: 50%;
  bottom: -14px;
  transform: translateX(-50%);
  width: 320px;
  height: 2px;
  background: linear-gradient(90deg, transparent, #22d3ee, transparent);
}

.ls-header__right {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 420px;
  justify-content: flex-end;
}

.ls-header__btn {
  color: #bae6fd !important;
  background: rgba(13, 40, 80, 0.7) !important;
  border-color: rgba(34, 211, 238, 0.45) !important;
}

.ls-header__btn:hover {
  color: #e0f2fe !important;
  border-color: #22d3ee !important;
  background: rgba(34, 211, 238, 0.18) !important;
}

/* ------------------------------ 预警滚动条 ------------------------------ */
.ls-ticker {
  flex: none;
  height: 32px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 12px;
  background: rgba(8, 22, 48, 0.78);
  border: 1px solid rgba(59, 130, 246, 0.26);
  border-radius: 4px;
  overflow: hidden;
}

.ls-ticker__label {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 600;
  color: #22d3ee;
  padding-right: 12px;
  border-right: 1px solid rgba(34, 211, 238, 0.28);
}

.ls-ticker__viewport {
  flex: 1;
  overflow: hidden;
}

.ls-ticker__track {
  display: inline-flex;
  align-items: center;
  gap: 42px;
  white-space: nowrap;
  animation-name: ls-marquee-x;
  animation-timing-function: linear;
  animation-iteration-count: infinite;
}

.ls-ticker__item {
  font-size: 13px;
  color: #cbd5f5;
}

.ls-ticker__level {
  display: inline-block;
  margin-right: 6px;
  padding: 0 6px;
  border-radius: 2px;
  font-size: 12px;
  color: #07142e;
  background: #22d3ee;
}

.ls-ticker__level.is-警告 {
  background: #f59e0b;
}

.ls-ticker__level.is-严重 {
  background: #ef4444;
  color: #fff;
}

.ls-ticker__empty {
  font-size: 12px;
  color: #64748b;
}

@keyframes ls-marquee-x {
  from {
    transform: translateX(0);
  }
  to {
    transform: translateX(-50%);
  }
}

/* ------------------------------ 主体布局 ------------------------------ */
.ls-main {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
  grid-template-columns: 420px 1fr 420px;
  gap: 10px;
}

.ls-col {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
}

.ls-col > .ls-panel--river,
.ls-col > .ls-panel--patrol {
  flex: none;
  height: 224px;
}

.ls-col > .ls-panel--trend {
  flex: 1 1 auto;
  min-height: 0;
}

.ls-col > .ls-panel--water {
  flex: none;
  height: 300px;
}

.ls-col > .ls-panel--warn {
  flex: 1 1 auto;
  min-height: 0;
}

/* ------------------------------ 面板 ------------------------------ */
.ls-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: linear-gradient(180deg, rgba(10, 28, 62, 0.92), rgba(6, 16, 38, 0.88));
  border: 1px solid rgba(34, 211, 238, 0.22);
  border-radius: 4px;
  box-shadow: 0 0 22px rgba(3, 12, 30, 0.55), inset 0 0 26px rgba(34, 211, 238, 0.05);
  overflow: hidden;
}

.ls-panel::before,
.ls-panel::after {
  content: '';
  position: absolute;
  width: 12px;
  height: 12px;
  border-color: #22d3ee;
  border-style: solid;
  opacity: 0.85;
  pointer-events: none;
  z-index: 2;
}

.ls-panel::before {
  left: -1px;
  top: -1px;
  border-width: 2px 0 0 2px;
}

.ls-panel::after {
  right: -1px;
  bottom: -1px;
  border-width: 0 2px 2px 0;
}

.ls-panel__head {
  position: relative;
  flex: none;
  height: 32px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  background: linear-gradient(90deg, rgba(34, 211, 238, 0.16), rgba(34, 211, 238, 0) 62%);
  border-bottom: 1px solid rgba(34, 211, 238, 0.18);
}

.ls-panel__head::after {
  content: '';
  position: absolute;
  left: 0;
  bottom: -1px;
  width: 120px;
  height: 1px;
  background: linear-gradient(90deg, #22d3ee, transparent);
  animation: ls-flow 3.4s linear infinite;
}

@keyframes ls-flow {
  from {
    left: -20%;
  }
  to {
    left: 100%;
  }
}

.ls-panel__bar {
  width: 3px;
  height: 14px;
  border-radius: 2px;
  background: #22d3ee;
  box-shadow: 0 0 8px rgba(34, 211, 238, 0.9);
}

.ls-panel__icon {
  color: #22d3ee;
}

.ls-panel__title {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 1px;
  color: #e2e8f0;
}

.ls-panel__en {
  font-size: 10px;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: rgba(125, 156, 199, 0.75);
}

.ls-panel__body {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 10px;
}

/* ------------------------------ 统计块 ------------------------------ */
.ls-stats {
  flex: none;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.ls-stat {
  padding: 5px 4px;
  text-align: center;
  background: rgba(14, 39, 78, 0.55);
  border: 1px solid rgba(59, 130, 246, 0.22);
  border-radius: 3px;
}

.ls-stat__value {
  font-family: 'DIN Alternate', 'Bahnschrift', Consolas, monospace;
  font-size: 24px;
  font-weight: 700;
  line-height: 1.1;
  color: #22d3ee;
  text-shadow: 0 0 12px rgba(34, 211, 238, 0.55);
  font-variant-numeric: tabular-nums;
  animation: ls-num-flicker 2.6s ease-in-out infinite;
}

.ls-stat__value.is-green {
  color: #34d399;
  text-shadow: 0 0 12px rgba(52, 211, 153, 0.45);
}

.ls-stat__value.is-blue {
  color: #60a5fa;
  text-shadow: 0 0 12px rgba(96, 165, 250, 0.45);
}

.ls-stat__value.is-orange {
  color: #fbbf24;
  text-shadow: 0 0 12px rgba(251, 191, 36, 0.45);
}

@keyframes ls-num-flicker {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.86;
  }
}

.ls-stat__label {
  margin-top: 2px;
  font-size: 11px;
  color: #7c93b5;
}

/* ------------------------------ 图表容器 ------------------------------ */
.ls-chart {
  flex: 1 1 auto;
  min-height: 0;
}

.ls-chart--left {
  height: 116px;
  flex: none;
}

.ls-chart--trend {
  height: 188px;
}

.ls-chart--water {
  height: 252px;
}

.ls-chart--duty {
  width: 200px;
  flex: none;
  height: 188px;
}

/* ------------------------------ 地图 ------------------------------ */
.ls-panel--map {
  overflow: visible;
}

.ls-map__3d {
  margin-left: auto;
  color: #bae6fd !important;
  background: rgba(13, 40, 80, 0.75) !important;
  border-color: rgba(34, 211, 238, 0.5) !important;
}

.ls-map {
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
  perspective: 1400px;
  overflow: hidden;
}

.ls-map__stage {
  position: absolute;
  inset: 0;
  transform-origin: 50% 42%;
  transform-style: preserve-3d;
  transition: transform 0.7s cubic-bezier(0.22, 0.61, 0.36, 1);
}

.ls-map.is-3d .ls-map__stage {
  transform: rotateX(45deg) scaleY(1.42) scaleX(1.02);
}

.ls-map__svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.ls-map__grid line {
  stroke: rgba(34, 211, 238, 0.09);
  stroke-width: 1;
}

.ls-map__province {
  fill: rgba(34, 211, 238, 0.05);
  stroke: rgba(34, 211, 238, 0.5);
  stroke-width: 1.6;
  stroke-dasharray: 6 4;
}

.ls-map__rivers path {
  fill: none;
  stroke: url(#lsRiver);
  stroke-width: 2.2;
  stroke-linecap: round;
  filter: drop-shadow(0 0 4px rgba(34, 211, 238, 0.6));
}

.ls-map__axis text {
  fill: rgba(125, 156, 199, 0.8);
  font-size: 11px;
}

.ls-map__chart {
  position: absolute;
  inset: 0;
}

.ls-map__legend {
  position: absolute;
  left: 12px;
  top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 6px 10px;
  background: rgba(4, 14, 34, 0.55);
  border: 1px solid rgba(34, 211, 238, 0.2);
  border-radius: 3px;
  font-size: 12px;
  color: #a8c1e6;
}

.ls-map__legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.ls-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.ls-dot.is-cyan {
  background: #22d3ee;
  box-shadow: 0 0 6px #22d3ee;
}

.ls-dot.is-blue {
  background: #3b82f6;
  box-shadow: 0 0 6px #3b82f6;
}

.ls-dot.is-orange {
  background: #f59e0b;
  box-shadow: 0 0 6px #f59e0b;
}

.ls-dot.is-purple {
  background: #a78bfa;
  box-shadow: 0 0 6px #a78bfa;
}

.ls-map__scan {
  position: absolute;
  left: 0;
  right: 0;
  top: -120px;
  height: 120px;
  pointer-events: none;
  background: linear-gradient(180deg, rgba(34, 211, 238, 0) 0%, rgba(34, 211, 238, 0.12) 62%, rgba(34, 211, 238, 0.26) 100%);
  animation: ls-scan 6s linear infinite;
}

@keyframes ls-scan {
  from {
    top: -120px;
  }
  to {
    top: 100%;
  }
}

.ls-map__bar {
  flex: none;
  height: 48px;
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  background: rgba(8, 24, 52, 0.7);
  border-top: 1px solid rgba(34, 211, 238, 0.2);
}

.ls-map__stat {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 6px;
}

.ls-map__num {
  font-family: 'DIN Alternate', 'Bahnschrift', Consolas, monospace;
  font-size: 22px;
  font-weight: 700;
  color: #22d3ee;
  text-shadow: 0 0 10px rgba(34, 211, 238, 0.5);
  font-variant-numeric: tabular-nums;
}

.ls-map__label {
  font-size: 12px;
  color: #7c93b5;
}

/* ------------------------------ 预警滚动列表 ------------------------------ */
.ls-warn__viewport {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}

.ls-warn__track {
  animation-name: ls-marquee-y;
  animation-timing-function: linear;
  animation-iteration-count: infinite;
}

@keyframes ls-marquee-y {
  from {
    transform: translateY(0);
  }
  to {
    transform: translateY(-50%);
  }
}

.ls-warn__list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.ls-warn__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 4px;
  border-bottom: 1px dashed rgba(59, 130, 246, 0.22);
}

.ls-warn__main {
  flex: 1;
  min-width: 0;
}

.ls-warn__title {
  font-size: 13px;
  color: #e2e8f0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ls-warn__meta {
  margin-top: 2px;
  font-size: 11px;
  color: #7c93b5;
}

.ls-warn__time {
  font-size: 11px;
  color: #64748b;
  white-space: nowrap;
}

/* ------------------------------ 底部三栏 ------------------------------ */
.ls-bottom {
  flex: none;
  height: 236px;
  display: grid;
  grid-template-columns: 520px 1fr 420px;
  gap: 10px;
}

/* 河长履职 */
.ls-duty {
  flex-direction: row;
  gap: 10px;
}

.ls-duty__rows {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.ls-duty__row {
  display: grid;
  grid-template-columns: 46px 1fr;
  align-items: center;
  gap: 4px 8px;
  padding: 2px 0;
  border-bottom: 1px dashed rgba(59, 130, 246, 0.18);
}

.ls-duty__row:last-child {
  border-bottom: none;
}

.ls-duty__label {
  grid-row: span 2;
  font-size: 12px;
  color: #bae6fd;
  text-align: center;
  padding: 2px 0;
  background: rgba(34, 211, 238, 0.12);
  border-radius: 2px;
}

.ls-duty__bar {
  display: flex;
  align-items: center;
  gap: 6px;
}

.ls-duty__bar-name {
  font-size: 11px;
  color: #7c93b5;
  width: 34px;
  flex: none;
}

.ls-duty__progress {
  flex: 1;
  min-width: 0;
}

.ls-duty__progress.is-empty {
  display: block;
  height: 7px;
  border-radius: 4px;
  background: rgba(148, 163, 184, 0.14);
}

.ls-duty__value {
  font-size: 11px;
  color: #a8c1e6;
  width: 34px;
  text-align: right;
  flex: none;
  font-family: 'DIN Alternate', 'Bahnschrift', Consolas, monospace;
}

:deep(.ls-duty__progress .el-progress-bar__outer) {
  background-color: rgba(148, 163, 184, 0.18);
}

/* 智能调度 */
.ls-chips {
  flex: none;
  display: flex;
  gap: 8px;
}

.ls-chip {
  flex: 1;
  text-align: center;
  font-size: 11px;
  color: #7c93b5;
  padding: 4px 0;
  background: rgba(14, 39, 78, 0.5);
  border: 1px solid rgba(34, 211, 238, 0.2);
  border-radius: 3px;
}

.ls-chip b {
  margin-left: 4px;
  font-size: 15px;
  color: #22d3ee;
  font-family: 'DIN Alternate', 'Bahnschrift', Consolas, monospace;
}

.ls-chip.is-blue b {
  color: #60a5fa;
}

.ls-chip.is-orange b {
  color: #fbbf24;
}

.ls-tasks {
  flex: 1 1 auto;
  min-height: 0;
  margin: 0;
  padding: 0;
  list-style: none;
  overflow: hidden;
}

.ls-task {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 4px;
  border-bottom: 1px dashed rgba(59, 130, 246, 0.2);
}

.ls-task:last-child {
  border-bottom: none;
}

.ls-task__title {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: #e2e8f0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ls-task__chief {
  flex: none;
  font-size: 12px;
  color: #a8c1e6;
  white-space: nowrap;
}

.ls-task__deadline {
  flex: none;
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}

/* 公众参与 */
.ls-public__stats {
  flex: none;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.ls-public__stat {
  text-align: center;
  padding: 5px 4px;
  background: rgba(14, 39, 78, 0.5);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 3px;
}

.ls-public__num {
  display: block;
  font-size: 22px;
  font-weight: 700;
  color: #22d3ee;
  font-family: 'DIN Alternate', 'Bahnschrift', Consolas, monospace;
  text-shadow: 0 0 10px rgba(34, 211, 238, 0.5);
  font-variant-numeric: tabular-nums;
}

.ls-public__num.is-green {
  color: #34d399;
}

.ls-public__num.is-orange {
  color: #fbbf24;
}

.ls-public__label {
  font-size: 11px;
  color: #7c93b5;
}

.ls-public__list {
  flex: 1 1 auto;
  min-height: 0;
  margin: 0;
  padding: 0;
  list-style: none;
  overflow: hidden;
}

.ls-public__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 7px 4px;
  font-size: 12px;
  color: #cbd5f5;
  border-bottom: 1px dashed rgba(59, 130, 246, 0.2);
}

.ls-public__item:last-child {
  border-bottom: none;
}

.ls-public__title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ------------------------------ Element 覆写 ------------------------------ */
:deep(.el-empty__description p) {
  color: #64748b;
  font-size: 12px;
}

:deep(.el-empty__image) {
  opacity: 0.35;
}

:deep(.el-button--small) {
  padding: 5px 10px;
}

:deep(.ls-map__3d.el-button--primary) {
  background: rgba(34, 211, 238, 0.85) !important;
  border-color: #22d3ee !important;
  color: #041225 !important;
}

:deep(.el-tag) {
  background-color: rgba(34, 211, 238, 0.12);
  border-color: rgba(34, 211, 238, 0.35);
}

:deep(.el-tag--success) {
  background-color: rgba(52, 211, 153, 0.15);
  border-color: rgba(52, 211, 153, 0.4);
}

:deep(.el-tag--warning) {
  background-color: rgba(245, 158, 11, 0.16);
  border-color: rgba(245, 158, 11, 0.42);
}

:deep(.el-tag--danger) {
  background-color: rgba(239, 68, 68, 0.16);
  border-color: rgba(239, 68, 68, 0.42);
}

:deep(.el-tag--info) {
  background-color: rgba(148, 163, 184, 0.14);
  border-color: rgba(148, 163, 184, 0.34);
}
</style>
