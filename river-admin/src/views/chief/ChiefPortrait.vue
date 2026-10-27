<script setup lang="ts">
/**
 * 数字河长画像列表
 * 以卡片网格展示河长履职画像，点击进入画像详情。
 */
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh, Search, UserFilled } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useTable } from '@/composables/useTable'
import { fetchChiefs } from '@/api/chief'
import { defaultText, formatDateTime, toNumber, toPercent } from '@/utils/format'
import type { AdminLevel, Chief, PageQuery } from '@/types'

interface ChiefQuery extends PageQuery {
  level: string
}

const router = useRouter()

const LEVEL_OPTIONS: Array<{ label: string; value: AdminLevel }> = [
  { label: '省级河长', value: 'province' },
  { label: '市级河长', value: 'city' },
  { label: '县级河长', value: 'county' },
  { label: '乡镇级河长', value: 'town' },
]

const {
  loading,
  list,
  total,
  query: baseQuery,
  load,
  search,
  reset,
  changePage,
  changePageSize,
} = useTable<Chief>(fetchChiefs, { level: '' })

const query = baseQuery as ChiefQuery

/** 头像占位取姓名首字 */
function initialText(name: string): string {
  return name ? name.charAt(0) : '河'
}

/** 得分对应的进度条颜色 */
function scoreColor(score: number): string {
  if (score >= 90) return '#16a34a'
  if (score >= 80) return '#1d4ed8'
  if (score >= 70) return '#f59e0b'
  return '#dc2626'
}

/** 卡片内的迷你指标条 */
function barItems(chief: Chief): Array<{ label: string; value: number; color: string; text: string }> {
  return [
    { label: '巡查率', value: chief.patrolRate, color: '#1d4ed8', text: toPercent(chief.patrolRate, 0) },
    { label: '处理率', value: chief.resolveRate, color: '#16a34a', text: toPercent(chief.resolveRate, 0) },
    { label: '综合得分', value: chief.score, color: '#7c3aed', text: `${chief.score}` },
  ]
}

/** 跳转到画像详情 */
function handlePortrait(chief: Chief): void {
  router.push(`/chief/portrait/${chief.id}`)
}

onMounted(() => {
  load()
})
</script>

<template>
  <div class="rv-page">
    <PageHeader title="数字河长画像" description="以数字化画像呈现河长履职成效与指标趋势">
      <template #extra>
        <el-button :icon="UserFilled" @click="router.push('/chief/list')">河长列表</el-button>
      </template>
    </PageHeader>

    <!-- 搜索条件 -->
    <div class="rv-card mb-4">
      <div class="rv-card-body">
        <div class="flex flex-wrap items-center gap-3">
          <el-input
            v-model="query.keyword"
            class="!w-64"
            placeholder="河长姓名 / 区域 / 职务"
            clearable
            :prefix-icon="Search"
            @keyup.enter="search()"
          />
          <el-select v-model="query.level" class="!w-40" placeholder="行政层级" clearable>
            <el-option
              v-for="item in LEVEL_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          <el-button type="primary" :icon="Search" @click="search()">查询</el-button>
          <el-button :icon="Refresh" @click="reset()">重置</el-button>
        </div>
      </div>
    </div>

    <!-- 画像卡片 -->
    <div class="rv-card">
      <div class="rv-card-header">
        <span class="rv-card-title">数字河长画像</span>
        <span class="rv-text-secondary">共 {{ toNumber(total) }} 位河长</span>
      </div>
      <div class="rv-card-body" v-loading="loading">
        <el-empty v-if="!list.length" description="暂无河长画像数据" />

        <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4">
          <div
            v-for="chief in list"
            :key="chief.id"
            class="rv-portrait-card"
            @click="handlePortrait(chief)"
          >
            <!-- 头像与基本信息 -->
            <div class="flex items-center gap-3">
              <div class="rv-portrait-card__avatar">{{ initialText(chief.name) }}</div>
              <div class="min-w-0 flex-1">
                <div class="rv-portrait-card__name">
                  {{ defaultText(chief.name) }}
                  <StatusTag :status="chief.status" />
                </div>
                <div class="rv-portrait-card__meta">
                  {{ defaultText(chief.levelName) }} · {{ defaultText(chief.region) }}
                </div>
                <div class="rv-portrait-card__meta">{{ defaultText(chief.post) }}</div>
              </div>
            </div>

            <!-- 综合得分环形进度 -->
            <div class="mt-4 flex items-center gap-4">
              <el-progress
                type="circle"
                :percentage="chief.score"
                :width="92"
                :stroke-width="8"
                :color="scoreColor(chief.score)"
              />
              <div class="flex-1 min-w-0">
                <div class="rv-text-secondary">管辖河道</div>
                <div class="rv-num text-xl font-semibold">{{ toNumber(chief.riverCount) }} 条</div>
                <div class="rv-text-secondary mt-2">最后巡查</div>
                <div class="text-sm">{{ formatDateTime(chief.lastPatrolAt) }}</div>
              </div>
            </div>

            <!-- 迷你指标条 -->
            <div class="mt-4 space-y-2">
              <div
                v-for="item in barItems(chief)"
                :key="item.label"
                class="rv-portrait-card__bar"
              >
                <span class="rv-portrait-card__bar-label">{{ item.label }}</span>
                <div class="rv-portrait-card__bar-track">
                  <div
                    class="rv-portrait-card__bar-inner"
                    :style="{ width: `${item.value}%`, background: item.color }"
                  />
                </div>
                <span class="rv-num rv-portrait-card__bar-value">{{ item.text }}</span>
              </div>
            </div>

            <div class="rv-portrait-card__footer">查看履职画像详情 →</div>
          </div>
        </div>

        <el-pagination
          :current-page="query.page"
          :page-size="query.pageSize"
          :total="total"
          :page-sizes="[8, 12, 20, 40]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="changePage"
          @size-change="changePageSize"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.rv-portrait-card {
  padding: 18px;
  border: 1px solid var(--rv-border);
  border-radius: var(--rv-radius);
  background: var(--rv-surface);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.rv-portrait-card:hover {
  transform: translateY(-3px);
  border-color: #bfdbfe;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.1);
}

.rv-portrait-card__avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  flex-shrink: 0;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  color: #fff;
  font-size: 20px;
  font-weight: 600;
}

.rv-portrait-card__name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--rv-text);
}

.rv-portrait-card__meta {
  margin-top: 2px;
  font-size: 12px;
  color: var(--rv-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rv-portrait-card__bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.rv-portrait-card__bar-label {
  width: 48px;
  flex-shrink: 0;
  font-size: 12px;
  color: var(--rv-text-secondary);
}

.rv-portrait-card__bar-track {
  flex: 1;
  height: 8px;
  border-radius: 999px;
  background: #f1f5f9;
  overflow: hidden;
}

.rv-portrait-card__bar-inner {
  height: 100%;
  border-radius: 999px;
  transition: width 0.3s ease;
}

.rv-portrait-card__bar-value {
  width: 46px;
  flex-shrink: 0;
  text-align: right;
  font-size: 12px;
  color: var(--rv-text-secondary);
}

.rv-portrait-card__footer {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed var(--rv-border);
  font-size: 12px;
  color: var(--rv-primary);
  text-align: center;
}
</style>
