<script setup lang="ts">
/**
 * 省级河长工作台：全省治理概览、下级河长考核、重大事项审批
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Bell, DocumentChecked, Medal, OfficeBuilding, Refresh, TrendCharts } from '@element-plus/icons-vue'
import * as echarts from '@/utils/echarts'
import EChart from '@/components/EChart.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useTable } from '@/composables/useTable'
import { fetchSummary } from '@/api/dashboard'
import type { DashboardSummary } from '@/api/dashboard'
import { fetchAssessments } from '@/api/assessment'
import { fetchEvents, updateEvent } from '@/api/event'
import { useUserStore } from '@/stores/user'
import type { RiverEvent } from '@/types'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const approving = ref('')
const summary = ref<DashboardSummary | null>(null)

/** 下级河长考核明细（分页） */
const {
  loading: assessmentLoading,
  list: assessmentList,
  total: assessmentTotal,
  query: assessmentQuery,
  load: loadAssessments,
  search: searchAssessments,
  reset: resetAssessments,
  changePage: changeAssessmentPage,
  changePageSize: changeAssessmentPageSize,
} = useTable(fetchAssessments)

/** 考核全量数据（用于排名统计） */
const { list: assessmentAll, load: loadAssessmentAll } = useTable(fetchAssessments, { pageSize: 100 })

/** 重大事项（事件等级为「重大」） */
const { loading: majorLoading, list: majorEvents, load: loadMajorEvents } = useTable(
  async (params) => {
    const result = await fetchEvents({ ...params, pageSize: 100 })
    const filtered = result.list.filter((item) => item.level === '重大')
    return { ...result, list: filtered, total: filtered.length }
  },
  { pageSize: 100 },
)

const LEVEL_OPTIONS = [
  { label: '市级河长', value: 'city' },
  { label: '县级河长', value: 'county' },
  { label: '乡镇级河长', value: 'town' },
]

