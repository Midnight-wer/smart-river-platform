<script setup lang="ts">
/**
 * 水质预测模型：基于 LSTM 的水质指标短期预测与置信区间评估
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Cpu, DataLine, Refresh, TrendCharts } from '@element-plus/icons-vue'
import * as echarts from '@/utils/echarts'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import EChart from '@/components/EChart.vue'
import { fetchPrediction } from '@/api/ai'
import type { PredictionPoint } from '@/api/ai'

const predictions = ref<PredictionPoint[]>([])
const loading = ref(false)

/** 模型信息 */
const MODEL_INFO = {
  type: 'LSTM 长短期记忆网络',
  version: 'v2.4.1',
  featureCount: 12,
  trainSamples: 21840,
  predictStep: 14,
  interval: 95,
}

/** 预测明细（含偏差） */
const detailRows = computed(() =>
  predictions.value.map((item) => ({
    ...item,
    deviation: Number((item.predict - item.actual).toFixed(2)),
  })),
)

/** 平均绝对偏差 */
const averageDeviation = computed(() => {
  if (!detailRows.value.length) return 0
  const total = detailRows.value.reduce((sum, item) => sum + Math.abs(item.deviation), 0)
  return Number((total / detailRows.value.length).toFixed(2))
})

/** 预测区间覆盖率 */
const coverageRate = computed(() => {
  if (!predictions.value.length) return 0
  const covered = predictions.value.filter(
    (item) => item.actual >= item.lower && item.actual <= item.upper,
  ).length
  return Number(((covered / predictions.value.length) * 100).toFixed(1))
})

/** 模型准确率（基于偏差反算） */
const accuracy = computed(() => {
  if (!predictions.value.length) return 0
  const total = predictions.value.reduce((sum, item) => sum + item.actual, 0) / predictions.value.length
  if (!total) return 0
  return Number((100 - (averageDeviation.value / total) * 100).toFixed(1))
})

/** 预测折线图（含置信区间带） */
const predictionOption = computed<echarts.EChartsOption>(() => {
  const lower = predictions.value.map((item) => item.lower)
  const upper = predictions.value.map((item) => item.upper)
  return {
    tooltip: { trigger: 'axis' },
    legend: {
      data: ['实际值', '预测值', '置信区间'],
      bottom: 0,
      itemWidth: 14,
      itemHeight: 8,
    },
    grid: { left: 56, right: 30, top: 40, bottom: 48 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: predictions.value.map((item) => item.date),
      axisLabel: { color: '#64748b' },
    },
    yAxis: {
      type: 'value',
      name: 'DO (mg/L)',
      scale: true,
      axisLabel: { color: '#64748b' },
    },
    series: [
      {
        name: '置信区间下界',
        type: 'line',
        stack: 'band',
        symbol: 'none',
        lineStyle: { opacity: 0 },
        areaStyle: { opacity: 0 },
        data: lower,
      },
      {
        name: '置信区间',
        type: 'line',
        stack: 'band',
        symbol: 'none',
        lineStyle: { opacity: 0 },
        areaStyle: { color: '#2563eb', opacity: 0.16 },
        data: upper.map((item, index) => Number((item - lower[index]).toFixed(3))),
      },
      {
        name: '实际值',
        type: 'line',
        smooth: true,
        symbolSize: 6,
        itemStyle: { color: '#16a34a' },
        data: predictions.value.map((item) => item.actual),
      },
      {
        name: '预测值',
        type: 'line',
        smooth: true,
        symbolSize: 6,
        itemStyle: { color: '#2563eb' },
        lineStyle: { type: 'dashed' },
        data: predictions.value.map((item) => item.predict),
      },
    ],
  }
})

