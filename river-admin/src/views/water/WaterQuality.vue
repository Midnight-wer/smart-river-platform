<script setup lang="ts">
/**
 * 水质监测：监测站点管理、实时水质数据、水质趋势与指标标准
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Refresh, Search } from '@element-plus/icons-vue'
import * as echarts from '@/utils/echarts'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import EChart from '@/components/EChart.vue'
import { useTable } from '@/composables/useTable'
import { fetchIndicators, fetchStations, fetchWaterRecords, fetchWaterTrend } from '@/api/water'
import type { WaterIndicator } from '@/api/water'
import type { WaterRecord, WaterStation, WaterTrendPoint } from '@/types'
import { formatDateTime, toFixed } from '@/utils/format'

const STATUS_OPTIONS = ['正常', '预警', '超标'] as const

/** 指标键与实时数据字段的映射 */
const INDICATOR_KEYS: Record<string, keyof WaterRecord> = {
  ph: 'ph',
  do: 'do',
  nh3n: 'nh3n',
  cod: 'cod',
  tp: 'tp',
  tn: 'tn',
}

const {
  loading,
  list,
  total,
  query,
  load,
  search,
  reset,
  changePage,
  changePageSize,
  refresh,
} = useTable(fetchWaterRecords, { status: '' })

const stations = ref<WaterStation[]>([])
const trend = ref<WaterTrendPoint[]>([])
const indicators = ref<Record<string, WaterIndicator>>({})
const statRecords = ref<WaterRecord[]>([])
const statLoading = ref(false)

/** 加载监测站点 */
async function loadStations(): Promise<void> {
  try {
    stations.value = await fetchStations()
  } catch (error) {
    console.error('[水质监测] 监测站点加载失败', error)
    ElMessage.error('监测站点加载失败')
    stations.value = []
  }
}

/** 加载水质趋势 */
async function loadTrend(): Promise<void> {
  try {
    trend.value = await fetchWaterTrend()
  } catch (error) {
    console.error('[水质监测] 水质趋势加载失败', error)
    ElMessage.error('水质趋势加载失败')
    trend.value = []
  }
}

/** 加载指标标准 */
async function loadIndicators(): Promise<void> {
  try {
    indicators.value = await fetchIndicators()
  } catch (error) {
    console.error('[水质监测] 指标标准加载失败', error)
    ElMessage.error('指标标准加载失败')
    indicators.value = {}
  }
}

/** 加载全量水质数据用于统计 */
async function loadStatRecords(): Promise<void> {
  statLoading.value = true
  try {
    const result = await fetchWaterRecords({ page: 1, pageSize: 500 })
    statRecords.value = result?.list ?? []
  } catch (error) {
    console.error('[水质监测] 水质统计加载失败', error)
    ElMessage.error('水质统计加载失败')
    statRecords.value = []
  } finally {
    statLoading.value = false
  }
}

const totalStations = computed(() => stations.value.length)
const onlineStations = computed(() => stations.value.filter((item) => item.online).length)
const exceedCount = computed(() => statRecords.value.filter((item) => item.status === '超标').length)
const warnCount = computed(() => statRecords.value.filter((item) => item.status === '预警').length)
const qualifyRate = computed(() => {
  if (!statRecords.value.length) return 0
  const qualified = statRecords.value.filter((item) => item.status !== '超标').length
  return Number(((qualified / statRecords.value.length) * 100).toFixed(1))
})

/** 最新一条水质数据，用于指标实时值比对 */
const latestRecord = computed<WaterRecord | null>(() => {
  if (!statRecords.value.length) return null
  return [...statRecords.value].sort((a, b) => (a.collectAt < b.collectAt ? 1 : -1))[0]
})

/** 指标标准明细，含是否超出标准的判定 */
const indicatorRows = computed(() => {
  const latest = latestRecord.value
  return Object.entries(indicators.value).map(([key, item]) => {
    const field = INDICATOR_KEYS[key]
    const value = latest && field ? Number(latest[field]) : undefined
    const hasValue = typeof value === 'number' && !Number.isNaN(value)
    const exceeded = hasValue ? value! < item.min || value! > item.max : false
    return { key, ...item, value: hasValue ? value! : undefined, exceeded }
  })
})

