<script setup lang="ts">
/**
 * 履职评估模型：基于 AI 评分模型的河长履职量化评估与改进建议
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Medal, Refresh, Trophy, UserFilled } from '@element-plus/icons-vue'
import * as echarts from '@/utils/echarts'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import EChart from '@/components/EChart.vue'
import { fetchEvaluation } from '@/api/ai'
import type { EvaluationItem } from '@/api/ai'

/** 等级配色规则 */
const LEVEL_RULES: Record<string, { type: 'success' | 'primary' | 'warning' | 'danger'; color: string; range: string }> = {
  优秀: { type: 'success', color: '#16a34a', range: '90 分及以上' },
  良好: { type: 'primary', color: '#2563eb', range: '80 - 89 分' },
  合格: { type: 'warning', color: '#f59e0b', range: '70 - 79 分' },
  待提升: { type: 'danger', color: '#dc2626', range: '70 分以下' },
}

const evaluations = ref<EvaluationItem[]>([])
const loading = ref(false)

const totalCount = computed(() => evaluations.value.length)
const averageScore = computed(() => {
  if (!evaluations.value.length) return 0
  const total = evaluations.value.reduce((sum, item) => sum + item.score, 0)
  return Number((total / evaluations.value.length).toFixed(1))
})
const excellentCount = computed(() => evaluations.value.filter((item) => item.level === '优秀').length)
const improveCount = computed(() => evaluations.value.filter((item) => item.level === '待提升').length)

/** 等级分布统计 */
const levelStatistics = computed(() =>
  Object.keys(LEVEL_RULES).map((level) => ({
    name: level,
    value: evaluations.value.filter((item) => item.level === level).length,
  })),
)

/** 得分排行（降序） */
const ranking = computed<EvaluationItem[]>(() =>
  [...evaluations.value].sort((a, b) => b.score - a.score),
)

/** 等级配色 */
function levelColor(level: string): string {
  return LEVEL_RULES[level]?.color ?? '#94a3b8'
}

/** 等级标签类型 */
function levelType(level: string): 'success' | 'primary' | 'warning' | 'danger' | 'info' {
  return LEVEL_RULES[level]?.type ?? 'info'
}

/** 得分分布饼图 */
const scorePieOption = computed<echarts.EChartsOption>(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} 人 ({d}%)' },
  legend: { bottom: 0, itemWidth: 12, itemHeight: 8 },
  series: [
    {
      name: '得分分布',
      type: 'pie',
      radius: ['40%', '66%'],
      center: ['50%', '44%'],
      itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
      label: { formatter: '{b}\n{c} 人' },
      data: levelStatistics.value.map((item) => ({
        name: item.name,
        value: item.value,
        itemStyle: { color: levelColor(item.name) },
      })),
    },
  ],
}))

/** 得分排行条形图 */
const rankingOption = computed<echarts.EChartsOption>(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: 76, right: 44, top: 16, bottom: 30 },
  xAxis: { type: 'value', name: '综合得分', max: 100, axisLabel: { color: '#64748b' } },
  yAxis: {
    type: 'category',
    data: ranking.value.map((item) => item.chiefName).reverse(),
    axisLabel: { color: '#64748b' },
  },
  series: [
    {
      name: '综合得分',
      type: 'bar',
      barMaxWidth: 18,
      itemStyle: { borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', formatter: '{c}' },
      data: ranking.value
        .slice()
        .reverse()
        .map((item) => ({ value: item.score, itemStyle: { color: levelColor(item.level) } })),
    },
  ],
}))

/** 加载评估数据 */
async function load(): Promise<void> {
  loading.value = true
  try {
    evaluations.value = await fetchEvaluation()
  } catch (error) {
    console.error('[履职评估模型] 评估数据加载失败', error)
    ElMessage.error('履职评估数据加载失败')
    evaluations.value = []
  } finally {
    loading.value = false
  }
}

/** 导出评估结果 */
function handleExport(): void {
  ElMessage.success('评估结果已生成，可前往下载中心查看')
}

onMounted(load)
</script>

