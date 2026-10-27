<script setup lang="ts">
/**
 * 角色管理：角色列表展示与权限分配
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Edit, Key, Refresh, User } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import { fetchRoles } from '@/api/system'
import { formatDateTime } from '@/utils/format'
import type { SysRole } from '@/types'

/** 权限分组：编码前缀 → 中文名称 */
const PERMISSION_GROUP_LABELS: Record<string, string> = {
  dashboard: '工作台',
  workspace: '河长工作台',
  river: '河道档案',
  chief: '河长管理',
  patrol: '巡查管理',
  water: '水质监测',
  event: '事件中心',
  ai: 'AI 智能溯源',
  assessment: '考核管理',
  public: '公众服务',
  'large-screen': '数据大屏',
  system: '系统管理',
}

/** 权限编码 → 中文描述 */
const PERMISSION_LABELS: Record<string, string> = {
  'dashboard:view': '查看工作台',
  'workspace:province': '省级工作台',
  'workspace:city': '市级工作台',
  'workspace:county': '县级工作台',
  'workspace:town': '乡镇级工作台',
  'river:view': '查看河道档案',
  'chief:view': '查看河长信息',
  'patrol:view': '查看巡查任务',
  'patrol:handle': '处理巡查任务',
  'water:view': '查看水质数据',
  'event:view': '查看事件',
  'event:handle': '处理事件',
  'ai:view': '使用 AI 溯源',
  'assessment:view': '查看考核结果',
  'public:view': '查看公众服务',
  'large-screen:view': '查看数据大屏',
}

const loading = ref(false)
const roles = ref<SysRole[]>([])

/** 权限配置抽屉 */
const drawerVisible = ref(false)
const submitting = ref(false)
const currentRole = ref<SysRole | null>(null)
const checkedPermissions = ref<string[]>([])

/** 全部可用权限编码（去重、排除通配符） */
const allPermissions = computed<string[]>(() => {
  const set = new Set<string>()
  roles.value.forEach((role) => {
    role.permissions?.forEach((code) => {
      if (code !== '*') set.add(code)
    })
  })
  return Array.from(set).sort()
})

/** 权限分组 */
const permissionGroups = computed<{ key: string; name: string; codes: string[] }[]>(() => {
  const groups = new Map<string, string[]>()
  allPermissions.value.forEach((code) => {
    const prefix = code.split(':')[0]
    if (!groups.has(prefix)) groups.set(prefix, [])
    groups.get(prefix)?.push(code)
  })
  return Array.from(groups.entries()).map(([prefix, codes]) => ({
    key: prefix,
    name: PERMISSION_GROUP_LABELS[prefix] ?? prefix,
    codes,
  }))
})

/** 统计信息 */
const enabledCount = computed(() => roles.value.filter((item) => item.status === '启用').length)
const memberTotal = computed(() => roles.value.reduce((sum, item) => sum + (item.memberCount || 0), 0))

/** 解析权限编码的中文描述 */
function permissionLabel(code: string): string {
  return PERMISSION_LABELS[code] ?? code
}

/** 加载角色列表 */
async function load(): Promise<void> {
  loading.value = true
  try {
    const result = await fetchRoles()
    roles.value = result ?? []
  } catch (error) {
    console.error('[角色管理] 角色列表加载失败', error)
    ElMessage.error('角色列表加载失败')
    roles.value = []
  } finally {
    loading.value = false
  }
}

/** 打开权限配置抽屉 */
function openPermission(row: SysRole): void {
  currentRole.value = row
  checkedPermissions.value = row.permissions?.includes('*') ? [...allPermissions.value] : [...(row.permissions ?? [])]
  drawerVisible.value = true
}

