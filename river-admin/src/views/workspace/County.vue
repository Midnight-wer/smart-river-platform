<script setup lang="ts">
/**
 * 县级河长工作台：辖区河道管理、待执行巡查任务跟踪、事件整改上报
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Bell, Compass, EditPen, OfficeBuilding, Refresh, Share } from '@element-plus/icons-vue'
import * as echarts from '@/utils/echarts'
import EChart from '@/components/EChart.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useTable } from '@/composables/useTable'
import { fetchEvents, createEvent } from '@/api/event'
import { fetchPatrols } from '@/api/patrol'
import { fetchRivers } from '@/api/river'
import { useUserStore } from '@/stores/user'
import { formatDateTime } from '@/utils/format'
import type { EventType, RiverEvent } from '@/types'

const router = useRouter()
const userStore = useUserStore()

/** 辖区河道 */
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

/** 巡查任务（用于统计与待执行清单） */
const { loading: patrolLoading, list: patrolList, load: loadPatrols } = useTable(fetchPatrols, { pageSize: 100 })

/** 辖区事件（全量，用于统计） */
const { list: eventAll, load: loadEventAll } = useTable(fetchEvents, { pageSize: 100 })

/** 辖区事件（分页列表） */
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

const RIVER_STATUS_OPTIONS = [
  { label: '正常', value: '正常' },
  { label: '预警', value: '预警' },
  { label: '停用', value: '停用' },
]

const EVENT_TYPE_OPTIONS: EventType[] = ['水质异常', '漂浮物', '违规排污', '堤岸损坏', '其他事件']

const EVENT_STATUS_OPTIONS = ['待处理', '处理中', '已完成', '已归档', '已驳回', '已关闭']

const PIE_COLORS = ['#1d4ed8', '#16a34a', '#f59e0b', '#dc2626', '#7c3aed']

/** 整改上报弹窗 */
const reportVisible = ref(false)
const reportLoading = ref(false)
const reportFormRef = ref<FormInstance>()
const reportForm = reactive({
  riverName: '',
  type: '水质异常' as EventType,
  level: '一般' as RiverEvent['level'],
  description: '',
  deadline: '',
})

const reportRules: FormRules = {
  riverName: [{ required: true, message: '请选择涉及河道', trigger: 'change' }],
  type: [{ required: true, message: '请选择问题类型', trigger: 'change' }],
  description: [{ required: true, message: '请填写问题描述', trigger: 'blur' }],
  deadline: [{ required: true, message: '请选择整改期限', trigger: 'change' }],
}

/** 待执行巡查任务 */
const pendingPatrols = computed(() => patrolList.value.filter((item) => item.status === '待执行'))

/** 待处理事件数 */
const pendingEventCount = computed(() => eventAll.value.filter((item) => item.status === '待处理').length)

/** 已办结事件数 */
const finishedEventCount = computed(
  () => eventAll.value.filter((item) => item.status === '已完成' || item.status === '已归档').length,
)

/** 巡查任务类型分布 */
const patrolTypeOption = computed<echarts.EChartsOption>(() => {
  const counts = new Map<string, number>()
  patrolList.value.forEach((item) => {
    counts.set(item.type, (counts.get(item.type) ?? 0) + 1)
  })
  return {
    color: PIE_COLORS,
    tooltip: { trigger: 'item', formatter: '{b}：{c} 项（{d}%）' },
    legend: { bottom: 0, itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 12 } },
    series: [
      {
        name: '巡查类型',
        type: 'pie',
        radius: ['40%', '66%'],
        center: ['50%', '44%'],
        itemStyle: { borderColor: '#fff', borderWidth: 2, borderRadius: 4 },
        label: { formatter: '{b}\n{c} 项' },
        data: Array.from(counts.entries()).map(([name, value]) => ({ name, value })),
      },
    ],
  }
})

/** 打开整改上报弹窗 */
function openReport(): void {
  reportForm.riverName = reportForm.riverName || riverList.value[0]?.name || ''
  reportForm.type = '水质异常'
  reportForm.level = '一般'
  reportForm.description = ''
  reportForm.deadline = ''
  reportVisible.value = true
}

/** 提交整改上报 */
async function handleReport(): Promise<void> {
  if (!reportFormRef.value) return
  const valid = await reportFormRef.value.validate().catch(() => false)
  if (!valid) return

  reportLoading.value = true
  try {
    await createEvent({
      title: `${reportForm.riverName}${reportForm.type}整改上报`,
      type: reportForm.type,
      status: '待处理',
      level: reportForm.level,
      riverName: reportForm.riverName,
      region: userStore.userInfo?.regionName || '',
      reporter: userStore.userInfo?.name || '',
      handler: '',
      occurAt: formatDateTime(new Date()),
      deadline: reportForm.deadline,
      description: reportForm.description,
    })
    ElMessage.success('整改上报已提交，等待上级审核派单')
    reportVisible.value = false
    await loadEvents()
    await loadEventAll()
  } catch (error) {
    console.error('[county-workspace] 整改上报提交失败', error)
    ElMessage.error('整改上报提交失败，请稍后重试')
  } finally {
    reportLoading.value = false
  }
}

onMounted(() => {
  loadRivers()
  loadPatrols()
  loadEvents()
  loadEventAll()
})
</script>

