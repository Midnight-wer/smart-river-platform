<script setup lang="ts">
/**
 * 许可数据库比对：实测水质指标与排污许可证限值自动比对
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { DataAnalysis, Document, Refresh, Warning } from '@element-plus/icons-vue'
import * as echarts from '@/utils/echarts'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import EChart from '@/components/EChart.vue'
import { fetchCompareRows } from '@/api/ai'
import type { CompareRow } from '@/api/ai'

const rows = ref<CompareRow[]>([])
const loading = ref(false)
/** 仅查看超标项 */
const onlyExceed = ref(false)

const totalCount = computed(() => rows.value.length)
const exceedCount = computed(() => rows.value.filter((item) => item.exceed).length)
const qualifyCount = computed(() => totalCount.value - exceedCount.value)
const exceedRate = computed(() => {
  if (!totalCount.value) return 0
  return Number(((exceedCount.value / totalCount.value) * 100).toFixed(1))
})

/** 涉及的许可证数量 */
const permitCount = computed(() => new Set(rows.value.map((item) => item.permitNo)).size)

/** 超标因子清单 */
const exceedFactors = computed(() => rows.value.filter((item) => item.exceed))

/** 表格展示数据 */
const tableRows = computed(() => (onlyExceed.value ? exceedFactors.value : rows.value))

/** 实测值与许可标准柱状对比图 */
const compareOption = computed<echarts.EChartsOption>(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  legend: { data: ['实测值', '许可标准'], top: 0, itemWidth: 14, itemHeight: 8 },
  grid: { left: 50, right: 24, top: 40, bottom: 56 },
  xAxis: {
    type: 'category',
    data: rows.value.map((item) => item.factor),
    axisLabel: { color: '#64748b', interval: 0, rotate: 30 },
  },
  yAxis: { type: 'value', name: '浓度(mg/L)', axisLabel: { color: '#64748b' } },
  series: [
    {
      name: '实测值',
      type: 'bar',
      barMaxWidth: 26,
      itemStyle: { color: '#2563eb', borderRadius: [3, 3, 0, 0] },
      data: rows.value.map((item) => item.value),
    },
    {
      name: '许可标准',
      type: 'bar',
      barMaxWidth: 26,
      itemStyle: { color: '#cbd5e1', borderRadius: [3, 3, 0, 0] },
      data: rows.value.map((item) => item.standard),
    },
  ],
}))

/** 许可标准覆盖率 */
const standardRate = computed(() => {
  if (!totalCount.value) return 0
  return Number(((permitCount.value / totalCount.value) * 100).toFixed(1))
})

/** 加载比对数据 */
async function load(): Promise<void> {
  loading.value = true
  try {
    rows.value = await fetchCompareRows()
  } catch (error) {
    console.error('[许可数据库比对] 比对数据加载失败', error)
    ElMessage.error('许可数据库比对数据加载失败')
    rows.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="rv-page">
    <PageHeader title="许可数据库比对" description="实测水质指标与排污许可证限值自动比对、超标预警">
      <template #extra>
        <el-button :icon="Refresh" @click="load">刷新数据</el-button>
        <el-button type="primary" :icon="Document">导出比对结果</el-button>
      </template>
    </PageHeader>

    <el-alert
      class="mb-4"
      type="warning"
      :closable="false"
      show-icon
      title="比对说明"
      description="比对结果由系统自动匹配排污许可证库生成，实际执行标准以许可证载明限值与现行标准从严孰高原则确定。"
    />

    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4 mb-4">
      <StatCard label="比对指标总数" :value="totalCount" suffix="项" color="blue" :icon="DataAnalysis" />
      <StatCard label="超标指标数" :value="exceedCount" suffix="项" color="red" :icon="Warning" />
      <StatCard label="达标指标数" :value="qualifyCount" suffix="项" color="green" />
      <StatCard label="指标超标率" :value="exceedRate" suffix="%" color="orange" />
    </div>

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-12 mb-4">
      <!-- 概览区 -->
      <div class="rv-card xl:col-span-4">
        <div class="rv-card-header">
          <span class="rv-card-title">比对概览</span>
          <span class="rv-text-secondary">许可证匹配情况</span>
        </div>
        <div class="rv-card-body">
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="比对指标">{{ totalCount }} 项</el-descriptions-item>
            <el-descriptions-item label="超标指标">{{ exceedCount }} 项</el-descriptions-item>
            <el-descriptions-item label="涉及许可证">{{ permitCount }} 本</el-descriptions-item>
            <el-descriptions-item label="许可证匹配率">{{ standardRate }}%</el-descriptions-item>
          </el-descriptions>

          <div class="mt-4 rv-text-secondary">超标因子清单</div>
          <div class="mt-2 flex flex-wrap gap-2">
            <el-tag
              v-for="item in exceedFactors"
              :key="item.id"
              type="danger"
              size="small"
              effect="light"
              round
            >
              {{ item.factor }} {{ item.value }}>{{ item.standard }}
            </el-tag>
            <el-empty v-if="!exceedFactors.length" description="暂无超标因子" :image-size="60" />
          </div>
        </div>
      </div>

      <!-- 柱状对比图 -->
      <div class="rv-card xl:col-span-8">
        <div class="rv-card-header">
          <span class="rv-card-title">实测值与许可标准对比</span>
          <span class="rv-text-secondary">按比对指标展示</span>
        </div>
        <div class="rv-card-body">
          <EChart :option="compareOption" height="320px" :loading="loading" />
        </div>
      </div>
    </div>

    <!-- 明细表格 -->
    <div class="rv-card">
      <div class="rv-card-header">
        <span class="rv-card-title">比对结果明细</span>
        <div class="flex items-center gap-2">
          <el-checkbox v-model="onlyExceed">仅看超标项</el-checkbox>
          <span class="rv-text-secondary">共 {{ tableRows.length }} 条</span>
        </div>
      </div>
      <div class="rv-card-body">
        <el-table v-loading="loading" :data="tableRows" size="small" border>
          <el-table-column prop="id" label="记录编号" width="110" />
          <el-table-column prop="factor" label="比对因子" min-width="120" show-overflow-tooltip />
          <el-table-column label="实测值" width="110" align="right">
            <template #default="{ row }">
              <span class="rv-num">{{ row.value }}</span>
            </template>
          </el-table-column>
          <el-table-column label="许可标准" width="110" align="right">
            <template #default="{ row }">
              <span class="rv-num">{{ row.standard }}</span>
            </template>
          </el-table-column>
          <el-table-column label="超出倍数" width="110" align="right">
            <template #default="{ row }">
              <span class="rv-num" :class="row.exceed ? 'text-red-600' : ''">
                {{ row.standard ? (row.value / row.standard).toFixed(2) : '-' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="是否超标" width="100" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.exceed" type="danger" size="small" effect="light" round>超标</el-tag>
              <el-tag v-else type="success" size="small" effect="light" round>达标</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="permitNo" label="许可证号" min-width="160" show-overflow-tooltip />
          <template #empty>
            <el-empty description="暂无比对记录" :image-size="70" />
          </template>
        </el-table>
      </div>
    </div>
  </div>
</template>
