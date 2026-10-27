<script setup lang="ts">
/**
 * 事件中心：事件检索、统计、分派、处理与归档
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Bell, CircleCheck, Search, User } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useTable } from '@/composables/useTable'
import { createEventLog, fetchEventDetail, fetchEvents, updateEvent } from '@/api/event'
import type { EventStatus, EventType, RiverEvent } from '@/types'
import { formatDateTime } from '@/utils/format'

const STATUS_OPTIONS: EventStatus[] = ['待处理', '处理中', '已完成', '已归档', '已驳回', '已关闭']
const TYPE_OPTIONS: EventType[] = ['水质异常', '漂浮物', '违规排污', '堤岸损坏', '其他事件']
const CLOSE_STATUS_OPTIONS: EventStatus[] = ['处理中', '已完成', '已关闭']

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
} = useTable(fetchEvents, { status: '', type: '' })

const allEvents = ref<RiverEvent[]>([])

/** 详情抽屉 */
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<RiverEvent | null>(null)

/** 分派弹窗 */
const assignVisible = ref(false)
const assignSubmitting = ref(false)
const assignFormRef = ref<FormInstance>()
const assignForm = reactive({
  id: '',
  handler: '',
  remark: '',
})

/** 处理弹窗 */
const handleVisible = ref(false)
const handleSubmitting = ref(false)
const handleFormRef = ref<FormInstance>()
const handleForm = reactive({
  id: '',
  operator: '',
  action: '处理反馈',
  remark: '',
  status: '已完成' as EventStatus,
})

const assignRules: FormRules = {
  handler: [{ required: true, message: '请选择处理人', trigger: 'blur' }],
}

const handleRules: FormRules = {
  operator: [{ required: true, message: '请填写处理人', trigger: 'blur' }],
  action: [{ required: true, message: '请填写处理动作', trigger: 'blur' }],
  remark: [{ required: true, message: '请填写处理说明', trigger: 'blur' }],
}

/** 加载全量事件用于统计 */
async function loadAllEvents(): Promise<void> {
  try {
    const result = await fetchEvents({ page: 1, pageSize: 500 })
    allEvents.value = result?.list ?? []
  } catch (error) {
    console.error('[事件中心] 事件统计加载失败', error)
    ElMessage.error('事件统计加载失败')
    allEvents.value = []
  }
}

const pendingCount = computed(() => allEvents.value.filter((item) => item.status === '待处理').length)
const doingCount = computed(() => allEvents.value.filter((item) => item.status === '处理中').length)
const doneCount = computed(() => allEvents.value.filter((item) => item.status === '已完成').length)

/** 打开事件详情 */
async function openDetail(row: RiverEvent): Promise<void> {
  detailVisible.value = true
  detailLoading.value = true
  try {
    detail.value = await fetchEventDetail(row.id)
  } catch (error) {
    console.error('[事件中心] 事件详情加载失败', error)
    ElMessage.error('事件详情加载失败')
  } finally {
    detailLoading.value = false
  }
}

/** 打开分派弹窗 */
function openAssign(row: RiverEvent): void {
  assignForm.id = row.id
  assignForm.handler = row.handler || ''
  assignForm.remark = ''
  assignVisible.value = true
}

/** 提交分派 */
async function submitAssign(): Promise<void> {
  if (!assignFormRef.value) return
  const valid = await assignFormRef.value.validate().catch(() => false)
  if (!valid) return

  assignSubmitting.value = true
  try {
    await updateEvent(assignForm.id, { handler: assignForm.handler, status: '处理中' })
    await createEventLog(assignForm.id, {
      operator: assignForm.handler,
      action: '分派处理',
      remark: assignForm.remark || '已分派处理人跟进处置',
    })
    ElMessage.success('分派成功')
    assignVisible.value = false
    await Promise.all([load(), loadAllEvents()])
  } catch (error) {
    console.error('[事件中心] 事件分派失败', error)
    ElMessage.error('事件分派失败')
  } finally {
    assignSubmitting.value = false
  }
}

/** 打开处理弹窗 */
function openHandle(row: RiverEvent): void {
  handleForm.id = row.id
  handleForm.operator = row.handler || ''
  handleForm.action = '处理反馈'
  handleForm.remark = ''
  handleForm.status = '已完成'
  handleVisible.value = true
}

