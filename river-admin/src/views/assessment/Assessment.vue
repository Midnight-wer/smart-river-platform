<script setup lang="ts">
/**
 * 考核管理：考核指标权重、考核结果排名与分数分布
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Medal, Search, TrendCharts } from '@element-plus/icons-vue'
import * as echarts from '@/utils/echarts'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import EChart from '@/components/EChart.vue'
import { useTable } from '@/composables/useTable'
import { fetchAssessments, fetchIndicators } from '@/api/assessment'
import type { AssessmentIndicator } from '@/api/assessment'
import type { Assessment, AdminLevel } from '@/types'
import { toFixed, toPercent } from '@/utils/format'

const LEVEL_OPTIONS: { value: AdminLevel; label: string }[] = [
  { value: 'province', label: '省级河长' },
  { value: 'city', label: '市级河长' },
  { value: 'county', label: '县级河长' },
  { value: 'town', label: '乡镇级河长' },
]

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
} = useTable(fetchAssessments, { level: '' })

const indicators = ref<AssessmentIndicator[]>([])
const indicatorLoading = ref(false)
const allAssessments = ref<Assessment[]>([])

/** 加载考核指标权重 */
async function loadIndicators(): Promise<void> {
  indicatorLoading.value = true
  try {
    indicators.value = await fetchIndicators()
  } catch (error) {
    console.error('[考核管理] 考核指标加载失败', error)
    ElMessage.error('考核指标加载失败')
    indicators.value = []
  } finally {
    indicatorLoading.value = false
  }
}

/** 加载全量考核结果用于图表统计 */
async function loadAllAssessments(): Promise<void> {
  try {
    const result = await fetchAssessments({ page: 1, pageSize: 500 })
    allAssessments.value = result?.list ?? []
  } catch (error) {
    console.error('[考核管理] 考核统计加载失败', error)
    ElMessage.error('考核统计加载失败')
    allAssessments.value = []
  }
}

const weightTotal = computed(() => indicators.value.reduce((sum, item) => sum + (item.weight || 0), 0))
const averageScore = computed(() => {
  if (!allAssessments.value.length) return 0
  const sum = allAssessments.value.reduce((acc, item) => acc + (item.totalScore || 0), 0)
  return toFixed(sum / allAssessments.value.length, 1)
})
const excellentCount = computed(() => allAssessments.value.filter((item) => item.totalScore >= 90).length)

/** 表格按综合得分降序展示 */
const sortedList = computed(() => [...list.value].sort((a, b) => b.totalScore - a.totalScore))

/** 前十名分数条形图 */
const topTen = computed(() =>
  [...allAssessments.value].sort((a, b) => b.totalScore - a.totalScore).slice(0, 10).reverse(),
)

const scoreOption = computed<echarts.EChartsOption>(() => ({
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    valueFormatter: (value) => `${value} 分`,
  },
  grid: { left: 96, right: 36, top: 16, bottom: 28 },
  xAxis: { type: 'value', name: '综合得分', max: 100 },
  yAxis: {
    type: 'category',
    data: topTen.value.map((item) => item.chiefName),
    axisLabel: { width: 86, overflow: 'truncate' },
  },
  series: [
    {
      name: '综合得分',
      type: 'bar',
      barWidth: 14,
      data: topTen.value.map((item) => item.totalScore),
      itemStyle: {
        color: '#1d4ed8',
        borderRadius: [0, 4, 4, 0],
      },
      label: { show: true, position: 'right', formatter: '{c}' },
    },
  ],
}))

onMounted(() => {
  load()
  loadIndicators()
  loadAllAssessments()
})
</script>

