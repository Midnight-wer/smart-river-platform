import { get } from './request'
import type { PageQuery, PageResult, WaterRecord, WaterStation, WaterTrendPoint } from '@/types'

export interface WaterIndicator {
  name: string
  unit: string
  standard: string
  min: number
  max: number
}

/** 监测站点列表 */
export function fetchStations(): Promise<WaterStation[]> {
  return get<WaterStation[]>('/water/stations')
}

/** 实时水质数据 */
export function fetchWaterRecords(query: PageQuery): Promise<PageResult<WaterRecord>> {
  return get<PageResult<WaterRecord>>('/water/records', query as Record<string, unknown>)
}

/** 历史趋势 */
export function fetchWaterTrend(): Promise<WaterTrendPoint[]> {
  return get<WaterTrendPoint[]>('/water/trend')
}

/** 指标标准配置 */
export function fetchIndicators(): Promise<Record<string, WaterIndicator>> {
  return get<Record<string, WaterIndicator>>('/water/indicators')
}
