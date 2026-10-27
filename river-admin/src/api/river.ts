import { del, get, post, put } from './request'
import type { PageQuery, PageResult, River, WaterTrendPoint } from '@/types'

export interface RiverDetail extends River {
  history: WaterTrendPoint[]
  events: unknown[]
  patrols: unknown[]
}

/** 河道列表（分页） */
export function fetchRivers(query: PageQuery): Promise<PageResult<River>> {
  return get<PageResult<River>>('/rivers', query as Record<string, unknown>)
}

/** 河道详情 */
export function fetchRiverDetail(id: string): Promise<RiverDetail> {
  return get<RiverDetail>(`/rivers/${id}`)
}

/** 新增河道 */
export function createRiver(data: Partial<River>): Promise<River> {
  return post<River>('/rivers', data)
}

/** 编辑河道 */
export function updateRiver(id: string, data: Partial<River>): Promise<River> {
  return put<River>(`/rivers/${id}`, data)
}

/** 删除河道 */
export function deleteRiver(id: string): Promise<{ success: boolean }> {
  return del<{ success: boolean }>(`/rivers/${id}`)
}
