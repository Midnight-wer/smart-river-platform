<script setup lang="ts">
/**
 * 河道详情
 * 展示河道基础信息、关联事件、关联巡查记录与水质历史趋势。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import * as echarts from '@/utils/echarts'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import EChart from '@/components/EChart.vue'
import { fetchRiverDetail, type RiverDetail } from '@/api/river'
import { defaultText, formatDateTime, toNumber, toPercent } from '@/utils/format'

interface RelatedEvent {
  id: string
  title: string
  type: string
  status: string
  level: string
  reporter: string
  handler: string
  occurAt: string
  description: string
}

interface RelatedPatrol {
  id: string
  title: string
  type: string
  status: string
  duration: number
  distance: number
  foundIssues: number
  assignee: string
  deadline: string
}

const route = useRoute()
const router = useRouter()

const id = route.params.id as string

const loading = ref(false)
const detail = ref<RiverDetail | null>(null)

/** 关联事件列表 */
const events = computed<RelatedEvent[]>(() => (detail.value?.events ?? []) as RelatedEvent[])
/** 关联巡查记录 */
const patrols = computed<RelatedPatrol[]>(() => (detail.value?.patrols ?? []) as RelatedPatrol[])

/** 水质历史趋势折线图 */
const trendOption = computed<echarts.EChartsOption>(() => {
  const history = detail.value?.history ?? []
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['pH 值', '溶解氧', '化学需氧量', '氨氮'], bottom: 0 },
    grid: { left: 50, right: 56, top: 40, bottom: 48 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: history.map((item) => item.date),
    },
    yAxis: [
      {
        type: 'value',
        name: 'pH / 溶解氧',
        splitLine: { lineStyle: { type: 'dashed' } },
      },
      {
        type: 'value',
        name: 'COD / 氨氮',
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: 'pH 值',
        type: 'line',
        smooth: true,
        yAxisIndex: 0,
        data: history.map((item) => item.ph),
      },
      {
        name: '溶解氧',
        type: 'line',
        smooth: true,
        yAxisIndex: 0,
        data: history.map((item) => item.do),
      },
      {
        name: '化学需氧量',
        type: 'line',
        smooth: true,
        yAxisIndex: 1,
        data: history.map((item) => item.cod),
      },
      {
        name: '氨氮',
        type: 'line',
        smooth: true,
        yAxisIndex: 1,
        data: history.map((item) => item.nh3n),
      },
    ],
  }
})

/** 加载河道详情 */
async function load(): Promise<void> {
  loading.value = true
  try {
    detail.value = await fetchRiverDetail(id)
  } catch (error) {
    console.error('[河道详情] 加载失败', error)
    ElMessage.error('河道详情加载失败')
  } finally {
    loading.value = false
  }
}

/** 返回河道列表 */
function goBack(): void {
  router.push('/river')
}

onMounted(() => {
  load()
})
</script>

<template>
  <div class="rv-page">
    <PageHeader
      :title="detail ? `${detail.name} · 河道详情` : '河道详情'"
      description="查看河道基础档案、关联事件与巡查记录"
    >
      <template #extra>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
        <el-button type="primary" :icon="ArrowLeft" @click="goBack">返回列表</el-button>
      </template>
    </PageHeader>

    <el-empty v-if="!loading && !detail" description="未获取到河道信息">
      <el-button type="primary" @click="goBack">返回列表</el-button>
    </el-empty>

    <template v-else>
      <!-- 基础信息 -->
      <div class="rv-card mb-4" v-loading="loading">
        <div class="rv-card-header">
          <span class="rv-card-title">基础信息</span>
        </div>
        <div class="rv-card-body">
          <el-descriptions v-if="detail" :column="3" border>
            <el-descriptions-item label="河道名称">{{ detail.name }}</el-descriptions-item>
            <el-descriptions-item label="河道编码">{{ defaultText(detail.code) }}</el-descriptions-item>
            <el-descriptions-item label="河道等级">
              <el-tag effect="plain">{{ detail.level }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="河道长度">{{ toNumber(detail.length) }} km</el-descriptions-item>
            <el-descriptions-item label="所属流域">{{ defaultText(detail.basin) }}</el-descriptions-item>
            <el-descriptions-item label="所属区域">{{ defaultText(detail.region) }}</el-descriptions-item>
            <el-descriptions-item label="起点">{{ defaultText(detail.startPoint) }}</el-descriptions-item>
            <el-descriptions-item label="终点">{{ defaultText(detail.endPoint) }}</el-descriptions-item>
            <el-descriptions-item label="河长">{{ defaultText(detail.chiefName) }}</el-descriptions-item>
            <el-descriptions-item label="水质目标">{{ defaultText(detail.qualityTarget) }}</el-descriptions-item>
            <el-descriptions-item label="水质达标率">
              {{ toPercent(detail.qualityRate) }}
            </el-descriptions-item>
            <el-descriptions-item label="巡查次数">{{ toNumber(detail.patrolCount) }}</el-descriptions-item>
            <el-descriptions-item label="关联事件">{{ toNumber(detail.eventCount) }}</el-descriptions-item>
            <el-descriptions-item label="档案状态">
              <StatusTag :status="detail.status" />
            </el-descriptions-item>
            <el-descriptions-item label="更新时间" :span="3">
              {{ formatDateTime(detail.updatedAt) }}
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </div>

      <!-- 水质历史趋势 -->
      <div class="rv-card mb-4">
        <div class="rv-card-header">
          <span class="rv-card-title">水质历史趋势</span>
        </div>
        <div class="rv-card-body">
          <EChart :option="trendOption" height="320px" :loading="loading" />
        </div>
      </div>

      <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <!-- 关联事件 -->
        <div class="rv-card">
          <div class="rv-card-header">
            <span class="rv-card-title">关联事件</span>
            <span class="rv-text-secondary">共 {{ events.length }} 条</span>
          </div>
          <div class="rv-card-body">
            <el-table :data="events" border stripe max-height="380">
              <el-table-column prop="title" label="事件标题" min-width="180" show-overflow-tooltip />
              <el-table-column prop="type" label="类型" width="110" align="center" />
              <el-table-column label="状态" width="90" align="center">
                <template #default="{ row }">
                  <StatusTag :status="row.status" />
                </template>
              </el-table-column>
              <el-table-column prop="occurAt" label="发生时间" width="160">
                <template #default="{ row }">{{ formatDateTime(row.occurAt) }}</template>
              </el-table-column>
            </el-table>
            <el-empty v-if="!events.length" description="暂无关联事件" :image-size="80" />
          </div>
        </div>

        <!-- 关联巡查记录 -->
        <div class="rv-card">
          <div class="rv-card-header">
            <span class="rv-card-title">关联巡查记录</span>
            <span class="rv-text-secondary">共 {{ patrols.length }} 条</span>
          </div>
          <div class="rv-card-body">
            <el-table :data="patrols" border stripe max-height="380">
              <el-table-column prop="title" label="巡查任务" min-width="180" show-overflow-tooltip />
              <el-table-column prop="type" label="类型" width="110" align="center" />
              <el-table-column label="状态" width="90" align="center">
                <template #default="{ row }">
                  <StatusTag :status="row.status" />
                </template>
              </el-table-column>
              <el-table-column prop="deadline" label="截止时间" width="160">
                <template #default="{ row }">{{ formatDateTime(row.deadline) }}</template>
              </el-table-column>
            </el-table>
            <el-empty v-if="!patrols.length" description="暂无巡查记录" :image-size="80" />
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