<template>
  <div class="rv-page">
    <PageHeader
      title="县级河长工作台"
      :description="`${userStore.userInfo?.regionName || '本县'}河长制日常履职 · 跟踪辖区河道与巡查任务，推进问题整改上报`"
    >
      <template #extra>
        <el-button :icon="Refresh" :loading="riverLoading" @click="loadRivers">刷新数据</el-button>
        <el-button type="primary" :icon="EditPen" @click="openReport">整改上报</el-button>
      </template>
    </PageHeader>

    <!-- 核心指标 -->
    <div class="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-4">
      <StatCard label="辖区河道总数" :value="riverTotal" suffix="条" :icon="OfficeBuilding" color="blue" />
      <StatCard label="待执行巡查任务" :value="pendingPatrols.length" suffix="项" :icon="Compass" color="orange" />
      <StatCard label="待处理事件" :value="pendingEventCount" suffix="件" :icon="Bell" color="red" />
      <StatCard label="已办结事件" :value="finishedEventCount" suffix="件" :icon="Share" color="green" />
    </div>

    <!-- 图表与待执行任务 -->
    <div class="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-4">
      <div class="rv-card xl:col-span-2">
        <div class="rv-card-header">
          <span class="rv-card-title">巡查任务类型分布</span>
        </div>
        <div class="rv-card-body">
          <EChart :option="patrolTypeOption" height="300px" :loading="patrolLoading" />
        </div>
      </div>

      <div class="rv-card">
        <div class="rv-card-header">
          <span class="rv-card-title">待执行巡查任务</span>
          <el-button link type="primary" @click="router.push('/patrol')">巡查管理</el-button>
        </div>
        <div v-loading="patrolLoading" class="rv-card-body">
          <el-empty v-if="!pendingPatrols.length" description="暂无待执行任务" :image-size="80" />
          <ul v-else class="rv-task-list">
            <li v-for="item in pendingPatrols" :key="item.id" class="rv-task">
              <div class="rv-task__head">
                <span class="rv-task__title">{{ item.title }}</span>
                <StatusTag :status="item.type" />
              </div>
              <div class="rv-task__meta">河道：{{ item.riverName }} · 执行人：{{ item.assignee }}</div>
              <div class="rv-task__deadline">截止时间：{{ item.deadline }}</div>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <!-- 辖区河道 -->
    <div class="rv-card mb-4">
      <div class="rv-card-header">
        <span class="rv-card-title">辖区河道</span>
        <div class="flex items-center gap-2">
          <el-input v-model="riverQuery.keyword" placeholder="河道名称 / 编码" clearable class="!w-44" @keyup.enter="searchRivers" />
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
            <el-table-column prop="name" label="河道名称" min-width="140" show-overflow-tooltip />
            <el-table-column prop="code" label="河道编码" width="130" />
            <el-table-column prop="level" label="等级" width="90" />
            <el-table-column prop="basin" label="所属流域" width="120" />
            <el-table-column prop="region" label="所属区域" width="110" />
            <el-table-column prop="chiefName" label="责任河长" width="100" />
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

    <!-- 辖区事件 -->
    <div class="rv-card">
      <div class="rv-card-header">
        <span class="rv-card-title">辖区事件</span>
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
            <el-table-column prop="deadline" label="办结时限" width="160" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <StatusTag :status="row.status" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="110" fixed="right">
              <template #default>
                <el-button link type="primary" :icon="EditPen" @click="openReport">整改上报</el-button>
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

    <!-- 整改上报弹窗 -->
    <el-dialog v-model="reportVisible" title="整改上报" width="560px" :close-on-click-modal="false">
      <el-form ref="reportFormRef" :model="reportForm" :rules="reportRules" label-width="96px">
        <el-form-item label="涉及河道" prop="riverName">
          <el-select v-model="reportForm.riverName" placeholder="请选择涉及河道" filterable class="w-full">
            <el-option v-for="item in riverList" :key="item.id" :label="`${item.name}（${item.region}）`" :value="item.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="问题类型" prop="type">
          <el-select v-model="reportForm.type" placeholder="请选择问题类型" class="w-full">
            <el-option v-for="item in EVENT_TYPE_OPTIONS" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="问题等级" prop="level">
          <el-radio-group v-model="reportForm.level">
            <el-radio value="一般">一般</el-radio>
            <el-radio value="较大">较大</el-radio>
            <el-radio value="重大">重大</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="整改期限" prop="deadline">
          <el-date-picker
            v-model="reportForm.deadline"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm"
            placeholder="请选择整改期限"
            class="w-full"
          />
        </el-form-item>
        <el-form-item label="问题描述" prop="description">
          <el-input v-model="reportForm.description" type="textarea" :rows="4" placeholder="请描述问题位置、现象及整改要求" maxlength="300" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reportVisible = false">取消</el-button>
        <el-button type="primary" :loading="reportLoading" @click="handleReport">提交上报</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.rv-task-list {
  margin: 0;
  padding: 0;
  list-style: none;
  max-height: 300px;
  overflow-y: auto;
}

.rv-task {
  padding: 10px 4px;
  border-bottom: 1px dashed var(--rv-border);
}

.rv-task:last-child {
  border-bottom: none;
}

.rv-task__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.rv-task__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--rv-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rv-task__meta {
  margin-top: 4px;
  font-size: 12px;
  color: var(--rv-text-secondary);
}

.rv-task__deadline {
  margin-top: 2px;
  font-size: 12px;
  color: var(--rv-warning);
}
</style>
