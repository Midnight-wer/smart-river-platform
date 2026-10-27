<script setup lang="ts">
/**
 * 巡查管理
 * 展示巡查任务统计与任务明细，支持新建、编辑、删除与状态流转。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Delete, Edit, Plus, Refresh, Search, Switch } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useTable } from '@/composables/useTable'
import { createPatrol, deletePatrol, fetchPatrols, updatePatrol } from '@/api/patrol'
import { defaultText, formatDateTime, toDistance, toNumber } from '@/utils/format'
import type { AdminLevel, PageQuery, PatrolTask } from '@/types'

interface PatrolQuery extends PageQuery {
  status: string
  type: string
}

interface PatrolForm {
  id: string
  title: string
  riverName: string
  chiefName: string
  level: AdminLevel
  type: PatrolTask['type']
  deadline: string
  assignee: string
}

const STATUS_OPTIONS: PatrolTask['status'][] = ['待执行', '进行中', '已完成', '已逾期']
const TYPE_OPTIONS: PatrolTask['type'][] = ['日常巡查', '专项巡查', '整改复查', '汛期排查']
const LEVEL_OPTIONS: Array<{ label: string; value: AdminLevel }> = [
  { label: '省级河长', value: 'province' },
  { label: '市级河长', value: 'city' },
  { label: '县级河长', value: 'county' },
  { label: '乡镇级河长', value: 'town' },
]

/** 可流转的目标状态 */
const FLOW_STATUS: PatrolTask['status'][] = ['进行中', '已完成']

const {
  loading,
  list,
  total,
  query: baseQuery,
  load,
  search,
  reset,
  changePage,
  changePageSize,
  refresh,
} = useTable<PatrolTask>(fetchPatrols, { status: '', type: '' })

const query = baseQuery as PatrolQuery

/** 统计用的全量任务列表（当前筛选条件下的全部任务） */
const statList = ref<PatrolTask[]>([])

/** 加载统计数据 */
async function loadStats(): Promise<void> {
  try {
    const result = await fetchPatrols({
      page: 1,
      pageSize: 500,
      keyword: query.keyword,
      status: query.status,
      type: query.type,
    })
    statList.value = result?.list ?? []
  } catch (error) {
    console.error('[巡查管理] 统计数据加载失败', error)
  }
}

/** 任务状态统计 */
const stats = computed(() => {
  const count = (status: PatrolTask['status']) =>
    statList.value.filter((item) => item.status === status).length
  return {
    total: statList.value.length,
    done: count('已完成'),
    doing: count('进行中'),
    overdue: count('已逾期'),
  }
})

const dialogVisible = ref(false)
const dialogTitle = ref('新建巡查任务')
const submitting = ref(false)
const formRef = ref<FormInstance>()

const form = reactive<PatrolForm>({
  id: '',
  title: '',
  riverName: '',
  chiefName: '',
  level: 'county',
  type: '日常巡查',
  deadline: '',
  assignee: '',
})

const rules: FormRules = {
  title: [{ required: true, message: '请输入任务标题', trigger: 'blur' }],
  riverName: [{ required: true, message: '请输入河道名称', trigger: 'blur' }],
  chiefName: [{ required: true, message: '请输入河长姓名', trigger: 'blur' }],
  type: [{ required: true, message: '请选择巡查类型', trigger: 'change' }],
  deadline: [{ required: true, message: '请选择截止时间', trigger: 'change' }],
  assignee: [{ required: true, message: '请输入执行人', trigger: 'blur' }],
}

/** 打开弹窗：传入行数据则为编辑 */
function openDialog(row?: PatrolTask): void {
  if (row) {
    dialogTitle.value = '编辑巡查任务'
    Object.assign(form, {
      id: row.id,
      title: row.title,
      riverName: row.riverName,
      chiefName: row.chiefName,
      level: row.level,
      type: row.type,
      deadline: row.deadline,
      assignee: row.assignee,
    })
  } else {
    dialogTitle.value = '新建巡查任务'
    Object.assign(form, {
      id: '',
      title: '',
      riverName: '',
      chiefName: '',
      level: 'county',
      type: '日常巡查',
      deadline: '',
      assignee: '',
    })
  }
  dialogVisible.value = true
}

/** 提交新建或编辑 */
async function handleSubmit(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (form.id) {
      await updatePatrol(form.id, { ...form })
      ElMessage.success('巡查任务更新成功')
    } else {
      await createPatrol({ ...form })
      ElMessage.success('巡查任务创建成功')
    }
    dialogVisible.value = false
    await refresh()
  } catch (error) {
    console.error('[巡查管理] 保存失败', error)
    ElMessage.error('保存失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

/** 删除巡查任务 */
async function handleDelete(row: PatrolTask): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除巡查任务「${row.title}」吗？删除后不可恢复。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deletePatrol(row.id)
    ElMessage.success('巡查任务已删除')
    await refresh()
    await loadStats()
  } catch (error) {
    console.error('[巡查管理] 删除失败', error)
    ElMessage.error('删除失败，请稍后重试')
  }
}

/** 状态流转 */
async function handleStatusChange(row: PatrolTask, status: PatrolTask['status']): Promise<void> {
  if (row.status === status) return
  try {
    await updatePatrol(row.id, { status })
    ElMessage.success(`任务状态已更新为「${status}」`)
    await refresh()
    await loadStats()
  } catch (error) {
    console.error('[巡查管理] 状态流转失败', error)
    ElMessage.error('状态更新失败，请稍后重试')
  }
}

