<script setup lang="ts">
/**
 * 状态标签：根据状态文案自动映射 Element Plus 标签类型
 */
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    status?: string
    size?: 'small' | 'default' | 'large'
  }>(),
  { status: '', size: 'small' },
)

const TYPE_MAP: Record<string, 'success' | 'warning' | 'danger' | 'info' | 'primary'> = {
  正常: 'success',
  在线: 'success',
  启用: 'success',
  在岗: 'success',
  已完成: 'success',
  已办结: 'success',
  已归档: 'success',
  良好: 'success',
  优秀: 'success',
  预警: 'warning',
  警告: 'warning',
  提示: 'warning',
  进行中: 'primary',
  已受理: 'primary',
  已确认: 'primary',
  已派单: 'primary',
  待执行: 'info',
  待处理: 'info',
  待审核: 'info',
  待确认: 'info',
  待提升: 'info',
  离岗: 'info',
  停用: 'info',
  禁用: 'info',
  已关闭: 'info',
  超标: 'danger',
  已逾期: 'danger',
  失败: 'danger',
  严重: 'danger',
  重大: 'danger',
  已驳回: 'danger',
  离线: 'danger',
  维护中: 'warning',
}

const tagType = computed(() => TYPE_MAP[props.status] ?? 'info')
</script>

<template>
  <el-tag :type="tagType" :size="size" effect="light" round>{{ status || '-' }}</el-tag>
</template>
