<script setup lang="ts">
/**
 * 污染溯源模型：基于水质突变与流路的污染源逆向溯源链条推演
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowDown, Compass, Download, MagicStick, Refresh, Timer } from '@element-plus/icons-vue'
import * as echarts from '@/utils/echarts'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import EChart from '@/components/EChart.vue'
import { fetchDiffusion, fetchTracing } from '@/api/ai'
import type { DiffusionPoint, TracingStep } from '@/api/ai'

const tracing = ref<TracingStep[]>([])
const diffusion = ref<DiffusionPoint[]>([])
const loading = ref(false)

/** 时间字符串转分钟数 */
function toMinutes(time: string): number {
  const [hour, minute] = time.split(':').map((item) => Number(item))
  return (hour || 0) * 60 + (minute || 0)
}

const nodeCount = computed(() => tracing.value.length)
const durationMinutes = computed(() => {
  if (tracing.value.length < 2) return 0
  const first = tracing.value[0]
  const last = tracing.value[tracing.value.length - 1]
  return Math.max(0, toMinutes(last.time) - toMinutes(first.time))
})
const startNode = computed(() => tracing.value[0]?.node ?? '-')
const finalNode = computed(() => tracing.value[tracing.value.length - 1]?.node ?? '-')

/** 溯源结论 */
const conclusion = computed(() => {
  if (!tracing.value.length) return '暂无溯源结论'
  return `经污染溯源模型推演，本次污染事件源头已锁定于「${finalNode.value}」，建议属地河长立即开展现场核查并追溯涉事主体责任。`
})

/** 溯源过程浓度变化曲线 */
const concentrationSeries = computed(() =>
  diffusion.value.map((item) => ({
    distance: Number((item.x * 5).toFixed(1)),
    concentration: Number(item.y.toFixed(2)),
  })),
)

/** 溯源节点在浓度曲线上的落点 */
const nodePoints = computed(() => {
  if (!diffusion.value.length || !tracing.value.length) return []
  const step = (diffusion.value.length - 1) / tracing.value.length
  return tracing.value.map((item, index) => {
    const position = Math.min(diffusion.value.length - 1, Math.round(index * step))
    return [position, Number(diffusion.value[position].y.toFixed(2))]
  })
})

/** 浓度变化折线图 */
const concentrationOption = computed<echarts.EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['浓度变化', '溯源节点'], bottom: 0, itemWidth: 14, itemHeight: 8 },
  grid: { left: 54, right: 26, top: 36, bottom: 46 },
  xAxis: {
    type: 'category',
    name: '距监测点(m)',
    data: concentrationSeries.value.map((item) => item.distance),
    axisLabel: { color: '#64748b' },
  },
  yAxis: { type: 'value', name: '浓度(mg/L)', axisLabel: { color: '#64748b' } },
  series: [
    {
      name: '浓度变化',
      type: 'line',
      smooth: true,
      areaStyle: { color: '#2563eb', opacity: 0.16 },
      itemStyle: { color: '#2563eb' },
      data: concentrationSeries.value.map((item) => item.concentration),
    },
    {
      name: '溯源节点',
      type: 'scatter',
      symbolSize: 14,
      itemStyle: { color: '#dc2626', borderColor: '#fff', borderWidth: 2 },
      data: nodePoints.value,
    },
  ],
}))

/** 加载溯源数据 */
async function load(): Promise<void> {
  loading.value = true
  try {
    const [steps, points] = await Promise.all([fetchTracing(), fetchDiffusion()])
    tracing.value = steps
    diffusion.value = points
  } catch (error) {
    console.error('[污染溯源模型] 溯源数据加载失败', error)
    ElMessage.error('污染溯源数据加载失败')
    tracing.value = []
    diffusion.value = []
  } finally {
    loading.value = false
  }
}

/** 导出溯源报告 */
function handleExport(): void {
  ElMessage.success('溯源报告已生成，可前往下载中心查看')
}

onMounted(load)
</script>

