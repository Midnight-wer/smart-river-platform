<script setup lang="ts">
/**
 * 设备管理：巡河无人机、监控设备、水质监测站等终端的运行状态维护
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Monitor, Position, Refresh, Search, Tools, VideoCamera } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { fetchDevices } from '@/api/system'
import { formatDateTime } from '@/utils/format'
import type { Device } from '@/types'

const DEVICE_TYPE_OPTIONS: Device['type'][] = ['无人机', '监控设备', '水质监测站', '雨量站', '浮标']
const DEVICE_STATUS_OPTIONS: Device['status'][] = ['在线', '离线', '维护中']

const loading = ref(false)
const devices = ref<Device[]>([])
const keyword = ref('')
const typeFilter = ref('')
const statusFilter = ref('')

/** 设备详情弹窗 */
const detailVisible = ref(false)
const currentDevice = ref<Device | null>(null)

/** 统计信息 */
const totalCount = computed(() => devices.value.length)
const onlineCount = computed(() => devices.value.filter((item) => item.status === '在线').length)
const offlineCount = computed(() => devices.value.filter((item) => item.status === '离线').length)
const maintainCount = computed(() => devices.value.filter((item) => item.status === '维护中').length)

/** 过滤后的设备列表 */
const filteredDevices = computed<Device[]>(() => {
  const kw = keyword.value.trim().toLowerCase()
  return devices.value.filter((item) => {
    if (typeFilter.value && item.type !== typeFilter.value) return false
    if (statusFilter.value && item.status !== statusFilter.value) return false
    if (!kw) return true
    return [item.name, item.code, item.type, item.region].some((field) => field.toLowerCase().includes(kw))
  })
})

/** 电量颜色 */
function batteryColor(value: number): string {
  if (value <= 20) return '#dc2626'
  if (value <= 50) return '#f59e0b'
  return '#16a34a'
}

/** 加载设备数据 */
async function load(): Promise<void> {
  loading.value = true
  try {
    const result = await fetchDevices()
    devices.value = result ?? []
  } catch (error) {
    console.error('[设备管理] 设备列表加载失败', error)
    ElMessage.error('设备列表加载失败')
    devices.value = []
  } finally {
    loading.value = false
  }
}

/** 查看设备详情 */
function openDetail(row: Device): void {
  currentDevice.value = row
  detailVisible.value = true
}

/** 设备维护（后端写接口暂未开放） */
function handleMaintain(row: Device): void {
  ElMessage.info(`设备「${row.name}」的维护接口暂未开放`)
}

/** 3D / 地图联动（后续接入地图服务） */
function handleMapLink(): void {
  ElMessage.info('3D 地图联动功能待后续接入地图服务')
}

onMounted(() => {
  load()
})
</script>

