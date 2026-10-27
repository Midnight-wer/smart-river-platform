<script setup lang="ts">
/**
 * 乡镇级河长工作台：日常巡查任务执行、问题上报、现场处理记录
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Bell, Compass, EditPen, OfficeBuilding, Refresh, Tickets } from '@element-plus/icons-vue'
import * as echarts from '@/utils/echarts'
import EChart from '@/components/EChart.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useTable } from '@/composables/useTable'
import { createEvent, fetchEvents } from '@/api/event'
import { fetchPatrols } from '@/api/patrol'
import { fetchRivers } from '@/api/river'
import { useUserStore } from '@/stores/user'
import { formatDateTime } from '@/utils/format'
import type { EventType, RiverEvent } from '@/types'

interface ProcessRecord {
  id: string
  title: string
  operator: string
  action: string
  remark: string
  time: string
}

const router = useRouter()
const userStore = useUserStore()

/** 巡查任务全量（用于统计与图表） */
const { loading: patrolLoading, list: patrolAll, load: loadPatrolAll } = useTable(fetchPatrols, { pageSize: 100 })

/** 日常巡查任务列表 */
const {
  loading: patrolListLoading,
  list: patrolList,
  total: patrolTotal,
  query: patrolQuery,
  load: loadPatrols,
  search: searchPatrols,
  reset: resetPatrols,
  changePage: changePatrolPage,
  changePageSize: changePatrolPageSize,
} = useTable(fetchPatrols)

/** 事件全量（用于现场处理记录） */
const { list: eventAll, load: loadEventAll } = useTable(fetchEvents, { pageSize: 100 })

/** 辖区河道（用于上报选择） */
const { list: riverList, load: loadRivers } = useTable(fetchRivers, { pageSize: 100 })

const PATROL_TYPE_OPTIONS = ['日常巡查', '专项巡查', '整改复查', '汛期排查']

const PATROL_STATUS_OPTIONS = ['待执行', '进行中', '已完成', '已逾期']

const EVENT_TYPE_OPTIONS: EventType[] = ['水质异常', '漂浮物', '违规排污', '堤岸损坏', '其他事件']

const PIE_COLORS = ['#1d4ed8', '#f59e0b', '#16a34a', '#dc2626']

/** 上报问题弹窗 */
const reportVisible = ref(false)
const reportLoading = ref(false)
const reportFormRef = ref<FormInstance>()
const reportForm = reactive({
  riverName: '',
  type: '水质异常' as EventType,
  level: '一般' as RiverEvent['level'],
  occurAt: formatDateTime(new Date()),
  deadline: '',
  description: '',
})

const reportRules: FormRules = {
  riverName: [{ required: true, message: '请选择涉及河道', trigger: 'change' }],
  type: [{ required: true, message: '请选择问题类型', trigger: 'change' }],
  occurAt: [{ required: true, message: '请选择发生时间', trigger: 'change' }],
  deadline: [{ required: true, message: '请选择办结时限', trigger: 'change' }],
  description: [{ required: true, message: '请填写问题描述', trigger: 'blur' }],
}

/** 待执行巡查任务 */
const pendingPatrols = computed(() => patrolAll.value.filter((item) => item.status === '待执行'))

/** 进行中巡查任务 */
const doingPatrols = computed(() => patrolAll.value.filter((item) => item.status === '进行中'))

/** 已逾期巡查任务 */
const overduePatrols = computed(() => patrolAll.value.filter((item) => item.status === '已逾期'))

