import { get, post } from './request'
import type { LoginParams, LoginResult, UserInfo } from '@/types'

/** 登录 */
export function login(params: LoginParams): Promise<LoginResult> {
  return post<LoginResult>('/auth/login', params)
}

/** 获取当前登录用户信息 */
export function fetchProfile(username?: string): Promise<UserInfo> {
  return get<UserInfo>('/auth/profile', username ? { username } : undefined)
}

/** 退出登录 */
export function logout(): Promise<{ success: boolean }> {
  return post<{ success: boolean }>('/auth/logout')
}
