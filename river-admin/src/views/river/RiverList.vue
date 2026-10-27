<script setup lang="ts">
/**
 * 河道档案列表
 * 提供河道档案的检索、新增、编辑与删除能力。
 */
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Delete, Edit, Plus, Refresh, Search, View } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useTable } from '@/composables/useTable'
import { createRiver, deleteRiver, fetchRivers, updateRiver } from '@/api/river'
import { defaultText, toNumber } from '@/utils/format'
import type { PageQuery, River } from '@/types'

interface RiverQuery extends PageQuery {
  level: string
  status: string
}

interface RiverForm {
  id: string
  name: string
  code: string
  level: River['level']
  length: number
  basin: string
  region: string
  startPoint: string
  endPoint: string
  chiefName: string
  qualityTarget: string
}

const router = useRouter()

const LEVEL_OPTIONS: River['level'][] = ['省级', '市级', '县级', '乡镇级']
const STATUS_OPTIONS: River['status'][] = ['正常', '预警', '停用']
const QUALITY_TARGETS = ['Ⅰ类', 'Ⅱ类', 'Ⅲ类', 'Ⅳ类']

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
} = useTable<River>(fetchRivers, { level: '', status: '' })

const query = baseQuery as RiverQuery

const dialogVisible = ref(false)
const dialogTitle = ref('新增河道')
const submitting = ref(false)
const formRef = ref<FormInstance>()

