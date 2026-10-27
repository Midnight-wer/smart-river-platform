import { del, get, post, put } from './request'
import type { PageQuery, PageResult, PatrolTask } from '@/types'

/** 巡查任务列表 */
export function fetchPatrols(query: PageQuery): Promise<PageResult<PatrolTask>> {
  return get<PageResult<PatrolTask>>('/patrols', query as Record<string, unknown>)
}

/** 新建巡查任务 */
export function createPatrol(data: Partial<PatrolTask>): Promise<PatrolTask> {
  return post<PatrolTask>('/patrols', data)
}

/** 更新巡查任务（状态、结果等） */
export function updatePatrol(id: string, data: Partial<PatrolTask>): Promise<PatrolTask> {
  return put<PatrolTask>(`/patrols/${id}`, data)
}

/** 删除巡查任务 */
export function deletePatrol(id: string): Promise<{ success: boolean }> {
  return del<{ success: boolean }>(`/patrols/${id}`)
}
