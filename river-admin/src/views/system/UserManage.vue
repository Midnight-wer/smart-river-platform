<script setup lang="ts">
/**
 * 用户管理：系统账号的查询、新增、编辑与删除
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Delete, Edit, Key, Plus, Refresh, Search } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useTable } from '@/composables/useTable'
import { createUser, deleteUser, fetchOrgs, fetchRoles, fetchUsers, updateUser } from '@/api/system'
import { useUserStore } from '@/stores/user'
import { formatDateTime } from '@/utils/format'
import type { SysOrg, SysRole, SysUser } from '@/types'

const USER_STATUS_OPTIONS: SysUser['status'][] = ['启用', '禁用']

const userStore = useUserStore()

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
  refresh,
} = useTable(fetchUsers, { status: '' })

/** 角色与部门下拉选项 */
const roleOptions = ref<SysRole[]>([])
const orgOptions = ref<SysOrg[]>([])

/** 新增 / 编辑弹窗 */
const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const isEdit = ref(false)

const form = reactive({
  id: '',
  username: '',
  name: '',
  roleName: '',
  orgName: '',
  phone: '',
  status: '启用' as SysUser['status'],
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  roleName: [{ required: true, message: '请选择角色', trigger: 'change' }],
  orgName: [{ required: true, message: '请选择所属部门', trigger: 'change' }],
  phone: [{ pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' }],
}

/** 加载角色、部门下拉数据 */
async function loadOptions(): Promise<void> {
  try {
    const [roles, orgs] = await Promise.all([fetchRoles(), fetchOrgs()])
    roleOptions.value = roles ?? []
    orgOptions.value = orgs ?? []
  } catch (error) {
    console.error('[用户管理] 角色部门选项加载失败', error)
    ElMessage.error('角色部门选项加载失败')
    roleOptions.value = []
    orgOptions.value = []
  }
}

/** 打开新增弹窗 */
function openCreate(): void {
  isEdit.value = false
  form.id = ''
  form.username = ''
  form.name = ''
  form.roleName = ''
  form.orgName = ''
  form.phone = ''
  form.status = '启用'
  dialogVisible.value = true
}

/** 打开编辑弹窗 */
function openEdit(row: SysUser): void {
  isEdit.value = true
  form.id = row.id
  form.username = row.username
  form.name = row.name
  form.roleName = row.roleName
  form.orgName = row.orgName
  form.phone = row.phone
  form.status = row.status
  dialogVisible.value = true
}

/** 提交表单 */
async function handleSubmit(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (isEdit.value) {
      await updateUser(form.id, {
        username: form.username,
        name: form.name,
        roleName: form.roleName,
        orgName: form.orgName,
        phone: form.phone,
        status: form.status,
      })
      ElMessage.success('用户信息已更新')
    } else {
      await createUser({
        username: form.username,
        name: form.name,
        roleName: form.roleName,
        orgName: form.orgName,
        phone: form.phone,
        status: form.status,
      })
      ElMessage.success('用户创建成功')
    }
    dialogVisible.value = false
    await load()
  } catch (error) {
    console.error('[用户管理] 保存用户失败', error)
    ElMessage.error('保存用户失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

/** 重置密码（后端暂未开放该能力） */
function handleResetPassword(row: SysUser): void {
  ElMessage.info(`密码重置接口暂未开放，请联系管理员处理「${row.name}」的账号`)
}

/** 删除用户 */
async function handleDelete(row: SysUser): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除用户「${row.name}（${row.username}）」吗？删除后不可恢复。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  try {
    await deleteUser(row.id)
    ElMessage.success('用户已删除')
    await load()
  } catch (error) {
    console.error('[用户管理] 删除用户失败', error)
    ElMessage.error('删除用户失败，请稍后重试')
  }
}

onMounted(() => {
  load()
  loadOptions()
})
</script>

<template>
  <div class="rv-page">
    <PageHeader title="用户管理" description="维护系统登录账号、所属角色与部门信息">
      <template #extra>
        <el-button :icon="Refresh" @click="refresh">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新增用户</el-button>
      </template>
    </PageHeader>

    <div class="rv-card">
      <div class="rv-card-header">
        <span class="rv-card-title">用户列表</span>
        <div class="flex items-center gap-2">
          <el-input
            v-model="query.keyword"
            placeholder="用户名 / 姓名 / 手机号"
            clearable
            class="!w-56"
            @keyup.enter="search"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-select v-model="query.status" placeholder="账号状态" clearable class="!w-32">
            <el-option v-for="item in USER_STATUS_OPTIONS" :key="item" :label="item" :value="item" />
          </el-select>
          <el-button type="primary" @click="search">查询</el-button>
          <el-button @click="reset">重置</el-button>
        </div>
      </div>

      <div class="rv-card-body">
        <el-table v-loading="loading" :data="list" size="small" border>
          <el-table-column prop="username" label="用户名" min-width="120" show-overflow-tooltip />
          <el-table-column prop="name" label="姓名" min-width="100" show-overflow-tooltip />
          <el-table-column prop="roleName" label="角色" min-width="120" show-overflow-tooltip />
          <el-table-column prop="orgName" label="部门" min-width="180" show-overflow-tooltip />
          <el-table-column prop="phone" label="手机号" width="130" />
          <el-table-column label="状态" width="92">
            <template #default="{ row }">
              <StatusTag :status="row.status" />
            </template>
          </el-table-column>
          <el-table-column label="最后登录时间" min-width="150">
            <template #default="{ row }">
              {{ formatDateTime(row.lastLoginAt) }}
            </template>
          </el-table-column>
          <el-table-column label="创建时间" min-width="150">
            <template #default="{ row }">
              {{ formatDateTime(row.createdAt) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" :icon="Edit" @click="openEdit(row)">编辑</el-button>
              <el-button link type="warning" :icon="Key" @click="handleResetPassword(row)">重置密码</el-button>
              <el-button
                v-if="userStore.hasPermission('system:user:delete')"
                link
                type="danger"
                :icon="Delete"
                @click="handleDelete(row)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="暂无用户数据" :image-size="70" />
          </template>
        </el-table>

        <el-pagination
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          :page-size="query.pageSize"
          :current-page="query.page"
          :page-sizes="[10, 20, 50, 100]"
          @size-change="changePageSize"
          @current-change="changePage"
        />
      </div>
    </div>

    <!-- 新增 / 编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑用户' : '新增用户'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入登录用户名" :disabled="isEdit" clearable />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" placeholder="请输入真实姓名" clearable />
        </el-form-item>
        <el-form-item label="角色" prop="roleName">
          <el-select v-model="form.roleName" placeholder="请选择角色" class="w-full" clearable>
            <el-option v-for="item in roleOptions" :key="item.id" :label="item.name" :value="item.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="部门" prop="orgName">
          <el-select v-model="form.orgName" placeholder="请选择所属部门" class="w-full" clearable filterable>
            <el-option v-for="item in orgOptions" :key="item.id" :label="item.name" :value="item.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="请输入手机号" clearable />
        </el-form-item>
        <el-form-item label="账号状态" prop="status">
          <el-radio-group v-model="form.status">
            <el-radio v-for="item in USER_STATUS_OPTIONS" :key="item" :value="item">{{ item }}</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