<template>
  <div class="rv-page">
    <PageHeader title="考核管理" description="考核指标权重配置与各级河长履职考核结果排名">
      <template #extra>
        <el-button :icon="Search" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </template>
    </PageHeader>

    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4 mb-4">
      <StatCard label="参与考核人数" :value="allAssessments.length" suffix="人" color="blue" :icon="Medal" />
      <StatCard label="平均综合得分" :value="averageScore" suffix="分" color="cyan" :icon="TrendCharts" />
      <StatCard label="优秀人数（≥90 分）" :value="excellentCount" suffix="人" color="green" />
      <StatCard label="指标权重合计" :value="weightTotal" suffix="%" color="purple" />
    </div>

    <!-- 指标权重 + 分数排行图 -->
    <div class="grid grid-cols-1 gap-4 xl:grid-cols-12 mb-4">
      <div class="rv-card xl:col-span-5">
        <div class="rv-card-header">
          <span class="rv-card-title">考核指标权重</span>
          <span class="rv-text-secondary">合计 {{ weightTotal }}%</span>
        </div>
        <div class="rv-card-body" v-loading="indicatorLoading">
          <el-table :data="indicators" size="small" border>
            <el-table-column prop="name" label="考核指标" min-width="120" />
            <el-table-column label="权重" width="70" align="right">
              <template #default="{ row }">
                <span class="rv-num">{{ row.weight }}%</span>
              </template>
            </el-table-column>
            <el-table-column label="权重占比" min-width="150">
              <template #default="{ row }">
                <el-progress :percentage="row.weight" :stroke-width="10" />
              </template>
            </el-table-column>
            <template #empty>
              <el-empty description="暂无考核指标" :image-size="70" />
            </template>
          </el-table>
        </div>
      </div>

      <div class="rv-card xl:col-span-7">
        <div class="rv-card-header">
          <span class="rv-card-title">综合得分排行（前 10 名）</span>
          <span class="rv-text-secondary">按综合得分降序</span>
        </div>
        <div class="rv-card-body">
          <EChart :option="scoreOption" height="320px" />
        </div>
      </div>
    </div>

    <!-- 考核结果 -->
    <div class="rv-card">
      <div class="rv-card-header">
        <span class="rv-card-title">考核结果</span>
        <div class="flex items-center gap-2">
          <el-input
            v-model="query.keyword"
            placeholder="河长姓名"
            clearable
            class="!w-52"
            @keyup.enter="search"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-select v-model="query.level" placeholder="河长层级" clearable class="!w-36">
            <el-option
              v-for="item in LEVEL_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          <el-button type="primary" @click="search">查询</el-button>
        </div>
      </div>
      <div class="rv-card-body">
        <el-table v-loading="loading" :data="sortedList" size="small" border>
          <el-table-column label="排名" width="80" align="center">
            <template #default="{ row }">
              <el-tag
                :type="row.rank === 1 ? 'danger' : row.rank <= 3 ? 'warning' : 'info'"
                size="small"
                effect="light"
                round
              >
                {{ row.rank }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="chiefName" label="姓名" min-width="90" />
          <el-table-column prop="levelName" label="层级" width="100" align="center" />
          <el-table-column prop="region" label="区域" min-width="110" show-overflow-tooltip />
          <el-table-column prop="period" label="考核周期" min-width="130" />
          <el-table-column label="巡查完成率" width="120" align="right">
            <template #default="{ row }">
              <span class="rv-num">{{ toPercent(row.patrolRate) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="问题处理率" width="120" align="right">
            <template #default="{ row }">
              <span class="rv-num">{{ toPercent(row.resolveRate) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="水质达标率" width="120" align="right">
            <template #default="{ row }">
              <span class="rv-num">{{ toPercent(row.qualityRate) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="响应时效" width="110" align="right">
            <template #default="{ row }">
              <span class="rv-num">{{ toFixed(row.responseTime, 1) }}</span>
              <span class="rv-text-secondary"> 小时</span>
            </template>
          </el-table-column>
          <el-table-column label="公众满意度" width="120" align="right">
            <template #default="{ row }">
              <span class="rv-num">{{ toPercent(row.satisfaction) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="综合得分" width="110" align="right">
            <template #default="{ row }">
              <span class="rv-num font-semibold text-blue-700">{{ toFixed(row.totalScore, 1) }}</span>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="暂无考核结果" :image-size="70" />
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
  </div>
</template>