/** 水质趋势图配置 */
const chartOption = computed<echarts.EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['pH', '溶解氧', 'COD', '氨氮'], bottom: 0 },
  grid: { left: 46, right: 46, top: 36, bottom: 48 },
  xAxis: { type: 'category', boundaryGap: false, data: trend.value.map((item) => item.date) },
  yAxis: [
    { type: 'value', name: 'pH / DO', min: 0, max: 12 },
    { type: 'value', name: 'COD / 氨氮' },
  ],
  series: [
    {
      name: 'pH',
      type: 'line',
      smooth: true,
      yAxisIndex: 0,
      itemStyle: { color: '#2563eb' },
      data: trend.value.map((item) => item.ph),
    },
    {
      name: '溶解氧',
      type: 'line',
      smooth: true,
      yAxisIndex: 0,
      itemStyle: { color: '#16a34a' },
      data: trend.value.map((item) => item.do),
    },
    {
      name: 'COD',
      type: 'line',
      smooth: true,
      yAxisIndex: 1,
      itemStyle: { color: '#f59e0b' },
      data: trend.value.map((item) => item.cod),
    },
    {
      name: '氨氮',
      type: 'line',
      smooth: true,
      yAxisIndex: 1,
      itemStyle: { color: '#dc2626' },
      data: trend.value.map((item) => item.nh3n),
    },
  ],
}))

/** 导出水质数据 */
function handleExport(): void {
  ElMessage.info('已生成导出任务')
}

/** 刷新全部数据 */
async function handleRefresh(): Promise<void> {
  await Promise.all([refresh(), loadStations(), loadTrend(), loadIndicators(), loadStatRecords()])
}

onMounted(() => {
  load()
  loadStations()
  loadTrend()
  loadIndicators()
  loadStatRecords()
})
</script>

