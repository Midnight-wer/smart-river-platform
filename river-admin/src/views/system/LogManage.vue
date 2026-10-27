<script setup lang="ts">
/**
 * 操作日志：记录系统内的关键操作行为并支持检索
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { CircleCheck, Histogram, Refresh, Search, Timer } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useTable } from '@/composables/useTable'
import { fetchLogs } from '@/api/system'
import { formatDateTime, toFixed } from '@/utils/format'
import type { OperationLog } from '@/types'

const LOG_STATUS_OPTIONS: OperationLog['status'][] = ['成功', '失败']

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
} = useTable(fetchLogs, { status: '' })

/** 全量日志，用于统计 */
const allLogs = ref<OperationLog[]>([])

/** 加载全量日志用于统计卡片 */
async function loadAllLogs(): Promise<void> {
  try {
    const result = await fetchLogs({ page: 1, pageSize: 500 })
    allLogs.value = result?.list ?? []
  } catch (error) {
    console.error('[操作日志] 日志统计加载失败', error)
    ElMessage.error('日志统计加载失败')
    allLogs.value = []
  }
}

/** 成功数量 */
const successCount = computed(() => allLogs.value.filter((item) => item.status === '成功').length)

/** 失败数量 */
const failCount = computed(() => allLogs.value.filter((item) => item.status === '失败').length)

/** 平均耗时 */
const avgDuration = computed(() => {
  if (!allLogs.value.length) return 0
  const sum = allLogs.value.reduce((acc, item) => acc + (item.duration || 0), 0)
  return Number(toFixed(sum / allLogs.value.length, 0))
})

/** 平均耗时格式化 */
const avgDurationText = computed(() => (avgDuration.value ? `${avgDuration.value} ms` : '-'))

onMounted(() => {
  load()
  loadAllLogs()
})
</script>

<template>
  <div class="rv-page">
    <PageHeader title="操作日志" description="记录系统关键操作行为，支持按关键字与执行结果检索">
      <template #extra>
        <el-button :icon="Refresh" @click="refresh">刷新</el-button>
      </template>
    </PageHeader>

    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4 mb-4">
      <StatCard label="日志总数" :value="allLogs.length" suffix="条" color="blue" :icon="Histogram" />
      <StatCard label="成功操作" :value="successCount" suffix="条" color="green" :icon="CircleCheck" />
      <StatCard label="失败操作" :value="failCount" suffix="条" color="red" />
      <StatCard label="平均耗时" :value="avgDurationText" color="orange" :icon="Timer" />
    </div>

    <div class="rv-card">
      <div class="rv-card-header">
        <span class="rv-card-title">日志列表</span>
        <div class="flex items-center gap-2">
          <el-input
            v-model="query.keyword"
            placeholder="操作人 / 模块 / 操作"
            clearable
            class="!w-56"
            @keyup.enter="search"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-select v-model="query.status" placeholder="执行结果" clearable class="!w-32">
            <el-option v-for="item in LOG_STATUS_OPTIONS" :key="item" :label="item" :value="item" />
          </el-select>
          <el-button type="primary" @click="search">查询</el-button>
          <el-button @click="reset">重置</el-button>
        </div>
      </div>

      <div class="rv-card-body">
        <el-table v-loading="loading" :data="list" size="small" border>
          <el-table-column prop="operator" label="操作人" min-width="120" show-overflow-tooltip />
          <el-table-column prop="module" label="模块" min-width="130" show-overflow-tooltip />
          <el-table-column prop="action" label="操作" min-width="110" show-overflow-tooltip />
          <el-table-column prop="ip" label="IP 地址" min-width="140" show-overflow-tooltip />
          <el-table-column label="耗时" width="110" align="right">
            <template #default="{ row }">
              <span class="rv-num">{{ row.duration }}</span>
              <span class="rv-text-secondary"> ms</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="92">
            <template #default="{ row }">
              <StatusTag :status="row.status" />
            </template>
          </el-table-column>
          <el-table-column label="发生时间" min-width="150">
            <template #default="{ row }">
              {{ formatDateTime(row.createdAt) }}
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="暂无操作日志" :image-size="70" />
          </template>
        </el-table>

        <el-pagination
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          :page-size="query.pageSize"
          :current-page="query.page"
          :page-sizes="[10, 20, 50, 100]"
          @size-change="changePageSize"
          @current-change="changePage"
        />
      </div>
    </div>
  </div>
</template>