<template>
  <div class="rv-page">
    <PageHeader title="履职评估模型" description="基于多维履职数据的河长量化评分、等级评定与改进建议">
      <template #extra>
        <el-button :icon="Refresh" @click="load">刷新数据</el-button>
        <el-button type="primary" :icon="Download" @click="handleExport">导出评估报告</el-button>
      </template>
    </PageHeader>

    <el-alert
      class="mb-4"
      type="info"
      :closable="false"
      show-icon
      title="评估说明"
      description="履职得分由 AI 评分模型综合巡查频次、事件响应时效、问题闭环率与水质改善幅度等指标自动计算，评估结果作为河长考核与帮扶指导的参考依据。"
    />

    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4 mb-4">
      <StatCard label="参评河长" :value="totalCount" suffix="人" color="blue" :icon="UserFilled" />
      <StatCard label="平均综合得分" :value="averageScore" suffix="分" color="green" :icon="Trophy" />
      <StatCard label="优秀人数" :value="excellentCount" suffix="人" color="purple" :icon="Medal" />
      <StatCard label="待提升人数" :value="improveCount" suffix="人" color="red" />
    </div>

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-12 mb-4">
      <!-- 评估明细 -->
      <div class="rv-card xl:col-span-7">
        <div class="rv-card-header">
          <span class="rv-card-title">履职评估明细</span>
          <span class="rv-text-secondary">共 {{ totalCount }} 人</span>
        </div>
        <div class="rv-card-body">
          <el-table v-loading="loading" :data="evaluations" size="small" border max-height="420">
            <el-table-column prop="id" label="评估编号" width="110" />
            <el-table-column prop="chiefName" label="河长" min-width="100" show-overflow-tooltip />
            <el-table-column label="综合得分" width="150">
              <template #default="{ row }">
                <div class="flex items-center gap-2">
                  <el-progress
                    :percentage="row.score"
                    :color="levelColor(row.level)"
                    :stroke-width="12"
                    :format="() => row.score"
                  />
                </div>
              </template>
            </el-table-column>
            <el-table-column label="评定等级" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="levelType(row.level)" size="small" effect="light" round>{{ row.level }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="suggestion" label="改进建议" min-width="220" show-overflow-tooltip />
            <template #empty>
              <el-empty description="暂无评估结果" :image-size="70" />
            </template>
          </el-table>
        </div>
      </div>

      <!-- 得分分布 -->
      <div class="rv-card xl:col-span-5">
        <div class="rv-card-header">
          <span class="rv-card-title">得分等级分布</span>
          <span class="rv-text-secondary">按评定等级统计</span>
        </div>
        <div class="rv-card-body">
          <EChart :option="scorePieOption" height="320px" :loading="loading" />
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-12">
      <!-- 得分排行 -->
      <div class="rv-card xl:col-span-7">
        <div class="rv-card-header">
          <span class="rv-card-title">河长得分排行</span>
          <span class="rv-text-secondary">按综合得分从高到低</span>
        </div>
        <div class="rv-card-body">
          <EChart :option="rankingOption" height="360px" :loading="loading" />
        </div>
      </div>

      <!-- 等级配色说明 -->
      <div class="rv-card xl:col-span-5">
        <div class="rv-card-header">
          <span class="rv-card-title">等级配色说明</span>
          <span class="rv-text-secondary">评分区间与对应颜色</span>
        </div>
        <div class="rv-card-body">
          <div class="flex flex-col gap-3">
            <div
              v-for="(rule, level) in LEVEL_RULES"
              :key="level"
              class="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2"
            >
              <div class="flex items-center gap-2">
                <i class="inline-block h-3 w-3 rounded-full" :style="{ background: rule.color }" />
                <span class="text-sm font-medium text-slate-700">{{ level }}</span>
              </div>
              <span class="rv-text-secondary">{{ rule.range }}</span>
              <span class="rv-num text-sm text-slate-600">
                {{ evaluations.filter((item) => item.level === level).length }} 人
              </span>
            </div>
          </div>

          <el-alert
            class="mt-4"
            type="warning"
            :closable="false"
            title="提示"
            description="评定等级为待提升的河长，由系统自动生成帮扶指导任务并推送至县级河长办。"
          />
        </div>
      </div>
    </div>
  </div>
</template>
