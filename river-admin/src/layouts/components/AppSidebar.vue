<script setup lang="ts">
/**
 * 侧边导航：按当前用户权限过滤菜单
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'
import { menus } from '@/router/menus'
import type { MenuItem } from '@/types'

const route = useRoute()
const appStore = useAppStore()
const userStore = useUserStore()

/** 依据权限过滤菜单树 */
const visibleMenus = computed<MenuItem[]>(() => {
  const filter = (list: MenuItem[]): MenuItem[] => {
    const result: MenuItem[] = []
    for (const item of list) {
      const children = item.children ? filter(item.children) : undefined
      const permitted = !item.permission || userStore.hasPermission(item.permission)
      if (!permitted && (!children || children.length === 0)) continue
      result.push({ ...item, children })
    }
    return result
  }
  return filter(menus)
})

const activeMenu = computed(() => (route.meta.activeMenu as string) || route.path)
</script>

<template>
  <aside class="rv-sidebar" :class="{ 'is-collapsed': appStore.sidebarCollapsed }">
    <div class="rv-sidebar__logo">
      <span class="rv-sidebar__mark">智</span>
      <span v-show="!appStore.sidebarCollapsed" class="rv-sidebar__title">智慧河长协同治理平台</span>
    </div>

    <el-scrollbar class="rv-sidebar__scroll">
      <el-menu
        :default-active="activeMenu"
        :collapse="appStore.sidebarCollapsed"
        :collapse-transition="false"
        router
        class="rv-sidebar__menu"
      >
        <template v-for="item in visibleMenus" :key="item.index">
          <el-sub-menu v-if="item.children && item.children.length" :index="item.index">
            <template #title>
              <el-icon v-if="item.icon"><component :is="item.icon" /></el-icon>
              <span>{{ item.title }}</span>
            </template>
            <el-menu-item v-for="child in item.children" :key="child.index" :index="child.index">
              <el-icon v-if="child.icon"><component :is="child.icon" /></el-icon>
              <span>{{ child.title }}</span>
            </el-menu-item>
          </el-sub-menu>

          <el-menu-item v-else :index="item.index">
            <el-icon v-if="item.icon"><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-scrollbar>
  </aside>
</template>

<style scoped>
.rv-sidebar {
  width: 232px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #0f2f6b 0%, #0b2557 100%);
  color: #fff;
  transition: width 0.22s ease;
  overflow: hidden;
}

.rv-sidebar.is-collapsed {
  width: 64px;
}

.rv-sidebar__logo {
  height: 60px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}

.rv-sidebar__mark {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  flex-shrink: 0;
}

.rv-sidebar__title {
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
}

.rv-sidebar__scroll {
  flex: 1;
  min-height: 0;
}

.rv-sidebar__menu {
  border-right: none;
  background: transparent;
}

.rv-sidebar__menu :deep(.el-menu-item),
.rv-sidebar__menu :deep(.el-sub-menu__title) {
  color: rgba(255, 255, 255, 0.78);
  height: 44px;
  line-height: 44px;
}

.rv-sidebar__menu :deep(.el-menu-item:hover),
.rv-sidebar__menu :deep(.el-sub-menu__title:hover) {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.rv-sidebar__menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, #2563eb, #1d4ed8);
  color: #fff;
}

.rv-sidebar__menu :deep(.el-menu--inline) {
  background: rgba(0, 0, 0, 0.16);
}

.rv-sidebar__menu :deep(.el-menu--inline .el-menu-item) {
  padding-left: 46px !important;
}
</style>