<template>
  <div class="rv-page">
    <PageHeader title="水质监测" description="站点在线情况、实时水质数据与指标标准管理">
      <template #extra>
        <el-button :icon="Refresh" @click="handleRefresh">刷新</el-button>
        <el-button type="primary" :icon="Download" @click="handleExport">导出数据</el-button>
      </template>
    </PageHeader>

    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4 mb-4">
      <StatCard
        label="监测站点 / 在线站点"
        :value="`${totalStations} / ${onlineStations}`"
        suffix="个"
        color="blue"
        :icon="Search"
      />
      <StatCard label="水质达标率" :value="qualifyRate" suffix="%" color="green" />
      <StatCard label="超标站点数" :value="exceedCount" suffix="个" color="red" />
      <StatCard label="预警站点数" :value="warnCount" suffix="个" color="orange" />
    </div>

    <!-- 站点管理 + 实时数据 -->
    <div class="grid grid-cols-1 gap-4 xl:grid-cols-12 mb-4">
      <div class="rv-card xl:col-span-4">
        <div class="rv-card-header">
          <span class="rv-card-title">监测站点</span>
          <span class="rv-text-secondary">共 {{ totalStations }} 个站点</span>
        </div>
        <div class="rv-card-body">
          <el-table :data="stations" size="small" border max-height="420">
            <el-table-column prop="name" label="站点名称" min-width="150" show-overflow-tooltip />
            <el-table-column prop="code" label="站点编码" min-width="110" show-overflow-tooltip />
            <el-table-column prop="riverName" label="所属河道" min-width="110" show-overflow-tooltip />
            <el-table-column prop="region" label="所属区域" min-width="100" show-overflow-tooltip />
            <el-table-column prop="deviceType" label="设备类型" min-width="100" />
            <el-table-column label="在线状态" width="88">
              <template #default="{ row }">
                <StatusTag :status="row.online ? '在线' : '离线'" />
              </template>
            </el-table-column>
            <el-table-column label="最后上报" min-width="140">
              <template #default="{ row }">
                {{ formatDateTime(row.lastReportAt) }}
              </template>
            </el-table-column>
            <template #empty>
              <el-empty description="暂无监测站点" :image-size="70" />
            </template>
          </el-table>
        </div>
      </div>

      <div class="rv-card xl:col-span-8">
        <div class="rv-card-header">
          <span class="rv-card-title">实时水质数据</span>
          <div class="flex items-center gap-2">
            <el-input
              v-model="query.keyword"
              placeholder="站点名称 / 河道名称"
              clearable
              class="!w-56"
              @keyup.enter="search"
            >
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-select v-model="query.status" placeholder="数据状态" clearable class="!w-32">
              <el-option v-for="item in STATUS_OPTIONS" :key="item" :label="item" :value="item" />
            </el-select>
            <el-button type="primary" @click="search">查询</el-button>
            <el-button @click="reset">重置</el-button>
          </div>
        </div>
        <div class="rv-card-body">
          <el-table v-loading="loading" :data="list" size="small" border>
            <el-table-column prop="stationName" label="站点" min-width="150" show-overflow-tooltip />
            <el-table-column prop="riverName" label="河道" min-width="110" show-overflow-tooltip />
            <el-table-column label="pH" width="72" align="right">
              <template #default="{ row }">
                <span class="rv-num">{{ toFixed(row.ph) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="溶解氧" width="88" align="right">
              <template #default="{ row }">
                <span class="rv-num">{{ toFixed(row.do) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="氨氮" width="82" align="right">
              <template #default="{ row }">
                <span class="rv-num">{{ toFixed(row.nh3n, 3) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="COD" width="82" align="right">
              <template #default="{ row }">
                <span class="rv-num">{{ toFixed(row.cod) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="TP" width="80" align="right">
              <template #default="{ row }">
                <span class="rv-num">{{ toFixed(row.tp, 3) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="TN" width="80" align="right">
              <template #default="{ row }">
                <span class="rv-num">{{ toFixed(row.tn, 3) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="grade" label="水质类别" width="90" align="center" />
            <el-table-column label="状态" width="88">
              <template #default="{ row }">
                <StatusTag :status="row.status" />
              </template>
            </el-table-column>
            <el-table-column label="采集时间" min-width="140">
              <template #default="{ row }">
                {{ formatDateTime(row.collectAt) }}
              </template>
            </el-table-column>
            <template #empty>
              <el-empty description="暂无水质数据" :image-size="70" />
            </template>
          </el-table>

          <el-pagination
            layout="total, sizes, prev, pager, next, jumper"
            :total="total"
            :page-size="query.pageSize"
            :current-page="query.page"
            :page-sizes="[10, 20, 50]"
            @size-change="changePageSize"
            @current-change="changePage"
          />
        </div>
      </div>
    </div>

    <!-- 趋势图 + 指标标准 -->
    <div class="grid grid-cols-1 gap-4 xl:grid-cols-12">
      <div class="rv-card xl:col-span-8">
        <div class="rv-card-header">
          <span class="rv-card-title">水质变化趋势</span>
          <span class="rv-text-secondary">近 12 个月 pH / 溶解氧 / COD / 氨氮</span>
        </div>
        <div class="rv-card-body">
          <EChart :option="chartOption" height="340px" />
        </div>
      </div>

      <div class="rv-card xl:col-span-4">
        <div class="rv-card-header">
          <span class="rv-card-title">指标标准</span>
          <span class="rv-text-secondary">实时值与控制标准比对</span>
        </div>
        <div class="rv-card-body" v-loading="statLoading">
          <el-table :data="indicatorRows" size="small" border>
            <el-table-column prop="name" label="指标名称" min-width="110" show-overflow-tooltip />
            <el-table-column prop="unit" label="单位" width="72" align="center">
              <template #default="{ row }">{{ row.unit || '-' }}</template>
            </el-table-column>
            <el-table-column prop="standard" label="控制标准" min-width="92" align="center" />
            <el-table-column label="实时值" width="88" align="right">
              <template #default="{ row }">
                <span class="rv-num">{{ row.value === undefined ? '-' : toFixed(row.value, 3) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.exceeded" type="danger" size="small" effect="light" round>超标</el-tag>
                <el-tag v-else type="success" size="small" effect="light" round>达标</el-tag>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty description="暂无指标标准" :image-size="70" />
            </template>
          </el-table>
        </div>
      </div>
    </div>
  </div>
</template>
