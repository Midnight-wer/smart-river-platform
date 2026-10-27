<script setup lang="ts">
/**
 * 疑似污染源锁定：AI 溯源结果排序、污染源锁定与核查任务派发
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Bell, Lock, Location, Promotion, Refresh } from '@element-plus/icons-vue'
import * as echarts from '@/utils/echarts'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import EChart from '@/components/EChart.vue'
import { fetchSources } from '@/api/ai'
import type { SourceItem } from '@/api/ai'

const sources = ref<SourceItem[]>([])
const loading = ref(false)
const submitting = ref(false)

/** 风险值配色 */
function riskColor(risk: number): string {
  if (risk >= 80) return '#dc2626'
  if (risk >= 60) return '#f97316'
  return '#f59e0b'
}

const totalCount = computed(() => sources.value.length)
const highRiskCount = computed(() => sources.value.filter((item) => item.risk >= 80).length)
const lockedCount = computed(() => sources.value.filter((item) => item.status === '已锁定').length)
const averageDistance = computed(() => {
  if (!sources.value.length) return 0
  const total = sources.value.reduce((sum, item) => sum + item.distance, 0)
  return Math.round(total / sources.value.length)
})

/** 按风险降序排序的污染源 */
const sortedSources = computed<SourceItem[]>(() =>
  [...sources.value].sort((a, b) => b.risk - a.risk),
)

/** 风险排序条形图 */
const riskBarOption = computed<echarts.EChartsOption>(() => ({
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    formatter: (params: any) => {
      const item = sortedSources.value[params[0]?.dataIndex ?? 0]
      if (!item) return ''
      return `${item.id}｜${item.source}<br/>风险值：${item.risk}<br/>距离：${item.distance} m`
    },
  },
  grid: { left: 70, right: 40, top: 16, bottom: 30 },
  xAxis: { type: 'value', name: '风险值', max: 100, axisLabel: { color: '#64748b' } },
  yAxis: {
    type: 'category',
    data: sortedSources.value.map((item) => item.id).reverse(),
    axisLabel: { color: '#64748b' },
  },
  series: [
    {
      name: '风险值',
      type: 'bar',
      barMaxWidth: 18,
      itemStyle: { borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', formatter: '{c}' },
      data: sortedSources.value
        .slice()
        .reverse()
        .map((item) => ({
          value: item.risk,
          itemStyle: { color: riskColor(item.risk) },
        })),
    },
  ],
}))

/** 距离与风险关系散点图 */
const distanceOption = computed<echarts.EChartsOption>(() => ({
  tooltip: {
    trigger: 'item',
    formatter: (params: any) => {
      const item = sources.value[params.dataIndex]
      if (!item) return ''
      return `${item.id}｜${item.source}<br/>距离：${item.distance} m<br/>风险值：${item.risk}<br/>状态：${item.status}`
    },
  },
  grid: { left: 56, right: 30, top: 30, bottom: 44 },
  xAxis: {
    type: 'value',
    name: '距监测点距离(m)',
    axisLabel: { color: '#64748b' },
    nameTextStyle: { color: '#64748b' },
  },
  yAxis: { type: 'value', name: '风险值', max: 100, axisLabel: { color: '#64748b' } },
  series: [
    {
      name: '疑似污染源',
      type: 'scatter',
      symbolSize: (value: number[]) => 10 + value[1] / 10,
      itemStyle: { color: '#2563eb', opacity: 0.75 },
      emphasis: { itemStyle: { color: '#dc2626' } },
      data: sources.value.map((item) => [item.distance, item.risk, item.id]),
    },
  ],
}))

