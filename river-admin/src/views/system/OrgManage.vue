<script setup lang="ts">
/**
 * 组织架构：以树形结构展示各级河长制办公室，并查看部门详情
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Edit, OfficeBuilding, Plus, Refresh } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { fetchOrgs } from '@/api/system'
import { defaultText } from '@/utils/format'
import type { SysOrg } from '@/types'

/** 树节点：在部门信息基础上补充子节点 */
interface OrgTreeNode extends SysOrg {
  children: OrgTreeNode[]
}

const loading = ref(false)
const orgList = ref<SysOrg[]>([])
const selected = ref<SysOrg | null>(null)

/** 新增子部门弹窗 */
const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const parentName = ref('')

const form = reactive({
  name: '',
  code: '',
  leader: '',
  phone: '',
  sort: 1,
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入部门名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入部门编码', trigger: 'blur' }],
  leader: [{ required: true, message: '请输入负责人', trigger: 'blur' }],
}

/** 依据 parentName 匹配上级部门名称构建层级树 */
const treeData = computed<OrgTreeNode[]>(() => {
  const nameToId = new Map<string, string>()
  orgList.value.forEach((item) => nameToId.set(item.name, item.id))

  const nodeMap = new Map<string, OrgTreeNode>()
  orgList.value.forEach((item) => {
    nodeMap.set(item.id, { ...item, children: [] })
  })

  const roots: OrgTreeNode[] = []
  nodeMap.forEach((node) => {
    const parentId = node.parentName ? nameToId.get(node.parentName) : undefined
    const parent = parentId ? nodeMap.get(parentId) : undefined
    if (parent && parent.id !== node.id) {
      parent.children.push(node)
    } else {
      roots.push(node)
    }
  })

  return roots
})

/** 统计信息 */
const totalCount = computed(() => orgList.value.length)
const memberTotal = computed(() => orgList.value.reduce((sum, item) => sum + (item.memberCount || 0), 0))

/** 加载组织架构数据 */
async function load(): Promise<void> {
  loading.value = true
  try {
    const result = await fetchOrgs()
    orgList.value = result ?? []
    if (selected.value) {
      selected.value = orgList.value.find((item) => item.id === selected.value?.id) ?? null
    }
  } catch (error) {
    console.error('[组织架构] 部门列表加载失败', error)
    ElMessage.error('部门列表加载失败')
    orgList.value = []
  } finally {
    loading.value = false
  }
}

/** 选中节点 */
function handleNodeClick(data: OrgTreeNode): void {
  selected.value = data
}

/** 打开新增弹窗 */
function openCreate(parent: string): void {
  parentName.value = parent
  form.name = ''
  form.code = ''
  form.leader = ''
  form.phone = ''
  form.sort = 1
  dialogVisible.value = true
}

/** 新增子部门 */
function openCreateChild(): void {
  if (!selected.value) {
    ElMessage.warning('请先选择上级部门')
    return
  }
  openCreate(selected.value.name)
}

/** 提交新增子部门（后端写接口暂未开放） */
async function handleSubmit(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    ElMessage.info('组织维护接口暂未开放')
    dialogVisible.value = false
  } catch (error) {
    console.error('[组织架构] 新增子部门失败', error)
    ElMessage.error('新增子部门失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

/** 编辑部门（后端写接口暂未开放） */
function handleEdit(): void {
  if (!selected.value) {
    ElMessage.warning('请先选择部门')
    return
  }
  ElMessage.info('组织维护接口暂未开放')
}

/** 删除部门（后端写接口暂未开放） */
function handleDelete(): void {
  if (!selected.value) {
    ElMessage.warning('请先选择部门')
    return
  }
  ElMessage.info('组织维护接口暂未开放')
}

onMounted(() => {
  load()
})
</script>

<template>
  <div class="rv-page">
    <PageHeader title="组织架构" description="展示省、市、县、乡镇各级河长制办公室的层级关系与人员构成">
      <template #extra>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
        <el-button :icon="Plus" @click="openCreate('')">新增部门</el-button>
        <el-button type="primary" :icon="Plus" :disabled="!selected" @click="openCreateChild">新增子部门</el-button>
      </template>
    </PageHeader>

    <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <!-- 部门树 -->
      <div class="rv-card lg:col-span-1">
        <div class="rv-card-header">
          <span class="rv-card-title">部门树</span>
          <div class="flex items-center gap-3 rv-text-secondary">
            <span>共 {{ totalCount }} 个部门</span>
            <span>在编 {{ memberTotal }} 人</span>
          </div>
        </div>
        <div class="rv-card-body" v-loading="loading">
          <el-tree
            :data="treeData"
            node-key="id"
            :props="{ label: 'name', children: 'children' }"
            default-expand-all
            highlight-current
            class="rv-org-tree"
            @node-click="handleNodeClick"
          >
            <template #default="{ data }">
              <div class="rv-org-node">
                <span class="rv-org-node__name">{{ data.name }}</span>
                <span class="rv-org-node__meta">{{ data.leader }} · {{ data.memberCount }} 人</span>
              </div>
            </template>
          </el-tree>
        </div>
      </div>

      <!-- 部门详情 -->
      <div class="rv-card lg:col-span-2">
        <div class="rv-card-header">
          <span class="rv-card-title">部门详情</span>
          <div class="flex items-center gap-2">
            <el-button :icon="Edit" :disabled="!selected" @click="handleEdit">编辑</el-button>
            <el-button type="danger" :disabled="!selected" @click="handleDelete">删除</el-button>
          </div>
        </div>
        <div class="rv-card-body">
          <el-descriptions v-if="selected" :column="2" border>
            <el-descriptions-item label="部门名称">
              <span class="flex items-center gap-2">
                <el-icon color="#1d4ed8"><OfficeBuilding /></el-icon>
                {{ selected.name }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="部门编码">{{ defaultText(selected.code) }}</el-descriptions-item>
            <el-descriptions-item label="上级部门">{{ defaultText(selected.parentName, '顶级部门') }}</el-descriptions-item>
            <el-descriptions-item label="负责人">{{ defaultText(selected.leader) }}</el-descriptions-item>
            <el-descriptions-item label="联系电话">{{ defaultText(selected.phone) }}</el-descriptions-item>
            <el-descriptions-item label="排序序号">{{ selected.sort }}</el-descriptions-item>
            <el-descriptions-item label="部门人数">{{ selected.memberCount }} 人</el-descriptions-item>
            <el-descriptions-item label="状态">
              <StatusTag :status="selected.status" />
            </el-descriptions-item>
          </el-descriptions>

          <el-empty v-else description="请选择左侧部门查看详细信息" :image-size="90" />
        </div>
      </div>
    </div>

    <!-- 新增子部门弹窗 -->
    <el-dialog v-model="dialogVisible" title="新增子部门" width="480px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="88px">
        <el-form-item label="上级部门">
          <el-input :model-value="parentName" disabled />
        </el-form-item>
        <el-form-item label="部门名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入部门名称" clearable />
        </el-form-item>
        <el-form-item label="部门编码" prop="code">
          <el-input v-model="form.code" placeholder="如 SC-ORG-0011" clearable />
        </el-form-item>
        <el-form-item label="负责人" prop="leader">
          <el-input v-model="form.leader" placeholder="请输入负责人姓名" clearable />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="form.phone" placeholder="请输入联系电话" clearable />
        </el-form-item>
        <el-form-item label="排序序号">
          <el-input-number v-model="form.sort" :min="1" :max="999" controls-position="right" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.rv-org-node {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  padding-right: 8px;
}

.rv-org-node__name {
  font-size: 13px;
  color: var(--rv-text);
}

.rv-org-node__meta {
  font-size: 12px;
  color: var(--rv-text-secondary);
  white-space: nowrap;
}

:deep(.rv-org-tree .el-tree-node__content) {
  height: 34px;
}
</style>
