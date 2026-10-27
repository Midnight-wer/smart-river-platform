<script setup lang="ts">
/**
 * 公众服务：公众举报审核、受理办结与积分奖励发放
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { ChatDotRound, Coin, Search } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useTable } from '@/composables/useTable'
import { fetchReports, reviewReport } from '@/api/public'
import type { PublicReport } from '@/types'
import { formatDateTime } from '@/utils/format'

const STATUS_OPTIONS: PublicReport['status'][] = ['待审核', '已受理', '已办结', '已驳回']
const REWARD_OPTIONS = [10, 20, 50]

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
} = useTable(fetchReports, { status: '' })

const allReports = ref<PublicReport[]>([])

/** 审核弹窗 */
const reviewVisible = ref(false)
const reviewSubmitting = ref(false)
const reviewFormRef = ref<FormInstance>()
const reviewForm = reactive({
  id: '',
  title: '',
  status: '已受理' as PublicReport['status'],
  reward: 10,
})

const reviewRules: FormRules = {
  status: [{ required: true, message: '请选择审核结果', trigger: 'change' }],
}

/** 加载全量举报用于统计 */
async function loadAllReports(): Promise<void> {
  try {
    const result = await fetchReports({ page: 1, pageSize: 500 })
    allReports.value = result?.list ?? []
  } catch (error) {
    console.error('[公众服务] 举报统计加载失败', error)
    ElMessage.error('举报统计加载失败')
    allReports.value = []
  }
}

const pendingCount = computed(() => allReports.value.filter((item) => item.status === '待审核').length)
const doneCount = computed(() => allReports.value.filter((item) => item.status === '已办结').length)
const rewardTotal = computed(() => allReports.value.reduce((sum, item) => sum + (item.reward || 0), 0))

/** 打开审核弹窗 */
function openReview(row: PublicReport, presetStatus: PublicReport['status'] = '已受理'): void {
  reviewForm.id = row.id
  reviewForm.title = row.title
  reviewForm.status = presetStatus
  reviewForm.reward = presetStatus === '已办结' ? 20 : 10
  reviewVisible.value = true
}

/** 提交审核结果 */
async function submitReview(): Promise<void> {
  if (!reviewFormRef.value) return
  const valid = await reviewFormRef.value.validate().catch(() => false)
  if (!valid) return

  reviewSubmitting.value = true
  try {
    await reviewReport(reviewForm.id, {
      status: reviewForm.status,
      reward: reviewForm.status === '已办结' ? reviewForm.reward : 0,
    })
    ElMessage.success('审核完成')
    reviewVisible.value = false
    await Promise.all([load(), loadAllReports()])
  } catch (error) {
    console.error('[公众服务] 举报审核失败', error)
    ElMessage.error('举报审核失败')
  } finally {
    reviewSubmitting.value = false
  }
}

/** 直接受理 */
async function handleAccept(row: PublicReport): Promise<void> {
  try {
    await reviewReport(row.id, { status: '已受理' })
    ElMessage.success('已受理该举报')
    await Promise.all([load(), loadAllReports()])
  } catch (error) {
    console.error('[公众服务] 举报受理失败', error)
    ElMessage.error('举报受理失败')
  }
}

/** 直接办结并发放积分 */
async function handleFinish(row: PublicReport): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认将举报「${row.title}」办结并发放积分吗？`, '办结确认', {
      type: 'warning',
      confirmButtonText: '确认办结',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  try {
    await reviewReport(row.id, { status: '已办结', reward: 20 })
    ElMessage.success('举报已办结，积分已发放')
    await Promise.all([load(), loadAllReports()])
  } catch (error) {
    console.error('[公众服务] 举报办结失败', error)
    ElMessage.error('举报办结失败')
  }
}

/** 驳回举报 */
async function handleReject(row: PublicReport): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认驳回举报「${row.title}」吗？`, '驳回确认', {
      type: 'warning',
      confirmButtonText: '确认驳回',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  try {
    await reviewReport(row.id, { status: '已驳回' })
    ElMessage.success('举报已驳回')
    await Promise.all([load(), loadAllReports()])
  } catch (error) {
    console.error('[公众服务] 举报驳回失败', error)
    ElMessage.error('举报驳回失败')
  }
}

