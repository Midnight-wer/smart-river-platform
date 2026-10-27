<script setup lang="ts">
/**
 * 顶部工具栏：折叠、面包屑、全屏、主题与用户菜单
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, Expand, Fold, FullScreen, Moon, Sunny } from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const userStore = useUserStore()

const fullscreen = ref(false)

const breadcrumbs = computed(() => {
  const matched = route.matched.filter((item) => item.meta?.title)
  return matched.map((item) => ({ title: item.meta.title as string, path: item.path }))
})

function toggleFullscreen(): void {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen?.().catch(() => ElMessage.warning('当前浏览器不支持全屏'))
    fullscreen.value = true
  } else {
    document.exitFullscreen?.().catch(() => undefined)
    fullscreen.value = false
  }
}

function onFullscreenChange(): void {
  fullscreen.value = Boolean(document.fullscreenElement)
}

function openLargeScreen(): void {
  router.push('/large-screen')
}

async function handleCommand(command: string): Promise<void> {
  if (command === 'logout') {
    try {
      await ElMessageBox.confirm('确定要退出登录吗？', '退出确认', {
        type: 'warning',
        confirmButtonText: '确定退出',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }
    await userStore.logoutAction()
    ElMessage.success('已安全退出')
    router.push({ path: '/login' })
    return
  }
  if (command === 'profile') {
    ElMessage.info(`当前角色：${userStore.userInfo?.roleName ?? '-'}，所属区域：${userStore.userInfo?.regionName ?? '-'}`)
  }
}

onMounted(() => {
  document.addEventListener('fullscreenchange', onFullscreenChange)
})

onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
})
</script>

<template>
  <header class="rv-header">
    <div class="rv-header__left">
      <el-icon class="rv-header__toggle" @click="appStore.toggleSidebar()">
        <component :is="appStore.sidebarCollapsed ? Expand : Fold" />
      </el-icon>

      <el-breadcrumb separator="/">
        <el-breadcrumb-item v-for="(item, index) in breadcrumbs" :key="item.path">
          <span :class="{ 'is-last': index === breadcrumbs.length - 1 }">{{ item.title }}</span>
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <div class="rv-header__right">
      <el-button link type="primary" @click="openLargeScreen">
        <el-icon><FullScreen /></el-icon>
        <span class="rv-header__btn-text">数据大屏</span>
      </el-button>

      <el-tooltip :content="appStore.theme === 'dark' ? '切换浅色模式' : '切换深色模式'" placement="bottom">
        <el-icon class="rv-header__icon" @click="appStore.setTheme(appStore.theme === 'dark' ? 'light' : 'dark')">
          <component :is="appStore.theme === 'dark' ? Sunny : Moon" />
        </el-icon>
      </el-tooltip>

      <el-tooltip content="全屏" placement="bottom">
        <el-icon class="rv-header__icon" @click="toggleFullscreen"><FullScreen /></el-icon>
      </el-tooltip>

      <el-dropdown trigger="click" @command="handleCommand">
        <div class="rv-header__user">
          <el-avatar :size="30" class="rv-header__avatar">
            {{ (userStore.userInfo?.name ?? '用').charAt(0) }}
          </el-avatar>
          <div class="rv-header__user-info">
            <span class="rv-header__user-name">{{ userStore.userInfo?.name ?? '未登录' }}</span>
            <span class="rv-header__user-role">{{ userStore.userInfo?.roleName ?? '-' }}</span>
          </div>
          <el-icon><ArrowDown /></el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">个人信息</el-dropdown-item>
            <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<style scoped>
.rv-header {
  height: 60px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 18px;
  background: var(--rv-surface);
  border-bottom: 1px solid var(--rv-border);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
}

.rv-header__left,
.rv-header__right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.rv-header__toggle {
  font-size: 19px;
  cursor: pointer;
  color: #475569;
  transition: color 0.2s ease;
}

.rv-header__toggle:hover {
  color: var(--rv-primary);
}

.rv-header__icon {
  font-size: 18px;
  cursor: pointer;
  color: #475569;
}

.rv-header__icon:hover {
  color: var(--rv-primary);
}

.rv-header__user {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  outline: none;
}

.rv-header__avatar {
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  color: #fff;
  font-weight: 600;
}

.rv-header__user-info {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
}

.rv-header__user-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--rv-text);
}

.rv-header__user-role {
  font-size: 11px;
  color: var(--rv-text-secondary);
}

@media (max-width: 900px) {
  .rv-header__btn-text,
  .rv-header__user-info {
    display: none;
  }
}
</style>
