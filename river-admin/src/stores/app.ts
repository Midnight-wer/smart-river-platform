import { defineStore } from 'pinia'
import { ref } from 'vue'

const APP_STATE_KEY = 'river_admin_app_state'

/**
 * 全局应用状态：侧边栏折叠、主题等
 * 使用 pinia-plugin-persistedstate 持久化。
 */
export const useAppStore = defineStore(
  'app',
  () => {
    const sidebarCollapsed = ref(false)
    const theme = ref<'light' | 'dark'>('light')
    const activeMenu = ref<string>('')

    function toggleSidebar(): void {
      sidebarCollapsed.value = !sidebarCollapsed.value
    }

    function setTheme(value: 'light' | 'dark'): void {
      theme.value = value
      document.documentElement.classList.toggle('dark', value === 'dark')
    }

    function setActiveMenu(path: string): void {
      activeMenu.value = path
    }

    return { sidebarCollapsed, theme, activeMenu, toggleSidebar, setTheme, setActiveMenu }
  },
  {
    persist: {
      key: APP_STATE_KEY,
      storage: localStorage,
    },
  },
)