/** 条件查询：列表与统计同步刷新 */
async function handleSearch(): Promise<void> {
  await search()
  await loadStats()
}

/** 重置条件：列表与统计同步刷新 */
async function handleReset(): Promise<void> {
  await reset()
  await loadStats()
}

onMounted(() => {
  load()
  loadStats()
})
</script>

<template>
  <div class="rv-page">
    <PageHeader title="巡查管理" description="统筹巡查任务派发、执行跟踪与结果核查">
      <template #extra>
        <el-button type="primary" :icon="Plus" @click="openDialog()">新建任务</el-button>
      </template>
    </PageHeader>

    <!-- 统计条 -->
    <div class="mb-4 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
      <StatCard label="任务总数" :value="toNumber(stats.total)" suffix="条" color="blue" />
      <StatCard label="已完成" :value="toNumber(stats.done)" suffix="条" color="green" />
      <StatCard label="进行中" :value="toNumber(stats.doing)" suffix="条" color="cyan" />
      <StatCard label="已逾期" :value="toNumber(stats.overdue)" suffix="条" color="red" />
    </div>

    <!-- 搜索条件 -->
    <div class="rv-card mb-4">
      <div class="rv-card-body">
        <div class="flex flex-wrap items-center gap-3">
          <el-input
            v-model="query.keyword"
            class="!w-64"
            placeholder="任务标题 / 河道 / 河长"
            clearable
            :prefix-icon="Search"
            @keyup.enter="search()"
          />
          <el-select v-model="query.status" class="!w-36" placeholder="任务状态" clearable>
            <el-option v-for="item in STATUS_OPTIONS" :key="item" :label="item" :value="item" />
          </el-select>
          <el-select v-model="query.type" class="!w-36" placeholder="巡查类型" clearable>
            <el-option v-for="item in TYPE_OPTIONS" :key="item" :label="item" :value="item" />
          </el-select>
          <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </div>
      </div>
    </div>

    <!-- 巡查任务列表 -->
    <div class="rv-card">
      <div class="rv-card-header">
        <span class="rv-card-title">巡查任务</span>
        <span class="rv-text-secondary">共 {{ toNumber(total) }} 条</span>
      </div>
      <div class="rv-card-body">
        <el-table v-loading="loading" :data="list" border stripe>
          <el-table-column prop="title" label="任务标题" min-width="180" show-overflow-tooltip />
          <el-table-column prop="riverName" label="河道" min-width="120" show-overflow-tooltip />
          <el-table-column prop="chiefName" label="河长" width="100">
            <template #default="{ row }">{{ defaultText(row.chiefName) }}</template>
          </el-table-column>
          <el-table-column prop="type" label="类型" width="110" align="center">
            <template #default="{ row }">
              <el-tag effect="plain">{{ row.type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <StatusTag :status="row.status" />
            </template>
          </el-table-column>
          <el-table-column prop="duration" label="时长(min)" width="100" align="right">
            <template #default="{ row }">{{ toNumber(row.duration) }}</template>
          </el-table-column>
          <el-table-column label="里程" width="100" align="right">
            <template #default="{ row }">{{ toDistance(row.distance) }}</template>
          </el-table-column>
          <el-table-column prop="foundIssues" label="发现问题数" width="110" align="right">
            <template #default="{ row }">{{ toNumber(row.foundIssues) }}</template>
          </el-table-column>
          <el-table-column prop="deadline" label="截止时间" width="160">
            <template #default="{ row }">{{ formatDateTime(row.deadline) }}</template>
          </el-table-column>
          <el-table-column prop="createdAt" label="创建时间" width="160">
            <template #default="{ row }">{{ formatDateTime(row.createdAt) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="240" fixed="right" align="center">
            <template #default="{ row }">
              <el-dropdown
                v-if="row.status !== '已完成'"
                trigger="click"
                @command="(command: PatrolTask['status']) => handleStatusChange(row, command)"
              >
                <el-button link type="primary" :icon="Switch">状态流转</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item
                      v-for="item in FLOW_STATUS"
                      :key="item"
                      :command="item"
                      :disabled="item === row.status"
                    >
                      标记为{{ item }}
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <el-button link type="primary" :icon="Edit" @click="openDialog(row)">编辑</el-button>
              <el-button link type="danger" :icon="Delete" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          :current-page="query.page"
          :page-size="query.pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="changePage"
          @size-change="changePageSize"
        />
      </div>
    </div>

    <!-- 新建 / 编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="640px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
        <el-form-item label="任务标题" prop="title">
          <el-input v-model="form.title" placeholder="请输入任务标题" />
        </el-form-item>
        <el-form-item label="河道名称" prop="riverName">
          <el-input v-model="form.riverName" placeholder="请输入河道名称" />
        </el-form-item>
        <el-form-item label="河长姓名" prop="chiefName">
          <el-input v-model="form.chiefName" placeholder="请输入河长姓名" />
        </el-form-item>
        <el-form-item label="行政层级" prop="level">
          <el-select v-model="form.level" placeholder="请选择行政层级" class="w-full">
            <el-option
              v-for="item in LEVEL_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="巡查类型" prop="type">
          <el-select v-model="form.type" placeholder="请选择巡查类型" class="w-full">
            <el-option v-for="item in TYPE_OPTIONS" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="截止时间" prop="deadline">
          <el-date-picker
            v-model="form.deadline"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm"
            placeholder="请选择截止时间"
            class="!w-full"
          />
        </el-form-item>
        <el-form-item label="执行人" prop="assignee">
          <el-input v-model="form.assignee" placeholder="请输入执行人" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
