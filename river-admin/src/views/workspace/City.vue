<script setup lang="ts">
/**
 * 市级河长工作台：本市河道管理、县级河长督导、市级事件处置
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Bell, OfficeBuilding, Refresh, Share, User } from '@element-plus/icons-vue'
import * as echarts from '@/utils/echarts'
import EChart from '@/components/EChart.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useTable } from '@/composables/useTable'
import { fetchCharts, fetchSummary } from '@/api/dashboard'
import type { DashboardCharts, DashboardSummary } from '@/api/dashboard'
import { fetchChiefs } from '@/api/chief'
import { fetchEvents } from '@/api/event'
import { fetchRivers } from '@/api/river'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const chartLoading = ref(false)
const summary = ref<DashboardSummary | null>(null)
const charts = ref<DashboardCharts | null>(null)

/** 本市河道列表 */
const {
  loading: riverLoading,
  list: riverList,
  total: riverTotal,
  query: riverQuery,
  load: loadRivers,
  search: searchRivers,
  reset: resetRivers,
  changePage: changeRiverPage,
  changePageSize: changeRiverPageSize,
} = useTable(fetchRivers)

/** 县级河长（固定范围） */
const {
  loading: chiefLoading,
  list: chiefList,
  total: chiefTotal,
  query: chiefQuery,
  load: loadChiefs,
  search: searchChiefs,
  changePage: changeChiefPage,
  changePageSize: changeChiefPageSize,
} = useTable(fetchChiefs, { level: 'county', pageSize: 100 })

/** 市级事件处理 */
const {
  loading: eventLoading,
  list: eventList,
  total: eventTotal,
  query: eventQuery,
  load: loadEvents,
  search: searchEvents,
  reset: resetEvents,
  changePage: changeEventPage,
  changePageSize: changeEventPageSize,
} = useTable(fetchEvents)

const RIVER_LEVEL_OPTIONS = [
  { label: '省级', value: '省级' },
  { label: '市级', value: '市级' },
  { label: '县级', value: '县级' },
  { label: '乡镇级', value: '乡镇级' },
]

const RIVER_STATUS_OPTIONS = [
  { label: '正常', value: '正常' },
  { label: '预警', value: '预警' },
  { label: '停用', value: '停用' },
]

const REGION_OPTIONS = [
  '成都市',
  '德阳市',
  '绵阳市',
  '乐山市',
  '宜宾市',
  '泸州市',
  '南充市',
  '眉山市',
]

const EVENT_STATUS_OPTIONS = ['待处理', '处理中', '已完成', '已归档', '已驳回', '已关闭']

const PIE_COLORS = ['#1d4ed8', '#16a34a', '#f59e0b', '#dc2626', '#7c3aed']

/** 县级河长按综合得分排序 */
const sortedChiefs = computed(() => [...chiefList.value].sort((a, b) => b.score - a.score))

/** 河道等级构成 */
const riverLevelOption = computed<echarts.EChartsOption>(() => ({
  color: PIE_COLORS,
  tooltip: { trigger: 'item', formatter: '{b}：{c} 条（{d}%）' },
  legend: { bottom: 0, itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 12 } },
  series: [
    {
      name: '河道等级',
      type: 'pie',
      radius: ['40%', '66%'],
      center: ['50%', '44%'],
      itemStyle: { borderColor: '#fff', borderWidth: 2, borderRadius: 4 },
      label: { formatter: '{b}\n{c} 条' },
      data: charts.value?.riverLevel ?? [],
    },
  ],
}))

/** 加载概览指标 */
async function loadSummary(): Promise<void> {
  loading.value = true
  try {
    summary.value = await fetchSummary()
  } catch (error) {
    console.error('[city-workspace] 概览数据加载失败', error)
    ElMessage.error('概览数据加载失败，请稍后重试')
    summary.value = null
  } finally {
    loading.value = false
  }
}

/** 加载图表数据 */
async function loadChartData(): Promise<void> {
  chartLoading.value = true
  try {
    charts.value = await fetchCharts()
  } catch (error) {
    console.error('[city-workspace] 图表数据加载失败', error)
    ElMessage.error('图表数据加载失败，请稍后重试')
    charts.value = null
  } finally {
    chartLoading.value = false
  }
}

