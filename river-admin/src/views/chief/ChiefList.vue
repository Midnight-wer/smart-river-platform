<script setup lang="ts">
/**
 * 河长列表
 * 展示各级河长的基础档案、履职率与在岗状态。
 */
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh, Search, UserFilled } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useTable } from '@/composables/useTable'
import { fetchChiefs } from '@/api/chief'
import { defaultText, formatDateTime, toNumber } from '@/utils/format'
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

/** 查看河长画像 */
function handlePortrait(row: Chief): void {
  router.push(`/chief/portrait/${row.id}`)
}

onMounted(() => {
  load()
})
</script>

<template>
  <div class="rv-page">
    <PageHeader title="河长列表" description="查看各级河长基础档案与履职指标">
      <template #extra>
        <el-button :icon="UserFilled" @click="router.push('/chief/portrait')">数字河长画像</el-button>
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

    <!-- 河长列表 -->
    <div class="rv-card">
      <div class="rv-card-header">
        <span class="rv-card-title">河长列表</span>
        <span class="rv-text-secondary">共 {{ toNumber(total) }} 条</span>
      </div>
      <div class="rv-card-body">
        <el-table v-loading="loading" :data="list" border stripe>
          <el-table-column prop="name" label="姓名" width="110" />
          <el-table-column prop="phone" label="联系电话" width="130">
            <template #default="{ row }">{{ defaultText(row.phone) }}</template>
          </el-table-column>
          <el-table-column prop="levelName" label="层级" width="120" align="center">
            <template #default="{ row }">
              <el-tag effect="plain">{{ defaultText(row.levelName) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="post" label="职务" min-width="170" show-overflow-tooltip />
          <el-table-column prop="region" label="所属区域" width="120" show-overflow-tooltip />
          <el-table-column prop="riverCount" label="管辖河道数" width="110" align="right">
            <template #default="{ row }">{{ toNumber(row.riverCount) }}</template>
          </el-table-column>
          <el-table-column label="巡查率" min-width="150">
            <template #default="{ row }">
              <el-progress :percentage="row.patrolRate" :stroke-width="10" text-inside />
            </template>
          </el-table-column>
          <el-table-column label="问题处理率" min-width="160">
            <template #default="{ row }">
              <el-progress :percentage="row.resolveRate" :stroke-width="10" text-inside />
            </template>
          </el-table-column>
          <el-table-column prop="score" label="综合得分" width="110" align="right">
            <template #default="{ row }">
              <span class="rv-num">{{ row.score }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <StatusTag :status="row.status" />
            </template>
          </el-table-column>
          <el-table-column prop="lastPatrolAt" label="最后巡查时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.lastPatrolAt) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="110" fixed="right" align="center">
            <template #default="{ row }">
              <el-button link type="primary" @click="handlePortrait(row)">查看画像</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          :current-page="query.page"
          :page-size="query.pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="changePage"
          @size-change="changePageSize"
        />
      </div>
    </div>
  </div>
</template>
