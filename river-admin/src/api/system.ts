import { del, get, post, put } from './request'
import type { Device, DictItem, OperationLog, PageQuery, PageResult, SysOrg, SysRole, SysUser } from '@/types'

/* ------------------------------ 用户管理 ------------------------------ */
export function fetchUsers(query: PageQuery): Promise<PageResult<SysUser>> {
  return get<PageResult<SysUser>>('/system/users', query as Record<string, unknown>)
}

export function createUser(data: Partial<SysUser>): Promise<SysUser> {
  return post<SysUser>('/system/users', data)
}

export function updateUser(id: string, data: Partial<SysUser>): Promise<SysUser> {
  return put<SysUser>(`/system/users/${id}`, data)
}

export function deleteUser(id: string): Promise<{ success: boolean }> {
  return del<{ success: boolean }>(`/system/users/${id}`)
}

/* ------------------------------ 组织架构 ------------------------------ */
export function fetchOrgs(): Promise<SysOrg[]> {
  return get<SysOrg[]>('/system/orgs')
}

/* ------------------------------ 角色管理 ------------------------------ */
export function fetchRoles(): Promise<SysRole[]> {
  return get<SysRole[]>('/system/roles')
}

/* ------------------------------ 数据字典 ------------------------------ */
export function fetchDicts(): Promise<DictItem[]> {
  return get<DictItem[]>('/system/dicts')
}

/* ------------------------------ 操作日志 ------------------------------ */
export function fetchLogs(query: PageQuery): Promise<PageResult<OperationLog>> {
  return get<PageResult<OperationLog>>('/system/logs', query as Record<string, unknown>)
}

/* ------------------------------ 设备管理 ------------------------------ */
export function fetchDevices(): Promise<Device[]> {
  return get<Device[]>('/system/devices')
}
