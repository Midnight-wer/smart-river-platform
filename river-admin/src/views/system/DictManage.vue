<script setup lang="ts">
/**
 * 数据字典：按字典类型分组维护字典项
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Document, Edit, Plus, Refresh } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { fetchDicts } from '@/api/system'
import type { DictItem } from '@/types'

const DICT_STATUS_OPTIONS: DictItem['status'][] = ['启用', '停用']

const loading = ref(false)
const dicts = ref<DictItem[]>([])
const activeType = ref('')

/** 新增 / 编辑字典项弹窗 */
const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const isEdit = ref(false)

const form = reactive({
  id: '',
  label: '',
  value: '',
  sort: 1,
  status: '启用' as DictItem['status'],
})

const rules: FormRules = {
  label: [{ required: true, message: '请输入字典标签', trigger: 'blur' }],
  value: [{ required: true, message: '请输入字典键值', trigger: 'blur' }],
}

/** 字典类型列表（按 type 聚合） */
const dictTypes = computed<{ type: string; typeLabel: string; count: number }[]>(() => {
  const map = new Map<string, { type: string; typeLabel: string; count: number }>()
  dicts.value.forEach((item) => {
    const exist = map.get(item.type)
    if (exist) {
      exist.count += 1
    } else {
      map.set(item.type, { type: item.type, typeLabel: item.typeLabel, count: 1 })
    }
  })
  return Array.from(map.values())
})

/** 当前类型下的字典项 */
const currentItems = computed<DictItem[]>(() => dicts.value.filter((item) => item.type === activeType.value))

/** 当前类型名称 */
const currentTypeLabel = computed(() => dictTypes.value.find((item) => item.type === activeType.value)?.typeLabel ?? '-')

/** 加载字典数据 */
async function load(): Promise<void> {
  loading.value = true
  try {
    const result = await fetchDicts()
    dicts.value = result ?? []
    if (!dicts.value.some((item) => item.type === activeType.value)) {
      activeType.value = dictTypes.value[0]?.type ?? ''
    }
  } catch (error) {
    console.error('[数据字典] 字典数据加载失败', error)
    ElMessage.error('字典数据加载失败')
    dicts.value = []
  } finally {
    loading.value = false
  }
}

/** 切换字典类型 */
function handleSelectType(type: string): void {
  activeType.value = type
}

/** 打开新增字典项弹窗 */
function openCreate(): void {
  if (!activeType.value) {
    ElMessage.warning('请先选择左侧字典类型')
    return
  }
  isEdit.value = false
  form.id = ''
  form.label = ''
  form.value = ''
  form.sort = currentItems.value.length + 1
  form.status = '启用'
  dialogVisible.value = true
}

/** 打开编辑字典项弹窗 */
function openEdit(row: DictItem): void {
  isEdit.value = true
  form.id = row.id
  form.label = row.label
  form.value = row.value
  form.sort = row.sort
  form.status = row.status
  dialogVisible.value = true
}

