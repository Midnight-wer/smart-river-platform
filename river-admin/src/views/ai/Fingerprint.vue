<script setup lang="ts">
/**
 * 排污口指纹识别：基于无人机/卫星影像的排污口热区识别与风险分级
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Aim, Histogram, Location, Refresh } from '@element-plus/icons-vue'
import * as echarts from '@/utils/echarts'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import EChart from '@/components/EChart.vue'
import { fetchFingerprints } from '@/api/ai'
import type { Fingerprint } from '@/api/ai'

/** 风险等级划分阈值 */
const HIGH_RISK = 80
const MID_RISK = 60

const fingerprints = ref<Fingerprint[]>([])
const loading = ref(false)

/** 风险等级配色 */
function riskColor(risk: number): string {
  if (risk >= HIGH_RISK) return '#dc2626'
  if (risk >= MID_RISK) return '#f97316'
  if (risk >= 40) return '#f59e0b'
  return '#38bdf8'
}

/** 风险等级文案 */
function riskLevel(risk: number): string {
  if (risk >= HIGH_RISK) return '高风险'
  if (risk >= MID_RISK) return '中风险'
  if (risk >= 40) return '低风险'
  return '关注'
}

const totalCount = computed(() => fingerprints.value.length)
const highRiskCount = computed(() => fingerprints.value.filter((item) => item.risk >= HIGH_RISK).length)
const lockedCount = computed(() => fingerprints.value.filter((item) => item.status === '已锁定').length)
const pendingCount = computed(() => fingerprints.value.filter((item) => item.status === '待核查').length)

/** 风险等级分布统计 */
const riskDistribution = computed(() => {
  const buckets: Record<string, number> = { 高风险: 0, 中风险: 0, 低风险: 0, 关注: 0 }
  fingerprints.value.forEach((item) => {
    const level = riskLevel(item.risk)
    buckets[level] = (buckets[level] ?? 0) + 1
  })
  return buckets
})

/** 来源类型统计 */
const sourceStatistics = computed(() => {
  const counter: Record<string, number> = {}
  fingerprints.value.forEach((item) => {
    counter[item.source] = (counter[item.source] ?? 0) + 1
  })
  return Object.entries(counter)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
})

/** 风险分布饼图 */
const riskPieOption = computed<echarts.EChartsOption>(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} 个 ({d}%)' },
  legend: { bottom: 0, itemWidth: 12, itemHeight: 8 },
  color: ['#dc2626', '#f97316', '#f59e0b', '#38bdf8'],
  series: [
    {
      name: '风险分布',
      type: 'pie',
      radius: ['42%', '68%'],
      center: ['50%', '44%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
      label: { formatter: '{b}\n{c} 个' },
      data: [
        { name: '高风险', value: riskDistribution.value['高风险'] ?? 0 },
        { name: '中风险', value: riskDistribution.value['中风险'] ?? 0 },
        { name: '低风险', value: riskDistribution.value['低风险'] ?? 0 },
        { name: '关注', value: riskDistribution.value['关注'] ?? 0 },
      ],
    },
  ],
}))

/** 悬停提示内容 */
function tooltipText(item: Fingerprint): string {
  return `${item.id}｜来源：${item.source}｜风险：${item.risk}（${riskLevel(item.risk)}）｜状态：${item.status}`
}

