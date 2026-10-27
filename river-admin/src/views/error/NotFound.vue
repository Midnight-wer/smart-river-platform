<script setup lang="ts">
/**
 * 404 页面
 */
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="rv-notfound">
    <div class="rv-notfound__code">404</div>
    <p class="rv-notfound__text">抱歉，您访问的页面不存在或已被移除</p>
    <el-button type="primary" @click="router.replace('/dashboard')">返回工作台</el-button>
  </div>
</template>

<style scoped>
.rv-notfound {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: var(--rv-bg);
}

.rv-notfound__code {
  font-size: 84px;
  font-weight: 700;
  color: #cbd5e1;
  line-height: 1;
}

.rv-notfound__text {
  margin: 0 0 8px;
  color: var(--rv-text-secondary);
}
</style>
