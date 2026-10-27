<script setup lang="ts">
/**
 * 后台主布局：左侧导航 + 顶部工具栏 + 内容区
 */
import { useAppStore } from '@/stores/app'
import AppSidebar from './components/AppSidebar.vue'
import AppHeader from './components/AppHeader.vue'

const appStore = useAppStore()
</script>

<template>
  <div class="rv-layout">
    <AppSidebar />
    <div class="rv-main" :class="{ 'is-collapsed': appStore.sidebarCollapsed }">
      <AppHeader />
      <section class="rv-content">
        <router-view v-slot="{ Component, route }">
          <transition name="fade-slide" mode="out-in">
            <keep-alive :max="12">
              <component :is="Component" :key="route.fullPath" />
            </keep-alive>
          </transition>
        </router-view>
      </section>
    </div>
  </div>
</template>

<style scoped>
.rv-layout {
  display: flex;
  height: 100%;
  overflow: hidden;
}

.rv-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  transition: margin 0.22s ease;
}

.rv-content {
  flex: 1;
  min-height: 0;
  overflow: auto;
  background: var(--rv-bg);
}
</style>
