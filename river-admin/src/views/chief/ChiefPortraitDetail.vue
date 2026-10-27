<script setup lang="ts">
/**
 * 河长画像详情
 * 展示指定河长的履职指标、履职趋势、巡查记录与处理事件。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Medal, Refresh, Share, TrendCharts, UserFilled } from '@element-plus/icons-vue'
import * as echarts from '@/utils/echarts'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import EChart from '@/components/EChart.vue'
import { fetchChiefPortrait, type ChiefPortrait } from '@/api/chief'
import { defaultText, formatDateTime, toDistance, toNumber, toPercent } from '@/utils/format'

interface PortraitEvent {
  id: string
  title: string
  type: string
  status: string
  level: string
  riverName: string
  handler: string
  occurAt: string
  description: string
}

interface PortraitPatrol {
  id: string
  title: string
  riverName: string
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
const portrait = ref<ChiefPortrait | null>(null)

/** 关联巡查记录 */
const patrolRecords = computed<PortraitPatrol[]>(
  () => (portrait.value?.patrolRecords ?? []) as PortraitPatrol[],
)
/** 关联处理事件 */
const events = computed<PortraitEvent[]>(() => (portrait.value?.events ?? []) as PortraitEvent[])

/** 履职趋势折线图 */
const trendOption = computed<echarts.EChartsOption>(() => {
  const trend = portrait.value?.trend
  const quality = trend?.qualityRate ?? []
  const resolve = trend?.resolveRate ?? []
  const patrol = trend?.patrolRate ?? []
  const dates = quality.length ? quality.map((item) => item.date) : []
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['水质达标率', '问题处理率', '巡查完成率'], bottom: 0 },
    grid: { left: 50, right: 24, top: 40, bottom: 48 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates,
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: { formatter: '{value}%' },
      splitLine: { lineStyle: { type: 'dashed' } },
    },
    series: [
      {
        name: '水质达标率',
        type: 'line',
        smooth: true,
        data: quality.map((item) => item.value),
      },
      {
        name: '问题处理率',
        type: 'line',
        smooth: true,
        data: resolve.map((item) => item.value),
      },
      {
        name: '巡查完成率',
        type: 'line',
        smooth: true,
        data: patrol.map((item) => item.value),
      },
    ],
  }
})

/** 加载河长画像 */
async function load(): Promise<void> {
  loading.value = true
  try {
    portrait.value = await fetchChiefPortrait(id)
  } catch (error) {
    console.error('[河长画像] 加载失败', error)
    ElMessage.error('河长画像加载失败')
  } finally {
    loading.value = false
  }
}

/** 返回画像列表 */
function goBack(): void {
  router.push('/chief/portrait')
}

onMounted(() => {
  load()
})
</script>