/** 锁定并派单 */
async function handleLock(row: SourceItem): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确认锁定疑似污染源「${row.id}（${row.source}）」并派发现场核查任务？`,
      '锁定并派单',
      { type: 'warning', confirmButtonText: '确认派单', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  submitting.value = true
  try {
    row.status = '已锁定'
    ElMessage.success(`污染源 ${row.id} 已锁定，核查任务已派发至属地河长`)
  } catch (error) {
    console.error('[疑似污染源锁定] 派单失败', error)
    ElMessage.error('派单失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

/** 批量锁定高风险污染源 */
async function handleBatchLock(): Promise<void> {
  const targets = sources.value.filter((item) => item.risk >= 80 && item.status !== '已锁定')
  if (!targets.length) {
    ElMessage.info('暂无需要锁定的高风险污染源')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认批量锁定 ${targets.length} 个高风险疑似污染源并派发核查任务？`,
      '批量锁定并派单',
      { type: 'warning', confirmButtonText: '确认派单', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  submitting.value = true
  try {
    targets.forEach((item) => {
      item.status = '已锁定'
    })
    ElMessage.success(`已锁定 ${targets.length} 个高风险污染源并完成派单`)
  } catch (error) {
    console.error('[疑似污染源锁定] 批量派单失败', error)
    ElMessage.error('批量派单失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

/** 加载污染源数据 */
async function load(): Promise<void> {
  loading.value = true
  try {
    sources.value = await fetchSources()
  } catch (error) {
    console.error('[疑似污染源锁定] 污染源数据加载失败', error)
    ElMessage.error('疑似污染源数据加载失败')
    sources.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="rv-page">
    <PageHeader title="疑似污染源锁定" description="AI 溯源疑似污染源风险排序、锁定与核查任务派发">
      <template #extra>
        <el-button :icon="Refresh" @click="load">刷新数据</el-button>
        <el-button type="danger" :icon="Promotion" :loading="submitting" @click="handleBatchLock">
          批量锁定高风险源
        </el-button>
      </template>
    </PageHeader>

    <el-alert
      class="mb-4"
      type="warning"
      :closable="false"
      show-icon
      title="处置说明"
      description="污染源由污染溯源模型结合水质突变、流向与排污特征推断得出，锁定后自动生成核查任务并推送至属地河长，最终认定需以现场核查结果为准。"
    />

    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4 mb-4">
      <StatCard label="疑似污染源" :value="totalCount" suffix="个" color="blue" :icon="Location" />
      <StatCard label="高风险污染源" :value="highRiskCount" suffix="个" color="red" />
      <StatCard label="已锁定" :value="lockedCount" suffix="个" color="purple" :icon="Lock" />
      <StatCard label="平均距离" :value="averageDistance" suffix="m" color="orange" />
    </div>

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-12 mb-4">
      <!-- 污染源列表 -->
      <div class="rv-card xl:col-span-7">
        <div class="rv-card-header">
          <span class="rv-card-title">疑似污染源清单</span>
          <span class="rv-text-secondary">按风险值降序</span>
        </div>
        <div class="rv-card-body">
          <el-table v-loading="loading" :data="sortedSources" size="small" border max-height="420">
            <el-table-column prop="id" label="源编号" width="100" />
            <el-table-column prop="source" label="来源类型" min-width="110" show-overflow-tooltip />
            <el-table-column label="风险值" width="90" align="right">
              <template #default="{ row }">
                <span class="rv-num" :class="row.risk >= 80 ? 'text-red-600' : ''">{{ row.risk }}</span>
              </template>
            </el-table-column>
            <el-table-column label="距离" width="100" align="right">
              <template #default="{ row }">
                <span class="rv-num">{{ row.distance }} m</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="96" align="center">
              <template #default="{ row }">
                <el-tag
                  :type="row.status === '已锁定' ? 'success' : 'warning'"
                  size="small"
                  effect="light"
                  round
                >
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" align="center" fixed="right">
              <template #default="{ row }">
                <el-button
                  size="small"
                  type="primary"
                  link
                  :icon="Promotion"
                  :loading="submitting"
                  @click="handleLock(row)"
                >
                  锁定并派单
                </el-button>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty description="暂无疑似污染源" :image-size="70" />
            </template>
          </el-table>
        </div>
      </div>

      <!-- 风险排序条形图 -->
      <div class="rv-card xl:col-span-5">
        <div class="rv-card-header">
          <span class="rv-card-title">污染源风险排序</span>
          <span class="rv-text-secondary">风险值从高到低</span>
        </div>
        <div class="rv-card-body">
          <EChart :option="riskBarOption" height="420px" :loading="loading" />
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-12">
      <!-- 距离散点图 -->
      <div class="rv-card xl:col-span-7">
        <div class="rv-card-header">
          <span class="rv-card-title">距离与风险分布</span>
          <span class="rv-text-secondary">圆点大小代表风险高低</span>
        </div>
        <div class="rv-card-body">
          <EChart :option="distanceOption" height="320px" :loading="loading" />
        </div>
      </div>

      <!-- 派单说明 -->
      <div class="rv-card xl:col-span-5">
        <div class="rv-card-header">
          <span class="rv-card-title">锁定派单规则</span>
          <span class="rv-text-secondary">处置策略</span>
        </div>
        <div class="rv-card-body">
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="高风险阈值">风险值 ≥ 80</el-descriptions-item>
            <el-descriptions-item label="处置时限">2 小时内响应</el-descriptions-item>
            <el-descriptions-item label="派单对象">属地河长 / 运维单位</el-descriptions-item>
            <el-descriptions-item label="当前已派单">{{ lockedCount }} 个</el-descriptions-item>
          </el-descriptions>

          <div class="mt-4 flex items-center gap-2">
            <el-button type="danger" :icon="Bell" :loading="submitting" @click="handleBatchLock">
              一键锁定高风险污染源
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