/** 提交处理结果 */
async function submitHandle(): Promise<void> {
  if (!handleFormRef.value) return
  const valid = await handleFormRef.value.validate().catch(() => false)
  if (!valid) return

  handleSubmitting.value = true
  try {
    await createEventLog(handleForm.id, {
      operator: handleForm.operator,
      action: handleForm.action,
      remark: handleForm.remark,
    })
    await updateEvent(handleForm.id, { handler: handleForm.operator, status: handleForm.status })
    ElMessage.success('处理记录已提交')
    handleVisible.value = false
    await Promise.all([load(), loadAllEvents()])
    if (detailVisible.value && detail.value?.id === handleForm.id) {
      await openDetail(detail.value)
    }
  } catch (error) {
    console.error('[事件中心] 事件处理失败', error)
    ElMessage.error('事件处理失败')
  } finally {
    handleSubmitting.value = false
  }
}

/** 归档事件 */
async function handleArchive(row: RiverEvent): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认将事件「${row.title}」归档吗？`, '归档确认', {
      type: 'warning',
      confirmButtonText: '确认归档',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  try {
    await updateEvent(row.id, { status: '已归档' })
    await createEventLog(row.id, {
      operator: row.handler || '系统管理员',
      action: '归档',
      remark: '事件处置完成，资料归档留存',
    })
    ElMessage.success('事件已归档')
    await Promise.all([load(), loadAllEvents()])
  } catch (error) {
    console.error('[事件中心] 事件归档失败', error)
    ElMessage.error('事件归档失败')
  }
}

onMounted(() => {
  load()
  loadAllEvents()
})
</script>

<template>
  <div class="rv-page">
    <PageHeader title="事件中心" description="河道事件全流程跟踪：上报、分派、处理与归档">
      <template #extra>
        <el-button :icon="Search" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </template>
    </PageHeader>

    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4 mb-4">
      <StatCard label="事件总数" :value="allEvents.length" suffix="件" color="blue" :icon="Bell" />
      <StatCard label="待处理" :value="pendingCount" suffix="件" color="orange" />
      <StatCard label="处理中" :value="doingCount" suffix="件" color="cyan" :icon="User" />
      <StatCard label="已完成" :value="doneCount" suffix="件" color="green" :icon="CircleCheck" />
    </div>

    <!-- 事件列表 -->
    <div class="rv-card">
      <div class="rv-card-header">
        <span class="rv-card-title">事件列表</span>
        <div class="flex items-center gap-2">
          <el-input
            v-model="query.keyword"
            placeholder="标题 / 河道 / 处理人 / 来源"
            clearable
            class="!w-60"
            @keyup.enter="search"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-select v-model="query.status" placeholder="事件状态" clearable class="!w-32">
            <el-option v-for="item in STATUS_OPTIONS" :key="item" :label="item" :value="item" />
          </el-select>
          <el-select v-model="query.type" placeholder="事件类型" clearable class="!w-32">
            <el-option v-for="item in TYPE_OPTIONS" :key="item" :label="item" :value="item" />
          </el-select>
          <el-button type="primary" @click="search">查询</el-button>
        </div>
      </div>
      <div class="rv-card-body">
        <el-table v-loading="loading" :data="list" size="small" border>
          <el-table-column prop="title" label="事件标题" min-width="180" show-overflow-tooltip />
          <el-table-column prop="type" label="类型" width="100" align="center" />
          <el-table-column label="级别" width="88" align="center">
            <template #default="{ row }">
              <el-tag
                :type="row.level === '重大' ? 'danger' : row.level === '较大' ? 'warning' : 'info'"
                size="small"
                effect="light"
                round
              >
                {{ row.level }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="riverName" label="河道" min-width="120" show-overflow-tooltip />
          <el-table-column prop="region" label="所属区域" min-width="110" show-overflow-tooltip />
          <el-table-column prop="reporter" label="来源" width="120" show-overflow-tooltip />
          <el-table-column prop="handler" label="处理人" width="100" show-overflow-tooltip />
          <el-table-column label="发生时间" min-width="140">
            <template #default="{ row }">
              {{ formatDateTime(row.occurAt) }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="92">
            <template #default="{ row }">
              <StatusTag :status="row.status" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="230" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDetail(row)">详情</el-button>
              <el-button link type="primary" @click="openAssign(row)">分派</el-button>
              <el-button link type="primary" @click="openHandle(row)">处理</el-button>
              <el-button link type="warning" @click="handleArchive(row)">归档</el-button>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="暂无事件记录" :image-size="70" />
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

    <!-- 事件详情抽屉 -->
    <el-drawer v-model="detailVisible" title="事件详情" size="620px">
      <div v-loading="detailLoading" class="rv-event-detail">
        <template v-if="detail">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="事件标题" :span="2">{{ detail.title }}</el-descriptions-item>
            <el-descriptions-item label="事件类型">{{ detail.type }}</el-descriptions-item>
            <el-descriptions-item label="事件级别">{{ detail.level }}</el-descriptions-item>
            <el-descriptions-item label="所属河道">{{ detail.riverName }}</el-descriptions-item>
            <el-descriptions-item label="所属区域">{{ detail.region }}</el-descriptions-item>
            <el-descriptions-item label="事件来源">{{ detail.reporter }}</el-descriptions-item>
            <el-descriptions-item label="处理人">{{ detail.handler || '-' }}</el-descriptions-item>
            <el-descriptions-item label="发生时间">{{ formatDateTime(detail.occurAt) }}</el-descriptions-item>
            <el-descriptions-item label="办理时限">{{ formatDateTime(detail.deadline) }}</el-descriptions-item>
            <el-descriptions-item label="当前状态">
              <StatusTag :status="detail.status" />
            </el-descriptions-item>
            <el-descriptions-item label="事件描述" :span="2">{{ detail.description }}</el-descriptions-item>
          </el-descriptions>

          <div class="rv-event-detail__title">处理记录</div>
          <el-timeline v-if="detail.logs?.length">
            <el-timeline-item
              v-for="item in detail.logs"
              :key="item.id"
              :timestamp="formatDateTime(item.time)"
              placement="top"
            >
              <div class="rv-event-detail__action">
                <span class="rv-event-detail__operator">{{ item.operator }}</span>
                <el-tag size="small" effect="plain">{{ item.action }}</el-tag>
              </div>
              <p class="rv-event-detail__remark">{{ item.remark }}</p>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无处理记录" :image-size="70" />
        </template>
        <el-empty v-else description="暂无事件详情" :image-size="70" />
      </div>
    </el-drawer>

    <!-- 分派弹窗 -->
    <el-dialog v-model="assignVisible" title="分派事件" width="460px">
      <el-form ref="assignFormRef" :model="assignForm" :rules="assignRules" label-width="88px">
        <el-form-item label="处理人" prop="handler">
          <el-input v-model="assignForm.handler" placeholder="请输入处理人姓名" clearable />
        </el-form-item>
        <el-form-item label="分派说明">
          <el-input
            v-model="assignForm.remark"
            type="textarea"
            :rows="3"
            placeholder="请输入分派说明"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button type="primary" :loading="assignSubmitting" @click="submitAssign">确认分派</el-button>
      </template>
    </el-dialog>

    <!-- 处理弹窗 -->
    <el-dialog v-model="handleVisible" title="事件处理" width="520px">
      <el-form ref="handleFormRef" :model="handleForm" :rules="handleRules" label-width="88px">
        <el-form-item label="处理人" prop="operator">
          <el-input v-model="handleForm.operator" placeholder="请输入处理人姓名" clearable />
        </el-form-item>
        <el-form-item label="处理动作" prop="action">
          <el-input v-model="handleForm.action" placeholder="如：处理反馈、审核结案" clearable />
        </el-form-item>
        <el-form-item label="结果状态" prop="status">
          <el-select v-model="handleForm.status" class="w-full">
            <el-option v-for="item in CLOSE_STATUS_OPTIONS" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="处理说明" prop="remark">
          <el-input
            v-model="handleForm.remark"
            type="textarea"
            :rows="3"
            placeholder="请输入现场处置情况与结果"
            maxlength="300"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleVisible = false">取消</el-button>
        <el-button type="primary" :loading="handleSubmitting" @click="submitHandle">提交处理</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.rv-event-detail__title {
  margin: 20px 0 14px;
  font-size: 15px;
  font-weight: 600;
  color: var(--rv-text);
}

.rv-event-detail__action {
  display: flex;
  align-items: center;
  gap: 8px;
}

.rv-event-detail__operator {
  font-size: 14px;
  font-weight: 600;
  color: var(--rv-text);
}

.rv-event-detail__remark {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--rv-text-secondary);
}
</style>
