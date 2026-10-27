import { get } from './request'
import type { ChartItem, WarnInfo } from '@/types'

export interface DashboardSummary {
  riverTotal: number
  riverNormal: number
  riverWarn: number
  qualityRate: number
  patrolTotal: number
  patrolDone: number
  patrolDoing: number
  patrolOverdue: number
  eventTotal: number
  eventPending: number
  eventDone: number
  chiefTotal: number
  stationOnline: number
  stationTotal: number
  reportPending: number
}

export interface TrendPoint {
  date: string
  value: number
}

export interface DashboardCharts {
  riverLevel: ChartItem[]
  eventType: ChartItem[]
  chiefDuty: ChartItem[]
}

/** 工作台概览指标 */
export function fetchSummary(): Promise<DashboardSummary> {
  return get<DashboardSummary>('/dashboard/summary')
}

/** 近期预警 */
export function fetchWarns(): Promise<WarnInfo[]> {
  return get<WarnInfo[]>('/dashboard/warns')
}

/** 趋势数据 */
export function fetchTrend(): Promise<{ qualityRate: TrendPoint[]; resolveRate: TrendPoint[]; patrolRate: TrendPoint[] }> {
  return get('/dashboard/trend')
}

/** 图表分布数据 */
export function fetchCharts(): Promise<DashboardCharts> {
  return get<DashboardCharts>('/dashboard/charts')
}