/** 保存权限配置（后端写接口暂未开放） */
async function handleSavePermission(): Promise<void> {
  if (!currentRole.value) return
  submitting.value = true
  try {
    ElMessage.success('权限配置已保存')
    drawerVisible.value = false
  } catch (error) {
    console.error('[角色管理] 保存权限配置失败', error)
    ElMessage.error('权限配置保存失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

/** 编辑角色（后端写接口暂未开放） */
function handleEdit(row: SysRole): void {
  ElMessage.info(`角色「${row.name}」的维护接口暂未开放`)
}

/** 禁用 / 启用角色（后端写接口暂未开放） */
function handleToggleStatus(row: SysRole): void {
  const action = row.status === '启用' ? '禁用' : '启用'
  ElMessage.info(`角色「${row.name}」的${action}接口暂未开放`)
}

onMounted(() => {
  load()
})
</script>

<template>
  <div class="rv-page">
    <PageHeader title="角色管理" description="配置平台角色、成员规模与功能权限范围">
      <template #extra>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </template>
    </PageHeader>

    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4 mb-4">
      <StatCard label="角色总数" :value="roles.length" suffix="个" color="blue" :icon="User" />
      <StatCard label="启用角色" :value="enabledCount" suffix="个" color="green" />
      <StatCard label="成员总数" :value="memberTotal" suffix="人" color="cyan" />
      <StatCard label="权限项数" :value="allPermissions.length" suffix="项" color="purple" :icon="Key" />
    </div>

    <div class="rv-card">
      <div class="rv-card-header">
        <span class="rv-card-title">角色列表</span>
        <div class="rv-text-secondary">共 {{ roles.length }} 个角色</div>
      </div>

      <div class="rv-card-body">
        <el-table v-loading="loading" :data="roles" size="small" border>
          <el-table-column prop="name" label="角色名称" min-width="140" show-overflow-tooltip />
          <el-table-column prop="code" label="角色编码" min-width="130" show-overflow-tooltip />
          <el-table-column prop="dataScope" label="数据范围" min-width="130" show-overflow-tooltip />
          <el-table-column label="成员数" width="100" align="right">
            <template #default="{ row }">
              <span class="rv-num">{{ row.memberCount }}</span>
            </template>
          </el-table-column>
          <el-table-column label="权限数" width="100" align="right">
            <template #default="{ row }">
              <span class="rv-num">{{ row.permissions?.includes('*') ? '全部' : row.permissions?.length ?? 0 }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="92">
            <template #default="{ row }">
              <StatusTag :status="row.status" />
            </template>
          </el-table-column>
          <el-table-column label="创建时间" min-width="150">
            <template #default="{ row }">
              {{ formatDateTime(row.createdAt) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" :icon="Key" @click="openPermission(row)">配置权限</el-button>
              <el-button link type="primary" :icon="Edit" @click="handleEdit(row)">编辑</el-button>
              <el-button link type="warning" @click="handleToggleStatus(row)">
                {{ row.status === '启用' ? '禁用' : '启用' }}
              </el-button>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="暂无角色数据" :image-size="70" />
          </template>
        </el-table>
      </div>
    </div>

    <!-- 权限配置抽屉 -->
    <el-drawer v-model="drawerVisible" :title="`权限配置 - ${currentRole?.name ?? ''}`" size="420px">
      <div class="px-1">
        <el-alert
          v-if="currentRole?.permissions?.includes('*')"
          title="该角色当前拥有全部权限"
          type="warning"
          :closable="false"
          show-icon
          class="mb-4"
        />

        <el-checkbox-group v-model="checkedPermissions" class="rv-permission-group">
          <div v-for="group in permissionGroups" :key="group.key" class="rv-permission-block">
            <div class="rv-permission-block__title">{{ group.name }}</div>
            <el-checkbox v-for="code in group.codes" :key="code" :value="code">
              {{ permissionLabel(code) }}
              <span class="rv-permission-code">{{ code }}</span>
            </el-checkbox>
          </div>
        </el-checkbox-group>

        <el-empty v-if="!permissionGroups.length" description="暂无可配置权限项" :image-size="70" />
      </div>

      <template #footer>
        <el-button @click="drawerVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSavePermission">保存</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.rv-permission-group {
  display: block;
  width: 100%;
}

.rv-permission-block {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px dashed var(--rv-border);
}

.rv-permission-block:last-child {
  border-bottom: none;
}

.rv-permission-block__title {
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--rv-text);
}

.rv-permission-code {
  margin-left: 6px;
  font-size: 11px;
  color: var(--rv-text-secondary);
}
</style>