<template>
  <div class="rv-page">
    <PageHeader title="污染溯源模型" description="基于水质突变识别与流路反演的污染源逆向溯源推演">
      <template #extra>
        <el-button :icon="Refresh" @click="load">刷新数据</el-button>
        <el-button type="primary" :icon="Download" @click="handleExport">导出溯源报告</el-button>
      </template>
    </PageHeader>

    <el-alert
      class="mb-4"
      type="info"
      :closable="false"
      show-icon
      title="模型说明"
      description="溯源链条由污染溯源模型结合水质突变点位、流速流向与历史排污记录推演生成，红色节点为溯源关键路径，最终责任认定须以现场核查与执法证据为准。"
    />

    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4 mb-4">
      <StatCard label="溯源节点数" :value="nodeCount" suffix="个" color="blue" :icon="Compass" />
      <StatCard label="溯源耗时" :value="durationMinutes" suffix="分钟" color="orange" :icon="Timer" />
      <StatCard label="起始疑点" :value="startNode" color="cyan" />
      <StatCard label="锁定结果" :value="finalNode" color="purple" :icon="MagicStick" />
    </div>

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-12 mb-4">
      <!-- 溯源链 -->
      <div class="rv-card xl:col-span-7">
        <div class="rv-card-header">
          <span class="rv-card-title">溯源路径链条</span>
          <span class="rv-text-secondary">自疑点至污染源主体的逆向推演</span>
        </div>
        <div class="rv-card-body" v-loading="loading">
          <el-steps v-if="tracing.length" direction="vertical" :active="tracing.length" finish-status="success">
            <el-step v-for="(step, index) in tracing" :key="step.step">
              <template #icon>
                <span class="tracing-index">{{ step.step }}</span>
              </template>
              <template #title>
                <span class="tracing-node">{{ step.node }}</span>
                <span class="rv-text-secondary ml-2">{{ step.time }}</span>
              </template>
              <template #description>
                <div class="tracing-desc">{{ step.desc }}</div>
                <el-icon v-if="index < tracing.length - 1" class="tracing-arrow">
                  <ArrowDown />
                </el-icon>
              </template>
            </el-step>
          </el-steps>
          <el-empty v-else description="暂无溯源链条" :image-size="80" />
        </div>
      </div>

      <!-- 浓度变化 -->
      <div class="rv-card xl:col-span-5">
        <div class="rv-card-header">
          <span class="rv-card-title">溯源过程浓度变化</span>
          <span class="rv-text-secondary">红点为溯源节点位置</span>
        </div>
        <div class="rv-card-body">
          <EChart :option="concentrationOption" height="360px" :loading="loading" />
        </div>
      </div>
    </div>

    <!-- 溯源结论 -->
    <div class="rv-card">
      <div class="rv-card-header">
        <span class="rv-card-title">溯源结论</span>
        <el-button type="primary" :icon="Download" @click="handleExport">导出溯源报告</el-button>
      </div>
      <div class="rv-card-body">
        <el-alert
          type="success"
          :closable="false"
          show-icon
          :title="`溯源完成：${finalNode}`"
          :description="conclusion"
        />

        <el-descriptions class="mt-4" :column="2" border size="small">
          <el-descriptions-item label="溯源起点">{{ startNode }}</el-descriptions-item>
          <el-descriptions-item label="溯源终点">{{ finalNode }}</el-descriptions-item>
          <el-descriptions-item label="节点数量">{{ nodeCount }} 个</el-descriptions-item>
          <el-descriptions-item label="推演耗时">{{ durationMinutes }} 分钟</el-descriptions-item>
          <el-descriptions-item label="处置建议">属地河长 2 小时内现场核查并反馈处置结果</el-descriptions-item>
          <el-descriptions-item label="报告状态">
            <el-tag type="success" size="small" effect="light" round>已生成</el-tag>
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tracing-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--rv-primary);
  color: #fff;
  font-size: 12px;
  line-height: 1;
}

.tracing-node {
  font-weight: 600;
  color: var(--rv-text);
}

.tracing-desc {
  margin-top: 4px;
  font-size: 13px;
  color: var(--rv-text-secondary);
}

.tracing-arrow {
  margin-top: 8px;
  color: var(--rv-primary);
  font-size: 18px;
}
</style>