/** 下辖市（州）平均考核得分排名 */
const regionRanking = computed(() => {
  const groups = new Map<string, { total: number; count: number }>()
  assessmentAll.value.forEach((item) => {
    const current = groups.get(item.region) ?? { total: 0, count: 0 }
    current.total += item.totalScore
    current.count += 1
    groups.set(item.region, current)
  })
  return Array.from(groups.entries())
    .map(([name, group]) => ({ name, value: Number((group.total / group.count).toFixed(1)) }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8)
})

/** 考核排名靠前的下级河长 */
const topAssessments = computed(() => [...assessmentAll.value].sort((a, b) => a.rank - b.rank).slice(0, 6))

/** 重大事项待处理数量 */
const majorPending = computed(() => majorEvents.value.filter((item) => item.status === '待处理').length)

const rankingOption = computed<echarts.EChartsOption>(() => ({
  color: ['#1d4ed8'],
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: 96, right: 44, top: 12, bottom: 28 },
  xAxis: {
    type: 'value',
    max: 100,
    splitLine: { lineStyle: { type: 'dashed' } },
    axisLabel: { fontSize: 11 },
  },
  yAxis: {
    type: 'category',
    inverse: true,
    data: regionRanking.value.map((item) => item.name),
    axisLabel: { fontSize: 12 },
  },
  series: [
    {
      name: '平均考核得分',
      type: 'bar',
      barWidth: 14,
      itemStyle: { borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', formatter: '{c}', fontSize: 11 },
      data: regionRanking.value.map((item) => item.value),
    },
  ],
}))

/** 加载概览指标 */
async function loadSummary(): Promise<void> {
  loading.value = true
  try {
    summary.value = await fetchSummary()
  } catch (error) {
    console.error('[province-workspace] 概览数据加载失败', error)
    ElMessage.error('概览数据加载失败，请稍后重试')
    summary.value = null
  } finally {
    loading.value = false
  }
}

/** 重大事项审批派单 */
async function handleApprove(row: RiverEvent): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认审批通过「${row.title}」并派单至 ${row.region} 属地河长？`, '重大事项审批', {
      type: 'warning',
      confirmButtonText: '确认审批',
      cancelButtonText: '取消',
    })
  } catch (error) {
    console.info('[province-workspace] 用户取消审批', error)
    return
  }

  approving.value = row.id
  try {
    await updateEvent(row.id, { status: '处理中', handler: userStore.userInfo?.name || row.handler })
    ElMessage.success('重大事项已审批并派单')
    await loadMajorEvents()
  } catch (error) {
    console.error('[province-workspace] 重大事项审批失败', error)
    ElMessage.error('重大事项审批失败，请稍后重试')
  } finally {
    approving.value = ''
  }
}

/** 重置考核查询条件 */
function handleReset(): Promise<void> {
  return resetAssessments()
}

onMounted(() => {
  loadSummary()
  loadAssessments()
  loadAssessmentAll()
  loadMajorEvents()
})
</script>

<template>
  <div class="rv-page">
    <PageHeader
      title="省级河长工作台"
      :description="`${userStore.userInfo?.regionName || '全省'}河长制统筹管理 · 考核下级河长履职情况，审批重大涉水事项`"
    >
      <template #extra>
        <el-button :icon="Refresh" :loading="loading" @click="loadSummary">刷新数据</el-button>
        <el-button type="primary" :icon="TrendCharts" @click="router.push('/assessment')">考核管理</el-button>
      </template>
    </PageHeader>

    <!-- 核心指标 -->
    <div v-loading="loading" class="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-4">
      <StatCard label="全省河道总数" :value="summary?.riverTotal ?? 0" suffix="条" :icon="OfficeBuilding" color="blue" />
      <StatCard label="水质达标率" :value="summary?.qualityRate ?? 0" suffix="%" :icon="TrendCharts" color="green" />
      <StatCard label="在册河长" :value="summary?.chiefTotal ?? 0" suffix="人" :icon="Medal" color="purple" />
      <StatCard label="待处理重大事项" :value="majorPending" suffix="件" :icon="Bell" color="red" />
    </div>

    <!-- 排名图表与考核列表 -->
    <div class="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-4">
      <div class="rv-card xl:col-span-2">
        <div class="rv-card-header">
          <span class="rv-card-title">下辖市（州）履职考核排名</span>
        </div>
        <div class="rv-card-body">
          <EChart :option="rankingOption" height="320px" />
        </div>
      </div>

      <div class="rv-card">
        <div class="rv-card-header">
          <span class="rv-card-title">考核下级河长</span>
          <el-button link type="primary" @click="router.push('/assessment')">查看全部</el-button>
        </div>
        <div v-loading="assessmentLoading" class="rv-card-body">
          <el-empty v-if="!topAssessments.length" description="暂无考核数据" :image-size="80" />
          <ul v-else class="rv-rank-list">
            <li v-for="item in topAssessments" :key="item.id" class="rv-rank">
              <span class="rv-rank__no" :class="`is-${item.rank}`">{{ item.rank }}</span>
              <div class="rv-rank__main">
                <div class="rv-rank__name">{{ item.chiefName }}<span>{{ item.levelName }}</span></div>
                <div class="rv-rank__region">{{ item.region }} · 巡查 {{ item.patrolRate }}% · 处置 {{ item.resolveRate }}%</div>
              </div>
              <span class="rv-rank__score rv-num">{{ item.totalScore }}</span>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <!-- 重大事项审批 -->
    <div class="rv-card mb-4">
      <div class="rv-card-header">
        <span class="rv-card-title">重大事项审批</span>
        <el-button link type="primary" @click="router.push('/event')">事件中心</el-button>
      </div>
      <div v-loading="majorLoading" class="rv-card-body">
        <el-empty v-if="!majorEvents.length" description="暂无重大事项" :image-size="80" />
        <el-table v-else :data="majorEvents" stripe size="default">
          <el-table-column prop="id" label="事件编号" width="120" />
          <el-table-column prop="title" label="事项标题" min-width="180" show-overflow-tooltip />
          <el-table-column prop="type" label="事件类型" width="110" />
          <el-table-column label="等级" width="90">
            <template #default="{ row }">
              <StatusTag :status="row.level" />
            </template>
          </el-table-column>
          <el-table-column prop="riverName" label="涉及河道" width="130" show-overflow-tooltip />
          <el-table-column prop="region" label="所属区域" width="120" />
          <el-table-column prop="handler" label="当前处理人" width="110" />
          <el-table-column prop="occurAt" label="发生时间" width="160" />
          <el-table-column prop="deadline" label="办结时限" width="160" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <StatusTag :status="row.status" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button
                link
                type="primary"
                :icon="DocumentChecked"
                :loading="approving === row.id"
                @click="handleApprove(row)"
              >
                审批派单
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 下级河长考核明细 -->
    <div class="rv-card">
      <div class="rv-card-header">
        <span class="rv-card-title">下级河长考核明细</span>
        <div class="flex items-center gap-2">
          <el-input
            v-model="assessmentQuery.keyword"
            placeholder="河长姓名"
            clearable
            class="!w-48"
            @keyup.enter="searchAssessments"
          />
          <el-select v-model="assessmentQuery.level" placeholder="河长层级" clearable class="!w-36">
            <el-option v-for="item in LEVEL_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-button type="primary" @click="searchAssessments">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </div>
      </div>
      <div v-loading="assessmentLoading" class="rv-card-body">
        <el-empty v-if="!assessmentList.length" description="暂无考核记录" :image-size="80" />
        <template v-else>
          <el-table :data="assessmentList" stripe size="default">
            <el-table-column prop="name" label="考核名称" min-width="160" show-overflow-tooltip />
            <el-table-column prop="chiefName" label="河长" width="100" />
            <el-table-column prop="levelName" label="层级" width="120" />
            <el-table-column prop="region" label="所属区域" width="120" />
            <el-table-column prop="period" label="考核周期" width="130" />
            <el-table-column label="巡查完成率" width="130">
              <template #default="{ row }">
                <el-progress :percentage="row.patrolRate" :stroke-width="8" />
              </template>
            </el-table-column>
            <el-table-column label="问题解决率" width="130">
              <template #default="{ row }">
                <el-progress :percentage="row.resolveRate" :stroke-width="8" status="success" />
              </template>
            </el-table-column>
            <el-table-column label="水质达标率" width="130">
              <template #default="{ row }">
                <el-progress :percentage="row.qualityRate" :stroke-width="8" status="warning" />
              </template>
            </el-table-column>
            <el-table-column prop="responseTime" label="响应时长(小时)" width="130" />
            <el-table-column prop="satisfaction" label="满意度(%)" width="110" />
            <el-table-column prop="totalScore" label="综合得分" width="110" />
            <el-table-column prop="rank" label="排名" width="80" />
          </el-table>
          <el-pagination
            background
            :current-page="assessmentQuery.page"
            :page-size="assessmentQuery.pageSize"
            :page-sizes="[10, 20, 50]"
            :total="assessmentTotal"
            layout="total, sizes, prev, pager, next"
            @current-change="changeAssessmentPage"
            @size-change="changeAssessmentPageSize"
          />
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rv-rank-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.rv-rank {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 4px;
  border-bottom: 1px dashed var(--rv-border);
}

.rv-rank:last-child {
  border-bottom: none;
}

.rv-rank__no {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 8px;
  background: var(--rv-primary-soft);
  color: var(--rv-primary);
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.rv-rank__no.is-1 {
  background: #fef2f2;
  color: #dc2626;
}

.rv-rank__no.is-2 {
  background: #fff7ed;
  color: #ea580c;
}

.rv-rank__no.is-3 {
  background: #eff6ff;
  color: #1d4ed8;
}

.rv-rank__main {
  flex: 1;
  min-width: 0;
}

.rv-rank__name {
  font-size: 13px;
  color: var(--rv-text);
  font-weight: 600;
}

.rv-rank__name span {
  margin-left: 6px;
  font-size: 12px;
  font-weight: 400;
  color: var(--rv-text-secondary);
}

.rv-rank__region {
  margin-top: 2px;
  font-size: 12px;
  color: var(--rv-text-secondary);
}

.rv-rank__score {
  font-size: 15px;
  font-weight: 600;
  color: var(--rv-primary);
}
</style>