onMounted(() => {
  load()
  loadAllReports()
})
</script>

<template>
  <div class="rv-page">
    <PageHeader title="公众服务" description="公众举报受理、办结与积分奖励发放">
      <template #extra>
        <el-button :icon="Search" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </template>
    </PageHeader>

    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4 mb-4">
      <StatCard label="举报总数" :value="allReports.length" suffix="件" color="blue" :icon="ChatDotRound" />
      <StatCard label="待审核" :value="pendingCount" suffix="件" color="orange" />
      <StatCard label="已办结" :value="doneCount" suffix="件" color="green" />
      <StatCard label="积分发放总额" :value="rewardTotal" suffix="分" color="purple" :icon="Coin" />
    </div>

    <!-- 举报列表 -->
    <div class="rv-card">
      <div class="rv-card-header">
        <span class="rv-card-title">公众举报</span>
        <div class="flex items-center gap-2">
          <el-input
            v-model="query.keyword"
            placeholder="标题 / 河道 / 举报人"
            clearable
            class="!w-56"
            @keyup.enter="search"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-select v-model="query.status" placeholder="处理状态" clearable class="!w-32">
            <el-option v-for="item in STATUS_OPTIONS" :key="item" :label="item" :value="item" />
          </el-select>
          <el-button type="primary" @click="search">查询</el-button>
        </div>
      </div>
      <div class="rv-card-body">
        <el-table v-loading="loading" :data="list" size="small" border>
          <el-table-column prop="title" label="举报标题" min-width="180" show-overflow-tooltip />
          <el-table-column label="内容摘要" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.content }}
            </template>
          </el-table-column>
          <el-table-column prop="riverName" label="河道" min-width="110" show-overflow-tooltip />
          <el-table-column prop="region" label="区域" min-width="100" show-overflow-tooltip />
          <el-table-column prop="reporter" label="举报人" width="100" />
          <el-table-column prop="phone" label="联系电话" width="120" />
          <el-table-column label="状态" width="92">
            <template #default="{ row }">
              <StatusTag :status="row.status" />
            </template>
          </el-table-column>
          <el-table-column label="积分" width="80" align="right">
            <template #default="{ row }">
              <span class="rv-num">{{ row.reward || 0 }}</span>
            </template>
          </el-table-column>
          <el-table-column label="提交时间" min-width="140">
            <template #default="{ row }">
              {{ formatDateTime(row.submitAt) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openReview(row)">审核</el-button>
              <el-button link type="primary" @click="handleAccept(row)">受理</el-button>
              <el-button link type="success" @click="handleFinish(row)">办结</el-button>
              <el-button link type="danger" @click="handleReject(row)">驳回</el-button>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="暂无公众举报" :image-size="70" />
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

    <!-- 审核弹窗 -->
    <el-dialog v-model="reviewVisible" title="举报审核" width="480px">
      <el-form ref="reviewFormRef" :model="reviewForm" :rules="reviewRules" label-width="88px">
        <el-form-item label="举报标题">
          <span class="rv-text-secondary">{{ reviewForm.title }}</span>
        </el-form-item>
        <el-form-item label="审核结果" prop="status">
          <el-select v-model="reviewForm.status" class="w-full">
            <el-option v-for="item in STATUS_OPTIONS" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="奖励积分">
          <el-input-number v-model="reviewForm.reward" :min="0" :max="500" :step="10" />
          <div class="mt-2 flex items-center gap-2">
            <el-tag
              v-for="item in REWARD_OPTIONS"
              :key="item"
              size="small"
              effect="plain"
              class="cursor-pointer"
              @click="reviewForm.reward = item"
            >
              {{ item }} 分
            </el-tag>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reviewVisible = false">取消</el-button>
        <el-button type="primary" :loading="reviewSubmitting" @click="submitReview">提交审核</el-button>
      </template>
    </el-dialog>
  </div>
</template>