/** 巡查任务状态分布 */
const patrolStatusOption = computed<echarts.EChartsOption>(() => {
  const counts = new Map<string, number>()
  patrolAll.value.forEach((item) => {
    counts.set(item.status, (counts.get(item.status) ?? 0) + 1)
  })
  return {
    color: PIE_COLORS,
    tooltip: { trigger: 'item', formatter: '{b}：{c} 项（{d}%）' },
    legend: { bottom: 0, itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 12 } },
    series: [
      {
        name: '任务状态',
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

/** 现场处理记录（按时间倒序） */
const processRecords = computed<ProcessRecord[]>(() => {
  const records: ProcessRecord[] = []
  eventAll.value.forEach((item) => {
    item.logs.forEach((log) => {
      records.push({
        id: log.id,
        title: item.title,
        operator: log.operator,
        action: log.action,
        remark: log.remark,
        time: log.time,
      })
    })
  })
  return records.sort((a, b) => (a.time < b.time ? 1 : -1)).slice(0, 12)
})

/** 打开上报问题弹窗 */
function openReport(): void {
  reportForm.riverName = reportForm.riverName || riverList.value[0]?.name || ''
  reportForm.type = '水质异常'
  reportForm.level = '一般'
  reportForm.occurAt = formatDateTime(new Date())
  reportForm.deadline = ''
  reportForm.description = ''
  reportVisible.value = true
}

/** 提交上报问题 */
async function handleReport(): Promise<void> {
  if (!reportFormRef.value) return
  const valid = await reportFormRef.value.validate().catch(() => false)
  if (!valid) return

  reportLoading.value = true
  try {
    await createEvent({
      title: `${reportForm.riverName}${reportForm.type}`,
      type: reportForm.type,
      status: '待处理',
      level: reportForm.level,
      riverName: reportForm.riverName,
      region: userStore.userInfo?.regionName || '',
      reporter: userStore.userInfo?.name || '',
      handler: '',
      occurAt: reportForm.occurAt,
      deadline: reportForm.deadline,
      description: reportForm.description,
    })
    ElMessage.success('问题已上报，等待属地河长核实处理')
    reportVisible.value = false
    await loadEventAll()
  } catch (error) {
    console.error('[town-workspace] 问题上报失败', error)
    ElMessage.error('问题上报失败，请稍后重试')
  } finally {
    reportLoading.value = false
  }
}

onMounted(() => {
  loadPatrolAll()
  loadPatrols()
  loadEventAll()
  loadRivers()
})
</script>

<template>
  <div class="rv-page">
    <PageHeader
      title="乡镇级河长工作台"
      :description="`${userStore.userInfo?.regionName || '本乡镇'}河长制日常履职 · 执行日常巡查任务，及时上报涉水问题`"
    >
      <template #extra>
        <el-button :icon="Refresh" :loading="patrolListLoading" @click="loadPatrols">刷新数据</el-button>
        <el-button type="primary" :icon="EditPen" @click="openReport">上报问题</el-button>
      </template>
    </PageHeader>

    <!-- 核心指标 -->
    <div class="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-4">
      <StatCard label="巡查任务总数" :value="patrolAll.length" suffix="项" :icon="Tickets" color="blue" />
      <StatCard label="待执行任务" :value="pendingPatrols.length" suffix="项" :icon="OfficeBuilding" color="orange" />
      <StatCard label="进行中任务" :value="doingPatrols.length" suffix="项" :icon="Compass" color="cyan" />
      <StatCard label="已逾期任务" :value="overduePatrols.length" suffix="项" :icon="Bell" color="red" />
    </div>

    <!-- 图表与待执行任务 -->
    <div class="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-4">
      <div class="rv-card xl:col-span-2">
        <div class="rv-card-header">
          <span class="rv-card-title">巡查任务状态分布</span>
        </div>
        <div class="rv-card-body">
          <EChart :option="patrolStatusOption" height="300px" :loading="patrolLoading" />
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

    <!-- 日常巡查任务 -->
    <div class="rv-card mb-4">
      <div class="rv-card-header">
        <span class="rv-card-title">日常巡查任务</span>
        <div class="flex items-center gap-2">
          <el-input v-model="patrolQuery.keyword" placeholder="任务名称 / 河道" clearable class="!w-44" @keyup.enter="searchPatrols" />
          <el-select v-model="patrolQuery.type" placeholder="任务类型" clearable class="!w-32">
            <el-option v-for="item in PATROL_TYPE_OPTIONS" :key="item" :label="item" :value="item" />
          </el-select>
          <el-select v-model="patrolQuery.status" placeholder="任务状态" clearable class="!w-32">
            <el-option v-for="item in PATROL_STATUS_OPTIONS" :key="item" :label="item" :value="item" />
          </el-select>
          <el-button type="primary" @click="searchPatrols">查询</el-button>
          <el-button @click="resetPatrols">重置</el-button>
        </div>
      </div>
      <div v-loading="patrolListLoading" class="rv-card-body">
        <el-empty v-if="!patrolList.length" description="暂无巡查任务" :image-size="80" />
        <template v-else>
          <el-table :data="patrolList" stripe size="default">
            <el-table-column prop="id" label="任务编号" width="110" />
            <el-table-column prop="title" label="任务名称" min-width="170" show-overflow-tooltip />
            <el-table-column prop="riverName" label="巡查河道" width="130" show-overflow-tooltip />
            <el-table-column prop="type" label="任务类型" width="110" />
            <el-table-column prop="assignee" label="执行人" width="100" />
            <el-table-column label="巡查时长(分钟)" width="130">
              <template #default="{ row }">
                <span class="rv-num">{{ row.duration }}</span>
              </template>
            </el-table-column>
            <el-table-column label="巡查里程(km)" width="120">
              <template #default="{ row }">
                <span class="rv-num">{{ (row.distance / 1000).toFixed(1) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="foundIssues" label="发现问题" width="100" />
            <el-table-column prop="deadline" label="截止时间" width="160" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <StatusTag :status="row.status" />
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            background
            :current-page="patrolQuery.page"
            :page-size="patrolQuery.pageSize"
            :page-sizes="[10, 20, 50]"
            :total="patrolTotal"
            layout="total, sizes, prev, pager, next"
            @current-change="changePatrolPage"
            @size-change="changePatrolPageSize"
          />
        </template>
      </div>
    </div>

    <!-- 现场处理记录 -->
    <div class="rv-card">
      <div class="rv-card-header">
        <span class="rv-card-title">现场处理记录</span>
        <el-button link type="primary" @click="router.push('/event')">事件中心</el-button>
      </div>
      <div v-loading="patrolLoading" class="rv-card-body">
        <el-empty v-if="!processRecords.length" description="暂无现场处理记录" :image-size="80" />
        <el-timeline v-else>
          <el-timeline-item
            v-for="item in processRecords"
            :key="item.id"
            :timestamp="item.time"
            placement="top"
            type="primary"
          >
            <div class="rv-record__title">{{ item.title }}</div>
            <div class="rv-record__action">{{ item.operator }} · {{ item.action }}</div>
            <div class="rv-record__remark">{{ item.remark }}</div>
          </el-timeline-item>
        </el-timeline>
      </div>
    </div>

    <!-- 上报问题弹窗 -->
    <el-dialog v-model="reportVisible" title="上报问题" width="560px" :close-on-click-modal="false">
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
        <el-form-item label="发生时间" prop="occurAt">
          <el-date-picker
            v-model="reportForm.occurAt"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm"
            placeholder="请选择发生时间"
            class="w-full"
          />
        </el-form-item>
        <el-form-item label="办结时限" prop="deadline">
          <el-date-picker
            v-model="reportForm.deadline"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm"
            placeholder="请选择办结时限"
            class="w-full"
          />
        </el-form-item>
        <el-form-item label="问题描述" prop="description">
          <el-input
            v-model="reportForm.description"
            type="textarea"
            :rows="4"
            placeholder="请描述问题位置、现象及处置建议"
            maxlength="300"
            show-word-limit
          />
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

.rv-record__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--rv-text);
}

.rv-record__action {
  margin-top: 2px;
  font-size: 12px;
  color: var(--rv-primary);
}

.rv-record__remark {
  margin-top: 2px;
  font-size: 12px;
  color: var(--rv-text-secondary);
}
</style>