/** 重置县级河长查询条件（保留县级范围） */
async function handleChiefReset(): Promise<void> {
  chiefQuery.keyword = ''
  chiefQuery.page = 1
  await loadChiefs()
}

onMounted(() => {
  loadSummary()
  loadChartData()
  loadRivers()
  loadChiefs()
  loadEvents()
})
</script>

<template>
  <div class="rv-page">
    <PageHeader
      title="市级河长工作台"
      :description="`${userStore.userInfo?.regionName || '本市'}河长制日常管理 · 统筹河道档案、督导县级河长、处置市级涉水事件`"
    >
      <template #extra>
        <el-button :icon="Refresh" :loading="loading" @click="loadSummary">刷新数据</el-button>
        <el-button type="primary" :icon="Share" @click="router.push('/river')">河道档案</el-button>
      </template>
    </PageHeader>

    <!-- 核心指标 -->
    <div v-loading="loading" class="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-4">
      <StatCard label="全市河道总数" :value="summary?.riverTotal ?? 0" suffix="条" :icon="OfficeBuilding" color="blue" />
      <StatCard label="水质预警河道" :value="summary?.riverWarn ?? 0" suffix="条" :icon="Share" color="orange" />
      <StatCard label="县级河长" :value="chiefTotal" suffix="人" :icon="User" color="purple" />
      <StatCard label="待处理事件" :value="summary?.eventPending ?? 0" suffix="件" :icon="Bell" color="red" />
    </div>

    <!-- 图表与县级河长督导 -->
    <div class="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-4">
      <div class="rv-card xl:col-span-2">
        <div class="rv-card-header">
          <span class="rv-card-title">全市河道等级构成</span>
        </div>
        <div class="rv-card-body">
          <EChart :option="riverLevelOption" height="300px" :loading="chartLoading" />
        </div>
      </div>

      <div class="rv-card">
        <div class="rv-card-header">
          <span class="rv-card-title">督导县级河长</span>
          <el-button link type="primary" @click="router.push('/chief/list')">河长列表</el-button>
        </div>
        <div v-loading="chiefLoading" class="rv-card-body">
          <el-empty v-if="!sortedChiefs.length" description="暂无县级河长数据" :image-size="80" />
          <ul v-else class="rv-chief-list">
            <li v-for="item in sortedChiefs" :key="item.id" class="rv-chief">
              <div class="rv-chief__head">
                <span class="rv-chief__name">{{ item.name }}</span>
                <StatusTag :status="item.status" />
              </div>
              <div class="rv-chief__meta">{{ item.region }} · {{ item.post }} · 负责 {{ item.riverCount }} 条河道</div>
              <div class="rv-chief__bar">
                <el-progress :percentage="item.patrolRate" :stroke-width="8" text-inside>
                  <span class="rv-chief__label">巡查完成率 {{ item.patrolRate }}%</span>
                </el-progress>
              </div>
              <div class="rv-chief__bar">
                <el-progress :percentage="item.resolveRate" :stroke-width="8" status="success" text-inside>
                  <span class="rv-chief__label">问题解决率 {{ item.resolveRate }}%</span>
                </el-progress>
              </div>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <!-- 本市河道列表 -->
    <div class="rv-card mb-4">
      <div class="rv-card-header">
        <span class="rv-card-title">本市河道列表</span>
        <div class="flex items-center gap-2">
          <el-input v-model="riverQuery.keyword" placeholder="河道名称 / 编码" clearable class="!w-44" @keyup.enter="searchRivers" />
          <el-select v-model="riverQuery.level" placeholder="河道等级" clearable class="!w-32">
            <el-option v-for="item in RIVER_LEVEL_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-select v-model="riverQuery.region" placeholder="所属区域" clearable filterable class="!w-32">
            <el-option v-for="item in REGION_OPTIONS" :key="item" :label="item" :value="item" />
          </el-select>
          <el-select v-model="riverQuery.status" placeholder="运行状态" clearable class="!w-28">
            <el-option v-for="item in RIVER_STATUS_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-button type="primary" @click="searchRivers">查询</el-button>
          <el-button @click="resetRivers">重置</el-button>
        </div>
      </div>
      <div v-loading="riverLoading" class="rv-card-body">
        <el-empty v-if="!riverList.length" description="暂无河道数据" :image-size="80" />
        <template v-else>
          <el-table :data="riverList" stripe size="default">
            <el-table-column prop="code" label="河道编码" width="130" />
            <el-table-column prop="name" label="河道名称" min-width="140" show-overflow-tooltip />
            <el-table-column prop="level" label="等级" width="90" />
            <el-table-column prop="basin" label="所属流域" width="120" />
            <el-table-column prop="region" label="所属区域" width="110" />
            <el-table-column prop="chiefName" label="责任河长" width="100" />
            <el-table-column label="河道长度(km)" width="120">
              <template #default="{ row }">
                <span class="rv-num">{{ row.length }}</span>
              </template>
            </el-table-column>
            <el-table-column label="水质达标率" width="130">
              <template #default="{ row }">
                <el-progress :percentage="row.qualityRate" :stroke-width="8" />
              </template>
            </el-table-column>
            <el-table-column prop="patrolCount" label="巡查次数" width="100" />
            <el-table-column prop="eventCount" label="事件数" width="90" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <StatusTag :status="row.status" />
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            background
            :current-page="riverQuery.page"
            :page-size="riverQuery.pageSize"
            :page-sizes="[10, 20, 50]"
            :total="riverTotal"
            layout="total, sizes, prev, pager, next"
            @current-change="changeRiverPage"
            @size-change="changeRiverPageSize"
          />
        </template>
      </div>
    </div>

    <!-- 市级事件处理 -->
    <div class="rv-card">
      <div class="rv-card-header">
        <span class="rv-card-title">市级事件处理</span>
        <div class="flex items-center gap-2">
          <el-input v-model="eventQuery.keyword" placeholder="事件标题 / 河道" clearable class="!w-44" @keyup.enter="searchEvents" />
          <el-select v-model="eventQuery.status" placeholder="处理状态" clearable class="!w-32">
            <el-option v-for="item in EVENT_STATUS_OPTIONS" :key="item" :label="item" :value="item" />
          </el-select>
          <el-button type="primary" @click="searchEvents">查询</el-button>
          <el-button @click="resetEvents">重置</el-button>
        </div>
      </div>
      <div v-loading="eventLoading" class="rv-card-body">
        <el-empty v-if="!eventList.length" description="暂无事件数据" :image-size="80" />
        <template v-else>
          <el-table :data="eventList" stripe size="default">
            <el-table-column prop="id" label="事件编号" width="110" />
            <el-table-column prop="title" label="事件标题" min-width="170" show-overflow-tooltip />
            <el-table-column prop="type" label="事件类型" width="110" />
            <el-table-column label="等级" width="90">
              <template #default="{ row }">
                <StatusTag :status="row.level" />
              </template>
            </el-table-column>
            <el-table-column prop="riverName" label="涉及河道" width="120" show-overflow-tooltip />
            <el-table-column prop="reporter" label="上报来源" width="120" />
            <el-table-column prop="handler" label="处理人" width="100" />
            <el-table-column prop="occurAt" label="发生时间" width="160" />
            <el-table-column prop="deadline" label="办结时限" width="160" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <StatusTag :status="row.status" />
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            background
            :current-page="eventQuery.page"
            :page-size="eventQuery.pageSize"
            :page-sizes="[10, 20, 50]"
            :total="eventTotal"
            layout="total, sizes, prev, pager, next"
            @current-change="changeEventPage"
            @size-change="changeEventPageSize"
          />
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rv-chief-list {
  margin: 0;
  padding: 0;
  list-style: none;
  max-height: 300px;
  overflow-y: auto;
}

.rv-chief {
  padding: 10px 4px;
  border-bottom: 1px dashed var(--rv-border);
}

.rv-chief:last-child {
  border-bottom: none;
}

.rv-chief__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.rv-chief__name {
  font-size: 13px;
  font-weight: 600;
  color: var(--rv-text);
}

.rv-chief__meta {
  margin: 2px 0 8px;
  font-size: 12px;
  color: var(--rv-text-secondary);
}

.rv-chief__bar {
  margin-bottom: 6px;
}

.rv-chief__label {
  font-size: 11px;
  color: var(--rv-text-secondary);
}
</style>
