import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { login as loginApi, fetchProfile, logout as logoutApi } from '@/api/auth'
import type { LoginParams, UserInfo } from '@/types'
import { StorageKey, getStorage, getStorageJSON, removeStorage, setStorage, setStorageJSON } from '@/utils/storage'

/**
 * 用户与权限状态
 * 登录态通过 localStorage 持久化，保证刷新页面后依然有效，
 * 也避免请求拦截器与 Store 之间产生循环依赖。
 */
export const useUserStore = defineStore('user', () => {
  const token = ref<string>(getStorage(StorageKey.TOKEN))
  const userInfo = ref<UserInfo | null>(getStorageJSON<UserInfo | null>(StorageKey.USER_INFO, null))

  /** 是否已登录 */
  const isLogin = computed(() => Boolean(token.value))

  /** 权限编码集合 */
  const permissions = computed<string[]>(() => userInfo.value?.permissions ?? [])

  /** 超级管理员拥有全部权限 */
  const isSuperAdmin = computed(() => userInfo.value?.role === 'super_admin')

  /**
   * 判断是否拥有指定权限
   * @param code 权限编码，如 event:handle
   */
  function hasPermission(code?: string | string[]): boolean {
    if (!code) return true
    if (isSuperAdmin.value) return true
    const list = Array.isArray(code) ? code : [code]
    if (list.length === 0) return true
    return list.some((item) => permissions.value.includes(item))
  }

  /** 登录：获取 token 后拉取用户信息 */
  async function loginAction(params: LoginParams): Promise<void> {
    const result = await loginApi(params)
    token.value = result.token
    setStorage(StorageKey.TOKEN, result.token)

    const profile = await fetchProfile(params.username)
    userInfo.value = profile
    setStorageJSON(StorageKey.USER_INFO, profile)
  }

  /** 重新拉取用户信息 */
  async function loadProfile(username?: string): Promise<UserInfo | null> {
    try {
      const profile = await fetchProfile(username ?? userInfo.value?.username)
      userInfo.value = profile
      setStorageJSON(StorageKey.USER_INFO, profile)
      return profile
    } catch (error) {
      console.error('[user-store] 获取用户信息失败', error)
      return null
    }
  }

  /** 退出登录 */
  async function logoutAction(): Promise<void> {
    try {
      await logoutApi()
    } catch (error) {
      console.warn('[user-store] 退出接口调用失败，仍将清除本地登录态', error)
    } finally {
      resetState()
    }
  }

  /** 清除本地登录态 */
  function resetState(): void {
    token.value = ''
    userInfo.value = null
    removeStorage(StorageKey.TOKEN)
    removeStorage(StorageKey.USER_INFO)
  }

  return {
    token,
    userInfo,
    isLogin,
    permissions,
    isSuperAdmin,
    hasPermission,
    loginAction,
    loadProfile,
    logoutAction,
    resetState,
  }
})