/** 提交字典项（后端写接口暂未开放） */
async function handleSubmit(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    ElMessage.info('字典维护接口暂未开放')
    dialogVisible.value = false
  } catch (error) {
    console.error('[数据字典] 保存字典项失败', error)
    ElMessage.error('保存字典项失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

/** 停用 / 启用字典项（后端写接口暂未开放） */
function handleToggleStatus(row: DictItem): void {
  ElMessage.info('字典维护接口暂未开放')
}

onMounted(() => {
  load()
})
</script>

<template>
  <div class="rv-page">
    <PageHeader title="数据字典" description="统一维护平台各类枚举字典，保障前后端取值口径一致">
      <template #extra>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
        <el-button type="primary" :icon="Plus" :disabled="!activeType" @click="openCreate">新增字典项</el-button>
      </template>
    </PageHeader>

    <div class="grid grid-cols-1 gap-4 lg:grid-cols-4">
      <!-- 字典类型列表 -->
      <div class="rv-card lg:col-span-1">
        <div class="rv-card-header">
          <span class="rv-card-title">字典类型</span>
          <div class="rv-text-secondary">共 {{ dictTypes.length }} 类</div>
        </div>
        <div class="rv-card-body" v-loading="loading">
          <el-scrollbar max-height="520px">
            <div
              v-for="item in dictTypes"
              :key="item.type"
              class="rv-dict-type"
              :class="{ 'is-active': item.type === activeType }"
              @click="handleSelectType(item.type)"
            >
              <el-icon class="rv-dict-type__icon"><Document /></el-icon>
              <div class="rv-dict-type__body">
                <div class="rv-dict-type__label">{{ item.typeLabel }}</div>
                <div class="rv-dict-type__code">{{ item.type }}</div>
              </div>
              <span class="rv-dict-type__count rv-num">{{ item.count }}</span>
            </div>
            <el-empty v-if="!dictTypes.length && !loading" description="暂无字典类型" :image-size="70" />
          </el-scrollbar>
        </div>
      </div>

      <!-- 字典项列表 -->
      <div class="rv-card lg:col-span-3">
        <div class="rv-card-header">
          <span class="rv-card-title">{{ currentTypeLabel }} · 字典项</span>
          <div class="flex items-center gap-2">
            <el-button :icon="Plus" :disabled="!activeType" @click="openCreate">新增字典项</el-button>
          </div>
        </div>
        <div class="rv-card-body">
          <el-table v-loading="loading" :data="currentItems" size="small" border>
            <el-table-column prop="label" label="标签" min-width="160" show-overflow-tooltip />
            <el-table-column prop="value" label="键值" min-width="180" show-overflow-tooltip />
            <el-table-column prop="typeLabel" label="所属类型" min-width="140" show-overflow-tooltip />
            <el-table-column label="排序" width="90" align="right">
              <template #default="{ row }">
                <span class="rv-num">{{ row.sort }}</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="92">
              <template #default="{ row }">
                <StatusTag :status="row.status" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" :icon="Edit" @click="openEdit(row)">编辑</el-button>
                <el-button link type="warning" @click="handleToggleStatus(row)">
                  {{ row.status === '启用' ? '停用' : '启用' }}
                </el-button>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty description="暂无字典项" :image-size="70" />
            </template>
          </el-table>
        </div>
      </div>
    </div>

    <!-- 新增 / 编辑字典项弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑字典项' : '新增字典项'" width="460px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="88px">
        <el-form-item label="所属类型">
          <el-input :model-value="currentTypeLabel" disabled />
        </el-form-item>
        <el-form-item label="标签" prop="label">
          <el-input v-model="form.label" placeholder="请输入字典标签" clearable />
        </el-form-item>
        <el-form-item label="键值" prop="value">
          <el-input v-model="form.value" placeholder="请输入字典键值" clearable />
        </el-form-item>
        <el-form-item label="排序序号">
          <el-input-number v-model="form.sort" :min="1" :max="999" controls-position="right" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio v-for="item in DICT_STATUS_OPTIONS" :key="item" :value="item">{{ item }}</el-radio>
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

<style scoped>
.rv-dict-type {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  margin-bottom: 6px;
  border: 1px solid var(--rv-border);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.18s ease;
}

.rv-dict-type:hover {
  border-color: #93c5fd;
  background: var(--rv-primary-soft);
}

.rv-dict-type.is-active {
  border-color: var(--rv-primary);
  background: var(--rv-primary-soft);
}

.rv-dict-type__icon {
  color: var(--rv-primary);
  flex-shrink: 0;
}

.rv-dict-type__body {
  flex: 1;
  min-width: 0;
}

.rv-dict-type__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--rv-text);
}

.rv-dict-type__code {
  font-size: 11px;
  color: var(--rv-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rv-dict-type__count {
  font-size: 12px;
  color: var(--rv-text-secondary);
  flex-shrink: 0;
}
</style>
