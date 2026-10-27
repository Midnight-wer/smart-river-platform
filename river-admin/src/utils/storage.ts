/**
 * 本地存储工具：统一处理隐私模式 / 存储配额异常，避免直接访问 localStorage 抛错
 */

const PREFIX = 'river_admin_'

export const StorageKey = {
  TOKEN: `${PREFIX}token`,
  USER_INFO: `${PREFIX}user_info`,
  SIDEBAR: `${PREFIX}sidebar_collapsed`,
} as const

function getStore(): Storage | null {
  try {
    return window.localStorage
  } catch (error) {
    console.warn('[storage] 无法访问 localStorage，已降级为内存存储', error)
    return null
  }
}

const memoryStore = new Map<string, string>()

export function setStorage(key: string, value: string): void {
  const store = getStore()
  if (!store) {
    memoryStore.set(key, value)
    return
  }
  try {
    store.setItem(key, value)
  } catch (error) {
    console.warn(`[storage] 写入 ${key} 失败`, error)
    memoryStore.set(key, value)
  }
}

export function getStorage(key: string): string {
  const store = getStore()
  if (!store) {
    return memoryStore.get(key) ?? ''
  }
  try {
    return store.getItem(key) ?? ''
  } catch (error) {
    console.warn(`[storage] 读取 ${key} 失败`, error)
    return memoryStore.get(key) ?? ''
  }
}

export function removeStorage(key: string): void {
  const store = getStore()
  memoryStore.delete(key)
  if (!store) return
  try {
    store.removeItem(key)
  } catch (error) {
    console.warn(`[storage] 移除 ${key} 失败`, error)
  }
}

/** 读取 JSON 数据，解析失败时返回默认值 */
export function getStorageJSON<T>(key: string, fallback: T): T {
  const raw = getStorage(key)
  if (!raw) return fallback
  try {
    return JSON.parse(raw) as T
  } catch (error) {
    console.warn(`[storage] 解析 ${key} 失败，已返回默认值`, error)
    removeStorage(key)
    return fallback
  }
}

/** 写入 JSON 数据 */
export function setStorageJSON(key: string, value: unknown): void {
  try {
    setStorage(key, JSON.stringify(value))
  } catch (error) {
    console.warn(`[storage] 序列化 ${key} 失败`, error)
  }
}
