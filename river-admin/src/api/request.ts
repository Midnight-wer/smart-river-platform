import axios, { type AxiosInstance, type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import type { ApiResult } from '@/types'
import { StorageKey, getStorage, removeStorage } from '@/utils/storage'
import { mockAdapter } from '@/mock/server'

/**
 * 统一请求封装
 * - 请求拦截：注入 token
 * - 响应拦截：解包业务数据、统一错误提示
 * - 401：清除登录态并跳转登录页
 */

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'
const BASE_URL = import.meta.env.VITE_API_BASE ?? '/api'

const service: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json;charset=UTF-8' },
})

if (USE_MOCK) {
  service.defaults.adapter = mockAdapter
}

service.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getStorage(StorageKey.TOKEN)
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

/** 触发重新登录的回调，由路由/Store 注入，避免此处产生循环依赖 */
let unauthorizedHandler: (() => void) | null = null

export function registerUnauthorizedHandler(handler: () => void): void {
  unauthorizedHandler = handler
}

service.interceptors.response.use(
  (response) => {
    const result = response.data as ApiResult
    if (result && typeof result === 'object' && 'code' in result) {
      if (result.code === 200) {
        return result.data as never
      }
      ElMessage.error(result.message || '请求处理失败')
      return Promise.reject(new Error(result.message || '请求处理失败'))
    }
    return response.data as never
  },
  (error) => {
    const status = error?.response?.status
    const message = (error?.response?.data as ApiResult)?.message || error?.message || '网络异常，请稍后重试'

    if (status === 401) {
      removeStorage(StorageKey.TOKEN)
      removeStorage(StorageKey.USER_INFO)
      ElMessage.warning('登录状态已失效，请重新登录')
      unauthorizedHandler?.()
    } else if (status === 403) {
      ElMessage.error('暂无访问权限，请联系管理员')
    } else if (!error?.response) {
      ElMessage.error('网络连接异常，请检查网络后重试')
    } else {
      ElMessage.error(message)
    }

    return Promise.reject(error)
  },
)

/** GET 请求 */
export function get<T>(url: string, params?: Record<string, unknown>, config?: AxiosRequestConfig): Promise<T> {
  return service.get(url, { params, ...config }) as unknown as Promise<T>
}

/** POST 请求 */
export function post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return service.post(url, data, config) as unknown as Promise<T>
}

/** 表单上传请求（multipart/form-data）
 * 实例默认头为 application/json，发 FormData 时必须置空，
 * 由浏览器自动生成含 boundary 的 multipart Content-Type（YOLO 接入方案 §4.3） */
export function postForm<T>(url: string, data: FormData, config?: AxiosRequestConfig): Promise<T> {
  return service.post(url, data, {
    ...config,
    headers: { 'Content-Type': null },
  }) as unknown as Promise<T>
}

/** PUT 请求 */
export function put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return service.put(url, data, config) as unknown as Promise<T>
}

/** DELETE 请求 */
export function del<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return service.delete(url, config) as unknown as Promise<T>
}

export default service