/** 加载预测数据 */
async function load(): Promise<void> {
  loading.value = true
  try {
    predictions.value = await fetchPrediction()
  } catch (error) {
    console.error('[水质预测模型] 预测数据加载失败', error)
    ElMessage.error('水质预测数据加载失败')
    predictions.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="rv-page">
    <PageHeader title="水质预测模型" description="基于 LSTM 神经网络的水质指标短期预测与置信区间评估">
      <template #extra>
        <el-button :icon="Refresh" @click="load">刷新数据</el-button>
        <el-button type="primary" :icon="TrendCharts">重新训练模型</el-button>
      </template>
    </PageHeader>

    <el-alert
      class="mb-4"
      type="warning"
      :closable="false"
      show-icon
      title="免责声明"
      description="水质预测结果由 AI 模型基于历史监测序列推算生成，预测结果仅供参考，不能替代现场监测数据与人工研判，实际水质情况以监测站实测结果为准。"
    />

    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4 mb-4">
      <StatCard label="预测天数" :value="predictions.length" suffix="天" color="blue" :icon="DataLine" />
      <StatCard label="平均绝对偏差" :value="averageDeviation" suffix="mg/L" color="orange" />
      <StatCard label="区间覆盖率" :value="coverageRate" suffix="%" color="green" />
      <StatCard label="模型准确率" :value="accuracy" suffix="%" color="purple" :icon="Cpu" />
    </div>

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-12 mb-4">
      <!-- 模型信息 -->
      <div class="rv-card xl:col-span-4">
        <div class="rv-card-header">
          <span class="rv-card-title">模型信息</span>
          <span class="rv-text-secondary">水质预测模型</span>
        </div>
        <div class="rv-card-body">
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="模型类型">{{ MODEL_INFO.type }}</el-descriptions-item>
            <el-descriptions-item label="模型版本">{{ MODEL_INFO.version }}</el-descriptions-item>
            <el-descriptions-item label="输入特征数">{{ MODEL_INFO.featureCount }} 项</el-descriptions-item>
            <el-descriptions-item label="训练样本量">{{ MODEL_INFO.trainSamples }} 条</el-descriptions-item>
            <el-descriptions-item label="预测步长">{{ MODEL_INFO.predictStep }} 天</el-descriptions-item>
            <el-descriptions-item label="置信水平">{{ MODEL_INFO.interval }}%</el-descriptions-item>
          </el-descriptions>

          <div class="mt-4">
            <el-alert
              type="info"
              :closable="false"
              title="说明"
              description="LSTM 模型通过门控机制捕捉水质序列的长短期依赖关系，输入包含历史溶解氧、氨氮、COD 等 12 项特征。"
            />
          </div>
        </div>
      </div>

      <!-- 预测折线图 -->
      <div class="rv-card xl:col-span-8">
        <div class="rv-card-header">
          <span class="rv-card-title">实际值与预测值对比</span>
          <span class="rv-text-secondary">阴影区域为 {{ MODEL_INFO.interval }}% 置信区间</span>
        </div>
        <div class="rv-card-body">
          <EChart :option="predictionOption" height="340px" :loading="loading" />
        </div>
      </div>
    </div>

    <!-- 预测明细 -->
    <div class="rv-card">
      <div class="rv-card-header">
        <span class="rv-card-title">预测明细</span>
        <span class="rv-text-secondary">共 {{ detailRows.length }} 天</span>
      </div>
      <div class="rv-card-body">
        <el-table v-loading="loading" :data="detailRows" size="small" border max-height="420">
          <el-table-column prop="date" label="日期" min-width="120" />
          <el-table-column label="实际值" width="110" align="right">
            <template #default="{ row }">
              <span class="rv-num">{{ row.actual.toFixed(2) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="预测值" width="110" align="right">
            <template #default="{ row }">
              <span class="rv-num">{{ row.predict.toFixed(2) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="偏差" width="110" align="right">
            <template #default="{ row }">
              <span class="rv-num" :class="Math.abs(row.deviation) > 0.2 ? 'text-red-600' : ''">
                {{ row.deviation > 0 ? '+' : '' }}{{ row.deviation.toFixed(2) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="置信区间下限" width="140" align="right">
            <template #default="{ row }">
              <span class="rv-num">{{ row.lower.toFixed(2) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="置信区间上限" width="140" align="right">
            <template #default="{ row }">
              <span class="rv-num">{{ row.upper.toFixed(2) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="是否命中区间" width="130" align="center">
            <template #default="{ row }">
              <el-tag
                :type="row.actual >= row.lower && row.actual <= row.upper ? 'success' : 'warning'"
                size="small"
                effect="light"
                round
              >
                {{ row.actual >= row.lower && row.actual <= row.upper ? '命中' : '超出' }}
              </el-tag>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="暂无预测数据" :image-size="70" />
          </template>
        </el-table>
      </div>
    </div>
  </div>
</template>