<template>
  <div class="rv-page">
    <PageHeader
      :title="portrait ? `${portrait.name} · 履职画像` : '河长履职画像'"
      description="呈现河长履职指标、履职趋势与工作实绩"
    >
      <template #extra>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
        <el-button type="primary" :icon="ArrowLeft" @click="goBack">返回画像列表</el-button>
      </template>
    </PageHeader>

    <el-empty v-if="!loading && !portrait" description="未获取到河长画像信息">
      <el-button type="primary" @click="goBack">返回画像列表</el-button>
    </el-empty>

    <template v-else>
      <!-- 基本信息 -->
      <div class="rv-card mb-4" v-loading="loading">
        <div class="rv-card-header">
          <span class="rv-card-title">基本信息</span>
        </div>
        <div class="rv-card-body">
          <el-descriptions v-if="portrait" :column="4" border>
            <el-descriptions-item label="姓名">{{ defaultText(portrait.name) }}</el-descriptions-item>
            <el-descriptions-item label="联系电话">{{ defaultText(portrait.phone) }}</el-descriptions-item>
            <el-descriptions-item label="行政层级">
              <el-tag effect="plain">{{ defaultText(portrait.levelName) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="在岗状态">
              <StatusTag :status="portrait.status" />
            </el-descriptions-item>
            <el-descriptions-item label="职务" :span="2">
              {{ defaultText(portrait.post) }}
            </el-descriptions-item>
            <el-descriptions-item label="所属区域">{{ defaultText(portrait.region) }}</el-descriptions-item>
            <el-descriptions-item label="最后巡查时间">
              {{ formatDateTime(portrait.lastPatrolAt) }}
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </div>

      <!-- 指标卡 -->
      <div class="mb-4 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          label="综合得分"
          :value="portrait ? portrait.score : 0"
          suffix="分"
          :icon="Medal"
          color="purple"
        />
        <StatCard
          label="巡查完成率"
          :value="portrait ? toPercent(portrait.patrolRate) : '-'"
          :icon="UserFilled"
          color="blue"
        />
        <StatCard
          label="问题处理率"
          :value="portrait ? toPercent(portrait.resolveRate) : '-'"
          :icon="TrendCharts"
          color="green"
        />
        <StatCard
          label="管辖河道数"
          :value="portrait ? toNumber(portrait.riverCount) : 0"
          suffix="条"
          :icon="Share"
          color="cyan"
        />
      </div>

      <!-- 履职趋势 -->
      <div class="rv-card mb-4">
        <div class="rv-card-header">
          <span class="rv-card-title">履职趋势</span>
        </div>
        <div class="rv-card-body">
          <EChart :option="trendOption" height="320px" :loading="loading" />
        </div>
      </div>

      <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <!-- 巡查记录 -->
        <div class="rv-card">
          <div class="rv-card-header">
            <span class="rv-card-title">巡查记录</span>
            <span class="rv-text-secondary">共 {{ patrolRecords.length }} 条</span>
          </div>
          <div class="rv-card-body">
            <el-table :data="patrolRecords" border stripe max-height="400">
              <el-table-column prop="title" label="巡查任务" min-width="170" show-overflow-tooltip />
              <el-table-column prop="riverName" label="河道" min-width="110" show-overflow-tooltip />
              <el-table-column label="状态" width="90" align="center">
                <template #default="{ row }">
                  <StatusTag :status="row.status" />
                </template>
              </el-table-column>
              <el-table-column label="里程" width="100" align="right">
                <template #default="{ row }">{{ toDistance(row.distance) }}</template>
              </el-table-column>
              <el-table-column prop="foundIssues" label="问题数" width="90" align="right">
                <template #default="{ row }">{{ toNumber(row.foundIssues) }}</template>
              </el-table-column>
              <el-table-column prop="deadline" label="截止时间" width="160">
                <template #default="{ row }">{{ formatDateTime(row.deadline) }}</template>
              </el-table-column>
            </el-table>
            <el-empty v-if="!patrolRecords.length" description="暂无巡查记录" :image-size="80" />
          </div>
        </div>

        <!-- 处理事件 -->
        <div class="rv-card">
          <div class="rv-card-header">
            <span class="rv-card-title">处理事件</span>
            <span class="rv-text-secondary">共 {{ events.length }} 条</span>
          </div>
          <div class="rv-card-body">
            <el-timeline v-if="events.length">
              <el-timeline-item
                v-for="item in events"
                :key="item.id"
                :timestamp="formatDateTime(item.occurAt)"
                placement="top"
              >
                <div class="flex items-center gap-2">
                  <span class="font-medium">{{ defaultText(item.title) }}</span>
                  <StatusTag :status="item.status" />
                </div>
                <div class="rv-text-secondary mt-1">
                  {{ defaultText(item.type) }} · {{ defaultText(item.riverName) }} · 等级
                  {{ defaultText(item.level) }}
                </div>
                <div class="rv-text-secondary mt-1">{{ defaultText(item.description) }}</div>
              </el-timeline-item>
            </el-timeline>
            <el-empty v-else description="暂无处理事件" :image-size="80" />
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