const form = reactive<RiverForm>({
  id: '',
  name: '',
  code: '',
  level: '县级',
  length: 0,
  basin: '',
  region: '',
  startPoint: '',
  endPoint: '',
  chiefName: '',
  qualityTarget: 'Ⅲ类',
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入河道名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入河道编码', trigger: 'blur' }],
  level: [{ required: true, message: '请选择河道等级', trigger: 'change' }],
  length: [{ required: true, message: '请输入河道长度', trigger: 'blur' }],
  region: [{ required: true, message: '请输入所属区域', trigger: 'blur' }],
  chiefName: [{ required: true, message: '请输入河长姓名', trigger: 'blur' }],
}

/** 打开弹窗：传入行数据则为编辑 */
function openDialog(row?: River): void {
  if (row) {
    dialogTitle.value = '编辑河道'
    Object.assign(form, {
      id: row.id,
      name: row.name,
      code: row.code,
      level: row.level,
      length: row.length,
      basin: row.basin,
      region: row.region,
      startPoint: row.startPoint,
      endPoint: row.endPoint,
      chiefName: row.chiefName,
      qualityTarget: row.qualityTarget,
    })
  } else {
    dialogTitle.value = '新增河道'
    Object.assign(form, {
      id: '',
      name: '',
      code: '',
      level: '县级',
      length: 0,
      basin: '',
      region: '',
      startPoint: '',
      endPoint: '',
      chiefName: '',
      qualityTarget: 'Ⅲ类',
    })
  }
  dialogVisible.value = true
}

/** 提交新增或编辑 */
async function handleSubmit(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (form.id) {
      await updateRiver(form.id, { ...form })
      ElMessage.success('河道信息更新成功')
    } else {
      await createRiver({ ...form })
      ElMessage.success('河道新增成功')
    }
    dialogVisible.value = false
    await load()
  } catch (error) {
    console.error('[河道档案] 保存失败', error)
    ElMessage.error('保存失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

/** 删除河道 */
async function handleDelete(row: River): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除河道「${row.name}」吗？删除后不可恢复。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteRiver(row.id)
    ElMessage.success('河道已删除')
    await load()
  } catch (error) {
    console.error('[河道档案] 删除失败', error)
    ElMessage.error('删除失败，请稍后重试')
  }
}

/** 跳转河道详情 */
function handleView(row: River): void {
  router.push(`/river/${row.id}`)
}

onMounted(() => {
  load()
})
</script>

<template>
  <div class="rv-page">
    <PageHeader title="河道档案" description="维护辖区河道基础信息、责任人及水质目标">
      <template #extra>
        <el-button type="primary" :icon="Plus" @click="openDialog()">新增河道</el-button>
      </template>
    </PageHeader>

    <!-- 搜索条件 -->
    <div class="rv-card mb-4">
      <div class="rv-card-body">
        <div class="flex flex-wrap items-center gap-3">
          <el-input
            v-model="query.keyword"
            class="!w-64"
            placeholder="河道名称 / 编码 / 河长"
            clearable
            :prefix-icon="Search"
            @keyup.enter="search()"
          />
          <el-select v-model="query.level" class="!w-36" placeholder="河道等级" clearable>
            <el-option v-for="item in LEVEL_OPTIONS" :key="item" :label="item" :value="item" />
          </el-select>
          <el-select v-model="query.status" class="!w-36" placeholder="档案状态" clearable>
            <el-option v-for="item in STATUS_OPTIONS" :key="item" :label="item" :value="item" />
          </el-select>
          <el-button type="primary" :icon="Search" @click="search()">查询</el-button>
          <el-button :icon="Refresh" @click="reset()">重置</el-button>
        </div>
      </div>
    </div>

    <!-- 河道列表 -->
    <div class="rv-card">
      <div class="rv-card-header">
        <span class="rv-card-title">河道列表</span>
        <span class="rv-text-secondary">共 {{ toNumber(total) }} 条</span>
      </div>
      <div class="rv-card-body">
        <el-table v-loading="loading" :data="list" border stripe>
          <el-table-column prop="name" label="河道名称" min-width="130" show-overflow-tooltip />
          <el-table-column prop="code" label="河道编码" min-width="120" show-overflow-tooltip />
          <el-table-column prop="level" label="等级" width="90" align="center">
            <template #default="{ row }">
              <el-tag effect="plain">{{ row.level }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="length" label="长度(km)" width="100" align="right">
            <template #default="{ row }">{{ toNumber(row.length) }}</template>
          </el-table-column>
          <el-table-column prop="basin" label="流域" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">{{ defaultText(row.basin) }}</template>
          </el-table-column>
          <el-table-column prop="region" label="所属区域" width="110" show-overflow-tooltip />
          <el-table-column prop="chiefName" label="河长" width="100">
            <template #default="{ row }">{{ defaultText(row.chiefName) }}</template>
          </el-table-column>
          <el-table-column prop="qualityTarget" label="水质目标" width="100" align="center" />
          <el-table-column label="达标率" min-width="150">
            <template #default="{ row }">
              <el-progress :percentage="row.qualityRate" :stroke-width="10" text-inside />
            </template>
          </el-table-column>
          <el-table-column prop="patrolCount" label="巡查次数" width="100" align="right">
            <template #default="{ row }">{{ toNumber(row.patrolCount) }}</template>
          </el-table-column>
          <el-table-column prop="eventCount" label="事件数" width="90" align="right">
            <template #default="{ row }">{{ toNumber(row.eventCount) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <StatusTag :status="row.status" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="190" fixed="right" align="center">
            <template #default="{ row }">
              <el-button link type="primary" :icon="View" @click="handleView(row)">详情</el-button>
              <el-button link type="primary" :icon="Edit" @click="openDialog(row)">编辑</el-button>
              <el-button link type="danger" :icon="Delete" @click="handleDelete(row)">删除</el-button>
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

    <!-- 新增 / 编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="720px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="河道名称" prop="name">
              <el-input v-model="form.name" placeholder="请输入河道名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="河道编码" prop="code">
              <el-input v-model="form.code" placeholder="请输入河道编码" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="河道等级" prop="level">
              <el-select v-model="form.level" placeholder="请选择河道等级" class="w-full">
                <el-option v-for="item in LEVEL_OPTIONS" :key="item" :label="item" :value="item" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="长度(km)" prop="length">
              <el-input-number v-model="form.length" :min="0" :precision="1" class="!w-full" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属流域" prop="basin">
              <el-input v-model="form.basin" placeholder="请输入所属流域" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属区域" prop="region">
              <el-input v-model="form.region" placeholder="请输入所属区域" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="起点" prop="startPoint">
              <el-input v-model="form.startPoint" placeholder="请输入河道起点" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="终点" prop="endPoint">
              <el-input v-model="form.endPoint" placeholder="请输入河道终点" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="河长姓名" prop="chiefName">
              <el-input v-model="form.chiefName" placeholder="请输入河长姓名" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="水质目标" prop="qualityTarget">
              <el-select v-model="form.qualityTarget" placeholder="请选择水质目标" class="w-full">
                <el-option v-for="item in QUALITY_TARGETS" :key="item" :label="item" :value="item" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
