<script setup lang="ts">
/**
 * 页面头部：标题、描述与右侧操作区
 */
withDefaults(
  defineProps<{
    title: string
    description?: string
  }>(),
  { description: '' },
)
</script>

<template>
  <div class="rv-page-header">
    <div class="rv-page-header__main">
      <h2 class="rv-page-header__title">{{ title }}</h2>
      <p v-if="description" class="rv-page-header__desc">{{ description }}</p>
    </div>
    <div class="rv-page-header__extra">
      <slot name="extra" />
    </div>
  </div>
</template>

<style scoped>
.rv-page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.rv-page-header__title {
  margin: 0;
  font-size: 19px;
  font-weight: 600;
  color: var(--rv-text);
}

.rv-page-header__desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--rv-text-secondary);
}

.rv-page-header__extra {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
</style>