/** 加载指纹数据 */
async function load(): Promise<void> {
  loading.value = true
  try {
    fingerprints.value = await fetchFingerprints()
  } catch (error) {
    console.error('[排污口指纹识别] 指纹数据加载失败', error)
    ElMessage.error('排污口指纹数据加载失败')
    fingerprints.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="rv-page">
    <PageHeader title="排污口指纹识别" description="基于遥感影像的排污口热区识别、风险分级与来源预判">
      <template #extra>
        <el-button :icon="Refresh" @click="load">刷新数据</el-button>
      </template>
    </PageHeader>

    <el-alert
      class="mb-4"
      type="info"
      :closable="false"
      show-icon
      title="识别说明"
      description="指纹点位由 AI 影像识别模型提取，坐标为监测河段相对坐标（百分比），风险值由排污特征与周边环境综合评估得出，需结合现场核查确认。"
    />

    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4 mb-4">
      <StatCard label="识别指纹总数" :value="totalCount" suffix="个" color="blue" :icon="Aim" />
      <StatCard label="高风险指纹" :value="highRiskCount" suffix="个" color="red" />
      <StatCard label="已锁定指纹" :value="lockedCount" suffix="个" color="purple" :icon="Location" />
      <StatCard label="待核查指纹" :value="pendingCount" suffix="个" color="orange" :icon="Histogram" />
    </div>

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-12 mb-4">
      <!-- 指纹热区图 -->
      <div class="rv-card xl:col-span-4">
        <div class="rv-card-header">
          <span class="rv-card-title">排污口指纹热区图</span>
          <span class="rv-text-secondary">悬停查看指纹详情</span>
        </div>
        <div class="rv-card-body">
          <div v-loading="loading" class="fp-heat">
            <div class="fp-heat-grid" />
            <el-tooltip
              v-for="item in fingerprints"
              :key="item.id"
              placement="top"
              :content="tooltipText(item)"
            >
              <span
                class="fp-dot"
                :style="{ left: `${item.x}%`, top: `${item.y}%`, background: riskColor(item.risk) }"
              />
            </el-tooltip>
            <span class="fp-axis fp-axis-x">河流流向 →</span>
            <span class="fp-axis fp-axis-y">↑ 沿岸</span>
          </div>

          <div class="fp-legend">
            <span v-for="item in [
              { label: '高风险 ≥ 80', color: '#dc2626' },
              { label: '中风险 60-79', color: '#f97316' },
              { label: '低风险 40-59', color: '#f59e0b' },
              { label: '关注 < 40', color: '#38bdf8' },
            ]" :key="item.label" class="fp-legend-item">
              <i class="fp-legend-dot" :style="{ background: item.color }" />
              <span class="rv-text-secondary">{{ item.label }}</span>
            </span>
          </div>
        </div>
      </div>

      <!-- 指纹列表 -->
      <div class="rv-card xl:col-span-8">
        <div class="rv-card-header">
          <span class="rv-card-title">指纹识别清单</span>
          <span class="rv-text-secondary">共 {{ totalCount }} 条记录</span>
        </div>
        <div class="rv-card-body">
          <el-table v-loading="loading" :data="fingerprints" size="small" border max-height="420">
            <el-table-column prop="id" label="指纹编号" width="110" />
            <el-table-column prop="source" label="来源类型" min-width="110" show-overflow-tooltip />
            <el-table-column label="相对坐标" width="120" align="center">
              <template #default="{ row }">
                <span class="rv-num">{{ row.x }}% / {{ row.y }}%</span>
              </template>
            </el-table-column>
            <el-table-column label="风险值" min-width="150">
              <template #default="{ row }">
                <el-progress
                  :percentage="row.risk"
                  :color="riskColor(row.risk)"
                  :stroke-width="10"
                  :format="() => row.risk"
                />
              </template>
            </el-table-column>
            <el-table-column label="风险等级" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.risk >= HIGH_RISK ? 'danger' : 'info'" size="small" effect="light" round>
                  {{ riskLevel(row.risk) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100" align="center">
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
            <template #empty>
              <el-empty description="暂无指纹识别数据" :image-size="70" />
            </template>
          </el-table>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-12">
      <!-- 风险分布 -->
      <div class="rv-card xl:col-span-5">
        <div class="rv-card-header">
          <span class="rv-card-title">风险等级分布</span>
          <span class="rv-text-secondary">按指纹风险分级统计</span>
        </div>
        <div class="rv-card-body">
          <EChart :option="riskPieOption" height="300px" :loading="loading" />
        </div>
      </div>

      <!-- 来源类型统计 -->
      <div class="rv-card xl:col-span-7">
        <div class="rv-card-header">
          <span class="rv-card-title">污染来源类型统计</span>
          <span class="rv-text-secondary">AI 预判的排放来源分布</span>
        </div>
        <div class="rv-card-body">
          <el-table :data="sourceStatistics" size="small" border>
            <el-table-column prop="name" label="来源类型" min-width="140" />
            <el-table-column label="指纹数量" min-width="160">
              <template #default="{ row }">
                <el-progress
                  :percentage="totalCount ? Math.round((row.value / totalCount) * 100) : 0"
                  :color="'#2563eb'"
                  :stroke-width="10"
                />
              </template>
            </el-table-column>
            <el-table-column prop="value" label="数量" width="90" align="right">
              <template #default="{ row }">
                <span class="rv-num">{{ row.value }}</span>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty description="暂无来源统计" :image-size="70" />
            </template>
          </el-table>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fp-heat {
  position: relative;
  width: 100%;
  height: 320px;
  border: 1px solid var(--rv-border);
  border-radius: var(--rv-radius);
  background: linear-gradient(180deg, #f8fafc 0%, #eff6ff 100%);
  overflow: hidden;
}

.fp-heat-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(to right, rgba(148, 163, 184, 0.18) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(148, 163, 184, 0.18) 1px, transparent 1px);
  background-size: 10% 10%;
}

.fp-dot {
  position: absolute;
  width: 16px;
  height: 16px;
  margin: -8px 0 0 -8px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.85);
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.08);
  cursor: pointer;
  transition: transform 0.15s ease;
}

.fp-dot:hover {
  transform: scale(1.35);
}

.fp-axis {
  position: absolute;
  font-size: 12px;
  color: var(--rv-text-secondary);
}

.fp-axis-x {
  right: 10px;
  bottom: 6px;
}

.fp-axis-y {
  left: 8px;
  top: 8px;
}

.fp-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 12px;
}

.fp-legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.fp-legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}
</style>
