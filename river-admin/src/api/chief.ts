import { get } from './request'
import type { Chief, PageQuery, PageResult } from '@/types'
import type { TrendPoint } from './dashboard'

export interface ChiefPortrait extends Chief {
  trend: { qualityRate: TrendPoint[]; resolveRate: TrendPoint[]; patrolRate: TrendPoint[] }
  patrolRecords: unknown[]
  events: unknown[]
}

/** 河长列表 */
export function fetchChiefs(query: PageQuery): Promise<PageResult<Chief>> {
  return get<PageResult<Chief>>('/chiefs', query as Record<string, unknown>)
}

/** 数字河长画像 */
export function fetchChiefPortrait(id: string): Promise<ChiefPortrait> {
  return get<ChiefPortrait>(`/chiefs/portrait/${id}`)
}