<template>
  <div class="rv-page">
    <PageHeader title="设备管理" description="管理无人机、监控设备与水质监测站等终端的运行状态">
      <template #extra>
        <el-button :icon="Position" @click="handleMapLink">3D / 地图联动</el-button>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </template>
    </PageHeader>

    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4 mb-4">
      <StatCard label="设备总数" :value="totalCount" suffix="台" color="blue" :icon="Monitor" />
      <StatCard label="在线设备" :value="onlineCount" suffix="台" color="green" />
      <StatCard label="离线设备" :value="offlineCount" suffix="台" color="red" />
      <StatCard label="维护中设备" :value="maintainCount" suffix="台" color="orange" :icon="Tools" />
    </div>

    <div class="rv-card">
      <div class="rv-card-header">
        <span class="rv-card-title">设备列表</span>
        <div class="flex items-center gap-2">
          <el-input v-model="keyword" placeholder="名称 / 编码 / 区域" clearable class="!w-52">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-select v-model="typeFilter" placeholder="设备类型" clearable class="!w-32">
            <el-option v-for="item in DEVICE_TYPE_OPTIONS" :key="item" :label="item" :value="item" />
          </el-select>
          <el-select v-model="statusFilter" placeholder="运行状态" clearable class="!w-32">
            <el-option v-for="item in DEVICE_STATUS_OPTIONS" :key="item" :label="item" :value="item" />
          </el-select>
        </div>
      </div>

      <div class="rv-card-body" v-loading="loading">
        <!-- 设备卡片网格 -->
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          <div v-for="item in filteredDevices" :key="item.id" class="rv-device">
            <div class="rv-device__head">
              <div class="rv-device__title">
                <el-icon color="#1d4ed8"><VideoCamera /></el-icon>
                <span class="rv-device__name">{{ item.name }}</span>
              </div>
              <StatusTag :status="item.status" />
            </div>

            <div class="rv-device__meta">
              <div class="rv-device__row">
                <span class="rv-device__label">编码</span>
                <span class="rv-num">{{ item.code }}</span>
              </div>
              <div class="rv-device__row">
                <span class="rv-device__label">类型</span>
                <span>{{ item.type }}</span>
              </div>
              <div class="rv-device__row">
                <span class="rv-device__label">区域</span>
                <span>{{ item.region }}</span>
              </div>
            </div>

            <div class="rv-device__battery">
              <div class="rv-device__row">
                <span class="rv-device__label">电量</span>
                <span class="rv-num">{{ item.battery }}%</span>
              </div>
              <el-progress
                :percentage="item.battery"
                :stroke-width="8"
                :color="batteryColor(item.battery)"
                :show-text="false"
              />
            </div>

            <div class="rv-device__foot">
              <span class="rv-text-secondary">最后在线：{{ formatDateTime(item.lastOnlineAt) }}</span>
              <div class="flex items-center gap-2">
                <el-button link type="primary" @click="openDetail(item)">查看详情</el-button>
                <el-button link type="warning" @click="handleMaintain(item)">维护</el-button>
              </div>
            </div>
          </div>
        </div>

        <el-empty v-if="!filteredDevices.length && !loading" description="暂无设备数据" :image-size="90" />
      </div>
    </div>

    <!-- 设备详情弹窗 -->
    <el-dialog v-model="detailVisible" title="设备详情" width="520px">
      <el-descriptions v-if="currentDevice" :column="2" border>
        <el-descriptions-item label="设备名称">{{ currentDevice.name }}</el-descriptions-item>
        <el-descriptions-item label="设备编码">{{ currentDevice.code }}</el-descriptions-item>
        <el-descriptions-item label="设备类型">{{ currentDevice.type }}</el-descriptions-item>
        <el-descriptions-item label="所属区域">{{ currentDevice.region }}</el-descriptions-item>
        <el-descriptions-item label="运行状态">
          <StatusTag :status="currentDevice.status" />
        </el-descriptions-item>
        <el-descriptions-item label="当前电量">{{ currentDevice.battery }}%</el-descriptions-item>
        <el-descriptions-item label="最后在线时间" :span="2">
          {{ formatDateTime(currentDevice.lastOnlineAt) }}
        </el-descriptions-item>
      </el-descriptions>

      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button type="primary" :icon="Tools" @click="currentDevice && handleMaintain(currentDevice)">报修维护</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.rv-device {
  padding: 14px 16px;
  border: 1px solid var(--rv-border);
  border-radius: var(--rv-radius);
  background: var(--rv-surface);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.rv-device:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.1);
}

.rv-device__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.rv-device__title {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.rv-device__name {
  font-size: 14px;
  font-weight: 600;
  color: var(--rv-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rv-device__meta {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 10px;
}

.rv-device__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
  color: var(--rv-text);
}

.rv-device__label {
  color: var(--rv-text-secondary);
  flex-shrink: 0;
}

.rv-device__battery {
  margin-bottom: 10px;
}

.rv-device__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-top: 10px;
  border-top: 1px dashed var(--rv-border);
  font-size: 12px;
}
</style>
